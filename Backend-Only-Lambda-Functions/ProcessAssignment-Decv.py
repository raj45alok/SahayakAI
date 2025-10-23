import json
import boto3
import uuid
import re
import time
from datetime import datetime
from botocore.config import Config

# Configure boto3 for better performance
boto_config = Config(
    retries=dict(max_attempts=3),
    read_timeout=300,
    connect_timeout=300
)

s3_client = boto3.client('s3', config=boto_config)
textract_client = boto3.client('textract', config=boto_config)
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1', config=boto_config)
dynamodb = boto3.resource('dynamodb', config=boto_config)
lambda_client = boto3.client('lambda', config=boto_config)

def lambda_handler(event, context):
    """Main Lambda handler with async processing support"""
    print("Starting assignment processing")
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Check if this is an async processing invocation
        if event.get('async_processing'):
            print("🔄 Processing async invocation")
            return handle_async_processing(event)
        
        # Handle CORS preflight
        if event.get('httpMethod') == 'OPTIONS':
            return cors_response()
        
        # Parse body
        body = extract_request_body(event)
        
        # Check if this is the new upload format (title, description, deadline, file)
        if 'title' in body and 'file' in body:
            return handle_upload_format(body, context)
        
        # Otherwise use the old format (file_key, teacher_id)
        return handle_direct_invocation(body, context)
            
    except Exception as e:
        print(f"❌ Error in lambda_handler: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(str(e))

def cors_response():
    """Return CORS preflight response"""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'POST,OPTIONS,GET'
        },
        'body': json.dumps({'message': 'OK'})
    }

