import json
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal

# Initialize DynamoDB - matching your actual setup
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Your actual table names (based on GetStudentProfile)
USERS_TABLE = dynamodb.Table('Users')  # Note: No -dev suffix
ENROLLMENTS_TABLE = dynamodb.Table('Enrollments')  # You may need to verify this name
CLASSES_TABLE = dynamodb.Table('Classes')  # You may need to verify this name

# CORS Headers - Use these consistently everywhere
CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',  # Or specify: 'http://localhost:3000'
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With'
}

def decimal_default(obj):
    """Helper to convert Decimal to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError

def lambda_handler(event, context):
    """
    Get all students enrolled in a specific class
    
    Query parameters:
    - classId: The class ID to fetch students for
    - className: Alternative - fetch by class name
    """
    
    print('GetStudentsByClass Lambda invoked')
    print('Event:', json.dumps(event, default=str))
    
    # ===== HANDLE OPTIONS PREFLIGHT REQUEST =====
    if event.get('httpMethod') == 'OPTIONS':
        print('Handling OPTIONS preflight request')
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': 'OK'})
        }
    
    try:
        # Extract query parameters
        query_params = event.get('queryStringParameters') or {}
        class_id = query_params.get('classId')
        class_name = query_params.get('className')
        
        print(f'Query params - classId: {class_id}, className: {class_name}')
        
        # Validate input
        if not class_id and not class_name:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'success': False,
                    'error': 'Either classId or className is required',
                    'students': [],
                    'count': 0
                })
            }
        
        # If className provided, lookup the classId first
        if class_name and not class_id:
            print(f'Looking up class by name: {class_name}')
            
            try:
                # Scan to find class by name
                response = CLASSES_TABLE.scan(
                    FilterExpression=Attr('name').eq(class_name) | Attr('className').eq(class_name)
                )
                
                if not response['Items']:
                    print(f'Class not found: {class_name}')
                    return {
                        'statusCode': 200,
                        'headers': CORS_HEADERS,
                        'body': json.dumps({
                            'success': True,
                            'message': f'Class not found: {class_name}',
                            'students': [],
                            'count': 0
                        })
                    }
                
                class_id = response['Items'][0].get('classId') or response['Items'][0].get('id')
                print(f'Found class ID: {class_id}')
            except Exception as e:
                print(f'Error looking up class: {e}')
                # If Classes table doesn't exist, use className as classId
                class_id = class_name
        
        print(f'Fetching students for classId: {class_id}')
        
        # OPTION 1: If you have an Enrollments table
        try:
            # Try to query enrollments
            try:
                enrollments_response = ENROLLMENTS_TABLE.query(
                    IndexName='ClassId-index',
                    KeyConditionExpression=Key('classId').eq(class_id)
                )
                print('✅ Used Enrollments table with GSI')
            except Exception as e:
                print(f'GSI query failed, trying scan: {e}')
                enrollments_response = ENROLLMENTS_TABLE.scan(
                    FilterExpression=Attr('classId').eq(class_id)
                )
                print('✅ Used Enrollments table with scan')
            
            enrollments = enrollments_response.get('Items', [])
            student_ids = [e.get('studentId') or e.get('userId') for e in enrollments if e.get('studentId') or e.get('userId')]
            print(f'Found {len(student_ids)} students in Enrollments table')
            
        except Exception as enrollment_error:
            print(f'⚠ Enrollments table not accessible: {enrollment_error}')
            print('Falling back to Users table scan with classId filter')
            
            # OPTION 2: Fallback - Query Users table directly if classId is stored there
            try:
                # Scan Users table for students with this classId
                users_response = USERS_TABLE.scan(
                    FilterExpression=Attr('role').eq('student') & Attr('classId').eq(class_id)
                )
                
                students_from_users = users_response.get('Items', [])
                print(f'Found {len(students_from_users)} students directly in Users table')
                
                # Extract valid students with emails
                valid_students = []
                for user in students_from_users:
                    user_email = user.get('email')
                    if user_email and '@' in user_email:
                        valid_students.append({
                            'id': user.get('userId'),
                            'name': user.get('name', 'Unknown'),
                            'email': user_email,
                            'classId': user.get('classId')
                        })
                
                print(f'✅ Found {len(valid_students)} students with valid emails')
                
                return {
                    'statusCode': 200,
                    'headers': CORS_HEADERS,
                    'body': json.dumps({
                        'success': True,
                        'students': valid_students,
                        'count': len(valid_students),
                        'source': 'users_table_direct'
                    }, default=decimal_default)
                }
                
            except Exception as users_error:
                print(f'❌ Users table scan also failed: {users_error}')
                raise Exception(f'Could not fetch students from any table: {users_error}')
        
        # If we got here, we have student IDs from Enrollments table
        if not student_ids:
            return {
                'statusCode': 200,
                'headers': CORS_HEADERS,
                'body': json.dumps({
                    'success': True,
                    'students': [],
                    'count': 0,
                    'message': 'No students enrolled in this class'
                })
            }
        
        print(f'Fetching details for student IDs: {student_ids}')
        
        # Fetch student details from Users table
        # CRITICAL: Your Users table has composite key (userId + role)
        students = []
        for student_id in student_ids:
            try:
                # Get user with composite key: userId (partition) + role (sort)
                response = USERS_TABLE.get_item(
                    Key={
                        'userId': student_id,
                        'role': 'student'
                    }
                )
                
                if 'Item' in response:
                    user = response['Item']
                    user_email = user.get('email')
                    
                    # Only include if has valid email
                    if user_email and '@' in user_email:
                        students.append({
                            'id': user.get('userId'),
                            'name': user.get('name', 'Unknown'),
                            'email': user_email,
                            'classId': class_id
                        })
                        print(f'✅ Added student: {user.get("name")} ({user_email})')
                else:
                    print(f'⚠ Student {student_id} not found in Users table')
                    
            except Exception as e:
                print(f'❌ Error fetching user {student_id}: {e}')
                continue
        
        print(f'✅ Successfully fetched {len(students)} students with valid emails')
        
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'success': True,
                'students': students,
                'count': len(students),
                'source': 'enrollments_table'
            }, default=decimal_default)
        }
        
    except Exception as e:
        print(f'❌ Error in GetStudentsByClass: {str(e)}')
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({
                'success': False,
                'error': f'Internal server error: {str(e)}',
                'students': [],
                'count': 0
            })
        }
