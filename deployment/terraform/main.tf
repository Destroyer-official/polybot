# Polymarket Arbitrage Bot - Terraform Infrastructure
# Deploys EC2 instance with all required AWS resources

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Data sources
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Security Group
resource "aws_security_group" "bot_sg" {
  name        = "${var.project_name}-sg"
  description = "Security group for Polymarket Arbitrage Bot"
  vpc_id      = var.vpc_id

  # SSH access (restrict to your IP in production)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
    description = "SSH access"
  }

  # Prometheus metrics
  ingress {
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = var.prometheus_allowed_cidrs
    description = "Prometheus metrics endpoint"
  }

  # Outbound internet access
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${var.project_name}-sg"
    Project     = var.project_name
    Environment = var.environment
  }
}

# IAM Role for EC2 instance
resource "aws_iam_role" "bot_role" {
  name = "${var.project_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-role"
    Project     = var.project_name
    Environment = var.environment
  }
}

# IAM Policy for Secrets Manager access
resource "aws_iam_policy" "secrets_policy" {
  name        = "${var.project_name}-secrets-policy"
  description = "Allow access to Secrets Manager for bot credentials"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.bot_credentials.arn
      }
    ]
  })
}

# IAM Policy for CloudWatch Logs
resource "aws_iam_policy" "cloudwatch_policy" {
  name        = "${var.project_name}-cloudwatch-policy"
  description = "Allow writing logs to CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "${aws_cloudwatch_log_group.bot_logs.arn}:*"
      }
    ]
  })
}

# IAM Policy for SNS alerts
resource "aws_iam_policy" "sns_policy" {
  name        = "${var.project_name}-sns-policy"
  description = "Allow publishing to SNS topic for alerts"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.bot_alerts.arn
      }
    ]
  })
}

# Attach policies to role
resource "aws_iam_role_policy_attachment" "secrets_attach" {
  role       = aws_iam_role.bot_role.name
  policy_arn = aws_iam_policy.secrets_policy.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch_attach" {
  role       = aws_iam_role.bot_role.name
  policy_arn = aws_iam_policy.cloudwatch_policy.arn
}

resource "aws_iam_role_policy_attachment" "sns_attach" {
  role       = aws_iam_role.bot_role.name
  policy_arn = aws_iam_policy.sns_policy.arn
}

# Instance profile
resource "aws_iam_instance_profile" "bot_profile" {
  name = "${var.project_name}-profile"
  role = aws_iam_role.bot_role.name

  tags = {
    Name        = "${var.project_name}-profile"
    Project     = var.project_name
    Environment = var.environment
  }
}

# Secrets Manager secret for credentials
resource "aws_secretsmanager_secret" "bot_credentials" {
  name        = "${var.project_name}-credentials"
  description = "Private key and API keys for Polymarket Arbitrage Bot"

  tags = {
    Name        = "${var.project_name}-credentials"
    Project     = var.project_name
    Environment = var.environment
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "bot_logs" {
  name              = "/polymarket-arbitrage-bot"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.project_name}-logs"
    Project     = var.project_name
    Environment = var.environment
  }
}

# SNS Topic for alerts
resource "aws_sns_topic" "bot_alerts" {
  name = "${var.project_name}-alerts"

  tags = {
    Name        = "${var.project_name}-alerts"
    Project     = var.project_name
    Environment = var.environment
  }
}

# SNS Topic subscription (email)
resource "aws_sns_topic_subscription" "alert_email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.bot_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# EC2 Instance
resource "aws_instance" "bot" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.bot_sg.id]
  subnet_id              = var.subnet_id
  iam_instance_profile   = aws_iam_instance_profile.bot_profile.name

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    aws_region            = var.aws_region
    secret_name           = aws_secretsmanager_secret.bot_credentials.name
    sns_topic_arn         = aws_sns_topic.bot_alerts.arn
    cloudwatch_log_group  = aws_cloudwatch_log_group.bot_logs.name
    github_repo           = var.github_repo
    github_branch         = var.github_branch
    dry_run               = var.dry_run_mode
  })

  tags = {
    Name        = "${var.project_name}-instance"
    Project     = var.project_name
    Environment = var.environment
  }

  lifecycle {
    ignore_changes = [ami]
  }
}

# Elastic IP (optional, for static IP)
resource "aws_eip" "bot_eip" {
  count    = var.use_elastic_ip ? 1 : 0
  instance = aws_instance.bot.id
  domain   = "vpc"

  tags = {
    Name        = "${var.project_name}-eip"
    Project     = var.project_name
    Environment = var.environment
  }
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.project_name}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors EC2 CPU utilization"
  alarm_actions       = [aws_sns_topic.bot_alerts.arn]

  dimensions = {
    InstanceId = aws_instance.bot.id
  }
}

resource "aws_cloudwatch_metric_alarm" "status_check_failed" {
  alarm_name          = "${var.project_name}-status-check-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = "60"
  statistic           = "Maximum"
  threshold           = "0"
  alarm_description   = "This metric monitors EC2 status checks"
  alarm_actions       = [aws_sns_topic.bot_alerts.arn]

  dimensions = {
    InstanceId = aws_instance.bot.id
  }
}
