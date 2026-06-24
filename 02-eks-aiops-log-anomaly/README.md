# EKS AIOps Log Anomaly Detector

An automated, event-driven log monitoring and anomaly detection engine for Amazon EKS using Fluent Bit, Amazon Kinesis Data Streams, AWS Lambda, AWS Bedrock (`openai.gpt-oss-safeguard-120b`), and Slack.

Troubleshooting application failures in a Kubernetes microservices environment is traditionally slow and manual. This project implements a real-time log ingestion pipeline that automatically filters application error logs, submits stack traces to an AI model for Root Cause Analysis (RCA), and sends actionable remediations directly to Slack.

---

## Ingestion & Analysis Flow

```
[ EKS Worker Nodes ]
         │ (Tails /var/log/containers/*.log via Fluent Bit DaemonSet)
         ▼
[ Amazon Kinesis Data Streams ] (High-throughput buffer)
         │ (Native Event Source Mapping batch triggers)
         ▼
[ AWS Lambda (Python) ] (Filters for ERROR/FATAL logs)
         │ (Submits stack trace to safeguard LLM)
         ▼
[ AWS Bedrock (safeguard LLM) ] (Performs Root Cause Analysis)
         │ (Generates structured remediation markdown)
         ▼
[ Slack Channel (#devops-alerts) ] (Instant, human-readable alert)
```

---

## Directory Structure

```
.
├── README.md                  # Setup & deployment guide
├── kubernetes/
│   └── fluentbit.yaml        # ConfigMap, ClusterRole, and DaemonSet configurations
├── src/
│   └── lambda_function.py    # Python Lambda analyzer and Slack exporter
└── terraform/
    └── eks.tf                # VPC & EKS Cluster Terraform setup
```

---

## Setup & Deployment Guide

### Step 1: Provision EKS Cluster
1. Navigate to the `terraform/` directory:
   ```bash
   cd terraform
   ```
2. Initialize and deploy infrastructure:
   ```bash
   terraform init
   ```
   ```bash
   terraform apply -auto-approve
   ```
   *Note: This creates a new dedicated VPC, NAT Gateways, EKS Control Plane, and worker nodes. It takes approximately 10-15 minutes.*
3. Configure your local `kubectl` context:
   ```bash
   aws eks update-kubeconfig --region us-east-1 --name my-cluster
   ```
4. Verify nodes are online:
   ```bash
   kubectl get nodes
   ```

### Step 2: Create Amazon Kinesis Stream
1. Open the AWS Console and navigate to **Amazon Kinesis**.
2. Create a new Data Stream:
   * **Name**: `eks-logs-stream`
   * **Capacity Mode**: `On-demand`
3. Save the **Kinesis Stream ARN**.

### Step 3: Configure Fluent Bit IAM & Service Account (IRSA)
To allow Fluent Bit pods to write log records securely to Kinesis:
1. Initialize the Service Account with IAM role association:
   ```bash
   eksctl create iamserviceaccount \
     --cluster=my-cluster \
     --region=us-east-1 \
     --name=fluent-bit \
     --namespace=logging \
     --attach-policy-arn=arn:aws:iam::aws:policy/AmazonKinesisFullAccess \
     --approve \
     --role-name=eks-fluentbit-kinesis-role
   ```

### Step 4: Deploy Fluent Bit
1. Deploy the namespace, ConfigMap, ClusterRole permissions, and DaemonSet:
   ```bash
   kubectl apply -f kubernetes/fluentbit.yaml
   ```
2. Verify all pods are running successfully in the `logging` namespace:
   ```bash
   kubectl get pods -n logging
   ```

### Step 5: Configure Slack & AWS Lambda
1. Go to your Slack Workspace and create an **Incoming Webhook** pointing to `#devops-alerts`.
2. Create an AWS Lambda function named `AIOps-Log-Analyzer` running **Python 3.11**.
3. Attach policies to the Lambda execution role:
   * `AmazonKinesisReadOnlyAccess`
   * `AmazonBedrockFullAccess`
4. Set the environment variable:
   * `SLACK_WEBHOOK_URL` = `<your-slack-incoming-webhook-url>`
5. Go to **Triggers -> Add trigger** and select **Kinesis**:
   * **Stream**: `eks-logs-stream`
   * **Batch size**: `100`
6. Paste and deploy the code from `src/lambda_function.py`.

---

## Real-Time Testing

1. Spin up a temporary pod in your EKS cluster to simulate a container crash:
   ```bash
   kubectl run error-generator --image=busybox -i --tty -- sh
   ```
2. Inside the container, run commands that emit database and memory issues to stdout:
   ```bash
   # Simulate Database Auth Failure
   echo "ERROR com.app.DatabaseService: Connection refused to jdbc:postgresql://db:5432/users. Exception: org.postgresql.util.PSQLException: FATAL: password authentication failed for user 'admin'"

   # Simulate JVM Crash
   echo "ERROR java.lang.OutOfMemoryError: Java heap space at com.app.DataProcessor.load(DataProcessor.java:45)"
   ```
3. Open your Slack channel. Within 5-10 seconds, you should receive a formatted message:
   > 🚨 **AIOps Anomaly Detected**
   > * **App/Component**: DataProcessor
   > * **Symptom**: Application crashed due to an OutOfMemoryError in Java heap space.
   > * **Root Cause**: The load function exhausted the allocated heap capacity at line 45.
   > * **Proposed Fix**: Increase the pod memory limit or update `JAVA_OPTS` `-Xmx` sizing in the Deployment spec.

---

## Cleanup
To dismantle resources and avoid ongoing AWS billing:
1. Delete the Lambda function.
2. Delete the Kinesis stream.
3. Clean up the Kubernetes resources:
   ```bash
   kubectl delete namespace logging
   ```
4. Destroy the EKS cluster and VPC via Terraform:
   ```bash
   cd terraform
   terraform destroy -auto-approve
   ```
