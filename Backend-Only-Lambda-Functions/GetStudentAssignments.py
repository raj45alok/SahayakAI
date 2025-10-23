import json
import boto3
from decimal import Decimal
from botocore.config import Config
from boto3.dynamodb.conditions import Key, Attr

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
    """Get all assignments for a specific student based on their class"""
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Handle CORS preflight
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS'
                },
                'body': json.dumps({'message': 'OK'})
            }
        
        # Get student_id from path parameters
        student_id = event.get('pathParameters', {}).get('studentId')
        
        if not student_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Missing studentId'})
            }
        
        print(f"📚 Fetching assignments for student: {student_id}")
        
        # Step 1: Get student's class from Users table
        users_table = dynamodb.Table('Users')
        student_response = users_table.get_item(
            Key={
                'userId': student_id,
                'role': 'student'
            }
        )
        
        if 'Item' not in student_response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Student not found'})
            }
        
        student = student_response['Item']
        student_class = student.get('classId')
        
        if not student_class:
            print(f"⚠️ Student {student_id} has no class assigned")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'assignments': [],
                    'message': 'No class assigned to student'
                }, default=decimal_to_native)
            }
        
        print(f"👤 Student class: {student_class}")
        
        # Step 2: Get all assignments for the student's class
        assignments_table = dynamodb.Table('Assignments-dev')
        
        # Scan for assignments with matching class
        # Note: If you have many assignments, consider adding a GSI on class_info
        assignments_response = assignments_table.scan(
            FilterExpression=Attr('class_info').eq(student_class)
        )
        
        assignments = assignments_response.get('Items', [])
        
        print(f"✅ Found {len(assignments)} assignments for class {student_class}")
        
        # Step 3: Get submission status for each assignment
        submissions_table = dynamodb.Table('Submissions')
        
        enriched_assignments = []
        for assignment in assignments:
            assignment_id = assignment.get('assignment_id')
            
            # Check if student has submitted this assignment
            try:
                submission_response = submissions_table.query(
                    KeyConditionExpression=Key('assignment_id').eq(assignment_id),
                    FilterExpression=Attr('student_id').eq(student_id)
                )
                
                submissions = submission_response.get('Items', [])
                
                if submissions:
                    # Student has submitted
                    submission = submissions[0]
                    status = submission.get('status', 'submitted')
                    score = submission.get('score')
                    feedback = submission.get('feedback')
                    
                    enriched_assignment = {
                        'assignmentId': assignment_id,
                        'title': assignment.get('title', 'Untitled Assignment'),
                        'subject': assignment.get('subject', 'General'),
                        'className': assignment.get('class_info', student_class),
                        'dueDate': assignment.get('due_date', ''),
                        'instructions': assignment.get('instructions', ''),
                        'status': status,
                        'score': score,
                        'feedback': feedback,
                        'teacherId': assignment.get('teacher_id', ''),
                        'createdAt': assignment.get('created_at', '')
                    }
                else:
                    # Student hasn't submitted yet
                    enriched_assignment = {
                        'assignmentId': assignment_id,
                        'title': assignment.get('title', 'Untitled Assignment'),
                        'subject': assignment.get('subject', 'General'),
                        'className': assignment.get('class_info', student_class),
                        'dueDate': assignment.get('due_date', ''),
                        'instructions': assignment.get('instructions', ''),
                        'status': 'pending',
                        'teacherId': assignment.get('teacher_id', ''),
                        'createdAt': assignment.get('created_at', '')
                    }
                
                enriched_assignments.append(enriched_assignment)
                
            except Exception as e:
                print(f"⚠️ Error checking submission for {assignment_id}: {str(e)}")
                # Add assignment as pending if we can't check submission status
                enriched_assignments.append({
                    'assignmentId': assignment_id,
                    'title': assignment.get('title', 'Untitled Assignment'),
                    'subject': assignment.get('subject', 'General'),
                    'className': assignment.get('class_info', student_class),
                    'dueDate': assignment.get('due_date', ''),
                    'instructions': assignment.get('instructions', ''),
                    'status': 'pending',
                    'teacherId': assignment.get('teacher_id', ''),
                    'createdAt': assignment.get('created_at', '')
                })
        
        # Sort by due date (most recent first)
        enriched_assignments.sort(key=lambda x: x.get('dueDate', ''), reverse=True)
        
        print(f"✅ Returning {len(enriched_assignments)} enriched assignments")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({
                'success': True,
                'assignments': enriched_assignments,
                'studentClass': student_class
            }, default=decimal_to_native)
        }
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
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
