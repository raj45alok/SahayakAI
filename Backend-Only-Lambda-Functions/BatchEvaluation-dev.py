import json
import boto3
import decimal
from datetime import datetime

def lambda_handler(event, context):
    print("Starting batch evaluation process")
    
    # Handle API Gateway proxy integration
    if 'httpMethod' in event:
        try:
            if event['httpMethod'] == 'POST' and event['resource'] == '/evaluate/batch':
                body = json.loads(event['body']) if event.get('body') else {}
                assignment_id = body.get('assignment_id')
                
                if not assignment_id:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            'error': 'Missing required parameter',
                            'message': 'assignment_id is required'
                        })
                    }
                
                # Continue with batch evaluation logic...
                return handle_batch_evaluation(assignment_id, is_api_call=True)
                
            else:
                return {
                    'statusCode': 405,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': 'Method not allowed',
                        'message': 'Only POST /evaluate/batch is supported'
                    })
                }
                
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Invalid JSON in request body',
                    'message': 'Request body must contain valid JSON'
                })
            }
        except Exception as e:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'API processing failed',
                    'message': str(e)
                })
            }
    else:
        # Direct Lambda invocation (EventBridge, manual, etc.)
        try:
            # This can be triggered by:
            # 1. EventBridge rule after assignment due date
            # 2. Manual API call for specific assignment
            # 3. S3 batch processing trigger
            
            if 'body' in event:
                body = json.loads(event['body'])
                assignment_id = body['assignment_id']
            else:
                assignment_id = event['assignment_id']
            
            return handle_batch_evaluation(assignment_id, is_api_call=False)
            
        except Exception as e:
            print(f"Error in batch evaluation: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Batch evaluation failed',
                    'message': str(e)
                })
            }

def handle_batch_evaluation(assignment_id, is_api_call=True):
    """Main batch evaluation logic"""
    print(f"Starting batch evaluation for assignment: {assignment_id}")
    
    # Get all pending submissions for this assignment
    pending_submissions = get_pending_submissions(assignment_id)
    
    if not pending_submissions:
        response_body = {
            'assignment_id': assignment_id,
            'status': 'completed',
            'message': 'No pending submissions found for evaluation',
            'processed_at': datetime.now().isoformat()
        }
        
        if is_api_call:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps(response_body)
            }
        else:
            return {
                'statusCode': 200,
                'body': json.dumps(response_body)
            }
    
    print(f"Found {len(pending_submissions)} pending submissions")
    
    # Process each submission
    results = {
        'successful': 0,
        'failed': 0,
        'failed_submissions': []
    }
    
    for submission in pending_submissions:
        try:
            # Call EvaluateSubmission Lambda for each submission
            evaluate_single_submission(submission['submission_id'], assignment_id)
            results['successful'] += 1
            print(f"✅ Queued evaluation for submission: {submission['submission_id']}")
            
        except Exception as e:
            results['failed'] += 1
            results['failed_submissions'].append({
                'submission_id': submission['submission_id'],
                'error': str(e)
            })
            print(f"❌ Failed to queue evaluation for {submission['submission_id']}: {str(e)}")
    
    response_body = {
        'assignment_id': assignment_id,
        'status': 'batch_completed',
        'total_submissions': len(pending_submissions),
        'successful': results['successful'],
        'failed': results['failed'],
        'failed_submissions': results['failed_submissions'],
        'message': f'Batch evaluation completed. Success: {results["successful"]}, Failed: {results["failed"]}',
        'processed_at': datetime.now().isoformat()
    }
    
    if is_api_call:
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body)
        }
    else:
        return {
            'statusCode': 200,
            'body': json.dumps(response_body)
        }

def get_pending_submissions(assignment_id):
    """Get all submissions pending evaluation for an assignment"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Submissions-dev')
    
    try:
        # Query using GSI to get all submissions for this assignment
        response = table.query(
            IndexName='AssignmentStudentIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('assignment_id').eq(assignment_id),
            FilterExpression=boto3.dynamodb.conditions.Attr('evaluation_status').eq('pending')
        )
        
        submissions = response.get('Items', [])
        
        # Handle pagination if there are more results
        while 'LastEvaluatedKey' in response:
            response = table.query(
                IndexName='AssignmentStudentIndex',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('assignment_id').eq(assignment_id),
                FilterExpression=boto3.dynamodb.conditions.Attr('evaluation_status').eq('pending'),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            submissions.extend(response.get('Items', []))
        
        return [convert_decimals_to_floats(sub) for sub in submissions]
        
    except Exception as e:
        print(f"Error getting pending submissions: {str(e)}")
        return []

def evaluate_single_submission(submission_id, assignment_id):
    """Trigger evaluation for a single submission"""
    lambda_client = boto3.client('lambda')
    
    try:
        # Invoke EvaluateSubmission Lambda asynchronously
        response = lambda_client.invoke(
            FunctionName='EvaluateSubmission-dev',
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                'submission_id': submission_id,
                'assignment_id': assignment_id
            })
        )
        return response
        
    except Exception as e:
        print(f"Error invoking EvaluateSubmission: {str(e)}")
        raise

def convert_decimals_to_floats(obj):
    """Recursively convert Decimal objects to float"""
    if isinstance(obj, list):
        return [convert_decimals_to_floats(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return float(obj) if obj % 1 != 0 else int(obj)
    else:
        return obj
