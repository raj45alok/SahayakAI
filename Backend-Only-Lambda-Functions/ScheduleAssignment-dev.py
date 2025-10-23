import json
import boto3
from datetime import datetime, timedelta
import decimal
import hashlib

def lambda_handler(event, context):
    print("Starting assignment scheduling or reminder processing")
    
    # Check if this is a reminder trigger from EventBridge
    if 'source' in event and event['source'] == 'aws.events':
        return handle_reminder_trigger(event, context)
    else:
        return handle_scheduling_request(event, context)

def handle_scheduling_request(event, context):
    """Handle initial assignment scheduling request"""
    print("Processing assignment scheduling request")
    
    try:
        # Parse the request
        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event
        
        assignment_id = body['assignment_id']
        teacher_id = body['teacher_id']
        due_date = body['due_date']
        subject = body['subject']
        class_info = body['class_info']
        student_emails = body['student_emails']
        
        print(f"Scheduling assignment: {assignment_id}, Due: {due_date}")
        
        # Get assignment details from DynamoDB
        assignment_details = get_assignment_details(assignment_id)
        if not assignment_details:
            raise ValueError(f"Assignment {assignment_id} not found")
        
        # Verify teacher ownership
        if assignment_details.get('teacher_id') != teacher_id:
            raise ValueError(f"Teacher {teacher_id} not authorized to schedule this assignment")
        
        # Create simplified assignment details for EventBridge (to avoid payload size limits)
        simplified_details = create_simplified_assignment_details(assignment_details)
        
        # Schedule reminder using EventBridge
        reminder_rule_arn = schedule_reminders(assignment_id, due_date, simplified_details, context)
        
        # Send initial notification emails
        send_assignment_notifications(assignment_id, assignment_details, due_date, student_emails, subject, class_info)
        
        # Update assignment with scheduling info in DynamoDB
        update_assignment_schedule(assignment_id, due_date, student_emails, reminder_rule_arn)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'assignment_id': assignment_id,
                'status': 'scheduled',
                'due_date': due_date,
                'reminder_rule_arn': reminder_rule_arn,
                'students_notified': len(student_emails),
                'message': 'Assignment scheduled and notifications sent successfully',
                'scheduled_at': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return error_response(str(e))

def handle_reminder_trigger(event, context):
    """Handle EventBridge reminder triggers"""
    print("Processing assignment reminder trigger")
    
    try:
        # Parse reminder data from EventBridge
        if 'detail' in event:
            reminder_data = event['detail']
        else:
            reminder_data = event
        
        assignment_id = reminder_data['assignment_id']
        reminder_type = reminder_data['reminder_type']
        due_date = reminder_data['due_date']
        assignment_details = reminder_data.get('assignment_details', {})
        
        print(f"Sending {reminder_type} for assignment {assignment_id}")
        
        # Get student emails from DynamoDB
        student_emails = get_student_emails(assignment_id)
        if not student_emails:
            print("⚠️ No student emails found for reminder")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'assignment_id': assignment_id,
                    'reminder_type': reminder_type,
                    'status': 'skipped',
                    'reason': 'no_emails_found',
                    'sent_at': datetime.now().isoformat()
                })
            }
        
        # If assignment_details is minimal, get full details from DynamoDB
        if not assignment_details.get('questions'):
            full_details = get_assignment_details(assignment_id)
            if full_details:
                assignment_details = full_details
        
        # Send reminder emails
        send_reminder_emails(assignment_id, reminder_type, due_date, assignment_details, student_emails)
        
        print(f"✅ Sent {reminder_type} to {len(student_emails)} students")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'assignment_id': assignment_id,
                'reminder_type': reminder_type,
                'students_notified': len(student_emails),
                'status': 'success',
                'sent_at': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error sending reminder: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Reminder sending failed',
                'message': str(e)
            })
        }

def create_simplified_assignment_details(assignment_details):
    """Create a simplified version of assignment details for EventBridge payload"""
    simplified = {
        'assignment_id': assignment_details.get('assignment_id'),
        'subject': assignment_details.get('subject', 'Assignment'),
        'class_info': assignment_details.get('class_info', ''),
        'questions_count': len(assignment_details.get('questions', []))
    }
    
    # Add only essential question info (not the full AI answers)
    questions = assignment_details.get('questions', [])
    simplified_questions = []
    
    for q in questions:
        simplified_questions.append({
            'question_number': q.get('question_number'),
            'question_text': truncate_text(q.get('question_text', ''), 100),
            'max_score': q.get('max_score'),
            'question_type': q.get('question_type')
        })
    
    simplified['questions'] = simplified_questions
    
    # Check the size of the payload
    payload_size = len(json.dumps(simplified))
    print(f"Simplified assignment details payload size: {payload_size} characters")
    
    if payload_size > 7000:  # Leave some buffer under 8192 limit
        # Further simplify by removing questions array if still too large
        simplified.pop('questions', None)
        simplified['questions_count'] = len(questions)
        print(f"Further simplified payload size: {len(json.dumps(simplified))} characters")
    
    return simplified

