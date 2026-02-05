# Terraform Variables for Polymarket Arbitrage Bot

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "polymarket-arbitrage-bot"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "instance_type" {
  description = "EC2 instance type (t3.micro for testing, c7i.large for production)"
  type        = string
  default     = "t3.micro"
  
  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium", "c7i.large", "c7i.xlarge"], var.instance_type)
    error_message = "Instance type must be one of: t3.micro, t3.small, t3.medium, c7i.large, c7i.xlarge"
  }
}

variable "key_pair_name" {
  description = "Name of the EC2 key pair for SSH access"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where resources will be created"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for EC2 instance"
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "CIDR blocks allowed to SSH to the instance"
  type        = list(string)
  default     = ["0.0.0.0/0"] # Restrict this in production!
}

variable "prometheus_allowed_cidrs" {
  description = "CIDR blocks allowed to access Prometheus metrics"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "root_volume_size" {
  description = "Size of root EBS volume in GB"
  type        = number
  default     = 20
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "alert_email" {
  description = "Email address for SNS alerts"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository URL for bot code"
  type        = string
  default     = "https://github.com/yourusername/polymarket-arbitrage-bot.git"
}

variable "github_branch" {
  description = "GitHub branch to deploy"
  type        = string
  default     = "main"
}

variable "dry_run_mode" {
  description = "Run bot in dry-run mode (no real trades)"
  type        = bool
  default     = true
}

variable "use_elastic_ip" {
  description = "Allocate an Elastic IP for the instance"
  type        = bool
  default     = false
}
