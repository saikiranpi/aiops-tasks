# Standalone EKS Deployment

This folder contains the Terraform configuration to deploy a standalone Amazon EKS cluster in AWS.

## Architecture

* **VPC:** Custom VPC with 3 public subnets and 3 private subnets.
* **NAT Gateway:** A single NAT Gateway for private subnets (economical for dev/test).
* **EKS Cluster:** Managed Kubernetes cluster (v1.34) with a managed node group containing `t3.medium` instances.
* **IAM Roles for Service Accounts (IRSA):** Enabled to allow Kubernetes service accounts to associate directly with AWS IAM roles.

## Usage

1. Initialize Terraform:
   ```bash
   terraform init
   ```
2. Plan the deployment:
   ```bash
   terraform plan
   ```
3. Apply the changes:
   ```bash
   terraform apply --auto-approve
   ```