def truncate_text(text, max_length):
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def schedule_reminders(assignment_id, due_date, assignment_details, context):
    """Schedule reminder events using EventBridge"""
    events_client = boto3.client('events')
    
    due_datetime = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
    
    # Create shorter rule names to stay under 64 character limit
    short_id = assignment_id[:8]  # Use first 8 chars of UUID
    unique_hash = hashlib.md5(assignment_id.encode()).hexdigest()[:6]  # Use only 6 chars
    
    rule_name_24hr = f"rem-24h-{short_id}-{unique_hash}"
    rule_name_1hr = f"rem-1h-{short_id}-{unique_hash}"
    
    print(f"Rule names - 24hr: {rule_name_24hr} ({len(rule_name_24hr)} chars), 1hr: {rule_name_1hr} ({len(rule_name_1hr)} chars)")
    
    # Calculate reminder times
    reminder_24hr = due_datetime - timedelta(hours=24)
    reminder_1hr = due_datetime - timedelta(hours=1)
    
    # Create cron expressions
    cron_24hr = create_cron_expression(reminder_24hr)
    cron_1hr = create_cron_expression(reminder_1hr)
    
    # Create minimal reminder payload
    reminder_payload = {
        'assignment_id': assignment_id,
        'due_date': due_date,
        'assignment_details': assignment_details  # Use the simplified version
    }
    
    # Check payload size
    payload_size = len(json.dumps(reminder_payload))
    print(f"Reminder payload size: {payload_size} characters")
    
    if payload_size > 8000:
        # If still too large, remove assignment_details entirely
        reminder_payload.pop('assignment_details', None)
        print(f"Minimal payload size: {len(json.dumps(reminder_payload))} characters")
    
    rule_arns = []
    
    try:
        # Schedule 24-hour reminder only if it's in the future
        if reminder_24hr > datetime.now(reminder_24hr.tzinfo):
            events_client.put_rule(
                Name=rule_name_24hr,
                ScheduleExpression=f"cron({cron_24hr})",
                State='ENABLED',
                Description=f'24h rem for {assignment_id[:16]}...'
            )
            
            events_client.put_targets(
                Rule=rule_name_24hr,
                Targets=[{
                    'Id': '1',
                    'Arn': get_reminder_lambda_arn(context),
                    'Input': json.dumps({
                        'detail': {
                            **reminder_payload,
                            'reminder_type': '24_hour_reminder'
                        }
                    })
                }]
            )
            rule_arns.append(f"arn:aws:events:{boto3.session.Session().region_name}:{context.invoked_function_arn.split(':')[4]}:rule/{rule_name_24hr}")
            print(f"✅ Scheduled 24-hour reminder: {rule_name_24hr}")
        else:
            print("⚠️ 24-hour reminder is in the past, skipping")
        
        # Schedule 1-hour reminder only if it's in the future
        if reminder_1hr > datetime.now(reminder_1hr.tzinfo):
            events_client.put_rule(
                Name=rule_name_1hr,
                ScheduleExpression=f"cron({cron_1hr})",
                State='ENABLED',
                Description=f'1h rem for {assignment_id[:16]}...'
            )
            
            events_client.put_targets(
                Rule=rule_name_1hr,
                Targets=[{
                    'Id': '1',
                    'Arn': get_reminder_lambda_arn(context),
                    'Input': json.dumps({
                        'detail': {
                            **reminder_payload,
                            'reminder_type': '1_hour_reminder'
                        }
                    })
                }]
            )
            rule_arns.append(f"arn:aws:events:{boto3.session.Session().region_name}:{context.invoked_function_arn.split(':')[4]}:rule/{rule_name_1hr}")
            print(f"✅ Scheduled 1-hour reminder: {rule_name_1hr}")
        else:
            print("⚠️ 1-hour reminder is in the past, skipping")
        
        if not rule_arns:
            raise ValueError("No reminders scheduled - both reminder times are in the past")
            
        print(f"✅ Scheduled {len(rule_arns)} reminders for assignment {assignment_id}")
        return rule_arns[0]  # Return first ARN for storage
        
    except Exception as e:
        print(f"Error scheduling reminders: {str(e)}")
        # Clean up any created rules if there's an error
        for rule_name in [rule_name_24hr, rule_name_1hr]:
            try:
                events_client.delete_rule(Name=rule_name)
            except:
                pass
        raise e