def handle_upload_format(body, context):
    """Handle new upload format - Returns immediately after S3 upload"""
    print("📤 Processing upload format request")
    
    import base64
    
    # Extract fields
    title = body.get('title')
    description = body.get('description')
    deadline = body.get('deadline')
    file_data = body.get('file')
    teacher_id = body.get('teacher_id', 'default_teacher')
    subject = body.get('subject', 'General')
    class_info = body.get('class_info', 'Default Class')
    
    if not all([title, description, deadline, file_data]):
        return error_response('Missing required fields: title, description, deadline, file')
    
    # Generate IDs
    assignment_id = str(uuid.uuid4())
    bucket_name = 'assignment-system-dev'
    
    # Decode file and detect content type
    try:
        content_type = 'application/pdf'
        file_extension = 'pdf'
        
        if file_data.startswith('data:'):
            file_parts = file_data.split(',')
            if len(file_parts) != 2:
                return error_response('Invalid file format')
            
            # Extract MIME type
            mime_match = re.match(r'data:([^;]+)', file_parts[0])
            if mime_match:
                content_type = mime_match.group(1)
                
                # Map MIME to extension
                mime_to_ext = {
                    'text/plain': 'txt',
                    'application/pdf': 'pdf',
                    'image/jpeg': 'jpg',
                    'image/png': 'png',
                    'image/tiff': 'tiff'
                }
                file_extension = mime_to_ext.get(content_type, 'pdf')
            
            file_content = base64.b64decode(file_parts[1])
        else:
            file_content = base64.b64decode(file_data)
    except Exception as e:
        return error_response(f'Failed to decode file: {str(e)}')
    
    # Upload to S3 with correct extension
    file_key = f"assignments/uploaded/{assignment_id}/{title.replace(' ', '_')}.{file_extension}"
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=file_content,
            ContentType=content_type
        )
        print(f"✅ Uploaded file to s3://{bucket_name}/{file_key}")
    except Exception as e:
        return error_response(f'Failed to upload file to S3: {str(e)}')
    
    # Store initial assignment record in DynamoDB with 'processing' status
    try:
        table = dynamodb.Table('Assignments-dev')
        table.put_item(Item={
            'assignment_id': assignment_id,
            'teacher_id': teacher_id,
            'title': title,
            'description': description,
            'deadline': deadline,
            'file_location': file_key,
            'subject': subject,
            'class_info': class_info,
            'status': 'processing',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
        print(f"✅ Created DynamoDB record with status: processing")
    except Exception as e:
        print(f"⚠️ Failed to create initial DynamoDB record: {e}")
    
    # Invoke async processing
    try:
        lambda_client.invoke(
            FunctionName=context.function_name,
            InvocationType='Event',  # Fire and forget
            Payload=json.dumps({
                'async_processing': True,
                'file_key': file_key,
                'bucket_name': bucket_name,
                'teacher_id': teacher_id,
                'assignment_id': assignment_id,
                'subject': subject,
                'class_info': class_info,
                'title': title
            })
        )
        print(f"✅ Invoked async processing for assignment {assignment_id}")
    except Exception as e:
        print(f"⚠️ Failed to invoke async processing: {e}")
    
    # Return immediately (within 3-5 seconds)
    return {
        'statusCode': 202,  # Accepted
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST,OPTIONS,GET'
        },
        'body': json.dumps({
            'assignmentId': assignment_id,
            'status': 'processing',
            'message': 'Assignment uploaded successfully. Questions are being generated in the background.',
            's3Location': f"s3://{bucket_name}/{file_key}",
            'estimatedCompletionTime': 45
        })
    }

def handle_async_processing(event):
    """Handle async processing without returning to API Gateway"""
    print("🔄 Starting async background processing")
    
    assignment_id = event['assignment_id']
    file_key = event['file_key']
    bucket_name = event['bucket_name']
    teacher_id = event['teacher_id']
    subject = event.get('subject', 'General')
    class_info = event.get('class_info', 'Default Class')
    
    try:
        # Extract text from file
        print(f"📄 Extracting text from {file_key}")
        assignment_text = extract_text_from_file(bucket_name, file_key)
        print(f"✅ Extracted {len(assignment_text)} characters")
        
        # Extract questions
        print(f"🔍 Extracting questions...")
        questions = extract_questions_smart(assignment_text)
        print(f"✅ Extracted {len(questions)} questions")
        
        # Get file extension
        file_extension = file_key.split('.')[-1]
        
        # Store file paths
        processed_file_key = f"assignments/processed/{assignment_id}/assignment.{file_extension}"
        answer_key_path = f"assignments/answer-keys/{assignment_id}/answer_key.json"
        
        # Process files in S3
        print(f"📦 Processing S3 files...")
        process_s3_files(s3_client, bucket_name, file_key, processed_file_key, answer_key_path, questions, assignment_id)
        
        # Update DynamoDB with questions
        print(f"💾 Updating DynamoDB with questions...")
        update_dynamodb_with_questions(assignment_id, teacher_id, processed_file_key, answer_key_path, questions, subject, class_info)
        
        print(f"✅ Async processing completed for assignment {assignment_id}")
        return {'statusCode': 200, 'body': json.dumps({'status': 'completed'})}
        
    except Exception as e:
        print(f"❌ Async processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Update DynamoDB with error status
        try:
            table = dynamodb.Table('Assignments-dev')
            table.update_item(
                Key={'assignment_id': assignment_id},
                UpdateExpression='SET #status = :status, error_message = :error, updated_at = :updated',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'failed',
                    ':error': str(e),
                    ':updated': datetime.now().isoformat()
                }
            )
        except Exception as db_error:
            print(f"Failed to update error status in DynamoDB: {db_error}")
        
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

def update_dynamodb_with_questions(assignment_id, teacher_id, file_key, answer_key_path, questions, subject, class_info):
    """Update DynamoDB record with extracted questions"""
    try:
        table = dynamodb.Table('Assignments-dev')
        
        table.update_item(
            Key={'assignment_id': assignment_id},
            UpdateExpression='SET file_location = :file, answer_key_location = :answer, questions = :questions, #status = :status, updated_at = :updated',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':file': file_key,
                ':answer': answer_key_path,
                ':questions': questions,
                ':status': 'pending_review',
                ':updated': datetime.now().isoformat()
            }
        )
        print(f"✅ Updated DynamoDB with {len(questions)} questions")
        
    except Exception as e:
        print(f"❌ Error updating DynamoDB: {str(e)}")
        raise

