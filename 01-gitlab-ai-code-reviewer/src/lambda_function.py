import json
import os
import urllib.request
import urllib.parse
import boto3
import re

# Initialize Bedrock Client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def get_mr_diff(gitlab_url, project_id, mr_iid, token):
    """
    Fetches the actual code changes (diff) from GitLab.
    """
    url = f"{gitlab_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes"
    req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            changes = data.get('changes', [])
            diff_text = ""
            for change in changes:
                diff_text += f"File: {change['new_path']}\n"
                diff_text += f"Diff:\n{change['diff']}\n\n"
            return diff_text
    except Exception as e:
        print(f"Error fetching diff: {e}")
        return None

def analyze_code_with_bedrock(diff_text):
    """
    Sends the diff to AWS Bedrock (openai.gpt-oss-safeguard-120b) for review.
    """
    prompt = f"""
    You are a Senior Staff Security and Software Engineer. Review the following code diff.
    Look for:
    1. Security vulnerabilities (SQLi, XSS, hardcoded secrets)
    2. Performance bottlenecks
    3. Bad practices
    
    If there is a severe security issue, start your response EXACTLY with: "[VERDICT: BLOCK]"
    Otherwise, start with: "[VERDICT: PASS]"
    
    Format your review nicely in Markdown.
    
    Code Diff:
    {diff_text}
    """
    
    payload = {
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = bedrock.invoke_model(
            modelId='openai.gpt-oss-safeguard-120b',
            body=json.dumps(payload),
            contentType='application/json'
        )
        body = json.loads(response['body'].read().decode())
        rca_text = body['choices'][0]['message']['content']
        rca_text = re.sub(r'<reasoning>.*?</reasoning>', '', rca_text, flags=re.DOTALL).strip()
        return rca_text.lstrip(': \n')
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"Error calling Bedrock: {error_msg}")
        return f"Error analyzing code: {error_msg}"

def post_gitlab_comment(gitlab_url, project_id, mr_iid, token, comment):
    """
    Posts the AI's review back to the GitLab Merge Request notes.
    """
    url = f"{gitlab_url}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes"
    data = json.dumps({"body": comment}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={
        "PRIVATE-TOKEN": token,
        "Content-Type": "application/json"
    })
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Error posting comment: {e}")

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    
    # Verify Webhook Secret
    headers = event.get('headers', {})
    gitlab_token_header = headers.get('x-gitlab-token')
    if gitlab_token_header != os.environ.get('WEBHOOK_SECRET'):
        return {"statusCode": 403, "body": "Unauthorized: Invalid Secret"}
    
    body = json.loads(event.get('body', '{}'))
    
    # Only process Merge Request open/reopen/update actions
    if body.get('object_kind') != 'merge_request':
        return {"statusCode": 200, "body": "Ignored non-MR event"}
        
    action = body['object_attributes'].get('action')
    if action not in ['open', 'reopen', 'update']:
        return {"statusCode": 200, "body": f"Ignored action: {action}"}
        
    mr_iid = body['object_attributes']['iid']
    project_id = os.environ['GITLAB_PROJECT_ID']
    token = os.environ['GITLAB_TOKEN']
    
    # Extract GitLab instance URL dynamic header
    gitlab_url = headers.get('x-gitlab-instance', 'https://gitlab.com')
    
    # 1. Fetch the code diff
    diff_text = get_mr_diff(gitlab_url, project_id, mr_iid, token)
    if not diff_text:
        return {"statusCode": 500, "body": "Failed to fetch diff"}
        
    if len(diff_text) < 10:
        return {"statusCode": 200, "body": "Diff too small, ignoring."}
        
    # 2. Invoke Bedrock to analyze code
    review_comment = analyze_code_with_bedrock(diff_text)
    
    # 3. Post the review as an MR comment
    final_comment = f"🤖 **AI Code Review (openai.gpt-oss-safeguard-120b)**\n\n{review_comment}"
    post_gitlab_comment(gitlab_url, project_id, mr_iid, token, final_comment)
    
    return {"statusCode": 200, "body": "Review completed successfully"}
