import json
import boto3
from datetime import datetime

# Initialize AWS clients
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

TABLE_NAME = 'ContentTable'
KNOWLEDGE_BASE_ID = 'EQUSJEXPFY'  # Your NCERT KB
MODEL_ID = 'amazon.titan-text-express-v1'

table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    Enhance content using AWS Bedrock
    
    Input:
    {
        "contentId": "CNT-ABC123",
        "extractedText": "...",
        "enhancementType": "Simplify Language",
        "targetAudience": "Elementary Students",
        "instruction": "Add examples",
        "subject": "Mathematics"
    }
    """
    
    try:
        content_id = event['contentId']
        extracted_text = event.get('extractedText', '')
        enhancement_type = event.get('enhancementType', 'Simplify Language')
        target_audience = event.get('targetAudience', 'Elementary Students')
        instruction = event.get('instruction', '')
        subject = event.get('subject', '')
        
        print(f"Enhancing content {content_id} for {target_audience}")
        
        # Update progress
        table.update_item(
            Key={'contentId': content_id},
            UpdateExpression='SET progress = :p, currentStep = :step',
            ExpressionAttributeValues={
                ':p': 50,
                ':step': 'Enhancing content with AI'
            }
        )
        
        # Step 1: Retrieve context from Knowledge Base
        kb_context = ""
        try:
            kb_query = f"{subject}: {extracted_text[:500]}"  # First 500 chars for context
            
            kb_response = bedrock_agent_runtime.retrieve(
                knowledgeBaseId=KNOWLEDGE_BASE_ID,
                retrievalQuery={'text': kb_query},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': 3
                    }
                }
            )
            
            # Concatenate retrieved context
            kb_results = kb_response.get('retrievalResults', [])
            if kb_results:
                kb_context = "\n\n".join([
                    result['content']['text'] 
                    for result in kb_results 
                    if 'content' in result and 'text' in result['content']
                ])
                print(f"Retrieved {len(kb_results)} KB results")
        
        except Exception as kb_error:
            print(f"KB retrieval failed (continuing without): {str(kb_error)}")
            kb_context = ""
        
        # Step 2: Build enhancement prompt
        prompt = build_enhancement_prompt(
            extracted_text=extracted_text,
            enhancement_type=enhancement_type,
            target_audience=target_audience,
            instruction=instruction,
            kb_context=kb_context
        )
        
        # Step 3: Call Bedrock Titan Text
        bedrock_body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 4096,
                "temperature": 0.7,
                "topP": 0.9
            }
        }
        
        bedrock_response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(bedrock_body)
        )
        
        response_body = json.loads(bedrock_response['body'].read())
        enhanced_text = response_body['results'][0]['outputText']
        
        print(f"Generated {len(enhanced_text)} characters of enhanced content")
        
        # Step 4: Parse enhanced content into structured format
        enhanced_data = parse_enhanced_content(enhanced_text, subject, target_audience)
        
        # Update progress
        table.update_item(
            Key={'contentId': content_id},
            UpdateExpression='SET progress = :p, currentStep = :step',
            ExpressionAttributeValues={
                ':p': 70,
                ':step': 'Content enhancement completed'
            }
        )
        
        # Return enhanced content
        return {
            'contentId': content_id,
            'enhanced': enhanced_data,
            **{k: v for k, v in event.items() if k not in ['contentId', 'extractedText', 'enhanced']}
        }
        
    except Exception as e:
        print(f"Error in CallBedrock: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Update status to FAILED
        try:
            table.update_item(
                Key={'contentId': event.get('contentId')},
                UpdateExpression='SET #status = :status, errorMessage = :error',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'FAILED',
                    ':error': str(e)
                }
            )
        except:
            pass
        
        raise


def build_enhancement_prompt(extracted_text, enhancement_type, target_audience, instruction, kb_context):
    """Build prompt for Bedrock"""
    
    prompt = f"""You are an expert educational content enhancer. Your task is to improve the following educational content.

