provider "aws" {
  region = "us-east-1"
}

# Fetch the latest Ubuntu 22.04 AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Security group to allow SSH, HTTP, and HTTPS
resource "aws_security_group" "gitlab_sg" {
  name        = "gitlab_sg"
  description = "Allow inbound traffic for GitLab"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# EC2 Instance for GitLab
resource "aws_instance" "gitlab_server" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.medium" # t3.medium is recommended over t2.medium for better CPU credit performance
  key_name      = "rv-usa"    # NOTE: Ensure this key pair exists in your us-east-1 region

  vpc_security_group_ids = [aws_security_group.gitlab_sg.id]

  # Allocate enough storage for GitLab (minimum recommended: 30GB+)
  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  # User data script to install GitLab automatically upon boot
  user_data = <<-EOF
              #!/bin/bash
              # Update packages
              apt-get update -y
              apt-get install -y curl openssh-server ca-certificates tzdata perl
              
              # Add 4GB Swap Space (CRITICAL for 4GB RAM instances like t3.medium to prevent GitLab OOM crashes)
              fallocate -l 4G /swapfile
              chmod 600 /swapfile
              mkswap /swapfile
              swapon /swapfile
              echo '/swapfile none swap sw 0 0' >> /etc/fstab

              # Add GitLab CE repository
              curl -sS https://packages.gitlab.com/install/repositories/gitlab/gitlab-ce/script.deb.sh | bash
              
              # Get the instance's public IP address using IMDSv2 (more secure/reliable than IMDSv1)
              TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
              PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
              
              # Install GitLab CE and set the External URL
              EXTERNAL_URL="http://$PUBLIC_IP" apt-get install -y gitlab-ce
              EOF

  tags = {
    Name = "GitLab-Server"
  }
}

# Wait for GitLab to become fully healthy on Port 80
resource "terraform_data" "wait_for_gitlab" {
  input = aws_instance.gitlab_server.public_ip

  provisioner "local-exec" {
    command = <<EOF
      echo "Waiting for GitLab to become ready on Port 80..."
      until curl -s -f -o /dev/null "http://${aws_instance.gitlab_server.public_ip}"; do
        echo "GitLab is starting up (running user_data)... retrying in 15 seconds..."
        sleep 15
      done
      echo "===================================================="
      echo "Success! GitLab is fully up and running!"
      echo "===================================================="
    EOF
  }
}

# Output the URL to access GitLab
output "gitlab_url" {
  value       = "http://${aws_instance.gitlab_server.public_ip}"
  description = "URL to access the GitLab web interface"
}
