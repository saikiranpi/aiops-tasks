import os
import time
import tarfile
import boto3

# Configuration from env vars
region = os.environ.get('AWS_REGION', 'ap-south-1')
bucket_name = os.environ.get('S3_BUCKET', 'mlops-training-data-2026')
role_arn = os.environ.get('SAGEMAKER_ROLE_ARN')
instance_type = os.environ.get('SAGEMAKER_INSTANCE_TYPE', 'ml.m5.large')

print("--- SageMaker Training Configuration ---")
print(f"AWS Region: {region}")
print(f"S3 Bucket: {bucket_name}")
print(f"SageMaker Role ARN: {role_arn}")
print(f"SageMaker Instance Type: {instance_type}")
print("-----------------------------------------")

if not role_arn:
    raise ValueError("SAGEMAKER_ROLE_ARN environment variable is required.")

s3 = boto3.client('s3', region_name=region)
sagemaker = boto3.client('sagemaker', region_name=region)

# Ensure local directories exist
os.makedirs('scripts', exist_ok=True)
os.makedirs('model', exist_ok=True)

# 1. Create a dummy training script 'train.py'
train_code = """import os
import pickle
from sklearn.ensemble import RandomForestClassifier

if __name__ == '__main__':
    # Train dummy model
    model = RandomForestClassifier()
    model.fit([[0, 0], [1, 1]], [0, 1])
    
    # Save output to SageMaker's standard model directory
    model_dir = os.environ.get('SM_MODEL_DIR', '/opt/ml/model')
    model_path = os.path.join(model_dir, 'fraud_model.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print("Dummy training completed successfully.")
"""

with open('scripts/train.py', 'w') as f:
    f.write(train_code)

# 2. Package train.py into sourcedir.tar.gz
print("Packaging training script...")
with tarfile.open('scripts/sourcedir.tar.gz', 'w:gz') as tar:
    tar.add('scripts/train.py', arcname='train.py')

# 3. Upload sourcedir.tar.gz to S3
print(f"Uploading training package to s3://{bucket_name}/source/sourcedir.tar.gz ...")
s3.upload_file('scripts/sourcedir.tar.gz', bucket_name, 'source/sourcedir.tar.gz')

# 4. Trigger SageMaker Training Job
job_name = f"mlops-fraud-training-{int(time.time())}"
image_uri = f"683313688378.dkr.ecr.{region}.amazonaws.com/sagemaker-scikit-learn:0.23-1-cpu-py3"

print(f"Starting SageMaker Training Job: {job_name} ...")
sagemaker.create_training_job(
    TrainingJobName=job_name,
    AlgorithmSpecification={
        'TrainingImage': image_uri,
        'TrainingInputMode': 'File'
    },
    RoleArn=role_arn,
    OutputDataConfig={
        'S3OutputPath': f"s3://{bucket_name}/output"
    },
    ResourceConfig={
        'InstanceType': instance_type,
        'InstanceCount': 1,
        'VolumeSizeInGB': 5
    },
    StoppingCondition={
        'MaxRuntimeInSeconds': 1200
    },
    HyperParameters={
        'sagemaker_submit_directory': f'"s3://{bucket_name}/source/sourcedir.tar.gz"',
        'sagemaker_program': '"train.py"',
        'sagemaker_region': f'"{region}"'
    }
)

# 5. Poll training job status
while True:
    status_response = sagemaker.describe_training_job(TrainingJobName=job_name)
    status = status_response['TrainingJobStatus']
    print(f"Training status: {status}")
    if status in ['Completed', 'Failed', 'Stopped']:
        break
    time.sleep(30)

if status != 'Completed':
    failure_reason = status_response.get('FailureReason', 'Unknown error')
    raise RuntimeError(f"SageMaker Training Job failed: {failure_reason}")

# 6. Download model.tar.gz from S3
s3_model_path = f"output/{job_name}/output/model.tar.gz"
local_model_tar = "model.tar.gz"
print(f"Downloading trained model from s3://{bucket_name}/{s3_model_path} ...")
s3.download_file(bucket_name, s3_model_path, local_model_tar)

# 7. Extract fraud_model.pkl
print("Extracting fraud_model.pkl ...")
with tarfile.open(local_model_tar, 'r:gz') as tar:
    tar.extract('fraud_model.pkl', path='model')

print("SageMaker training orchestrator finished successfully! Model saved at model/fraud_model.pkl")