def handle_direct_invocation(event, context):
    """Handle direct Lambda invocation or API Gateway request"""
    print("Processing direct invocation")
    print(f"Event keys: {list(event.keys())}")
    
    # Parse the request based on different invocation patterns
    body = extract_request_body(event)
    
    # Validate required fields
    required_fields = ['file_key', 'teacher_id']
    for field in required_fields:
        if field not in body:
            raise Exception(f"Missing required field: {field}")
    
    bucket_name = body.get('bucket_name', 'assignment-system-dev')
    file_key = body['file_key']
    teacher_id = body['teacher_id']
    subject = body.get('subject', 'General')
    class_info = body.get('class_info', 'Default Class')
    
    print(f"Processing - Bucket: {bucket_name}, File: {file_key}, Teacher: {teacher_id}")
    
    # Validate file type
    validate_file_type(file_key)
    
    # Validate S3 object exists and is accessible
    validate_s3_object(bucket_name, file_key)
    
    assignment_id = str(uuid.uuid4())
    print(f"Generated assignment ID: {assignment_id}")
    
    # Extract text from the uploaded file with better error handling
    try:
        assignment_text = extract_text_from_file(bucket_name, file_key)
        print(f"Extracted text length: {len(assignment_text)} characters")
        
        if len(assignment_text.strip()) < 10:
            raise Exception("Extracted text is too short or empty")
            
    except Exception as e:
        print(f"Text extraction failed: {str(e)}")
        return error_response(f"Failed to extract text from document: {str(e)}")
    
    questions = extract_questions_smart(assignment_text)
    print(f"Extracted {len(questions)} questions")
    
    # Get original file extension
    file_extension = file_key.split('.')[-1]
    
    # Store file paths with correct extension
    processed_file_key = f"assignments/processed/{assignment_id}/assignment.{file_extension}"
    answer_key_path = f"assignments/answer-keys/{assignment_id}/answer_key.json"
    
    # Process files in S3
    process_s3_files(s3_client, bucket_name, file_key, processed_file_key, answer_key_path, questions, assignment_id)
    
    # Store in DynamoDB
    store_in_dynamodb(assignment_id, teacher_id, processed_file_key, answer_key_path, questions, subject, class_info)
    
    return success_response(assignment_id, questions, bucket_name, processed_file_key, answer_key_path)

# All the helper functions from your original code remain the same:

def extract_request_body(event):
    """Extract and parse request body from different event sources"""
    print("Extracting request body from event...")
    
    # Case 1: S3 Event
    if 'Records' in event:
        print("S3 event detected")
        try:
            s3_record = event['Records'][0]['s3']
            bucket_name = s3_record['bucket']['name']
            file_key = s3_record['object']['key']
            
            import urllib.parse
            file_key = urllib.parse.unquote_plus(file_key)
            
            print(f"S3 Event - Bucket: {bucket_name}, Key: {file_key}")
            
            path_parts = file_key.split('/')
            teacher_id = 'default_teacher'
            
            try:
                try:
                    tags_response = s3_client.get_object_tagging(
                        Bucket=bucket_name,
                        Key=file_key
                    )
                    tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagSet', [])}
                    if 'teacher_id' in tags:
                        teacher_id = tags['teacher_id']
                        print(f"Found teacher_id in tags: {teacher_id}")
                except Exception as tag_error:
                    print(f"No tags found or accessible: {tag_error}")
                
                if teacher_id == 'default_teacher':
                    try:
                        metadata_response = s3_client.head_object(
                            Bucket=bucket_name,
                            Key=file_key
                        )
                        metadata = metadata_response.get('Metadata', {})
                        if 'teacher_id' in metadata:
                            teacher_id = metadata['teacher_id']
                            print(f"Found teacher_id in metadata: {teacher_id}")
                        elif 'teacherid' in metadata:
                            teacher_id = metadata['teacherid']
                            print(f"Found teacher_id in metadata: {teacher_id}")
                    except Exception as meta_error:
                        print(f"No metadata found or accessible: {meta_error}")
                
            except Exception as e:
                print(f"Could not fetch S3 metadata/tags: {e}")
            
            if teacher_id == 'default_teacher':
                filename = path_parts[-1] if path_parts else file_key
                filename_match = re.match(r'^([a-zA-Z0-9_-]+)_', filename)
                if filename_match:
                    teacher_id = filename_match.group(1)
                    print(f"Extracted teacher_id from filename: {teacher_id}")
            
            print(f"Final teacher_id: {teacher_id}")
            
            return {
                'file_key': file_key,
                'bucket_name': bucket_name,
                'teacher_id': teacher_id
            }
        except Exception as e:
            print(f"Error parsing S3 event: {str(e)}")
            print(f"Full event: {json.dumps(event)}")
            raise Exception(f"Failed to parse S3 event: {str(e)}")
    
    # Case 2: Direct Lambda invocation
    elif 'file_key' in event:
        print("Direct Lambda invocation with JSON object")
        return event
    
    # Case 3: API Gateway proxy event
    elif 'body' in event:
        print("API Gateway proxy event")
        body = event['body']
        
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {'file_key': body}
        else:
            return body
    
    # Case 4: Query string parameters
    elif 'queryStringParameters' in event and event['queryStringParameters']:
        print("API Gateway with query string parameters")
        return event['queryStringParameters']
    
    # Case 5: Direct test event
    elif 'key' in event or 'path' in event:
        print("Direct test event")
        for key in ['file_key', 'key', 'path', 'fileName', 'filename']:
            if key in event:
                return {'file_key': event[key], 'teacher_id': event.get('teacher_id', 'test_teacher')}
    
    else:
        print("Unexpected event structure")
        print(f"Available keys: {list(event.keys())}")
        raise Exception("Could not extract required parameters from event")

