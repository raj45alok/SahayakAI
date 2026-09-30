import json
import boto3
import re
import os
import time
from datetime import datetime

# Initialize clients
s3 = boto3.client('s3')
textract = boto3.client('textract')
dynamodb = boto3.resource('dynamodb')

# Environment variables
RAW_BUCKET = os.environ.get('RAW_BUCKET', 'sahayak-raw-worksheets')
WORKSHEETS_TABLE = os.environ.get('WORKSHEETS_TABLE', 'Worksheets')
PROCESSED_PREFIX = os.environ.get('PROCESSED_PREFIX', 'processed-content/')

table = dynamodb.Table(WORKSHEETS_TABLE)

def extract_text_from_pdf(bucket, key):
    """Try both DetectDocumentText and S3-based StartDocumentTextDetection"""
    print(f"Attempting Textract for s3://{bucket}/{key}")
    text = ""

    try:
        # First, try direct detect_document_text (for small PDFs)
        response = textract.detect_document_text(
            Document={"S3Object": {"Bucket": bucket, "Name": key}}
        )
        text = " ".join(
            [blk["Text"] for blk in response["Blocks"] if blk["BlockType"] == "LINE"]
        )
        print(f"Direct Textract succeeded with {len(text)} chars")
        return text
    except Exception as e:
        print(f"Direct Textract failed: {e}. Trying async mode...")

    # Async Textract for larger PDFs
    try:
        job = textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
        )
        job_id = job["JobId"]
        print(f"Started Textract job: {job_id}")

        for _ in range(20):  # Wait up to ~100 seconds
            job_status = textract.get_document_text_detection(JobId=job_id)
            status = job_status["JobStatus"]
            print(f"Job status: {status}")
            if status == "SUCCEEDED":
                blocks = job_status.get("Blocks", [])
                text = " ".join(
                    [blk["Text"] for blk in blocks if blk["BlockType"] == "LINE"]
                )
                print(f"Async Textract succeeded with {len(text)} chars")
                return text
            elif status == "FAILED":
                raise Exception("Textract job failed")
            time.sleep(5)

        raise Exception("Textract job timed out")

    except Exception as e:
        print(f"Textract async failed: {e}")
        return ""

def lambda_handler(event, context):
    print("=== ProcessUploadedWorksheetFunction invoked ===")
    print(json.dumps(event, indent=2))

    try:
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        print(f"S3 event for: {bucket} {key}")

        # Extract worksheet ID and content ID
        match = re.search(r"raw-content/(WS-[^/]+)/([^_]+)", key)
        if not match:
            print("Invalid key structure, skipping.")
            return

        worksheet_id = match.group(1)
        content_id = match.group(2)
        print(f"Worksheet: {worksheet_id}, Content: {content_id}")

        # Extract text
        text = extract_text_from_pdf(bucket, key)

        # Store extracted text to processed-content/
        processed_key = f"{PROCESSED_PREFIX}{worksheet_id}/{content_id}_text.txt"
        s3.put_object(
            Bucket=bucket,
            Key=processed_key,
            Body=text.encode("utf-8"),
            ContentType="text/plain"
        )
        print(f"Extracted text saved to s3://{bucket}/{processed_key}")

        # Update DynamoDB
        now = datetime.utcnow().isoformat()
        table.update_item(
            Key={"worksheetId": worksheet_id},
            UpdateExpression="SET linkedContentId = :c, processedAt = :t",
            ExpressionAttributeValues={":c": content_id, ":t": now}
        )
        print(f"Updated worksheet {worksheet_id} -> linkedContentId {content_id}")

    except Exception as e:
        print(f"Lambda error: {e}")
        raise
