import base64
import json
import urllib.request
import os
import boto3
import re

# Initialize AWS Bedrock runtime client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def lambda_handler(event, context):
    error_logs = []
    
    # 1. Decode Kinesis Records
    for record in event['Records']:
        payload = base64.b64decode(record['kinesis']['data']).decode('utf-8')
        try:
            log_entry = json.loads(payload)
            log_msg = log_entry.get('log', '').upper()
            
            # Filter only for errors/exceptions to minimize token usage and save Bedrock costs
            if 'ERROR' in log_msg or 'EXCEPTION' in log_msg or 'FATAL' in log_msg:
                error_logs.append(log_entry['log'])
        except Exception:
            pass

    if not error_logs:
        return {"statusCode": 200, "body": "No errors found in batch."}

    # 2. Ask Bedrock for Root Cause Analysis (RCA)
    # Send up to the last 20 error lines to stay within prompt efficiency boundaries
    logs_text = "\n".join(error_logs[-20:])
    prompt = f"""
    You are an Expert DevOps SRE. Look at the following Kubernetes error logs.
    Provide a highly concise 4-line summary of the issue.
    Format your final response EXACTLY like this (with no other text, introduction, reasoning blocks, or greeting):
    
    *App/Component:* <service name that failed>
    *Symptom:* <short symptom description in 1 sentence>
    *Root Cause:* <likely reason in 1 sentence>
    *Proposed Fix:* <direct remediation command or action in 1 sentence>
    
    Logs:
    {logs_text}
    """
    
    # Prepare payload for openai.gpt-oss-safeguard-120b (OpenAI-compatible schema)
    body = {
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    try:
        response = bedrock.invoke_model(
            modelId='openai.gpt-oss-safeguard-120b',
            body=json.dumps(body),
            contentType='application/json'
        )
        
        response_data = json.loads(response['body'].read().decode())
        rca_text = response_data['choices'][0]['message']['content']
        
        # Clean up any potential reasoning/thought blocks returned by the model
        rca_text = re.sub(r'<reasoning>.*?</reasoning>', '', rca_text, flags=re.DOTALL).strip()
        rca_text = rca_text.lstrip(': \n')
        
    except Exception as e:
        rca_text = f"Failed to perform Bedrock RCA. Error: {str(e)}"

    # 3. Send Alert to Slack Webhook
    slack_payload = {
        "text": f"🚨 *AIOps Anomaly Detected*\n\n{rca_text}"
    }
    
    try:
        req = urllib.request.Request(
            os.environ['SLACK_WEBHOOK_URL'],
            data=json.dumps(slack_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Error sending message to Slack: {e}")
        return {"statusCode": 500, "body": f"Failed to send Slack alert. Error: {str(e)}"}
    
    return {"statusCode": 200, "body": "Alert Sent"}