def validate_s3_object(bucket_name, file_key):
    """Validate that S3 object exists and is accessible"""
    try:
        print(f"Validating S3 object: s3://{bucket_name}/{file_key}")
        
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket exists: {bucket_name}")
        
        s3_client.head_object(Bucket=bucket_name, Key=file_key)
        print(f"Object exists and is accessible: {file_key}")
        
        response = s3_client.head_object(Bucket=bucket_name, Key=file_key)
        size = response.get('ContentLength', 0)
        if size == 0:
            raise Exception(f"S3 object is empty: {file_key}")
        print(f"Object size: {size} bytes")
        
    except Exception as e:
        raise Exception(f"Failed to validate S3 object: {str(e)}")

def validate_file_type(file_key):
    """Validate supported file types"""
    supported_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'tiff', 'tif', 'txt']
    file_extension = file_key.lower().split('.')[-1]
    
    if file_extension not in supported_extensions:
        raise Exception(f"Unsupported file type: {file_extension}")

def extract_text_from_file(bucket_name, file_key):
    """Extract text from uploaded file using Textract"""
    print(f"Extracting text from: s3://{bucket_name}/{file_key}")
    
    file_extension = file_key.lower().split('.')[-1]
    
    if file_extension in ['pdf']:
        return extract_text_from_pdf(textract_client, bucket_name, file_key)
    elif file_extension in ['jpg', 'jpeg', 'png', 'tiff', 'tif']:
        return extract_text_from_image(textract_client, bucket_name, file_key)
    else:
        return extract_text_directly(bucket_name, file_key)

def extract_text_from_pdf(textract, bucket_name, file_key):
    """Extract text from PDF using Textract"""
    print("Starting Textract PDF processing...")
    
    try:
        response = textract.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': file_key
                }
            }
        )
        
        job_id = response['JobId']
        print(f"Textract PDF job started: {job_id}")
        
        return wait_for_textract_job(textract, job_id)
        
    except Exception as e:
        print(f"Textract PDF processing failed: {str(e)}")
        raise Exception(f"Failed to extract text from PDF: {str(e)}")

