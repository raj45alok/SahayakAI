import json
import boto3
import csv
import io
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    print("Starting class report generation")
    
    try:
        # Extract parameters based on invocation type
        if 'body' in event:
            # API Gateway invocation
            body = json.loads(event['body'])
            assignment_id = body.get('assignment_id')
            teacher_id = body.get('teacher_id')
        else:
            # Direct Lambda invocation
            assignment_id = event.get('assignment_id')
            teacher_id = event.get('teacher_id')
        
        # Validate required parameters
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
        
        print(f"Generating class report for assignment: {assignment_id}")
        
        # Get assignment details
        assignments_table = dynamodb.Table('Assignments-dev')
        assignment_response = assignments_table.get_item(Key={'assignment_id': assignment_id})
        assignment = convert_decimals_to_floats(assignment_response.get('Item'))
        
        if not assignment:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Assignment not found',
                    'message': f'Assignment {assignment_id} does not exist'
                })
            }
        
        # Get all submissions for this assignment
        submissions_table = dynamodb.Table('Submissions-dev')
        response = submissions_table.query(
            IndexName='AssignmentStudentIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('assignment_id').eq(assignment_id)
        )
        submissions = convert_decimals_to_floats(response.get('Items', []))
        
        if not submissions:
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'assignment_id': assignment_id,
                    'status': 'completed',
                    'message': 'No submissions found for this assignment',
                    'submission_count': 0
                })
            }
        
        print(f"Found {len(submissions)} submissions for assignment {assignment_id}")
        
        # Generate CSV report
        csv_buffer = generate_csv_report(assignment, submissions)
        
        # Upload to S3
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_key = f"reports/class-reports/{assignment_id}_{timestamp}.csv"
        
        s3.put_object(
            Bucket='assignment-system-dev',
            Key=report_key,
            Body=csv_buffer.getvalue().encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Generate report summary
        report_summary = generate_report_summary(assignment, submissions)
        
        # Send email notification if teacher email is available
        teacher_email = assignment.get('teacher_email')
        if teacher_email:
            send_report_email(assignment_id, report_key, assignment, teacher_email)
        
        response_body = {
            'message': 'Class report generated successfully',
            'assignment_id': assignment_id,
            'assignment_title': assignment.get('subject', 'Unknown Assignment'),
            'report_location': f"s3://assignment-system-dev/{report_key}",
            'report_url': f"https://assignment-system-dev.s3.amazonaws.com/{report_key}",
            'report_summary': report_summary,
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
        print(f"Error generating class report: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to generate class report',
                'message': str(e)
            })
        }

def generate_csv_report(assignment, submissions):
    """Generate CSV report from submissions data"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Student ID', 'Student Name', 'Email', 
        'Score', 'Max Score', 'Percentage', 'Grade',
        'Submission Status', 'Evaluation Status',
        'Submitted At', 'Evaluated At'
    ])
    
    # Write data rows
    for submission in submissions:
        max_score = submission.get('max_score', 100)
        final_score = submission.get('final_score', 0)
        percentage = (final_score / max_score * 100) if max_score > 0 else 0
        grade = calculate_grade(percentage)
        
        writer.writerow([
            submission.get('student_id', ''),
            submission.get('student_name', ''),
            submission.get('student_email', ''),
            final_score,
            max_score,
            f"{percentage:.2f}%",
            grade,
            submission.get('status', 'submitted'),
            submission.get('evaluation_status', 'pending'),
            submission.get('submitted_at', ''),
            submission.get('evaluated_at', '')
        ])
    
    return output

def generate_report_summary(assignment, submissions):
    """Generate summary statistics for the report"""
    total_students = len(submissions)
    evaluated_count = sum(1 for s in submissions if s.get('evaluation_status') == 'completed')
    pending_count = total_students - evaluated_count
    
    scores = [s.get('final_score', 0) for s in submissions if s.get('final_score') is not None]
    avg_score = sum(scores) / len(scores) if scores else 0
    max_possible = submissions[0].get('max_score', 100) if submissions else 100
    
    # Calculate grade distribution
    grade_dist = {}
    for submission in submissions:
        max_score = submission.get('max_score', 100)
        final_score = submission.get('final_score', 0)
        percentage = (final_score / max_score * 100) if max_score > 0 else 0
        grade = calculate_grade(percentage)
        grade_dist[grade] = grade_dist.get(grade, 0) + 1
    
    return {
        'assignment_title': assignment.get('subject', 'Unknown'),
        'total_students': total_students,
        'evaluated_count': evaluated_count,
        'pending_count': pending_count,
        'submission_rate': round((total_students / total_students * 100), 2) if total_students > 0 else 0,
        'average_score': round(avg_score, 2),
        'average_percentage': round((avg_score / max_possible * 100), 2) if max_possible > 0 else 0,
        'highest_score': max(scores) if scores else 0,
        'lowest_score': min(scores) if scores else 0,
        'grade_distribution': grade_dist
    }

def send_report_email(assignment_id, report_key, assignment, teacher_email):
    """Send email notification when report is ready"""
    lambda_client = boto3.client('lambda')
    
    try:
        report_url = f"https://assignment-system-dev.s3.amazonaws.com/{report_key}"
        
        lambda_client.invoke(
            FunctionName='EmailService-dev',
            InvocationType='Event',
            Payload=json.dumps({
                'email_type': 'report_ready',
                'to_emails': [teacher_email],
                'report_type': 'class_report',
                'report_url': report_url,
                'assignment_title': assignment.get('subject', 'Assignment')
            })
        )
        print(f"✅ Report notification email triggered for {teacher_email}")
    except Exception as e:
        print(f"⚠️ Failed to trigger email notification: {str(e)}")
        # Don't fail the report generation if email fails

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
