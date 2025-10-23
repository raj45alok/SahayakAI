import json
import boto3
import decimal

def lambda_handler(event, context):
    print("Getting evaluation results")
    
    try:
        # Extract parameters based on invocation type
        if 'httpMethod' in event and event['httpMethod'] == 'GET':
            # API Gateway invocation
            submission_id = event.get('pathParameters', {}).get('submission_id')
            assignment_id = event.get('queryStringParameters', {}).get('assignment_id')
        else:
            # Direct Lambda invocation
            submission_id = event.get('submission_id')
            assignment_id = event.get('assignment_id')
        
        if not submission_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing required parameter',
                    'message': 'submission_id is required'
                })
            }
        
        print(f"Getting results for submission: {submission_id}, assignment: {assignment_id}")
        
        # Get evaluation results from DynamoDB
        evaluation_data = get_evaluation_data(submission_id, assignment_id)
        
        if not evaluation_data:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Evaluation results not found',
                    'message': f'No evaluation data found for submission {submission_id}'
                })
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'submission_id': submission_id,
                'assignment_id': assignment_id,
                'evaluation_data': evaluation_data,
                'status': 'success'
            })
        }
        
    except Exception as e:
        print(f"Error getting evaluation results: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to get evaluation results',
                'message': str(e)
            })
        }

# [Keep the existing get_evaluation_data and convert_decimals_to_floats functions]
def get_evaluation_data(submission_id, assignment_id):
    """Get evaluation data from DynamoDB"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Submissions-dev')
    
    try:
        if assignment_id:
            # Exact lookup with both keys
            response = table.get_item(Key={
                'submission_id': submission_id,
                'assignment_id': assignment_id
            })
        else:
            # Scan for submission_id (less efficient)
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('submission_id').eq(submission_id)
            )
            items = response.get('Items', [])
            if items:
                response = {'Item': items[0]}
            else:
                response = {}
        
        item = response.get('Item')
        if item:
            return convert_decimals_to_floats({
                'student_name': item.get('student_name'),
                'student_id': item.get('student_id'),
                'final_score': item.get('final_score'),
                'max_score': item.get('max_score'),
                'evaluation_status': item.get('evaluation_status'),
                'evaluated_at': item.get('evaluated_at'),
                'evaluation_results': item.get('evaluation_results', []),
                'submission_type': item.get('submission_type'),
                'submitted_at': item.get('submitted_at')
            })
        return None
        
    except Exception as e:
        print(f"Error getting evaluation data: {str(e)}")
        return None

def convert_decimals_to_floats(obj):
    """Recursively convert Decimal objects to float"""
    if isinstance(obj, list):
        return [convert_decimals_to_floats(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals_to_floats(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return float(obj) if obj % 1 != 0 else int(obj)
    else:
        return obj
