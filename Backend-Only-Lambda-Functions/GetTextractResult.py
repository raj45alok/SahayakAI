import json
import boto3
import time

# Initialize AWS clients
textract = boto3.client('textract', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

TABLE_NAME = 'ContentTable'
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    Check Textract job status and retrieve extracted text
    
    Input:
    {
        "contentId": "CNT-ABC123",
        "textractJobId": "abc-xyz-123"
    }
    """
    
    try:
        content_id = event['contentId']
        job_id = event['textractJobId']
        
        print(f"Checking Textract job {job_id} for content {content_id}")
        
        # Check job status
        response = textract.get_document_text_detection(JobId=job_id)
        
        status = response['JobStatus']
        print(f"Textract status: {status}")
        
        if status == 'IN_PROGRESS':
            # Return status to trigger retry in Step Functions
            return {
                'contentId': content_id,
                'textractJobId': job_id,
                'status': 'IN_PROGRESS',
                'waitTime': 5,  # Wait 5 seconds before retry
                **{k: v for k, v in event.items() if k not in ['contentId', 'textractJobId']}
            }
        
        elif status == 'SUCCEEDED':
            # Extract all text blocks
            extracted_text = []
            
            # Get all pages (handle pagination)
            next_token = None
            while True:
                if next_token:
                    response = textract.get_document_text_detection(
                        JobId=job_id,
                        NextToken=next_token
                    )
                
                # Extract LINE blocks (preserve document structure)
                for block in response.get('Blocks', []):
                    if block['BlockType'] == 'LINE':
                        extracted_text.append(block['Text'])
                
                next_token = response.get('NextToken')
                if not next_token:
                    break
            
            full_text = '\n'.join(extracted_text)
            
            print(f"Extracted {len(extracted_text)} lines, {len(full_text)} characters")
            
            # Update progress
            table.update_item(
                Key={'contentId': content_id},
                UpdateExpression='SET progress = :p, extractedText = :text, currentStep = :step',
                ExpressionAttributeValues={
                    ':p': 30,
                    ':text': full_text[:5000],  # Store first 5000 chars in DynamoDB
                    ':step': 'Text extraction completed'
                }
            )
            
            # Return extracted text for next step
            return {
                'contentId': content_id,
                'extractedText': full_text,
                'status': 'SUCCEEDED',
                **{k: v for k, v in event.items() if k not in ['contentId', 'textractJobId', 'status']}
            }
        
        else:  # FAILED or PARTIAL_SUCCESS
            error_msg = f"Textract job failed with status: {status}"
            print(error_msg)
            
            # Update DynamoDB
            table.update_item(
                Key={'contentId': content_id},
                UpdateExpression='SET #status = :status, errorMessage = :error',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'FAILED',
                    ':error': error_msg
                }
            )
            
            raise Exception(error_msg)
        
    except Exception as e:
        print(f"Error in GetTextractResult: {str(e)}")
        
        # Update status to FAILED
        try:
            table.update_item(
                Key={'contentId': event.get('contentId')},
                UpdateExpression='SET #status = :status, errorMessage = :error',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'FAILED',
                    ':error': str(e)
                }
            )
        except:
            pass
        
        raise
