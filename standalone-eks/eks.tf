provider "aws" {
  region = "us-east-1"
}

# Filter for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Create a VPC for the EKS Cluster
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "eks-vpc"
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = true # Economical for test/development environments
  enable_dns_hostnames = true

  public_subnet_tags = {
    "kubernetes.io/cluster/my-cluster" = "shared"
    "kubernetes.io/role/elb"             = 1
  }

  private_subnet_tags = {
    "kubernetes.io/cluster/my-cluster" = "shared"
    "kubernetes.io/role/internal-elb"    = 1
  }
}

# Create EKS Cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "my-cluster"
  cluster_version = "1.34"

  cluster_endpoint_public_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    main = {
      name = "node-group"

      instance_types = ["t3.medium"]
      ami_type       = "AL2023_x86_64_STANDARD"

      min_size     = 2
      max_size     = 3
      desired_size = 2
    }
  }

  # Enable IAM Roles for Service Accounts (IRSA)
  enable_irsa = true

  # Enable cluster creator admin permissions (required in EKS module v20+ to allow the creator to access the cluster)
  enable_cluster_creator_admin_permissions = true

  tags = {
    Environment = "dev"
    Terraform   = "true"
  }
}

output "cluster_name" {
  description = "EKS Cluster Name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS Cluster API Endpoint"
  value       = module.eks.cluster_endpoint
}

output "update_kubeconfig" {
  description = "Command to configure kubectl on your management server"
  value       = "aws eks update-kubeconfig --region us-east-1 --name ${module.eks.cluster_name}"
}
