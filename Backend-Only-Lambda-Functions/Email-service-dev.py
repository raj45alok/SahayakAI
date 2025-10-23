import json
import os
import logging
import boto3
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from botocore.exceptions import ClientError
from typing import List, Tuple, Dict, Any

# ------------------------------
# Configuration / Constants
# ------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
USE_SECRETS_MANAGER = os.environ.get("USE_SECRETS_MANAGER", "false").lower() == "true"
SMTP_SECRET_NAME = os.environ.get("SMTP_SECRET_NAME", "")  # Name or ARN for Secrets Manager (JSON with keys sender_email, sender_password, smtp_server, smtp_port, sender_name optional)
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")
SENDER_NAME = os.environ.get("SENDER_NAME", "Assignment System")
SMTP_TIMEOUT = int(os.environ.get("SMTP_TIMEOUT", 30))  # seconds
MAX_BATCH_SIZE = int(os.environ.get("MAX_BATCH_SIZE", 25))  # how many recipients to send per connection
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
RETRY_BASE_SECONDS = float(os.environ.get("RETRY_BASE_SECONDS", 1.0))
DEBUG_SMTP = os.environ.get("DEBUG_SMTP", "false").lower() == "true"

# Configure logging
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)


# ------------------------------
# Utils: Secrets Manager
# ------------------------------
def load_smtp_config_from_secrets() -> Dict[str, Any]:
    """
    Load SMTP configuration (sender_email, sender_password, smtp_server, smtp_port, sender_name) from AWS Secrets Manager.
    Secret should be a JSON string containing the keys mentioned above.
    """
    if not SMTP_SECRET_NAME:
        raise ValueError("SMTP_SECRET_NAME must be set when USE_SECRETS_MANAGER=true")

    logger.debug("Fetching SMTP config from Secrets Manager: %s", SMTP_SECRET_NAME)
    client = boto3.client("secretsmanager")
    try:
        resp = client.get_secret_value(SecretId=SMTP_SECRET_NAME)
        secret_str = resp.get("SecretString", "{}")
        secret = json.loads(secret_str)
        return {
            "smtp_server": secret.get("smtp_server", SMTP_SERVER),
            "smtp_port": int(secret.get("smtp_port", SMTP_PORT)),
            "sender_email": secret["sender_email"],
            "sender_password": secret["sender_password"],
            "sender_name": secret.get("sender_name", SENDER_NAME)
        }
    except ClientError as e:
        logger.exception("Failed to read SMTP secret from Secrets Manager")
        raise


def get_smtp_config() -> Dict[str, Any]:
    """
    Consolidate SMTP configuration from Secrets Manager or environment variables.
    Validates required fields.
    """
    if USE_SECRETS_MANAGER:
        config = load_smtp_config_from_secrets()
    else:
        config = {
            "smtp_server": SMTP_SERVER,
            "smtp_port": SMTP_PORT,
            "sender_email": SENDER_EMAIL,
            "sender_password": SENDER_PASSWORD,
            "sender_name": SENDER_NAME
        }

    # Basic validation
    if not config.get("sender_email") or not config.get("sender_password"):
        raise ValueError("SMTP credentials missing. Provide SENDER_EMAIL & SENDER_PASSWORD or enable Secrets Manager with credentials.")

    # Log safe summary (no secrets)
    safe_sender = config["sender_email"]
    if "@" in safe_sender:
        safe_sender = f"{safe_sender[:3]}***@{safe_sender.split('@',1)[1]}"
    logger.info("SMTP config loaded. Server=%s Port=%s Sender=%s", config["smtp_server"], config["smtp_port"], safe_sender)

    return config


# ------------------------------
# Helper: safe sleep/backoff
# ------------------------------
def backoff_sleep(attempt: int) -> None:
    delay = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
    logger.debug("Sleeping for %.2f seconds before retry (attempt %d)", delay, attempt)
    time.sleep(delay)


