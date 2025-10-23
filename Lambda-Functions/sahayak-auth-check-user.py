import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table('Users')

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def response(status_code, body):
    """Response with PROPER CORS headers"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS, PUT, DELETE',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token',
            'Access-Control-Max-Age': '86400'
        },
        'body': json.dumps(body, default=decimal_default)
    }

def handle_options():
    """Handle preflight CORS requests"""
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS, PUT, DELETE',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token',
            'Access-Control-Max-Age': '86400'
        },
        'body': ''
    }

def lambda_handler(event, context):
    """Check if user exists by Firebase UID"""
    
    # Handle preflight CORS OPTIONS request
    if event.get('httpMethod') == 'OPTIONS':
        return handle_options()
    
    try:
        body = json.loads(event.get('body', '{}'))
        firebase_uid = body.get('firebaseUid')
        
        if not firebase_uid:
            return response(400, {
                'success': False,
                'error': 'firebaseUid is required'
            })
        
        result = users_table.query(
            IndexName='FirebaseUid-index',
            KeyConditionExpression='firebaseUid = :uid',
            ExpressionAttributeValues={
                ':uid': firebase_uid
            }
        )
        
        exists = len(result['Items']) > 0
        user_data = result['Items'][0] if exists else None
        
        return response(200, {
            'success': True,
            'exists': exists,
            'data': user_data
        })
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {
            'success': False,
            'error': f'Internal server error: {str(e)}'
        })
