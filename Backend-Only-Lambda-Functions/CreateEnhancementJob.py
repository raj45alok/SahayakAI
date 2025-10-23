import json
import boto3
import os
from datetime import datetime
import uuid

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sfn = boto3.client('stepfunctions', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

# Environment variables
TABLE_NAME = 'ContentTable'
STATE_MACHINE_ARN = 'arn:aws:states:us-east-1:029179924107:stateMachine:SahayakContentEnhancerStateMachine'
INPUT_BUCKET = 'sahayak-enhancer-input-01'

table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    Entry point for content enhancement pipeline
    
    Expected event structure:
    {
        "body": {
            "s3Key": "uploads/file.pdf" (OR)
            "fileContent": "base64_encoded_content",
            "teacherId": "TCH-001",
            "classSubject": "Grade 5 Mathematics",
            "subject": "Mathematics",
            "enhancementType": "Simplify Language",
            "targetAudience": "Elementary Students",
            "instruction": "Add real-world examples",
            "language": "en"
        }
    }
    """
    
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)
        
        # Generate unique content ID
        content_id = f"CNT-{uuid.uuid4().hex[:12].upper()}"
        timestamp = datetime.utcnow().isoformat()
        
        # Extract parameters
        teacher_id = body.get('teacherId', 'UNKNOWN')
        class_subject = body.get('classSubject', '')
        subject = body.get('subject', '')
        enhancement_type = body.get('enhancementType', 'Simplify Language')
        target_audience = body.get('targetAudience', 'Elementary Students')
        instruction = body.get('instruction', '')
        language = body.get('language', 'en')
        
        # Handle S3 key or file content
        s3_key = body.get('s3Key')
        file_content = body.get('fileContent')
        
        if not s3_key and not file_content:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Either s3Key or fileContent must be provided'
                })
            }
        
        # If base64 content provided, upload to S3
        if file_content and not s3_key:
            import base64
            
            # Decode base64
            file_bytes = base64.b64decode(file_content)
            
            # Generate S3 key
            s3_key = f"uploads/{teacher_id}/{content_id}.pdf"
            
            # Upload to S3
            s3.put_object(
                Bucket=INPUT_BUCKET,
                Key=s3_key,
                Body=file_bytes,
                ContentType='application/pdf'
            )
            
            print(f"Uploaded base64 content to s3://{INPUT_BUCKET}/{s3_key}")
        
        # Create DynamoDB record
        item = {
            'contentId': content_id,
            'teacherId': teacher_id,
            'status': 'PENDING',
            'classSubject': class_subject,
            'subject': subject,
            'enhancementType': enhancement_type,
            'targetAudience': target_audience,
            'instruction': instruction,
            'language': language,
            's3Key': s3_key,
            'createdAt': timestamp,
            'updatedAt': timestamp,
            'progress': 0
        }
        
        table.put_item(Item=item)
        print(f"Created DynamoDB record for {content_id}")
        
        # Prepare Step Functions input
        sfn_input = {
            'contentId': content_id,
            'teacherId': teacher_id,
            'classSubject': class_subject,
            'subject': subject,
            'enhancementType': enhancement_type,
            'targetAudience': target_audience,
            'instruction': instruction,
            'language': language,
            's3Key': s3_key,
            'inputBucket': INPUT_BUCKET
        }
        
        # Start Step Functions execution
        execution_name = f"{content_id}-{int(datetime.utcnow().timestamp())}"
        
        sfn_response = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(sfn_input)
        )
        
        print(f"Started Step Functions execution: {execution_name}")
        
        # Update DynamoDB with execution ARN
        table.update_item(
            Key={'contentId': content_id},
            UpdateExpression='SET executionArn = :arn, #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':arn': sfn_response['executionArn'],
                ':status': 'RUNNING'
            }
        )
        
        # Return success response
        return {
            'statusCode': 202,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'data': {
                    'contentId': content_id,
                    'status': 'RUNNING',
                    'message': 'Enhancement job started successfully',
                    's3Key': s3_key,
                    'estimatedCompletionTime': 120
                }
            })
        }
        
    except Exception as e:
        print(f"Error in CreateEnhancementJob: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
            })
        }
