import json
import boto3
from datetime import datetime

s3 = boto3.client('s3', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

TABLE_NAME = 'ContentTable'
OUTPUT_BUCKET = 'sahayak-enhancer-output-02'

table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    """
    Generate output files (.txt, .md) and upload to S3
    """
    
    try:
        content_id = event['contentId']
        enhanced = event['enhanced']
        
        print(f"Generating output files for {content_id}")
        
        # Update progress
        table.update_item(
            Key={'contentId': content_id},
            UpdateExpression='SET progress = :p, currentStep = :step',
            ExpressionAttributeValues={
                ':p': 80,
                ':step': 'Generating output files'
            }
        )
        
        # Generate JSON output
        json_content = json.dumps(enhanced, indent=2, ensure_ascii=False)
        txt_key = f"{content_id}/enhanced.txt"
        
        s3.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=txt_key,
            Body=json_content.encode('utf-8'),
            ContentType='text/plain'
        )
        
        # Generate Markdown output
        md_content = generate_markdown(enhanced)
        md_key = f"{content_id}/enhanced.md"
        
        s3.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=md_key,
            Body=md_content.encode('utf-8'),
            ContentType='text/markdown'
        )
        
        print(f"Uploaded files to s3://{OUTPUT_BUCKET}/{content_id}/")
        
        # Return paths for next step
        return {
            'contentId': content_id,
            'enhanced': enhanced,
            's3Paths': {
                'textFile': f"s3://{OUTPUT_BUCKET}/{txt_key}",
                'markdownFile': f"s3://{OUTPUT_BUCKET}/{md_key}"
            },
            **{k: v for k, v in event.items() if k not in ['contentId', 'enhanced', 's3Paths']}
        }
        
    except Exception as e:
        print(f"Error in GenerateText: {str(e)}")
        raise


def generate_markdown(enhanced):
    """Convert enhanced content to Markdown format"""
    
    md = f"# {enhanced.get('title', 'Enhanced Content')}\n\n"
    md += f"**Subject:** {enhanced.get('subject', 'N/A')}\n"
    md += f"**Target Audience:** {enhanced.get('targetAudience', 'N/A')}\n"
    md += f"**Estimated Study Time:** {enhanced.get('estimatedStudyTime', 'N/A')} minutes\n\n"
    md += "---\n\n"
    
    # Summary
    md += f"## Summary\n\n{enhanced.get('summary', '')}\n\n"
    
    # Sections
    for section in enhanced.get('sections', []):
        md += f"## {section.get('heading', 'Section')}\n\n"
        md += f"{section.get('content', '')}\n\n"
    
    # Practice Questions
    if enhanced.get('practiceQuestions'):
        md += "## Practice Questions\n\n"
        for idx, qa in enumerate(enhanced['practiceQuestions'], 1):
            md += f"**Q{idx}:** {qa.get('question', '')}\n\n"
            md += f"<details>\n<summary>Show Answer</summary>\n\n"
            md += f"{qa.get('answer', '')}\n\n</details>\n\n"
    
    return md
