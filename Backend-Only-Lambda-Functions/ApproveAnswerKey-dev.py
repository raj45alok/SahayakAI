import json
import boto3
from datetime import datetime
from decimal import Decimal
import decimal

def lambda_handler(event, context):
    print("Starting answer key approval process")
    
    try:
        # Parse the request
        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event
        
        # Check if it's a preview request or approval request
        action = body.get('action', 'approve')
        
        if action == 'preview':
            return preview_generated_answers(body, context)
        elif action == 'approve':
            return approve_answers(body, context)
        else:
            raise ValueError(f"Unknown action: {action}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return error_response(str(e))

def decimal_default(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def preview_generated_answers(body, context):
    """Preview AI-generated answers before approval"""
    assignment_id = body['assignment_id']
    teacher_id = body['teacher_id']
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Assignments-dev')
    
    # Get assignment with AI-generated answers
    response = table.get_item(Key={'assignment_id': assignment_id})
    if 'Item' not in response:
        raise ValueError(f"Assignment {assignment_id} not found")
    
    assignment = response['Item']
    
    # Verify teacher ownership
    if assignment.get('teacher_id') != teacher_id:
        raise ValueError(f"Teacher {teacher_id} not authorized for this assignment")
    
    # Extract questions with AI answers for preview
    preview_data = []
    for question in assignment.get('questions', []):
        preview_data.append({
            'question_number': question['question_number'],
            'question_text': question['question_text'],
            'question_type': question.get('question_type', 'text'),
            'ai_generated_answer': question.get('suggested_answer', 'No answer generated'),
            'max_score': question.get('max_score', 10),
            'needs_review': True  # Flag for teacher to review
        })
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json', 
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'assignment_id': assignment_id,
            'teacher_id': teacher_id,
            'status': 'ready_for_review',
            'questions': preview_data,
            'message': 'Review AI-generated answers and provide approved versions',
            'preview_at': datetime.now().isoformat()
        }, default=decimal_default)  # Use custom serializer
    }

def approve_answers(body, context):
    """Teacher approves/modifies AI-generated answers"""
    assignment_id = body['assignment_id']
    teacher_id = body['teacher_id']
    approved_answers = body['approved_answers']
    
    bucket_name = "assignment-system-dev"
    
    print(f"Processing approval for assignment: {assignment_id}")
    print(f"Teacher provided {len(approved_answers)} approved answers")
    
    # Update DynamoDB with teacher-approved answers
    update_assignment_approval(assignment_id, teacher_id, approved_answers)
    
    # Update answer key files
    update_answer_key_file(bucket_name, assignment_id, teacher_id, approved_answers)
    create_final_answer_key(bucket_name, assignment_id, approved_answers)
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json', 
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'assignment_id': assignment_id,
            'status': 'approved',
            'message': 'Answer key approved and finalized successfully',
            'approved_questions': len(approved_answers),
            'approved_at': datetime.now().isoformat(),
            'teacher_id': teacher_id
        }, default=decimal_default)  # Use custom serializer
    }

def update_assignment_approval(assignment_id, teacher_id, approved_answers):
    """Update assignment with teacher-approved answers while preserving AI suggestions"""
    dynamodb = boto3.resource('dynamodb')
    table_name = 'Assignments-dev'
    
    try:
        table = dynamodb.Table(table_name)
        
        # Get current assignment
        response = table.get_item(Key={'assignment_id': assignment_id})
        if 'Item' not in response:
            raise ValueError(f"Assignment {assignment_id} not found in DynamoDB")
        
        assignment = response['Item']
        
        # Verify teacher ownership
        if assignment.get('teacher_id') != teacher_id:
            raise ValueError(f"Teacher {teacher_id} not authorized to approve assignment {assignment_id}")
        
        # Track modifications
        modifications = []
        updated_questions = []
        
        for question in assignment['questions']:
            q_num = question['question_number']
            ai_answer = question.get('suggested_answer', '')
            
            if q_num in approved_answers:
                teacher_answer = approved_answers[q_num]
                
                # Check if teacher modified the AI answer
                is_modified = (teacher_answer != ai_answer)
                
                if is_modified:
                    modifications.append({
                        'question_number': q_num,
                        'ai_answer': ai_answer,
                        'teacher_answer': teacher_answer
                    })
                
                # Update question with both AI and teacher answers
                question['approved_answer'] = teacher_answer
                question['answer_status'] = 'approved'
                question['approved_by'] = teacher_id
                question['approved_at'] = datetime.now().isoformat()
                question['was_modified'] = is_modified
                question['ai_suggested_answer'] = ai_answer  # Preserve original AI answer
                
            else:
                question['answer_status'] = 'pending'
                question['was_modified'] = False
            
            updated_questions.append(question)
        
        # Update the assignment
        table.update_item(
            Key={'assignment_id': assignment_id},
            UpdateExpression='SET questions = :q, #s = :s, updated_at = :u, approved_by = :ab, approved_at = :aa, modifications = :m',
            ExpressionAttributeNames={
                '#s': 'status'
            },
            ExpressionAttributeValues={
                ':q': updated_questions,
                ':s': 'approved', 
                ':u': datetime.now().isoformat(),
                ':ab': teacher_id,
                ':aa': datetime.now().isoformat(),
                ':m': modifications
            }
        )
        
        print(f"✅ Updated assignment {assignment_id} with {len(modifications)} modifications")
        
    except Exception as e:
        print(f"❌ Error updating DynamoDB: {str(e)}")
        raise Exception(f"Failed to update assignment: {str(e)}")

