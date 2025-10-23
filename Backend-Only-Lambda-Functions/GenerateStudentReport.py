import json
import boto3
import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    print("Starting student report generation")
    
    try:
        # Extract parameters
        if 'body' in event:
            body = json.loads(event['body'])
            student_id = body.get('student_id')
            days_back = body.get('days', 90)
            report_type = body.get('report_type', 'detailed')
        else:
            student_id = event.get('student_id')
            days_back = event.get('days', 90)
            report_type = event.get('report_type', 'detailed')
        
        if not student_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing required parameter',
                    'message': 'student_id is required'
                })
            }
        
        print(f"Generating {report_type} student report for: {student_id}")
        
        # Get student's submissions using GSI
        submissions_table = dynamodb.Table('Submissions-dev')
        
        # Query using GSI - no date filter since submitted_at is the sort key
        response = submissions_table.query(
            IndexName='StudentSubmissionIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('student_id').eq(student_id)
        )
        submissions = convert_decimals_to_floats(response.get('Items', []))
        
        # Filter by date in code (after query)
        if days_back > 0:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            submissions = [
                sub for sub in submissions 
                if sub.get('submitted_at') and datetime.fromisoformat(sub['submitted_at'].replace('Z', '+00:00')) >= cutoff_date
            ]
        
        if not submissions:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'No submissions found',
                    'message': f'No submissions found for student {student_id} in the last {days_back} days'
                })
            }
        
        print(f"Found {len(submissions)} submissions for student {student_id}")
        
        # Get student name from first submission
        student_name = submissions[0].get('student_name', 'Student')
        student_email = submissions[0].get('student_email', '')
        
        # Generate student report
        if report_type == 'detailed':
            csv_buffer = generate_detailed_student_report(student_id, student_name, submissions)
            file_suffix = 'detailed'
        else:
            csv_buffer = generate_summary_student_report(student_id, student_name, submissions)
            file_suffix = 'summary'
        
        # Upload to S3
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_key = f"reports/student-reports/{student_id}_{file_suffix}_{timestamp}.csv"
        
        s3.put_object(
            Bucket='assignment-system-dev',
            Key=report_key,
            Body=csv_buffer.getvalue().encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Generate performance analytics
        analytics = generate_student_analytics(submissions)
        
        # Send email notification if student email is available
        if student_email:
            send_student_report_email(student_id, report_key, student_name, student_email)
        
        response_body = {
            'message': 'Student report generated successfully',
            'student_id': student_id,
            'student_name': student_name,
            'report_location': f"s3://assignment-system-dev/{report_key}",
            'report_url': f"https://assignment-system-dev.s3.amazonaws.com/{report_key}",
            'report_type': report_type,
            'student_analytics': analytics,
            'timestamp': timestamp
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error generating student report: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to generate student report',
                'message': str(e)
            })
        }

