import os
import json
import boto3
import uuid
import base64
from datetime import datetime

# Environment
TABLE_NAME = os.environ.get("WORKSHEETS_TABLE", "Worksheets")
RAW_BUCKET = os.environ.get("RAW_BUCKET", "sahayak-raw-worksheets")
RAW_PREFIX = os.environ.get("RAW_PREFIX", "raw-content/")
PROCESSED_PREFIX = os.environ.get("PROCESSED_PREFIX", "processed-content/")

# AWS clients
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)
s3 = boto3.client("s3")
textract = boto3.client("textract")

def _save_raw_file(content_bytes: bytes, content_id: str, file_name: str):
    key = f"{RAW_PREFIX}{content_id}_{file_name}"
    s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=content_bytes)
    return key

def _save_processed_text(text: str, content_id: str):
    key = f"{PROCESSED_PREFIX}{content_id}.txt"
    s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=text.encode("utf-8"))
    return key

def _run_textract_sync(file_bytes: bytes):
    # Synchronous Textract call (works for images + small PDFs)
    resp = textract.detect_document_text(Document={"Bytes": file_bytes})
    lines = [b["Text"] for b in resp.get("Blocks", []) if b.get("BlockType") == "LINE"]
    return "\n".join(lines)

def lambda_handler(event, context):
    try:
        # Parse request body (API Gateway proxy)
        if "body" in event:
            body = json.loads(event["body"])
        else:
            body = event

        # Required: worksheetId created in Step 1
        worksheet_id = body.get("worksheetId")
        if not worksheet_id:
            return {"statusCode": 400, "body": json.dumps({"error": "worksheetId is required"})}

        # Read the existing Worksheet item (it was created in Step1 with contentId="NONE")
        try:
            # we assume the Step1 created item with contentId = "NONE"
            resp = table.get_item(Key={"worksheetId": worksheet_id, "contentId": "NONE"})
            item = resp.get("Item")
            if not item:
                return {"statusCode": 404, "body": json.dumps({"error": "Worksheet not found (expected contentId=NONE)"})}
        except Exception as e:
            print("DDB get_item error:", str(e))
            return {"statusCode": 500, "body": json.dumps({"error": "Error fetching worksheet item"})}

        # Decide mode:
        # 1) fileName + fileContent (base64) => Mode 1
        # 2) pastedText => Mode 3
        # 3) neither => Mode 2 (RAG)
        linked_content_id = None
        raw_s3_key = None
        processed_s3_key = None

        if "fileName" in body and "fileContent" in body:
            # Mode 1 - file upload
            file_name = body["fileName"]
            file_b64 = body["fileContent"]
            try:
                file_bytes = base64.b64decode(file_b64)
            except Exception as e:
                return {"statusCode": 400, "body": json.dumps({"error": "fileContent must be base64-encoded"})}

            # create content id and upload raw
            linked_content_id = f"CNT-{str(uuid.uuid4())[:8]}"
            raw_s3_key = _save_raw_file(file_bytes, linked_content_id, file_name)

            # Textract (synchronous) - good for images and small PDFs
            extracted_text = None
            try:
                extracted_text = _run_textract_sync(file_bytes)
            except Exception as e:
                # Textract sync may fail for very large/complex PDFs.
                print("Textract error (sync):", str(e))
                extracted_text = ""  # continue; teacher can fallback to pastedText

            if extracted_text:
                processed_s3_key = _save_processed_text(extracted_text, linked_content_id)

        elif "pastedText" in body and body.get("pastedText"):
            # Mode 3 - pasted text
            pasted = body.get("pastedText")
            linked_content_id = f"CNT-{str(uuid.uuid4())[:8]}"
            processed_s3_key = _save_processed_text(pasted, linked_content_id)

        else:
            # Mode 2 - RAG (no file, no pastedText)
            linked_content_id = "RAG"

        # Update the Worksheet item (we do NOT change primary key contentId)
        update_expr = "SET linkedContentId = :lc, updatedAt = :u, #st = :s"
        expr_attr_vals = {
            ":lc": linked_content_id,
            ":u": datetime.utcnow().isoformat(),
            ":s": "processing"
        }
        expr_attr_names = {"#st": "status"}

        if raw_s3_key:
            update_expr += ", rawFileS3Path = :raw"
            expr_attr_vals[":raw"] = raw_s3_key
        if processed_s3_key:
            update_expr += ", processedFileS3Path = :proc"
            expr_attr_vals[":proc"] = processed_s3_key

        # perform update on the existing item (Key must match table keys)
        table.update_item(
            Key={"worksheetId": worksheet_id, "contentId": "NONE"},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_vals,
            ExpressionAttributeNames=expr_attr_names
        )

        # return helpful response
        resp_body = {
            "message": "Content processed and linked",
            "worksheetId": worksheet_id,
            "linkedContentId": linked_content_id,
            "rawFileS3Path": raw_s3_key,
            "processedFileS3Path": processed_s3_key,
            "status": "processing"
        }
        return {"statusCode": 200, "body": json.dumps(resp_body)}

    except Exception as e:
        print("Unhandled error:", str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