# ------------------------------
# Email message builders (templates)
# ------------------------------
def generate_evaluation_email(data: dict) -> Tuple[str, str, str]:
    student_name = data.get('student_name', 'Student')
    assignment_title = data.get('assignment_title', 'Assignment')
    final_score = data.get('final_score', 0)
    max_score = data.get('max_score', 100)
    evaluation_results = data.get('evaluation_results', [])
    report_url = data.get('report_url', '')
    
    percentage = (final_score / max_score * 100) if max_score > 0 else 0
    grade = calculate_grade(percentage)
    subject = f"Evaluation Results - {assignment_title}"

    # Plain text content
    text_content = f"""
Dear {student_name},

Your assignment "{assignment_title}" has been evaluated.

Overall Score: {final_score}/{max_score} ({percentage:.1f}%)
Grade: {grade}

Question-wise Results:
"""
    
    for q in evaluation_results:
        text_content += f"""
Q{q.get('question_number', 'N/A')}: {q.get('score', 0)}/{q.get('max_score', 0)} - {q.get('status', 'N/A').upper()}
Feedback: {q.get('feedback', 'No feedback')}
"""
    
    text_content += f"""
Detailed report: {report_url}

You can view detailed feedback in the student portal.

Best regards,
Assignment System
"""

    # HTML content
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .score-box {{ background: white; padding: 20px; border-radius: 5px; margin: 15px 0; text-align: center; }}
        .question-result {{ background: white; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        .correct {{ border-left: 4px solid #4CAF50; }}
        .partial {{ border-left: 4px solid #FFC107; }}
        .incorrect {{ border-left: 4px solid #F44336; }}
        .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
        .button {{ background: #4CAF50; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Evaluation Results</h1>
        </div>
        <div class="content">
            <h2>Dear {student_name},</h2>
            <p>Your assignment "<strong>{assignment_title}</strong>" has been evaluated.</p>
            
            <div class="score-box">
                <h3>Overall Score</h3>
                <h1 style="font-size: 48px; margin: 10px 0; color: #4CAF50;">{final_score}/{max_score}</h1>
                <p style="font-size: 24px; margin: 5px 0;">{percentage:.1f}% - {grade}</p>
            </div>
            
            <h3>Question-wise Results:</h3>
"""
    
    for q in evaluation_results:
        status_class = q.get('status', 'incorrect')
        html_content += f"""
            <div class="question-result {status_class}">
                <h4>Question {q.get('question_number', 'N/A')}: {q.get('score', 0)}/{q.get('max_score', 0)} points</h4>
                <p><strong>Feedback:</strong> {q.get('feedback', 'No feedback')}</p>
                <p><strong>Status:</strong> <span style="text-transform: capitalize;">{q.get('status', 'N/A')}</span></p>
            </div>
"""
    
    html_content += f"""
            <div style="background: #e8f4fd; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p><strong>Note:</strong> This evaluation was performed automatically.</p>
                {f'<p><a href="{report_url}" class="button">Download Detailed Report</a></p>' if report_url else ''}
            </div>
        </div>
        <div class="footer">
            <p>This is an automated evaluation result. Please do not reply to this email.</p>
            <p>Student Assignment System</p>
        </div>
    </div>
</body>
</html>"""
    
    return subject, text_content, html_content


def generate_report_email(data: dict) -> Tuple[str, str, str]:
    report_type = data.get('report_type', 'report')
    report_url = data.get('report_url', '')
    assignment_title = data.get('assignment_title', 'Assignment')
    
    if report_type == 'class_report':
        subject = f"Class Report Ready - {assignment_title}"
        
        text_content = f"""
Dear Teacher,

Your class performance report for "{assignment_title}" is ready for download.

Download the report here: {report_url}

The report includes student-wise performance analysis, class statistics, and grade distribution.

Best regards,
Assignment System
"""
        
        html_content = f"""<!DOCTYPE html>
<html>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #2196F3; color: white; padding: 20px; text-align: center;">
            <h1>Class Report Ready</h1>
        </div>
        <div style="padding: 20px; background: #f9f9f9;">
            <h2>Dear Teacher,</h2>
            <p>Your class performance report for "<strong>{assignment_title}</strong>" is ready for download.</p>
            
            <div style="background: white; padding: 20px; border-radius: 5px; margin: 15px 0; text-align: center;">
                <a href="{report_url}" style="background: #2196F3; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; display: inline-block;">Download Class Report</a>
            </div>
            
            <div style="background: #e8f4fd; padding: 15px; border-radius: 5px;">
                <h3>Report Includes:</h3>
                <ul>
                    <li>Student-wise performance analysis</li>
                    <li>Class average and statistics</li>
                    <li>Question-wise performance breakdown</li>
                    <li>Grade distribution</li>
                    <li>Performance trends</li>
                </ul>
            </div>
        </div>
        <div style="padding: 20px; text-align: center; font-size: 12px; color: #666;">
            <p>Assignment System - Automated Reporting</p>
        </div>
    </div>
</body>
</html>"""
    else:
        # Student report
        student_name = data.get('student_name', 'Student')
        subject = "Your Performance Report Ready"
        
        text_content = f"""
Dear {student_name},

Your personal performance report is ready!

Download your report: {report_url}

Track your progress and identify areas for improvement.

Best regards,
Assignment System
"""
        
        html_content = f"""<!DOCTYPE html>
<html>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #9C27B0; color: white; padding: 20px; text-align: center;">
            <h1>Performance Report Ready</h1>
        </div>
        <div style="padding: 20px; background: #f9f9f9;">
            <h2>Dear {student_name},</h2>
            <p>Your personal performance report is ready for download!</p>
            
            <div style="background: white; padding: 20px; border-radius: 5px; margin: 15px 0; text-align: center;">
                <a href="{report_url}" style="background: #9C27B0; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; display: inline-block;">Download My Report</a>
            </div>
            
            <div style="background: #f3e5f5; padding: 15px; border-radius: 5px;">
                <h3>Report Includes:</h3>
                <ul>
                    <li>Your score history and trends</li>
                    <li>Subject-wise performance analysis</li>
                    <li>Grade analysis and comparisons</li>
                    <li>Improvement suggestions</li>
                    <li>Progress tracking</li>
                </ul>
            </div>
        </div>
        <div style="padding: 20px; text-align: center; font-size: 12px; color: #666;">
            <p>Assignment System - Student Portal</p>
        </div>
    </div>
</body>
</html>"""
    
    return subject, text_content, html_content


def generate_reminder_email(data: dict) -> Tuple[str, str, str]:
    student_name = data.get('student_name', 'Student')
    assignment_title = data.get('assignment_title', 'Assignment')
    due_date = data.get('due_date', 'Soon')
    submission_url = data.get('submission_url', '')
    
    subject = f"Assignment Reminder - {assignment_title}"
    
    text_content = f"""
Dear {student_name},

This is a friendly reminder that you have an upcoming assignment due.

Assignment: {assignment_title}
Due Date: {due_date}

Please make sure to submit your assignment before the deadline.

Best regards,
Assignment System
"""
    
    html_content = f"""<!DOCTYPE html>
<html>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #FF9800; color: white; padding: 20px; text-align: center;">
            <h1>Assignment Reminder</h1>
        </div>
        <div style="padding: 20px; background: #f9f9f9;">
            <h2>Dear {student_name},</h2>
            <p>This is a friendly reminder about your upcoming assignment.</p>
            
            <div style="background: white; padding: 20px; border-radius: 5px; margin: 15px 0;">
                <h3>{assignment_title}</h3>
                <p><strong>Due Date:</strong> {due_date}</p>
                {f'<p><a href="{submission_url}" style="color: #FF9800;">Submit Assignment</a></p>' if submission_url else ''}
            </div>
        </div>
    </div>
</body>
</html>"""
    
    return subject, text_content, html_content


def generate_teacher_email(data: dict) -> Tuple[str, str, str]:
    teacher_name = data.get('teacher_name', 'Teacher')
    notification_type = data.get('notification_type', 'Notification')
    assignment_title = data.get('assignment_title', 'Assignment')
    message = data.get('message', '')
    action_url = data.get('action_url', '')
    
    subject = f"Teacher Notification - {notification_type}"
    
    text_content = f"""
Dear {teacher_name},

{message}

Assignment: {assignment_title}
"""
    
    if action_url:
        text_content += f"Action Required: {action_url}"
    
    text_content += """
Best regards,
Assignment System
"""
    
    html_content = f"""<!DOCTYPE html>
<html>
<body>
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #673AB7; color: white; padding: 20px; text-align: center;">
            <h1>Teacher Notification</h1>
        </div>
        <div style="padding: 20px; background: #f9f9f9;">
            <h2>Dear {teacher_name},</h2>
            <p>{message}</p>
            <p><strong>Assignment:</strong> {assignment_title}</p>
            {f'<p><a href="{action_url}" style="color: #673AB7;">Take Action</a></p>' if action_url else ''}
        </div>
    </div>
</body>
</html>"""
    
    return subject, text_content, html_content


def calculate_grade(percentage: float) -> str:
    if percentage >= 90: return 'A+'
    elif percentage >= 85: return 'A'
    elif percentage >= 80: return 'A-'
    elif percentage >= 75: return 'B+'
    elif percentage >= 70: return 'B'
    elif percentage >= 65: return 'B-'
    elif percentage >= 60: return 'C+'
    elif percentage >= 55: return 'C'
    elif percentage >= 50: return 'C-'
    elif percentage >= 45: return 'D'
    else: return 'F'


# ------------------------------
# SMTP Send helpers
# ------------------------------
def create_mime_message(smtp_config: dict, to_email: str, subject: str, text_content: str, html_content: str) -> MIMEMultipart:
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{smtp_config.get('sender_name', SENDER_NAME)} <{smtp_config['sender_email']}>"
    msg['To'] = to_email
    part1 = MIMEText(text_content or "", 'plain', 'utf-8')
    part2 = MIMEText(html_content or "", 'html', 'utf-8')
    msg.attach(part1)
    msg.attach(part2)
    return msg


def open_smtp_connection(smtp_config: dict):
    server = smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port'], timeout=SMTP_TIMEOUT)
    # Greet and upgrade to TLS
    server.ehlo()
    server.starttls()
    server.ehlo()
    if DEBUG_SMTP:
        server.set_debuglevel(1)
    server.login(smtp_config['sender_email'], smtp_config['sender_password'])
    return server


def send_single_email(smtp_config: dict, to_email: str, subject: str, text_content: str, html_content: str) -> None:
    """Send a single email using SMTP with retry logic"""
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug("Attempt %d to send email to %s", attempt, to_email)
            msg = create_mime_message(smtp_config, to_email, subject, text_content, html_content)
            
            with smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port'], timeout=SMTP_TIMEOUT) as server:
                if DEBUG_SMTP:
                    server.set_debuglevel(1)
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_config['sender_email'], smtp_config['sender_password'])
                server.send_message(msg)
            
            logger.info("Email sent successfully to %s", to_email)
            return
            
        except Exception as e:
            last_error = e
            logger.warning("Send attempt %d failed for %s: %s", attempt, to_email, str(e))
            if attempt < MAX_RETRIES:
                backoff_sleep(attempt)
    
    # If all retries failed
    logger.error("All %d retries failed for %s", MAX_RETRIES, to_email)
    raise last_error


def send_batch_emails(smtp_config: dict, recipients: List[str], subject: str, text_content: str, html_content: str) -> Dict[str, Any]:
    """
    Send a batch of emails over a single SMTP connection. Use retries per recipient.
    Returns success/failure counts and details.
    """
    success_count = 0
    failure_count = 0
    failed_emails = []

    server = None
    try:
        server = open_smtp_connection(smtp_config)
        logger.info("SMTP connection opened and authenticated")
    except Exception as e:
        logger.exception("Failed to open SMTP connection")
        # If connection can't be established, mark all recipients as failed
        for r in recipients:
            failed_emails.append({'email': r, 'error': f"SMTP connect/login failed: {str(e)}"})
        return {'success_count': success_count, 'failure_count': len(recipients), 'failed_emails': failed_emails}

    try:
        for to_email in recipients:
            sent = False
            last_error = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    msg = create_mime_message(smtp_config, to_email, subject, text_content, html_content)
                    server.send_message(msg)
                    success_count += 1
                    sent = True
                    logger.info("Email sent to %s", to_email)
                    break
                except Exception as e:
                    last_error = e
                    logger.warning("Send attempt %d failed for %s: %s", attempt, to_email, str(e))
                    if attempt < MAX_RETRIES:
                        backoff_sleep(attempt)
                    else:
                        logger.exception("All retries failed for %s", to_email)

            if not sent:
                failure_count += 1
                failed_emails.append({'email': to_email, 'error': str(last_error)})
    finally:
        try:
            server.quit()
            logger.info("SMTP connection closed")
        except Exception:
            try:
                server.close()
            except Exception:
                pass

    return {'success_count': success_count, 'failure_count': failure_count, 'failed_emails': failed_emails}


def chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


# ------------------------------
# Main send_emails wrapper
# ------------------------------
def send_emails(to_emails: List[str], subject: str, text_content: str, html_content: str) -> Dict[str, Any]:
    if not isinstance(to_emails, list):
        raise ValueError("to_emails must be a list of recipient email addresses")

    smtp_config = get_smtp_config()
    total_success = 0
    total_failure = 0
    failed_emails = []

    # For single email, use simpler approach; for multiple, use batching
    if len(to_emails) == 1:
        try:
            send_single_email(smtp_config, to_emails[0], subject, text_content, html_content)
            total_success = 1
        except Exception as e:
            total_failure = 1
            failed_emails.append({'email': to_emails[0], 'error': str(e)})
    else:
        # Break recipients into batches to reuse connections and avoid giant RCPT lists
        batches = chunk_list(to_emails, MAX_BATCH_SIZE)
        logger.info("Sending emails in %d batch(es) (batch size %d)", len(batches), MAX_BATCH_SIZE)

        for batch in batches:
            batch_result = send_batch_emails(smtp_config, batch, subject, text_content, html_content)
            total_success += batch_result['success_count']
            total_failure += batch_result['failure_count']
            failed_emails.extend(batch_result['failed_emails'])

    return {'success_count': total_success, 'failure_count': total_failure, 'failed_emails': failed_emails}


# ------------------------------
# Handler & Routing
# ------------------------------
def handle_simple_email(body: dict):
    to_emails = body.get('to_emails', [])
    subject = body.get('subject', '')
    text_content = body.get('text_content', '')
    html_content = body.get('html_content', '')

    if not to_emails:
        raise ValueError("No recipient emails provided")
    if not subject:
        raise ValueError("Email subject is required")

    logger.info("handle_simple_email: sending %s to %d recipients", subject, len(to_emails))
    results = send_emails(to_emails, subject, text_content, html_content)
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'success',
            'emails_sent': results['success_count'],
            'emails_failed': results['failure_count'],
            'failed_emails': results['failed_emails'],
            'message': f"Sent {results['success_count']} emails successfully"
        })
    }


def handle_template_email(data: dict):
    email_type = data.get('email_type')
    to_emails = data.get('to_emails', [])

    if not email_type:
        raise ValueError("email_type is required for template emails")
    if not to_emails:
        raise ValueError("to_emails is required for template emails")

    logger.info("handle_template_email: type=%s recipients=%d", email_type, len(to_emails))

    if email_type == 'evaluation_results':
        subject, text_content, html_content = generate_evaluation_email(data)
    elif email_type == 'report_ready':
        subject, text_content, html_content = generate_report_email(data)
    elif email_type == 'assignment_reminder':
        subject, text_content, html_content = generate_reminder_email(data)
    elif email_type in ['reminder_24_hour_reminder', 'reminder_1_hour_reminder', 'assignment_notification']:
        subject = data.get('subject', 'Assignment Reminder')
        text_content = data.get('text_content', '')
        html_content = data.get('html_content', '')
    elif email_type == 'teacher_notification':
        subject, text_content, html_content = generate_teacher_email(data)
    else:
        raise ValueError(f"Unknown email type: {email_type}")

    results = send_emails(to_emails, subject, text_content, html_content)
    return {
        'statusCode': 200,
        'body': json.dumps({
            'status': 'success',
            'email_type': email_type,
            'emails_sent': results['success_count'],
            'emails_failed': results['failure_count'],
            'failed_emails': results['failed_emails'],
            'message': f"Sent {results['success_count']} {email_type} emails successfully"
        })
    }


def lambda_handler(event, context):
    """
    Entry point for Lambda. Supports:
      - Direct invocation with JSON payload
      - API Gateway proxy integration: event contains 'body' string (JSON)
    """
    logger.info("Email Service: Processing email request")
    logger.debug("Received event: %s", json.dumps(event))

    try:
        if 'body' in event and isinstance(event['body'], str):
            # API Gateway request
            body = json.loads(event['body']) if event['body'] else {}
        else:
            # direct invocation
            body = event or {}

        logger.debug("Parsed body: %s", json.dumps(body))

        email_type = body.get('email_type')
        if email_type:
            response = handle_template_email(body)
        else:
            response = handle_simple_email(body)

        # Ensure CORS headers if used via API Gateway
        response.setdefault('headers', {})
        response['headers'].update({
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        })
        return response

    except Exception as e:
        logger.exception("Email Service Error")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Email sending failed',
                'message': str(e)
            })
        }
