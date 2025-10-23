import os, json, boto3, uuid
from datetime import datetime

RAW_BUCKET = os.environ.get("RAW_BUCKET", "sahayak-raw-worksheets")
PROCESSED_PREFIX = os.environ.get("PROCESSED_PREFIX", "processed-content/")
TABLE_NAME = os.environ.get("WORKSHEETS_TABLE", "Worksheets")

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def _save_processed_text(content, worksheet_id, content_id):
    key = f"{PROCESSED_PREFIX}{worksheet_id}/{content_id}.txt"
    s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=content.encode("utf-8"))
    return f"s3://{RAW_BUCKET}/{key}"

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body","{}")) if "body" in event else event
        worksheet_id = body.get("worksheetId")
        pasted = body.get("pastedText")
        mode = "RAG" if (not pasted) else "PASTED"

        if not worksheet_id:
            return {"statusCode":400, "body": json.dumps({"error":"worksheetId required"})}

        if mode == "PASTED":
            content_id = f"CNT-{uuid.uuid4().hex[:8]}"
            processed_s3 = _save_processed_text(pasted, worksheet_id, content_id)
            table.update_item(
                Key={"worksheetId": worksheet_id, "contentId": "NONE"},
                UpdateExpression="SET linkedContentId = :lc, processedFileS3Path = :proc, updatedAt = :u, #st = :s",
                ExpressionAttributeValues={":lc": content_id, ":proc": processed_s3, ":u": datetime.utcnow().isoformat(), ":s": "ready_for_generation"},
                ExpressionAttributeNames={"#st":"status"}
            )
            return {"statusCode":200, "body": json.dumps({"message":"Pasted text saved","linkedContentId":content_id,"processedFileS3": processed_s3})}

        else:
            # RAG mode
            table.update_item(
                Key={"worksheetId": worksheet_id, "contentId": "NONE"},
                UpdateExpression="SET linkedContentId = :lc, updatedAt = :u, #st = :s",
                ExpressionAttributeValues={":lc":"RAG", ":u": datetime.utcnow().isoformat(), ":s": "ready_for_generation"},
                ExpressionAttributeNames={"#st":"status"}
            )
            return {"statusCode":200, "body": json.dumps({"message":"Marked as RAG","linkedContentId":"RAG"})}

    except Exception as e:
        print("Error:", str(e))
        return {"statusCode":500, "body": json.dumps({"error":str(e)})}
