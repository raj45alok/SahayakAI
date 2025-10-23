import json
import boto3
import os
from datetime import datetime

# Initialize AWS clients
textract = boto3.client('textract', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

TABLE_NAME = 'ContentTable'
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    Start AWS Textract job to extract text from uploaded PDF
    
    Input from Step Functions:
    {
        "contentId": "CNT-ABC123",
        "s3Key": "uploads/file.pdf",
        "inputBucket": "sahayak-enhancer-input-01"
    }
    """
    
    try:
        content_id = event['contentId']
        s3_key = event['s3Key']
        input_bucket = event['inputBucket']
        
        print(f"Starting Textract for {content_id}: s3://{input_bucket}/{s3_key}")
        
        # Update progress
        table.update_item(
            Key={'contentId': content_id},
            UpdateExpression='SET progress = :p, currentStep = :step',
            ExpressionAttributeValues={
                ':p': 10,
                ':step': 'Extracting text from document'
            }
        )
        
        # Start Textract job
        response = textract.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': input_bucket,
                    'Name': s3_key
                }
            }
        )
        
        job_id = response['JobId']
        print(f"Textract JobId: {job_id}")
        
        # Update DynamoDB with Textract Job ID
        table.update_item(
            Key={'contentId': content_id},
            UpdateExpression='SET textractJobId = :jobId',
            ExpressionAttributeValues={
                ':jobId': job_id
            }
        )
        
        # Return for next step
        return {
            'contentId': content_id,
            'textractJobId': job_id,
            's3Key': s3_key,
            'inputBucket': input_bucket,
            'teacherId': event.get('teacherId'),
            'classSubject': event.get('classSubject'),
            'subject': event.get('subject'),
            'enhancementType': event.get('enhancementType'),
            'targetAudience': event.get('targetAudience'),
            'instruction': event.get('instruction'),
            'language': event.get('language')
        }
        
    except Exception as e:
        print(f"Error in ExtractText: {str(e)}")
        
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