def wait_for_textract_job(textract, job_id, max_wait_time=120):
    """Wait for Textract job to complete"""
    print("Waiting for Textract job to complete...")
    
    start_time = time.time()
    checks = 0
    
    while time.time() - start_time < max_wait_time:
        try:
            response = textract.get_document_text_detection(JobId=job_id)
            status = response['JobStatus']
            checks += 1
            
            if status == 'SUCCEEDED':
                print(f"Textract job succeeded after {checks} checks")
                return extract_text_from_textract_response(textract, job_id)
            elif status == 'FAILED':
                error_message = response.get('StatusMessage', 'Unknown error')
                print(f"Textract job failed: {error_message}")
                raise Exception(f"Textract job failed: {error_message}")
            elif status == 'PARTIAL_SUCCESS':
                print(f"Textract job partial success after {checks} checks")
                return extract_text_from_textract_response(textract, job_id)
            else:
                wait_time = min(2 ** (checks // 3), 10)
                print(f"Textract status: {status}, check {checks}, waiting {wait_time}s...")
                time.sleep(wait_time)
                
        except Exception as e:
            if 'Textract job failed' in str(e):
                raise
            print(f"Error checking Textract job status: {str(e)}")
            time.sleep(5)
    
    print(f"Textract job timed out after {max_wait_time} seconds")
    raise Exception("Textract job timed out")

def extract_text_from_textract_response(textract, job_id):
    """Extract text from Textract response"""
    text = ""
    next_token = None
    
    while True:
        if next_token:
            response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
        else:
            response = textract.get_document_text_detection(JobId=job_id)
        
        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                text += block['Text'] + '\n'
        
        next_token = response.get('NextToken')
        if not next_token:
            break
    
    print(f"Extracted {len(text)} characters from Textract")
    return text

def extract_text_from_image(textract, bucket_name, file_key):
    """Extract text from image using Textract"""
    print("Starting Textract image processing...")
    
    try:
        response = textract.detect_document_text(
            Document={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': file_key
                }
            }
        )
        
        text = ""
        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                text += block['Text'] + '\n'
        
        print(f"Extracted {len(text)} characters from image")
        return text
        
    except Exception as e:
        print(f"Textract image processing failed: {str(e)}")
        raise Exception(f"Failed to extract text from image: {str(e)}")

def extract_text_directly(bucket_name, file_key):
    """Extract text directly from text files"""
    try:
        print("Reading text file directly from S3...")
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        content = response['Body'].read().decode('utf-8')
        print(f"Extracted {len(content)} characters")
        return content
        
    except Exception as e:
        print(f"Direct text extraction failed: {str(e)}")
        raise Exception(f"Failed to read text file: {str(e)}")

def extract_questions_smart(assignment_text):
    """Smart question extraction"""
    print("Starting smart question extraction...")
    
    questions = extract_questions_direct(assignment_text)
    
    if len(questions) > 0:
        print(f"Direct extraction found {len(questions)} questions")
        return questions
    
    print("Direct extraction failed, trying with mild cleaning...")
    cleaned_text = clean_text_preserve_content(assignment_text)
    questions = extract_questions_direct(cleaned_text)
    
    if len(questions) > 0:
        print(f"Mild cleaning extraction found {len(questions)} questions")
        return questions
    
    print("Rule-based extraction failed, trying Bedrock...")
    bedrock_questions = try_bedrock_fallback(assignment_text)
    if bedrock_questions:
        return bedrock_questions
    
    print("All methods failed, using basic sentence extraction...")
    return extract_questions_basic(assignment_text)

def extract_questions_direct(text):
    """Direct pattern matching"""
    questions = []
    
    print(f"Analyzing text: {text[:200]}...")
    
    question_pattern1 = r'(?:Question|Problem)\s*(\d+)\s*[:\.]\s*(.+?)(?=(?:Question|Problem)\s*\d+|$)'
    matches1 = re.finditer(question_pattern1, text, re.IGNORECASE | re.DOTALL)
    
    for match in matches1:
        question_num = match.group(1)
        question_text = match.group(2).strip()
        question_text = clean_question_text_gentle(question_text)
        
        if len(question_text) > 10:
            questions.append(create_question_object(question_num, question_text))
    
    if len(questions) < 2:
        question_pattern2 = r'(\d+)\.\s*(.+?)(?=\d+\.|$)'
        matches2 = re.finditer(question_pattern2, text, re.DOTALL)
        
        for match in matches2:
            question_num = match.group(1)
            question_text = match.group(2).strip()
            question_text = clean_question_text_gentle(question_text)
            
            if len(question_text) > 10 and looks_like_question(question_text):
                questions.append(create_question_object(question_num, question_text))
    
    for i, question in enumerate(questions):
        question['question_number'] = str(i + 1)
    
    return questions[:5]

def clean_text_preserve_content(text):
    """Gentle text cleaning"""
    lines = text.split('\n')
    cleaned_lines = []
    
    header_removed = False
    for line in lines:
        line = line.strip()
        if not header_removed and re.match(r'^(MATHEMATICS|ASSIGNMENT|GRADE|CLASS)', line, re.IGNORECASE):
            continue
        elif line:
            cleaned_lines.append(line)
            header_removed = True
    
    text = ' '.join(cleaned_lines)
    text = re.sub(r'x\s*[\^²2]\s*', 'x²', text)
    text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def clean_question_text_gentle(text):
    """Gentle cleaning of question text"""
    text = re.split(r'\b(?:Answer|Solution|Hint)[\s\:]', text, flags=re.IGNORECASE)[0]
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def create_question_object(number, text):
    """Create a question object"""
    question_type = classify_question_type_simple(text)
    return {
        'question_number': str(number),
        'question_text': text,
        'question_type': question_type,
        'suggested_answer': generate_specific_answer(text, question_type),
        'max_score': 10
    }

def looks_like_question(text):
    """Check if text looks like a question"""
    if len(text) < 15 or len(text) > 500:
        return False
    
    text_lower = text.lower()
    question_indicators = [
        'solve', 'calculate', 'find', 'determine', 'explain', 'describe',
        'what', 'how', 'why', 'compute', 'evaluate', 'derive'
    ]
    
    return any(indicator in text_lower for indicator in question_indicators)

def classify_question_type_simple(text):
    """Simple question type classification"""
    text_lower = text.lower()
    
    if any(word in text_lower for word in ['solve', 'calculate', 'find', 'compute']):
        return 'problem_solving'
    elif any(word in text_lower for word in ['explain', 'describe', 'discuss']):
        return 'explanation'
    elif any(word in text_lower for word in ['define', 'what is']):
        return 'definition'
    
    return 'problem_solving'

def try_bedrock_fallback(assignment_text):
    """Bedrock fallback for question extraction"""
    try:
        prompt = f"""
        You are an assistant helping teachers process assignments. 
        Extract all the questions from the following text. 
        Do not answer them — just return a clean, numbered list of the questions exactly as written. 
        The text may include subjects like Math, Science, Literature, or History. 
        Return results in this format:

        1. <question text>
        2. <question text>
        3. <question text>

        Assignment text:
        {assignment_text[:1500]}
        """
        
        body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 700,
                "temperature": 0.2,
                "topP": 0.9
            }
        }
        
        response = bedrock_runtime.invoke_model(
            modelId='amazon.titan-text-lite-v1',
            body=json.dumps(body)
        )
        
        response_body_raw = response['body'].read()
        print(f"Bedrock raw response length: {len(response_body_raw)} bytes")
        
        if not response_body_raw:
            print("Empty response from Bedrock")
            return None
        
        response_body = json.loads(response_body_raw)
        extracted_content = response_body.get('results', [{}])[0].get('outputText', '')
        
        if not extracted_content:
            print("No output text in Bedrock response")
            return None
        
        print(f"Bedrock response: {extracted_content[:200]}...")
        
        return extract_questions_from_bedrock_response(extracted_content, assignment_text)
        
    except Exception as e:
        print(f"Bedrock fallback failed: {e}")
        return None