# Keep all other functions the same as before (get_student_emails, convert_decimals_to_floats, send_reminder_emails, etc.)
def get_student_emails(assignment_id):
    """Get student emails from DynamoDB"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Assignments-dev')
    
    try:
        response = table.get_item(Key={'assignment_id': assignment_id})
        assignment = response.get('Item', {})
        # Convert Decimals before returning
        assignment = convert_decimals_to_floats(assignment)
        return assignment.get('student_emails', [])
    except Exception as e:
        print(f"Error getting student emails: {str(e)}")
        return []

def convert_decimals_to_floats(obj):
    """Recursively convert Decimal objects to float in a DynamoDB item"""
    if isinstance(obj, list):
        return [convert_decimals_to_floats(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return float(obj) if obj % 1 != 0 else int(obj)
    else:
        return obj

def send_reminder_emails(assignment_id, reminder_type, due_date, assignment_details, student_emails):
    """Send reminder emails using EmailService"""
    lambda_client = boto3.client('lambda')
    
    due_datetime = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
    due_date_str = due_datetime.strftime('%B %d, %Y at %I:%M %p')
    
    # Different email content based on reminder type
    if reminder_type == '24_hour_reminder' or reminder_type == '24hr':
        subject = f"⏰ Reminder: Assignment Due Tomorrow - {assignment_details.get('subject', 'Assignment')}"
        urgency_text = "tomorrow"
        email_reminder_type = '24_hour_reminder'
    elif reminder_type == '1_hour_reminder' or reminder_type == '1hr':
        subject = f"🚨 Reminder: Assignment Due in 1 Hour - {assignment_details.get('subject', 'Assignment')}"
        urgency_text = "in 1 hour"
        email_reminder_type = '1_hour_reminder'
    else:
        subject = f"Reminder: {assignment_details.get('subject', 'Assignment')}"
        urgency_text = "soon"
        email_reminder_type = reminder_type
    
    text_content = create_reminder_text(reminder_type, due_date_str, assignment_details, urgency_text)
    html_content = create_reminder_html(reminder_type, due_date_str, assignment_details, urgency_text)
    
    try:
        # Call EmailService Lambda
        response = lambda_client.invoke(
            FunctionName='EmailService-dev',
            InvocationType='Event',
            Payload=json.dumps({
                'email_type': f'reminder_{email_reminder_type}',
                'to_emails': student_emails,
                'subject': subject,
                'text_content': text_content,
                'html_content': html_content
            })
        )
        print(f"✅ Triggered reminder emails for {len(student_emails)} students")
        
    except Exception as e:
        print(f"⚠️ Failed to trigger reminder emails: {str(e)}")

def create_reminder_text(reminder_type, due_date_str, assignment_details, urgency):
    """Create plain text reminder email"""
    email_content = f"""
ASSIGNMENT REMINDER

Your assignment is due {urgency}.

Assignment: {assignment_details.get('subject', 'Assignment')}
Due Date: {due_date_str}
Total Questions: {assignment_details.get('questions_count', len(assignment_details.get('questions', [])))}

Please ensure you submit your work on time through the student portal.

This is an automated reminder. Please do not reply to this email.
"""
    return email_content

def create_reminder_html(reminder_type, due_date_str, assignment_details, urgency):
    """Create HTML reminder email"""
    if reminder_type == '24_hour_reminder' or reminder_type == '24hr':
        alert_color = "#f39c12"  # Orange
        icon = "⏰"
        title = "Assignment Due Tomorrow"
    elif reminder_type == '1_hour_reminder' or reminder_type == '1hr':
        alert_color = "#e74c3c"  # Red
        icon = "🚨" 
        title = "Assignment Due in 1 Hour"
    else:
        alert_color = "#3498db"  # Blue
        icon = "📅"
        title = "Assignment Reminder"
    
    questions_count = assignment_details.get('questions_count', len(assignment_details.get('questions', [])))
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {alert_color}; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .due-date {{ color: #e74c3c; font-weight: bold; }}
        .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
        .urgency-box {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid {alert_color}; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{icon} {title}</h1>
        </div>
        <div class="content">
            <h2>{assignment_details.get('subject', 'Assignment')}</h2>
            
            <div class="urgency-box">
                <p><strong>Your assignment is due {urgency}!</strong></p>
            </div>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p><strong>Due Date:</strong> <span class="due-date">{due_date_str}</span></p>
                <p><strong>Total Questions:</strong> {questions_count}</p>
                <p><strong>Status:</strong> Waiting for your submission</p>
            </div>
            
            <p>Please log in to the student portal to submit your work before the deadline.</p>
            
            <div style="background: #e8f4fd; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p><strong>💡 Important:</strong> The assignment system will automatically evaluate your submission after the due date.</p>
            </div>
        </div>
        <div class="footer">
            <p>This is an automated reminder. Please do not reply to this email.</p>
            <p>Student Assignment System</p>
        </div>
    </div>
</body>
</html>
"""
    return html_content