def update_answer_key_file(bucket_name, assignment_id, teacher_id, approved_answers):
    """Update the answer key file with approval status"""
    s3 = boto3.client('s3')
    answer_key_path = f"assignments/answer-keys/{assignment_id}/answer_key.json"
    
    try:
        # Get current answer key
        response = s3.get_object(Bucket=bucket_name, Key=answer_key_path)
        answer_key = json.loads(response['Body'].read().decode('utf-8'))
        
        # Update with approval information
        answer_key['status'] = 'approved'
        answer_key['approved_by'] = teacher_id
        answer_key['approved_at'] = datetime.now().isoformat()
        answer_key['approved_answers'] = approved_answers
        
        # Update questions
        for question in answer_key.get('questions', []):
            q_num = question['question_number']
            if q_num in approved_answers:
                question['approved_answer'] = approved_answers[q_num]
                question['answer_status'] = 'approved'
                # Keep AI answer for reference
                question['ai_suggested_answer'] = question.get('suggested_answer', '')
        
        # Save updated answer key
        s3.put_object(
            Bucket=bucket_name,
            Key=answer_key_path,
            Body=json.dumps(answer_key, indent=2),
            ContentType='application/json'
        )
        
        print(f"✅ Updated answer key: {answer_key_path}")
        
    except Exception as e:
        print(f"❌ Error updating answer key: {e}")
        raise Exception(f"Failed to update answer key: {str(e)}")

def create_final_answer_key(bucket_name, assignment_id, approved_answers):
    """Create final answer key for evaluation"""
    s3 = boto3.client('s3')
    final_path = f"assignments/answer-keys/{assignment_id}/final_answer_key.json"
    
    try:
        # Get original answer key
        original_path = f"assignments/answer-keys/{assignment_id}/answer_key.json"
        response = s3.get_object(Bucket=bucket_name, Key=original_path)
        original_key = json.loads(response['Body'].read().decode('utf-8'))
        
        # Create final version
        final_key = {
            'assignment_id': assignment_id,
            'status': 'final_approved',
            'approved_at': datetime.now().isoformat(),
            'questions': []
        }
        
        for question in original_key.get('questions', []):
            q_num = question['question_number']
            if q_num in approved_answers:
                final_question = {
                    'question_number': q_num,
                    'question_text': question['question_text'],
                    'question_type': question.get('question_type', 'text'),
                    'approved_answer': approved_answers[q_num],
                    'max_score': float(question.get('max_score', 10)),  # Convert to float
                    'evaluation_criteria': generate_evaluation_criteria(question.get('question_type', 'text'))
                }
                final_key['questions'].append(final_question)
        
        # Save final key
        s3.put_object(
            Bucket=bucket_name,
            Key=final_path,
            Body=json.dumps(final_key, indent=2),
            ContentType='application/json'
        )
        
        print(f"✅ Created final answer key: {final_path}")
        
    except Exception as e:
        print(f"⚠️ Error creating final key: {e}")

def generate_evaluation_criteria(question_type):
    """Generate evaluation criteria"""
    criteria = {
        'problem_solving': ['Correct approach', 'Step-by-step working', 'Final answer', 'Units included'],
        'algebra': ['Correct formula', 'Step-by-step solution', 'Final answer', 'Checking work'],
        'text': ['Completeness', 'Accuracy', 'Clarity', 'Relevance to question']
    }
    return criteria.get(question_type, ['Completeness', 'Accuracy', 'Clarity'])

def error_response(error_message):
    """Return error response"""
    return {
        'statusCode': 500,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': 'Processing failed',
            'message': error_message
        }, default=decimal_default)  # Use custom serializer
    }
