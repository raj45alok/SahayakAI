import os
import json
import boto3
import uuid

S3_BUCKET = os.environ.get("RAW_BUCKET", "sahayak-raw-worksheets")
PRESIGNED_EXPIRATION = int(os.environ.get("PRESIGNED_EXPIRATION", "900"))
TABLE_NAME = os.environ.get("WORKSHEETS_TABLE", None)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME) if TABLE_NAME else None

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}")) if "body" in event else event
        worksheet_id = body.get("worksheetId")
        file_name = body.get("fileName")
        content_type = body.get("contentType", "application/pdf")

        if not worksheet_id or not file_name:
            return {"statusCode":400, "body": json.dumps({"error":"worksheetId and fileName required"})}

        # Optional validate worksheet exists
        if table:
            try:
                res = table.get_item(Key={"worksheetId": worksheet_id, "contentId": "NONE"})
                if "Item" not in res:
                    return {"statusCode":404, "body": json.dumps({"error":"worksheetId not found. Run Step1 first."})}
            except Exception as e:
                print("DDB read error:", e)

        content_id = f"CNT-{uuid.uuid4().hex[:8]}"
        key = f"raw-content/{worksheet_id}/{content_id}_{file_name}"

        presigned_url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": S3_BUCKET, "Key": key, "ContentType": content_type},
            ExpiresIn=PRESIGNED_EXPIRATION,
            HttpMethod="PUT"
        )

        return {"statusCode":200, "body": json.dumps({
            "presignedUrl": presigned_url,
            "uploadKey": key,
            "contentId": content_id,
            "expiresIn": PRESIGNED_EXPIRATION
        })}
    except Exception as e:
        print("Error:", str(e))
        return {"statusCode":500, "body": json.dumps({"error":str(e)})}
