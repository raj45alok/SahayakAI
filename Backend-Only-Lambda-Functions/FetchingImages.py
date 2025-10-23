import json
import boto3
import urllib3
from datetime import datetime

s3 = boto3.client('s3', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

TABLE_NAME = 'ContentTable'
OUTPUT_BUCKET = 'sahayak-enhancer-output-02'
UNSPLASH_API_URL = 'https://source.unsplash.com/800x600/?'

table = dynamodb.Table(TABLE_NAME)
http = urllib3.PoolManager()

def lambda_handler(event, context):
    """
    Fetch images based on prompts and upload to S3
    
    Input:
    {
        "contentId": "CNT-ABC123",
        "enhanced": {
            "imagePrompts": [
                {"prompt": "fraction pizza diagram"}
            ]
        }
    }
    """
    
    try:
        content_id = event['contentId']
        enhanced = event.get('enhanced', {})
        image_prompts = enhanced.get('imagePrompts', [])
        
        print(f"Fetching {len(image_prompts)} images for {content_id}")
        
        # Update progress
        table.update_item(
            Key={'contentId': content_id},
            UpdateExpression='SET progress = :p, currentStep = :step',
            ExpressionAttributeValues={
                ':p': 90,
                ':step': 'Fetching educational images'
            }
        )
        
        image_links = []
        
        for idx, img_prompt in enumerate(image_prompts[:5], 1):  # Max 5 images
            prompt = img_prompt.get('prompt', '')
            if not prompt:
                continue
            
            try:
                # Generate search query from prompt
                search_query = prompt.replace(' ', ',')
                image_url = f"{UNSPLASH_API_URL}{search_query}"
                
                print(f"Fetching image {idx}: {image_url}")
                
                # Download image
                response = http.request('GET', image_url, timeout=10.0, retries=3)
                
                if response.status == 200:
                    # Upload to S3
                    img_key = f"{content_id}/images/img{idx}.jpg"
                    
                    s3.put_object(
                        Bucket=OUTPUT_BUCKET,
                        Key=img_key,
                        Body=response.data,
                        ContentType='image/jpeg'
                    )
                    
                    s3_url = f"s3://{OUTPUT_BUCKET}/{img_key}"
                    
                    image_links.append({
                        'prompt': prompt,
                        'imageUrl': image_url,
                        's3Key': img_key,
                        's3Url': s3_url
                    })
                    
                    print(f"Uploaded image to {s3_url}")
                
            except Exception as img_error:
                print(f"Failed to fetch image {idx}: {str(img_error)}")
                continue
        
        # Update enhanced data with image links
        enhanced['images'] = image_links
        
        print(f"Successfully fetched {len(image_links)} images")
        
        # Return updated enhanced content
        return {
            'contentId': content_id,
            'enhanced': enhanced,
            's3Paths': event.get('s3Paths', {}),
            **{k: v for k, v in event.items() if k not in ['contentId', 'enhanced', 's3Paths']}
        }
        
    except Exception as e:
        print(f"Error in FetchImages: {str(e)}")
        # Non-critical error - continue without images
        return {
            'contentId': event.get('contentId'),
            'enhanced': event.get('enhanced', {}),
            's3Paths': event.get('s3Paths', {}),
            'imageError': str(e)
        }
