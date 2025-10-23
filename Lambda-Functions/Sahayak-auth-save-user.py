import json
import boto3
import uuid
from datetime import datetime
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
    """Save new user (Student or Teacher) to DynamoDB"""
    
    # Handle preflight CORS OPTIONS request
    if event.get('httpMethod') == 'OPTIONS':
        return handle_options()
    
    try:
        body = json.loads(event.get('body', '{}'))
        firebase_user = body.get('firebaseUser', {})
        user_type = body.get('userType')  # 'student' or 'teacher'
        additional_data = body.get('additionalData', {})
        
        # Validation: Firebase UID required
        if not firebase_user.get('uid'):
            return response(400, {
                'success': False,
                'error': 'Firebase user uid is required'
            })
        
        # Validation: User type must be student or teacher
        if user_type not in ['student', 'teacher']:
            return response(400, {
                'success': False,
                'error': 'userType must be "student" or "teacher"'
            })
        
        # Generate unique user ID based on type
        # Students: STU-XXXXXXXX
        # Teachers: TCH-XXXXXXXX
        prefix = 'STU' if user_type == 'student' else 'TCH'
        user_id = f'{prefix}-{str(uuid.uuid4())[:8].upper()}'
        
        # Build common user data for both types
        user_data = {
            'userId': user_id,
            'firebaseUid': firebase_user.get('uid'),
            'email': firebase_user.get('email'),
            'displayName': firebase_user.get('displayName', ''),
            'role': user_type,  # 'student' or 'teacher'
            'phone': additional_data.get('phone', ''),
            'createdAt': datetime.utcnow().isoformat(),
            'updatedAt': datetime.utcnow().isoformat(),
        }
        
        # Add role-specific fields
        if user_type == 'student':
            # For students: add classId
            user_data['classId'] = additional_data.get('classId', '')
        elif user_type == 'teacher':
            # For teachers: add subject specialization
            user_data['subjectSpecialization'] = additional_data.get('subjectSpecialization', [])
        
        # Save to DynamoDB
        users_table.put_item(Item=user_data)
        
        return response(201, {
            'success': True,
            'message': 'User created successfully',
            'data': user_data
        })
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {
            'success': False,
            'error': f'Internal server error: {str(e)}'
        })
