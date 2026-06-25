# MLOps Pipeline: SageMaker → EKS via ArgoCD

A production-grade, GitOps-driven MLOps project that automates machine learning model training on AWS SageMaker and continuous deployment to Amazon EKS using ArgoCD and GitLab CI.

---

## Ingestion & Analysis Flow

```
GitLab Repo 1 (Code) ──► GitLab CI (triggers SageMaker training job)
                              │
                              ▼
                       AWS SageMaker (Trains model, outputs model.tar.gz to S3)
                              │
                              ▼
                       GitLab CI (Downloads model, builds Docker image, pushes to ECR)
                              │
                              ▼
                       GitLab CI (Commits updated image tag to GitLab Repo 2)
                              │
                              ▼
                       ArgoCD (Detects Git commit in Repo 2)
                              │
                              ▼
                       Amazon EKS (Pulls ECR image, rolling updates Model API pods)
```

---

## Directory Structure

This directory contains the code templates needed to set up both GitLab repositories:

```
.
├── README.md                  # Setup & deployment guide
├── argocd-app.yaml            # ArgoCD Application manifest
├── gitlab-ci-pipeline/        # Contents for GitLab Repo 1 (Source & Pipeline)
│   ├── .gitlab-ci.yml         # GitLab CI/CD Pipeline
│   ├── app.py                 # Flask Model Prediction API
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile             # Container image configuration
│   └── scripts/
│       └── run_sagemaker_job.py # Python script orchestrating SageMaker
└── gitops-manifests/          # Contents for GitLab Repo 2 (Kubernetes Manifests)
    ├── deployment.yaml        # K8s Deployment template
    └── kustomization.yaml     # Kustomize image tag patcher
```

---

## Setup & Deployment Guide

### Step 1: Provision Infrastructure
If you haven't set up the self-hosted GitLab server and EKS Cluster, you can use the Terraform setup in the `Infra-Terraform` directory:
1. Navigate to the `Infra-Terraform/` directory:
   ```bash
   cd Infra-Terraform
   ```
2. Initialize and apply the Terraform configuration:
   ```bash
   terraform init
   terraform apply -auto-approve
   ```
3. Configure `kubectl` to access your new cluster:
   ```bash
   aws eks update-kubeconfig --region ap-south-1 --name my-cluster
   ```

### Step 2: AWS Configuration (IAM, S3, ECR)
1. Create an S3 bucket named `mlops-training-data-2026` in the AWS console.
2. Create a private ECR repository named `mlops-fraud-model`.
3. Create an IAM Role named `SageMaker-ExecutionRole` for the SageMaker service with `AmazonS3FullAccess` and trust relationships. Note the Role ARN.
4. Create an IAM User `gitlab-ci-user` with programmatic access. Attach the policies `AmazonSageMakerFullAccess`, `AmazonEC2ContainerRegistryPowerUser`, and `AmazonS3FullAccess`. Save the Access Key and Secret Key.

### Step 3: GitLab Runner Setup
1. SSH into the GitLab EC2 instance, install Docker, and register the runner:
   ```bash
   sudo apt-get update -y && sudo apt-get install -y docker.io gitlab-runner
   sudo usermod -aG docker gitlab-runner
   sudo gitlab-runner register
   ```
2. Provide the instance URL and Registration token from GitLab UI project runner settings.
3. In `/etc/gitlab-runner/config.toml`, configure `privileged = true` under `[runners.docker]`. Restart the runner:
   ```bash
   sudo systemctl restart gitlab-runner
   ```
4. Enable **"Run untagged jobs"** under project runner settings in the GitLab UI.

### Step 4: Configure Repository 1 (Model Code & Pipeline)
1. Create a GitLab repository for your model source code (e.g., `mlops-code`).
2. Push all files inside [gitlab-ci-pipeline/](./gitlab-ci-pipeline) directly to the root of this repository.
3. Set the following CI/CD environment variables in GitLab settings (**Settings -> CI/CD -> Variables**):
   - `AWS_ACCESS_KEY_ID`: Access Key for the `gitlab-ci-user`
   - `AWS_SECRET_ACCESS_KEY`: Secret Key for the `gitlab-ci-user`
   - `AWS_DEFAULT_REGION`: `ap-south-1`
   - `SAGEMAKER_ROLE_ARN`: The ARN of the `SageMaker-ExecutionRole`
   - `S3_BUCKET`: `mlops-training-data-2026`
   - `GITOPS_TOKEN`: A GitLab Project Access Token with `write_repository` permission for the manifests repository (Repo 2)

### Step 5: Configure Repository 2 (GitOps Manifests)
1. Create a second GitLab repository (e.g., `mlops-manifests`).
2. Push all files inside [gitops-manifests/](./gitops-manifests) directly to the root of this repository.

### Step 6: Set up ArgoCD
1. Install ArgoCD on the EKS cluster:
   ```bash
   kubectl create namespace argocd
   kubectl apply -n argocd --server-side --force-conflicts -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   ```
2. Apply the application tracking manifest:
   ```bash
   kubectl apply -f argocd-app.yaml
   ```

### Step 7: Testing the Pipeline
1. Make a small code change to `app.py` in Repo 1 and run `git push`.
2. Watch the GitLab CI pipeline run:
   - **Train**: Triggers SageMaker training, waits for completion, and downloads the trained `fraud_model.pkl`.
   - **Build**: Packages the prediction app and model file, builds the Docker image, and pushes it to ECR.
   - **Update Manifests**: Updates the image tag inside `kustomization.yaml` in Repo 2.
3. Verify that ArgoCD detects the change and triggers a rolling update in EKS:
   ```bash
   kubectl get pods -n ml-workloads -w
   ```
4. Test the prediction endpoint:
   ```bash
   kubectl port-forward deployment/fraud-model-api 8080:8080 -n ml-workloads
   curl -X POST http://localhost:8080/predict -H "Content-Type: application/json" -d '{"features": [1.0, 1.0]}'
   ```
