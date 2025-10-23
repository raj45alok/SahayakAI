import json
import boto3
import uuid
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Worksheets')

# Premade templates
PREMADE_TEMPLATES = {
    "TEMPLATE_1": {
        "mcq": {"count": 5, "marks": 1},
        "oneWord": {"count": 5, "marks": 1},
        "briefAnswer": {"count": 2, "marks": 5}
    },
    "TEMPLATE_2": {
        "mcq": {"count": 10, "marks": 1},
        "oneWord": {"count": 5, "marks": 1},
        "shortAnswer": {"count": 5, "marks": 2},
        "longAnswer": {"count": 5, "marks": 5}
    },
    "TEMPLATE_3": {
        "mcq": {"count": 10, "marks": 1},
        "oneWord": {"count": 10, "marks": 1},
        "shortAnswer": {"count": 5, "marks": 3},
        "briefAnswer": {"count": 5, "marks": 5},
        "longAnswer": {"count": 2, "marks": 10}
    }
}

def lambda_handler(event, context):
    try:
        # Parse API Gateway event body
        if "body" in event:
            body = json.loads(event["body"])
        else:
            body = event

        # ✅ Required fields
        required_fields = [
            "teacherId", "classId", "subject", "chapter", 
            "topic", "difficulty", "language", "templateType"
        ]
        missing_fields = [f for f in required_fields if f not in body]

        if missing_fields:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Missing fields: {', '.join(missing_fields)}"})
            }

        # ✅ Handle template
        template_type = body["templateType"]
        if template_type in PREMADE_TEMPLATES:
            template = PREMADE_TEMPLATES[template_type]
        elif template_type == "CUSTOM":
            if "template" not in body:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Custom template requires 'template' field"})
                }
            template = body["template"]
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid templateType"})
            }

        # ✅ Generate worksheetId
        worksheet_id = f"WS-{str(uuid.uuid4())[:8]}"

        # ✅ Insert into DynamoDB (always include contentId since it’s Sort Key)
        item = {
            "worksheetId": worksheet_id,
            "contentId": "NONE",   # required because contentId is Sort Key
            "teacherId": body["teacherId"],
            "classId": body["classId"],
            "subject": body["subject"],
            "chapter": body["chapter"],
            "topic": body["topic"],
            "difficulty": body["difficulty"],
            "language": body["language"],
            "templateType": template_type,
            "template": template,
            "status": "processing",
            "createdAt": datetime.utcnow().isoformat()
        }

        table.put_item(Item=item)

        # ✅ Return success
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Worksheet job created",
                "worksheetId": worksheet_id,
                "status": "processing",
                "templateType": template_type,
                "template": template
            })
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
