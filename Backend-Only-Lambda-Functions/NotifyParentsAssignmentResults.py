import json
import boto3
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from boto3.dynamodb.conditions import Key
from decimal import Decimal
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
users_table = dynamodb.Table('Users')
assignments_table = dynamodb.Table('Assignments-dev')
submissions_table = dynamodb.Table('Submissions-dev')

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    raise TypeError

def send_email(to_email, subject, html_body):
    """Send email via Gmail SMTP"""
    try:
        gmail_user = os.environ['GMAIL_USER']
        gmail_password = os.environ['GMAIL_APP_PASSWORD']
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = gmail_user
        msg['To'] = to_email
        
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        # Connect to Gmail SMTP
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, to_email, msg.as_string())
        server.quit()
        
        return True, None
    except Exception as e:
        return False, str(e)

def lambda_handler(event, context):
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        assignment_id = body.get('assignmentId')
        teacher_id = body.get('teacherId')
        class_id = body.get('classId')
        
        if not assignment_id or not teacher_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'assignmentId and teacherId are required'
                })
            }
        
        # 1. Get assignment details
        assignment_response = assignments_table.get_item(
            Key={'assignment_id': assignment_id}
        )
        
        if 'Item' not in assignment_response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Assignment not found'
                })
            }
        
        assignment = assignment_response['Item']
        
        # Verify teacher owns this assignment
        if assignment.get('teacher_id') != teacher_id:
            return {
                'statusCode': 403,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Unauthorized: You do not own this assignment'
                })
            }
        
        # 2. Get teacher info
        teacher_response = users_table.get_item(
            Key={'userId': teacher_id, 'role': 'teacher'}
        )
        teacher = teacher_response.get('Item', {})
        teacher_name = teacher.get('name', 'Teacher')
        
        # 3. Get all submissions for this assignment
        submissions_response = submissions_table.query(
            IndexName='AssignmentStudentIndex',
            KeyConditionExpression=Key('assignment_id').eq(assignment_id)
        )
        
        submissions = submissions_response.get('Items', [])
        
        if not submissions:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': True,
                    'data': {
                        'totalSubmissions': 0,
                        'emailsSent': 0,
                        'message': 'No submissions found for this assignment'
                    }
                })
            }
        
        # Filter completed submissions only
        completed_submissions = [s for s in submissions if s.get('evaluation_status') == 'completed']
        
        # Calculate class average
        class_average = 0
        if completed_submissions:
            scores = [s.get('final_score', 0) for s in completed_submissions if s.get('final_score')]
            class_average = round(sum(scores) / len(scores)) if scores else 0
        
        # 4. Send emails to parents
        emails_sent = 0
        emails_failed = 0
        no_parent_email = 0
        details = []
        
        for submission in completed_submissions:
            student_id = submission.get('student_id')
            
            try:
                # Get student info
                student_response = users_table.get_item(
                    Key={'userId': student_id, 'role': 'student'}
                )
                
                if 'Item' not in student_response:
                    details.append({
                        'studentId': student_id,
                        'status': 'student_not_found'
                    })
                    continue
                
                student = student_response['Item']
                parent_email = student.get('parentEmail')
                
                if not parent_email:
                    no_parent_email += 1
                    details.append({
                        'studentId': student_id,
                        'studentName': student.get('name', 'Student'),
                        'status': 'no_parent_email'
                    })
                    continue
                
                # Prepare email data
                student_name = student.get('name', 'Student')
                student_score = submission.get('final_score', 0)
                max_score = submission.get('max_score', 100)
                percentage = round((student_score / max_score) * 100) if max_score > 0 else 0
                
                performance_text = (
                    "Your child scored above the class average. Excellent work!"
                    if student_score > class_average
                    else "Your child scored below the class average. Additional support may be helpful."
                )
                
                # Email content
                subject = f"Assignment Results - {assignment.get('title', 'Assignment')}"
                
                html_body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2>Dear Parent/Guardian of {student_name},</h2>
                    
                    <p>Your child has completed the assignment "<strong>{assignment.get('title', 'Assignment')}</strong>" 
                    for {assignment.get('subject', 'the subject')}.</p>
                    
                    <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Student Performance:</h3>
                        <p><strong>Score:</strong> {student_score}/{max_score} ({percentage}%)</p>
                        <p><strong>Class Average:</strong> {class_average}%</p>
                        <p style="color: {'green' if student_score > class_average else 'orange'};">
                            {performance_text}
                        </p>
                    </div>
                    
                    <h3>Assignment Details:</h3>
                    <ul>
                        <li><strong>Subject:</strong> {assignment.get('subject', 'N/A')}</li>
                        <li><strong>Class:</strong> {assignment.get('class_info', class_id or 'N/A')}</li>
                        <li><strong>Due Date:</strong> {assignment.get('due_date', 'N/A')}</li>
                        <li><strong>Teacher:</strong> {teacher_name}</li>
                    </ul>
                    
                    <p>If you have questions, please contact the school.</p>
                    
                    <p style="margin-top: 30px;">
                        Best regards,<br>
                        <strong>{teacher_name}</strong><br>
                        Sahayak AI Learning Platform
                    </p>
                </body>
                </html>
                """
                
                # Send email
                success, error = send_email(parent_email, subject, html_body)
                
                if success:
                    emails_sent += 1
                    
                    # Update submission record
                    submissions_table.update_item(
                        Key={
                            'submission_id': submission.get('submission_id'),
                            'assignment_id': assignment_id
                        },
                        UpdateExpression='SET parent_notified = :notified, parent_notification_sent_at = :timestamp, parent_notification_status = :status',
                        ExpressionAttributeValues={
                            ':notified': True,
                            ':timestamp': datetime.utcnow().isoformat(),
                            ':status': 'sent'
                        }
                    )
                    
                    details.append({
                        'studentId': student_id,
                        'studentName': student_name,
                        'parentEmail': parent_email,
                        'status': 'sent',
                        'score': f'{student_score}/{max_score}'
                    })
                else:
                    emails_failed += 1
                    details.append({
                        'studentId': student_id,
                        'studentName': student_name,
                        'parentEmail': parent_email,
                        'status': 'failed',
                        'error': error
                    })
                
            except Exception as email_error:
                print(f"Error processing student {student_id}: {email_error}")
                emails_failed += 1
                details.append({
                    'studentId': student_id,
                    'status': 'failed',
                    'error': str(email_error)
                })
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'data': {
                    'totalSubmissions': len(submissions),
                    'completedSubmissions': len(completed_submissions),
                    'emailsSent': emails_sent,
                    'emailsFailed': emails_failed,
                    'noParentEmail': no_parent_email,
                    'classAverage': class_average,
                    'assignmentTitle': assignment.get('title', 'Assignment'),
                    'details': details
                }
            }, default=decimal_default)
        }
        
    except Exception as e:
        print(f"Lambda error: {str(e)}")
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
                'error': str(e)
            })
        }
