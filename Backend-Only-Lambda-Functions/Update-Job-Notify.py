import os, boto3, json, datetime
dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')
ses = boto3.client('ses', region_name='us-east-1')

CONTENT_TABLE = os.environ['CONTENT_TABLE']
OUT_BUCKET = os.environ['OUTPUT_BUCKET']
FROM_EMAIL = os.environ.get('FROM_EMAIL')
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL')

def lambda_handler(event, context):
    contentId = event.get('contentId')
    classSubject = event.get('classSubject') or event.get('class','unknown') or 'unknown'
    enhancedS3Path = event.get('enhancedTextS3Path', event.get('enhancedS3Path',''))
    assets = event.get('assets', [])
    now = datetime.datetime.utcnow().isoformat() + "Z"
    dynamodb.update_item(
        TableName=CONTENT_TABLE,
        Key={'contentId':{'S':contentId}, 'classSubject':{'S':classSubject}},
        UpdateExpression="SET enhancedTextS3Path=:p, enhancedAssets=:a, #s=:st, updatedAt=:u",
        ExpressionAttributeNames={'#s':'status'},
        ExpressionAttributeValues={':p':{'S':enhancedS3Path}, ':a':{'S': json.dumps(assets)}, ':st':{'S':'DELIVERED'}, ':u':{'S':now}}
    )
    url = None
    if enhancedS3Path.startswith("s3://"):
        parts = enhancedS3Path.replace("s3://","").split("/",1)
        bucket = parts[0]; key = parts[1]
        url = s3.generate_presigned_url('get_object', Params={'Bucket':bucket,'Key':key}, ExpiresIn=3600)
    if url and FROM_EMAIL and NOTIFY_EMAIL:
        try:
            ses.send_email(Source=FROM_EMAIL, Destination={'ToAddresses':[NOTIFY_EMAIL]}, Message={'Subject': {'Data': f'Enhanced content ready — {contentId}'}, 'Body': {'Text': {'Data': f'Your enhanced content is ready. Download: {url}'}}})
        except Exception:
            pass
    return {"status":"OK","contentId":contentId}