def generate_detailed_student_report(student_id, student_name, submissions):
    """Generate detailed student report"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Assignment ID', 'Subject', 'Topic', 'Teacher',
        'Score', 'Max Score', 'Percentage', 'Grade',
        'Submission Date', 'Evaluation Date',
        'Status', 'Overall Feedback'
    ])
    
    # Write data rows
    for submission in submissions:
        assignment = get_assignment_details(submission['assignment_id'])
        max_score = submission.get('max_score', 100)
        final_score = submission.get('final_score', 0)
        percentage = (final_score / max_score * 100) if max_score > 0 else 0
        grade = calculate_grade(percentage)
        
        writer.writerow([
            submission['assignment_id'],
            assignment.get('subject', 'Unknown'),
            assignment.get('topic', ''),
            assignment.get('teacher_name', ''),
            final_score,
            max_score,
            f"{percentage:.2f}%",
            grade,
            submission.get('submitted_at', ''),
            submission.get('evaluated_at', ''),
            submission.get('evaluation_status', 'pending'),
            get_overall_feedback(submission)
        ])
    
    return output

def generate_summary_student_report(student_id, student_name, submissions):
    """Generate summary student report"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header for summary report
    writer.writerow([
        'Subject', 'Assignments Completed', 'Average Score',
        'Highest Score', 'Lowest Score', 'Overall Grade', 'Performance Trend'
    ])
    
    # Group by subject
    subject_data = {}
    for submission in submissions:
        assignment = get_assignment_details(submission['assignment_id'])
        subject = assignment.get('subject', 'Unknown')
        
        if subject not in subject_data:
            subject_data[subject] = {
                'scores': [],
                'count': 0
            }
        
        final_score = submission.get('final_score', 0)
        max_score = submission.get('max_score', 100)
        percentage = (final_score / max_score * 100) if max_score > 0 else 0
        
        subject_data[subject]['scores'].append(percentage)
        subject_data[subject]['count'] += 1
    
    # Write subject-wise summary
    for subject, data in subject_data.items():
        avg_score = sum(data['scores']) / len(data['scores'])
        highest = max(data['scores'])
        lowest = min(data['scores'])
        overall_grade = calculate_grade(avg_score)
        
        # Simple trend calculation
        if len(data['scores']) > 1:
            first_half_avg = sum(data['scores'][:len(data['scores'])//2]) / (len(data['scores'])//2)
            second_half_avg = sum(data['scores'][len(data['scores'])//2:]) / (len(data['scores']) - len(data['scores'])//2)
            trend = 'Improving' if second_half_avg > first_half_avg else 'Stable'
        else:
            trend = 'Stable'
        
        writer.writerow([
            subject,
            data['count'],
            f"{avg_score:.2f}%",
            f"{highest:.2f}%",
            f"{lowest:.2f}%",
            overall_grade,
            trend
        ])
    
    return output

def get_assignment_details(assignment_id):
    """Get assignment details from DynamoDB"""
    try:
        table = dynamodb.Table('Assignments-dev')
        response = table.get_item(Key={'assignment_id': assignment_id})
        return convert_decimals_to_floats(response.get('Item', {}))
    except Exception as e:
        print(f"Error getting assignment details for {assignment_id}: {str(e)}")
        return {}

def get_overall_feedback(submission):
    """Extract overall feedback from submission"""
    if 'evaluation_results' in submission:
        results = submission['evaluation_results']
        if isinstance(results, list) and len(results) > 0:
            return results[0].get('feedback', 'No feedback available')
    return 'Evaluation pending'

def generate_student_analytics(submissions):
    """Generate student performance analytics"""
    if not submissions:
        return {}
    
    scores = []
    completed_assignments = 0
    subject_performance = {}
    
    for submission in submissions:
        if submission.get('evaluation_status') == 'completed':
            completed_assignments += 1
            final_score = submission.get('final_score', 0)
            max_score = submission.get('max_score', 100)
            percentage = (final_score / max_score * 100) if max_score > 0 else 0
            scores.append(percentage)
            
            # Track subject performance
            assignment = get_assignment_details(submission['assignment_id'])
            subject = assignment.get('subject', 'Unknown')
            if subject not in subject_performance:
                subject_performance[subject] = []
            subject_performance[subject].append(percentage)
    
    if not scores:
        return {
            'total_assignments': len(submissions),
            'completed_assignments': 0,
            'completion_rate': 0,
            'average_score': 0,
            'overall_grade': 'N/A'
        }
    
    avg_score = sum(scores) / len(scores)
    overall_grade = calculate_grade(avg_score)
    
    # Calculate subject averages
    subject_averages = {}
    for subject, subject_scores in subject_performance.items():
        subject_averages[subject] = round(sum(subject_scores) / len(subject_scores), 2)
    
    return {
        'total_assignments': len(submissions),
        'completed_assignments': completed_assignments,
        'completion_rate': round((completed_assignments / len(submissions)) * 100, 2),
        'average_score': round(avg_score, 2),
        'overall_grade': overall_grade,
        'performance_band': get_performance_band(avg_score),
        'subject_performance': subject_averages
    }

def send_student_report_email(student_id, report_key, student_name, student_email):
    """Send email notification when student report is ready"""
    lambda_client = boto3.client('lambda')
    
    try:
        report_url = f"https://assignment-system-dev.s3.amazonaws.com/{report_key}"
        
        lambda_client.invoke(
            FunctionName='EmailService-dev',
            InvocationType='Event',
            Payload=json.dumps({
                'email_type': 'report_ready',
                'to_emails': [student_email],
                'report_type': 'student_report',
                'report_url': report_url,
                'student_name': student_name
            })
        )
        print(f"✅ Student report notification email triggered for {student_email}")
    except Exception as e:
        print(f"⚠️ Failed to trigger student email notification: {str(e)}")

def calculate_grade(percentage):
    """Calculate grade from percentage"""
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

def get_performance_band(percentage):
    """Get performance band description"""
    if percentage >= 85: return 'Excellent'
    elif percentage >= 70: return 'Good'
    elif percentage >= 60: return 'Average'
    else: return 'Needs Improvement'

def convert_decimals_to_floats(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, list):
        return [convert_decimals_to_floats(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj) if obj % 1 != 0 else int(obj)
    else:
        return obj