**Target Audience:** {target_audience}
**Enhancement Type:** {enhancement_type}

"""
    
    if kb_context:
        prompt += f"""**Reference Material (NCERT Context):**
{kb_context}

"""
    
    if instruction:
        prompt += f"""**Special Instructions:** {instruction}

"""
    
    prompt += f"""**Original Content:**
{extracted_text[:3000]}

**Your Task:**
1. Create a clear, engaging title
2. Write a brief summary (2-3 sentences)
3. Enhance the content according to the enhancement type
4. Structure it into logical sections with headings
5. Generate 3-5 practice questions with answers
6. Suggest image prompts for visual aids

**Output Format:**
TITLE: [Enhanced title]

SUMMARY: [Brief summary]

SECTIONS:
## [Section 1 Heading]
[Enhanced content...]

## [Section 2 Heading]
[Enhanced content...]

PRACTICE_QUESTIONS:
Q1: [Question]
A1: [Answer]

IMAGE_PROMPTS:
1. [Description of helpful visual/diagram]
2. [Another visual suggestion]

Please enhance this content now:"""
    
    return prompt


def parse_enhanced_content(enhanced_text, subject, target_audience):
    """Parse Bedrock output into structured format"""
    
    # Extract title
    title = "Enhanced Educational Content"
    if "TITLE:" in enhanced_text:
        title_part = enhanced_text.split("TITLE:")[1].split("\n")[0].strip()
        if title_part:
            title = title_part
    
    # Extract summary
    summary = ""
    if "SUMMARY:" in enhanced_text:
        summary_parts = enhanced_text.split("SUMMARY:")[1].split("SECTIONS:")[0].strip()
        summary = summary_parts[:500]
    
    # Extract sections
    sections = []
    if "SECTIONS:" in enhanced_text:
        sections_text = enhanced_text.split("SECTIONS:")[1]
        if "PRACTICE_QUESTIONS:" in sections_text:
            sections_text = sections_text.split("PRACTICE_QUESTIONS:")[0]
        
        # Split by ## headers
        section_parts = sections_text.split("##")
        for idx, part in enumerate(section_parts[1:], 1):  # Skip first empty part
            lines = part.strip().split("\n", 1)
            if len(lines) >= 2:
                sections.append({
                    "heading": lines[0].strip(),
                    "content": lines[1].strip(),
                    "order": idx
                })
    
    # Extract practice questions
    practice_questions = []
    if "PRACTICE_QUESTIONS:" in enhanced_text:
        qa_text = enhanced_text.split("PRACTICE_QUESTIONS:")[1]
        if "IMAGE_PROMPTS:" in qa_text:
            qa_text = qa_text.split("IMAGE_PROMPTS:")[0]
        
        # Parse Q/A pairs
        lines = qa_text.strip().split("\n")
        current_q = None
        for line in lines:
            line = line.strip()
            if line.startswith("Q") and ":" in line:
                current_q = line.split(":", 1)[1].strip()
            elif line.startswith("A") and ":" in line and current_q:
                answer = line.split(":", 1)[1].strip()
                practice_questions.append({
                    "question": current_q,
                    "answer": answer
                })
                current_q = None
    
    # Extract image prompts
    image_prompts = []
    if "IMAGE_PROMPTS:" in enhanced_text:
        img_text = enhanced_text.split("IMAGE_PROMPTS:")[1]
        lines = img_text.strip().split("\n")
        for line in lines[:5]:  # Max 5 images
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                prompt = line.lstrip("0123456789.-) ").strip()
                if prompt:
                    image_prompts.append({"prompt": prompt})
    
    return {
        "title": title,
        "subject": subject,
        "targetAudience": target_audience,
        "summary": summary,
        "sections": sections,
        "practiceQuestions": practice_questions,
        "imagePrompts": image_prompts,
        "estimatedStudyTime": max(10, len(sections) * 15)  # 15 min per section
    }
