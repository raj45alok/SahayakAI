import json
import boto3

def lambda_handler(event, context):
    print("Processing Google Forms webhook")
    
    try:
        # Parse the webhook payload from Google Forms
        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event
        
        print(f"Received webhook payload: {json.dumps(body, indent=2)}")
        
        # Extract form response data and map to our submission format
        submission_data = map_google_forms_response(body)
        
        # Validate required fields
        if not submission_data.get('assignment_id') or submission_data['assignment_id'] == 'unknown':
            raise ValueError("Assignment ID not found in form response")
        
        if not submission_data.get('student_id') or submission_data['student_id'] == 'unknown@example.com':
            raise ValueError("Student email not found in form response")
        
        if not submission_data.get('answers'):
            raise ValueError("No answers found in form response")
        
        print(f"Mapped submission data: {json.dumps(submission_data, indent=2)}")
        
        # Call ProcessSubmission Lambda
        lambda_client = boto3.client('lambda')
        response = lambda_client.invoke(
            FunctionName='ProcessSubmission-dev',
            InvocationType='RequestResponse',
            Payload=json.dumps(submission_data)
        )
        
        # Parse the response from ProcessSubmission
        response_payload = json.loads(response['Payload'].read())
        
        if response_payload['statusCode'] == 200:
            result_body = json.loads(response_payload['body'])
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'status': 'success',
                    'submission_id': result_body.get('submission_id'),
                    'assignment_id': result_body.get('assignment_id'),
                    'student_id': result_body.get('student_id'),
                    'message': 'Google Forms submission processed successfully'
                })
            }
        else:
            # Forward the error from ProcessSubmission
            error_body = json.loads(response_payload['body'])
            raise Exception(f"ProcessSubmission failed: {error_body.get('message', 'Unknown error')}")
        
    except Exception as e:
        print(f"Error processing Google Forms webhook: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Google Forms webhook processing failed',
                'message': str(e)
            })
        }

def map_google_forms_response(form_data):
    """Map Google Forms response to our submission format"""
    # Google Forms webhook typically has this structure:
    # {
    #   "responseId": "abc123",
    #   "respondentEmail": "student@school.edu", 
    #   "totalScore": 0,
    #   "questions": [
    #     {
    #       "questionId": "abc",
    #       "text": "What is your name?",
    #       "answers": [{"value": "John Smith"}]
    #     }
    #   ]
    # }
    
    answers = []
    
    # Extract from different possible Google Forms structures
    respondent_email = form_data.get('respondentEmail') or form_data.get('email')
    form_id = form_data.get('formId') or form_data.get('responseId')
    response_id = form_data.get('responseId')
    
    # Try to extract assignment_id - this could be in different places
    assignment_id = (form_data.get('assignment_id') or 
                    form_data.get('assignmentId') or 
                    form_data.get('customAssignmentId') or 
                    'unknown')
    
    # Try to extract student name
    student_name = (form_data.get('respondentName') or 
                   form_data.get('name') or 
                   form_data.get('student_name') or 
                   'Unknown Student')
    
    # Process questions and answers
    questions = form_data.get('questions', [])
    
    for i, question in enumerate(questions, 1):
        question_text = question.get('text', question.get('question', f'Question {i}'))
        
        # Extract answer value - handle different answer structures
        answer_value = extract_answer_value(question.get('answers'))
        
        answers.append({
            'question_number': str(i),
            'question_text': question_text,
            'answer_text': answer_value
        })
    
    # If no structured questions found, look for flat answer structure
    if not answers and 'answers' in form_data:
        flat_answers = form_data.get('answers', [])
        for i, answer_item in enumerate(flat_answers, 1):
            answers.append({
                'question_number': str(i),
                'question_text': answer_item.get('question', f'Question {i}'),
                'answer_text': answer_item.get('answer', 'No answer provided')
            })
    
    submission_data = {
        'submission_type': 'google_forms',
        'assignment_id': assignment_id,
        'student_id': respondent_email or 'unknown@example.com',
        'student_name': student_name,
        'answers': answers,
        'form_id': form_id or 'unknown',
        'response_id': response_id or 'unknown',
        'submission_timestamp': form_data.get('timestamp') or form_data.get('createTime')
    }
    
    print(f"✅ Mapped Google Forms response to {len(answers)} answers")
    return submission_data

def extract_answer_value(answers_data):
    """Extract answer value from different Google Forms answer structures"""
    if not answers_data:
        return 'No answer provided'
    
    if isinstance(answers_data, list):
        if len(answers_data) == 0:
            return 'No answer provided'
        
        first_answer = answers_data[0]
        if isinstance(first_answer, dict):
            # Could be: {"value": "answer text"} or {"text": "answer text"}
            return first_answer.get('value') or first_answer.get('text') or str(first_answer)
        else:
            return str(first_answer)
    elif isinstance(answers_data, dict):
        return answers_data.get('value') or answers_data.get('text') or str(answers_data)
    else:
        return str(answers_data)
