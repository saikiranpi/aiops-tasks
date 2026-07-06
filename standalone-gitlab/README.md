# Standalone GitLab Deployment

This folder contains the Terraform configuration to deploy a standalone GitLab CE (Community Edition) Server on an EC2 instance in AWS.

## Features

* **Ubuntu 22.04 AMI:** Fetches the latest Canonical Ubuntu 22.04 LTS image dynamically.
* **Instance Sizing:** Deploys on a `t3.medium` instance.
* **Storage:** Allocates 30GB gp3 EBS storage (recommended minimum for GitLab).
* **Automated Installation:** Bootstraps GitLab automatically via User Data, including configuring a 4GB Swap file to prevent Out-Of-Memory (OOM) crashes on 4GB RAM instances.
* **Provisioner Verification:** Automatically waits for GitLab to become fully healthy and accessible on port 80 before completing.

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