def extract_questions_from_bedrock_response(bedrock_response, original_text):
    """Extract questions from Bedrock's response"""
    questions = []
    lines = bedrock_response.strip().splitlines()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = re.match(r'^(?:Q(?:uestion)?\s*)?(\d+)[\.\:\-\)]\s*(.+)', line, re.IGNORECASE)
        if match:
            question_num = match.group(1)
            question_text = match.group(2).strip()
            question_text = clean_question_text_gentle(question_text)

            if len(question_text) > 8:
                questions.append(create_question_object(question_num, question_text))

    if not questions:
        sentences = re.split(r'[.!?]', bedrock_response)
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if looks_like_question(sentence) and 10 < len(sentence) < 400:
                questions.append(create_question_object(str(len(questions) + 1), sentence))

    for i, question in enumerate(questions):
        question['question_number'] = str(i + 1)

    return questions[:10]

def extract_questions_basic(text):
    """Basic fallback extraction"""
    print("Using basic sentence extraction...")
    questions = []
    
    if len(text.strip()) < 50:
        print("Text too short, creating test question")
        questions.append({
            'question_number': '1',
            'question_text': 'This is a test assignment question extracted from the text',
            'question_type': 'problem_solving',
            'suggested_answer': 'Provide a clear, detailed, and structured answer.',
            'max_score': 10
        })
        return questions
    
    sentences = re.split(r'[.!?]+', text)
    
    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if (looks_like_question(sentence) and 
            len(sentence) > 20 and 
            len(sentence) < 300 and
            not any(word in sentence.lower() for word in ['mathematics', 'assignment', 'name', 'date', 'grade'])):
            
            if len(questions) >= 5:
                break
                
            questions.append(create_question_object(str(len(questions) + 1), sentence))
    
    if len(questions) == 0:
        print("No questions extracted, creating generic question")
        questions.append({
            'question_number': '1',
            'question_text': 'Analyze and discuss the content provided',
            'question_type': 'problem_solving',
            'suggested_answer': 'Provide a clear, detailed, and structured answer.',
            'max_score': 10
        })
    
    print(f"Basic extraction found {len(questions)} questions")
    return questions

