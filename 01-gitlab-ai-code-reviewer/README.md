# GitLab AI Code Reviewer Bot

An automated, event-driven GitLab Merge Request code reviewer built with AWS Lambda, AWS API Gateway, and AWS Bedrock (`openai.gpt-oss-safeguard-120b`). 

Every time a developer opens or updates a Merge Request, this bot automatically fetches the code changes (git diff) from GitLab, sends them to AWS Bedrock for analysis, and comments back with a summary verdict (`PASS` or `BLOCK`) detailing security vulnerabilities, performance bottlenecks, and code quality recommendations.

---

## Architecture Diagram

```
[Developer Opens MR] 
         │
         ▼
[GitLab Webhook (POST)] ──► [AWS API Gateway] ──► [AWS Lambda]
                                                      │
                                                      ├─► [Get Code Diff from GitLab API]
                                                      ├─► [Invoke AWS Bedrock (safeguard LLM)]
                                                      └─► [Post Review Comment back to GitLab]
```

---

## Directory Structure

```
.
├── .gitignore
├── README.md
├── src/
│   └── lambda_function.py      # Core Lambda handler and logic
└── terraform/
    └── gitlab.tf               # Terraform config to launch test GitLab EC2 Server
```

---

## Setup & Deployment Guide

### Step 1: GitLab Instance Setup
You can run this bot with either **GitLab.com** or your own **self-hosted GitLab instance**.
If you want to spin up a test self-hosted GitLab server in AWS using Terraform:
1. Navigate to the `terraform/` directory:
   ```bash
   cd terraform
   ```
2. Run Terraform init and apply:
   ```bash
   terraform init
   ```
   ```bash
   terraform apply -auto-approve
   ```
3. Retrieve your initial root password by SSHing into the newly created EC2 instance:
   ```bash
   ssh -i /path/to/your-key.pem ubuntu@<GITLAB_PUBLIC_IP> "sudo cat /etc/gitlab/initial_root_password"
   ```

### Step 2: Configure GitLab Project
1. Create a GitLab repository/project (e.g., `finance-api-service`).
2. Go to **Settings -> Access Tokens** to generate a **Project Access Token**:
   - **Name**: `aws-ai-bot-token`
   - **Role**: `Maintainer`
   - **Scopes**: `api`, `read_repository`, `write_repository`
3. Save the token value and note your **Project ID** from the project's homepage.

### Step 3: Create the AWS Lambda Execution Role
Create an IAM execution role for the Lambda function containing the following policies:
- `AWSLambdaBasicExecutionRole` (for writing CloudWatch logs)
- `AmazonBedrockFullAccess` (to allow calling the bedrock models)

### Step 4: Deploy the AWS Lambda Function
1. Create a Lambda function with **Python 3.11** as the runtime.
2. Select the execution role created in the previous step.
3. In the Lambda **Configuration -> Environment Variables**, add:
   - `GITLAB_TOKEN`: Your project access token.
   - `GITLAB_PROJECT_ID`: Your GitLab Project ID.
   - `WEBHOOK_SECRET`: A secret string of your choice (e.g. `super-secret-string-123`).
4. Paste the Python code from `src/lambda_function.py` into `lambda_function.py` in the Lambda editor and click **Deploy**.
5. Adjust the function's timeout to **1 minute** (Bedrock reviews may take 10-20 seconds to complete).

### Step 5: Expose Lambda via AWS API Gateway
1. Create an **HTTP API** in API Gateway.
2. Add a **Lambda integration** pointing to your `GitLab-AI-Code-Reviewer` function.
3. Configure the route:
   - **Method**: `POST`
   - **Path**: `/webhook`
4. Deploy the API and note the final **Invoke URL** (e.g., `https://<api-id>.execute-api.us-east-1.amazonaws.com/webhook`).

### Step 6: Connect Webhook in GitLab
1. In your GitLab project, go to **Settings -> Webhooks**.
2. Click **Add new webhook**:
   - **URL**: Paste your API Gateway Invoke URL.
   - **Secret token**: Use the same `WEBHOOK_SECRET` string set in the Lambda environment variables.
   - **Trigger**: Uncheck "Push events", check **"Merge request events"**.
3. Save changes. You can test the integration by clicking **Test -> Merge request events**.

---

## Licensing & Contributions
This project is open-source. Feel free to open issues and pull requests to improve the reviewer prompts or extend platform support.
