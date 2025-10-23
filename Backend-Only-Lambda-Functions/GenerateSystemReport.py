import json
import boto3
import csv
import io
from datetime import datetime, timedelta

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    try:
        report_type = event.get('report_type', 'daily')  # daily, weekly, monthly
        days_back = event.get('days', 1)
        
        if report_type == 'weekly':
            days_back = 7
        elif report_type == 'monthly':
            days_back = 30
        
        # Generate system report
        csv_buffer = generate_system_report(days_back)
        
        # Upload to S3 with new folder structure
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_key = f"reports/system-reports/{report_type}_system_report_{timestamp}.csv"
        
        s3.put_object(
            Bucket='assignment-system-dev',
            Key=report_key,
            Body=csv_buffer.getvalue().encode('utf-8'),
            ContentType='text/csv'
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': f'{report_type.capitalize()} system report generated successfully',
                'report_location': f"s3://assignment-system-dev/{report_key}",
                'report_type': report_type,
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        print(f"Error generating system report: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to generate system report',
                'message': str(e)
            })
        }

def generate_system_report(days_back):
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Metric', 'Value', 'Previous Period', 'Change %',
        'Date Range', 'Generated At'
    ])
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    previous_start = start_date - timedelta(days=days_back)
    
    # Get system metrics
    metrics = calculate_system_metrics(start_date, end_date, previous_start, start_date)
    
    # Write metrics
    for metric_name, values in metrics.items():
        writer.writerow([
            metric_name,
            values['current'],
            values['previous'],
            values['change_percentage'],
            f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return output

def calculate_system_metrics(current_start, current_end, previous_start, previous_end):
    # Get current period data
    current_metrics = get_period_metrics(current_start, current_end)
    previous_metrics = get_period_metrics(previous_start, previous_end)
    
    metrics = {}
    
    for metric_name, current_value in current_metrics.items():
        previous_value = previous_metrics.get(metric_name, 0)
        change_percentage = ((current_value - previous_value) / previous_value * 100) if previous_value > 0 else 100
        
        metrics[metric_name] = {
            'current': current_value,
            'previous': previous_value,
            'change_percentage': f"{change_percentage:.2f}%"
        }
    
    return metrics

def get_period_metrics(start_date, end_date):
    dynamodb = boto3.resource('dynamodb')
    
    # Get submissions count
    submissions_table = dynamodb.Table('Submissions-dev')
    submissions_response = submissions_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('submitted_at').between(
            start_date.isoformat(), end_date.isoformat()
        )
    )
    submissions_count = len(submissions_response.get('Items', []))
    
    # Get assignments count
    assignments_table = dynamodb.Table('Assignments-dev')
    assignments_response = assignments_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('created_at').between(
            start_date.isoformat(), end_date.isoformat()
        )
    )
    assignments_count = len(assignments_response.get('Items', []))
    
    # Get evaluated submissions count
    evaluated_response = submissions_table.scan(
        FilterExpression=(
            boto3.dynamodb.conditions.Attr('submitted_at').between(
                start_date.isoformat(), end_date.isoformat()
            ) &
            boto3.dynamodb.conditions.Attr('evaluation_status').eq('completed')
        )
    )
    evaluated_count = len(evaluated_response.get('Items', []))
    
    # Calculate average evaluation time (simplified)
    avg_evaluation_time = calculate_avg_evaluation_time(submissions_response.get('Items', []))
    
    return {
        'Total Submissions': submissions_count,
        'New Assignments': assignments_count,
        'Evaluated Submissions': evaluated_count,
        'Evaluation Rate (%)': (evaluated_count / submissions_count * 100) if submissions_count > 0 else 0,
        'Average Evaluation Time (hours)': avg_evaluation_time
    }

def calculate_avg_evaluation_time(submissions):
    total_time = 0
    count = 0
    
    for submission in submissions:
        if submission.get('submitted_at') and submission.get('evaluated_at'):
            try:
                submitted = datetime.fromisoformat(submission['submitted_at'].replace('Z', '+00:00'))
                evaluated = datetime.fromisoformat(submission['evaluated_at'].replace('Z', '+00:00'))
                time_diff = (evaluated - submitted).total_seconds() / 3600  # Convert to hours
                total_time += time_diff
                count += 1
            except ValueError:
                continue
    
    return round(total_time / count, 2) if count > 0 else 0