def generate_specific_answer(question_text, question_type):
    """Generate appropriate answers using Bedrock"""
    try:
        prompt = f"""
        You are an expert teacher assistant.
        Answer the following student question clearly, step by step if needed.
        Subject may be math, science, literature, history, or general knowledge.
        Provide a well-structured answer with examples if applicable.
        
        Question: {question_text}
        """
        
        body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 500,
                "temperature": 0.3,
                "topP": 0.9
            }
        }
        
        response = bedrock_runtime.invoke_model(
            modelId='amazon.titan-text-lite-v1',
            body=json.dumps(body)
        )
        
        response_body_raw = response['body'].read()
        
        if not response_body_raw:
            raise Exception("Empty AI response")
        
        response_body = json.loads(response_body_raw)
        answer = response_body.get('results', [{}])[0].get('outputText', '').strip()
        
        if not answer or len(answer) < 10:
            raise Exception("Empty AI answer")
        return answer
    
    except Exception as e:
        print(f"Bedrock answer generation failed: {e}")
        
        templates = {
            'problem_solving': "Identify the correct method or formula. Show step-by-step reasoning and verify the answer.",
            'explanation': "Break down the concept into clear parts. Use simple language and real-life examples where possible.",
            'definition': "Provide a precise definition with essential characteristics and a concrete example.",
            'comparison': "Highlight key similarities and differences, using examples where relevant.",
            'analysis': "Examine causes, effects, and relationships with supporting evidence."
        }
        return templates.get(question_type, "Provide a clear, detailed, and structured answer.")

def process_s3_files(s3_client, bucket_name, source_key, dest_key, answer_key_path, questions, assignment_id):
    """Handle all S3 file operations"""
    try:
        copy_source = {'Bucket': bucket_name, 'Key': source_key}
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=bucket_name,
            Key=dest_key
        )
        print(f"Copied file to processed folder: {dest_key}")
        
        answer_key_content = {
            'assignment_id': assignment_id,
            'generated_at': datetime.now().isoformat(),
            'questions': questions,
            'status': 'pending_review',
            'version': '1.0'
        }
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=answer_key_path,
            Body=json.dumps(answer_key_content, indent=2),
            ContentType='application/json'
        )
        print(f"Created answer key: {answer_key_path}")
        
    except Exception as e:
        print(f"S3 operation failed: {e}")
        raise Exception(f"Failed to process file in S3: {str(e)}")

def store_in_dynamodb(assignment_id, teacher_id, file_key, answer_key_path, questions, subject, class_info):
    """Store assignment data in DynamoDB"""
    table_name = 'Assignments-dev'
    
    try:
        table = dynamodb.Table(table_name)
        
        item = {
            'assignment_id': assignment_id,
            'teacher_id': teacher_id,
            'file_location': file_key,
            'answer_key_location': answer_key_path,
            'questions': questions,
            'subject': subject,
            'class_info': class_info,
            'status': 'pending_review',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        table.put_item(Item=item)
        print(f"Stored assignment {assignment_id} in DynamoDB")
        
    except Exception as e:
        print(f"Error storing in DynamoDB: {str(e)}")

def success_response(assignment_id, questions, bucket_name, processed_file_key, answer_key_path):
    """Return standardized success response"""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'POST,OPTIONS,GET'
        },
        'body': json.dumps({
            'assignment_id': assignment_id,
            'status': 'processed',
            'questions': questions,
            'file_location': f"s3://{bucket_name}/{processed_file_key}",
            'answer_key_location': f"s3://{bucket_name}/{answer_key_path}",
            'bucket_name': bucket_name,
            'message': 'Assignment processed successfully with AI question extraction',
            'processed_at': datetime.now().isoformat(),
            'question_count': len(questions)
        })
    }

def error_response(error_message):
    """Return standardized error response"""
    return {
        'statusCode': 500,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST,OPTIONS,GET',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
        },
        'body': json.dumps({
            'error': 'Assignment processing failed',
            'message': error_message
        })
    }