def get_assignment_details(assignment_id):
    """Get assignment details from DynamoDB"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Assignments-dev')
    
    try:
        response = table.get_item(Key={'assignment_id': assignment_id})
        assignment = response.get('Item', {})
        # Convert Decimals before returning
        assignment = convert_decimals_to_floats(assignment)
        return assignment
    except Exception as e:
        print(f"Error getting assignment details: {str(e)}")
        return None

def create_cron_expression(dt):
    """Create cron expression from datetime"""
    # Cron format: minute hour day month year day-of-week
    return f"{dt.minute} {dt.hour} {dt.day} {dt.month} ? {dt.year}"

def get_reminder_lambda_arn(context):
    """Get the ARN of this Lambda function for EventBridge target"""
    return context.invoked_function_arn

def send_assignment_notifications(assignment_id, assignment_details, due_date, student_emails, subject, class_info):
    """Send initial assignment notification emails"""
    lambda_client = boto3.client('lambda')
    
    due_datetime = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
    due_date_str = due_datetime.strftime('%B %d, %Y at %I:%M %p')
    
    text_content = create_email_text(assignment_details, due_date_str, class_info)
    html_content = create_email_html(assignment_details, due_date_str, class_info)
    
    try:
        response = lambda_client.invoke(
            FunctionName='EmailService-dev',
            InvocationType='Event',
            Payload=json.dumps({
                'email_type': 'assignment_notification',
                'to_emails': student_emails,
                'subject': f"📚 New Assignment: {subject}",
                'text_content': text_content,
                'html_content': html_content
            })
        )
        print(f"✅ Triggered assignment notifications for {len(student_emails)} students")
        
    except Exception as e:
        print(f"⚠️ Failed to trigger assignment notifications: {str(e)}")

def create_email_text(assignment_details, due_date_str, class_info):
    """Create plain text email content"""
    email_content = f"""
NEW ASSIGNMENT

You have been assigned a new assignment for {class_info}.

Assignment: {assignment_details.get('subject', 'Assignment')}
Due Date: {due_date_str}
Total Questions: {len(assignment_details.get('questions', []))}

Please log in to the student portal to complete the assignment before the due date.

This is an automated notification. Please do not reply to this email.
"""
    return email_content

def create_email_html(assignment_details, due_date_str, class_info):
    """Create HTML email content"""
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #3498db; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .due-date {{ color: #e74c3c; font-weight: bold; }}
        .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📚 New Assignment</h1>
        </div>
        <div class="content">
            <h2>{assignment_details.get('subject', 'Assignment')}</h2>
            <p><strong>Class:</strong> {class_info}</p>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p><strong>Due Date:</strong> <span class="due-date">{due_date_str}</span></p>
                <p><strong>Total Questions:</strong> {len(assignment_details.get('questions', []))}</p>
            </div>
            
            <p>Please log in to the student portal to complete this assignment before the due date.</p>
            
            <div style="background: #e8f4fd; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p><strong>💡 Reminder:</strong> You will receive reminder emails 24 hours and 1 hour before the due date.</p>
            </div>
        </div>
        <div class="footer">
            <p>This is an automated notification. Please do not reply to this email.</p>
            <p>Student Assignment System</p>
        </div>
    </div>
</body>
</html>
"""
    return html_content

def update_assignment_schedule(assignment_id, due_date, student_emails, reminder_rule_arn):
    """Update assignment with scheduling information in DynamoDB"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Assignments-dev')
    
    try:
        response = table.update_item(
            Key={'assignment_id': assignment_id},
            UpdateExpression='SET due_date = :due_date, student_emails = :emails, reminder_rule_arn = :arn, scheduled_at = :now',
            ExpressionAttributeValues={
                ':due_date': due_date,
                ':emails': student_emails,
                ':arn': reminder_rule_arn,
                ':now': datetime.now().isoformat()
            },
            ReturnValues='UPDATED_NEW'
        )
        print(f"✅ Updated assignment {assignment_id} with scheduling info")
        
    except Exception as e:
        print(f"Error updating assignment: {str(e)}")
        raise e

def error_response(error_message):
    """Return standardized error response"""
    return {
        'statusCode': 500,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': 'Processing failed',
            'message': error_message
        })
    }
