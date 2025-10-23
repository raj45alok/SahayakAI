import json
import boto3
from decimal import Decimal
from botocore.config import Config

boto_config = Config(
    retries=dict(max_attempts=3),
    read_timeout=300,
    connect_timeout=300
)

dynamodb = boto3.resource('dynamodb', config=boto_config)

def decimal_to_native(obj):
    """Convert Decimal objects to native Python types for JSON serialization"""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError

def lambda_handler(event, context):
    """Get assignment by ID from DynamoDB"""
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Handle CORS preflight
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS'
                },
                'body': json.dumps({'message': 'OK'})
            }
        
        # Get assignment_id from path parameters
        assignment_id = event.get('pathParameters', {}).get('assignmentId')
        
        if not assignment_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Missing assignmentId'})
            }
        
        # Query DynamoDB
        table = dynamodb.Table('Assignments-dev')
        response = table.get_item(Key={'assignment_id': assignment_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Assignment not found'})
            }
        
        assignment = response['Item']
        
        # Return assignment data with Decimal conversion
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps(assignment, default=decimal_to_native)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }
