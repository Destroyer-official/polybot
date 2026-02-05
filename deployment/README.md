# Deployment Guide

This directory contains infrastructure-as-code templates for deploying the Polymarket Arbitrage Bot to AWS.

## Deployment Options

Choose one of the following deployment methods:

1. **Terraform** - Recommended for infrastructure management and version control
2. **CloudFormation** - Native AWS solution, good for AWS-centric workflows

## Prerequisites

- AWS account with appropriate permissions
- AWS CLI configured with credentials
- SSH key pair created in AWS EC2
- (For Terraform) Terraform >= 1.0 installed
- (For CloudFormation) AWS CLI >= 2.0

## Terraform Deployment

### 1. Configure Variables

Create a `terraform.tfvars` file in the `terraform/` directory:

```hcl
aws_region           = "us-east-1"
project_name         = "polymarket-arbitrage-bot"
environment          = "prod"
instance_type        = "t3.micro"  # Use c7i.large for production
key_pair_name        = "your-key-pair-name"
vpc_id               = "vpc-xxxxx"
subnet_id            = "subnet-xxxxx"
ssh_allowed_cidrs    = ["YOUR_IP/32"]  # Restrict to your IP
prometheus_allowed_cidrs = ["YOUR_IP/32"]
alert_email          = "your-email@example.com"
github_repo          = "https://github.com/yourusername/polymarket-arbitrage-bot.git"
github_branch        = "main"
dry_run_mode         = true  # Set to false for live trading
use_elastic_ip       = false
```

### 2. Initialize Terraform

```bash
cd terraform
terraform init
```

### 3. Plan Deployment

```bash
terraform plan
```

Review the planned changes carefully.

### 4. Deploy Infrastructure

```bash
terraform apply
```

Type `yes` when prompted to confirm.

### 5. Configure Secrets

After deployment, add your credentials to AWS Secrets Manager:

```bash
# Get the secret name from Terraform output
SECRET_NAME=$(terraform output -raw secrets_manager_secret_name)

# Create secret value (replace with your actual values)
aws secretsmanager put-secret-value \
  --secret-id "$SECRET_NAME" \
  --secret-string '{
    "private_key": "your_private_key_here",
    "wallet_address": "0xYourWalletAddress",
    "nvidia_api_key": "your_nvidia_api_key",
    "kalshi_api_key": "your_kalshi_api_key"
  }'
```

### 6. Access the Instance

```bash
# Get SSH command from Terraform output
terraform output ssh_command

# Or manually
ssh -i ~/.ssh/your-key.pem ubuntu@$(terraform output -raw instance_public_ip)
```

### 7. Destroy Infrastructure (when done)

```bash
terraform destroy
```

## CloudFormation Deployment

### 1. Create Parameters File

Create a `parameters.json` file in the `cloudformation/` directory:

```json
[
  {
    "ParameterKey": "ProjectName",
    "ParameterValue": "polymarket-arbitrage-bot"
  },
  {
    "ParameterKey": "Environment",
    "ParameterValue": "prod"
  },
  {
    "ParameterKey": "InstanceType",
    "ParameterValue": "t3.micro"
  },
  {
    "ParameterKey": "KeyPairName",
    "ParameterValue": "your-key-pair-name"
  },
  {
    "ParameterKey": "VpcId",
    "ParameterValue": "vpc-xxxxx"
  },
  {
    "ParameterKey": "SubnetId",
    "ParameterValue": "subnet-xxxxx"
  },
  {
    "ParameterKey": "SSHAllowedCIDR",
    "ParameterValue": "YOUR_IP/32"
  },
  {
    "ParameterKey": "PrometheusAllowedCIDR",
    "ParameterValue": "YOUR_IP/32"
  },
  {
    "ParameterKey": "AlertEmail",
    "ParameterValue": "your-email@example.com"
  },
  {
    "ParameterKey": "GitHubRepo",
    "ParameterValue": "https://github.com/yourusername/polymarket-arbitrage-bot.git"
  },
  {
    "ParameterKey": "GitHubBranch",
    "ParameterValue": "main"
  },
  {
    "ParameterKey": "DryRunMode",
    "ParameterValue": "true"
  }
]
```

### 2. Validate Template

```bash
cd cloudformation
aws cloudformation validate-template --template-body file://template.yaml
```

### 3. Deploy Stack

```bash
aws cloudformation create-stack \
  --stack-name polymarket-arbitrage-bot \
  --template-body file://template.yaml \
  --parameters file://parameters.json \
  --capabilities CAPABILITY_NAMED_IAM
```

### 4. Monitor Deployment

```bash
aws cloudformation describe-stacks \
  --stack-name polymarket-arbitrage-bot \
  --query 'Stacks[0].StackStatus'
```

Wait until status is `CREATE_COMPLETE`.

### 5. Get Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name polymarket-arbitrage-bot \
  --query 'Stacks[0].Outputs'
```

### 6. Configure Secrets

```bash
# Get secret name from stack outputs
SECRET_NAME=$(aws cloudformation describe-stacks \
  --stack-name polymarket-arbitrage-bot \
  --query 'Stacks[0].Outputs[?OutputKey==`SecretsManagerSecretName`].OutputValue' \
  --output text)

# Add credentials
aws secretsmanager put-secret-value \
  --secret-id "$SECRET_NAME" \
  --secret-string '{
    "private_key": "your_private_key_here",
    "wallet_address": "0xYourWalletAddress",
    "nvidia_api_key": "your_nvidia_api_key",
    "kalshi_api_key": "your_kalshi_api_key"
  }'
```

### 7. Delete Stack (when done)

```bash
aws cloudformation delete-stack --stack-name polymarket-arbitrage-bot
```

## Post-Deployment Steps

### 1. Verify Deployment

SSH into the instance and check the setup:

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<instance-ip>

# Check if bot is installed
cd /home/botuser/polymarket-bot
ls -la

# Check logs
tail -f /var/log/user-data.log
```

### 2. Run Deployment Script

The deployment script (created in task 24.2) will:
- Configure systemd service
- Set up log rotation
- Start the bot

```bash
sudo /home/botuser/polymarket-bot/deployment/scripts/deploy.sh
```

### 3. Monitor the Bot

```bash
# Check systemd service status
sudo systemctl status polymarket-bot

# View logs
sudo journalctl -u polymarket-bot -f

# Check Prometheus metrics
curl http://localhost:9090/metrics
```

### 4. Confirm Email Subscription

If you provided an alert email, check your inbox for an SNS subscription confirmation email and click the confirmation link.

## Resources Created

Both deployment methods create:

- **EC2 Instance**: t3.micro or c7i.large running Ubuntu 22.04
- **Security Group**: Allows SSH (port 22) and Prometheus (port 9090)
- **IAM Role**: With permissions for Secrets Manager, CloudWatch, and SNS
- **Secrets Manager Secret**: For storing private keys and API keys
- **CloudWatch Log Group**: For centralized logging
- **SNS Topic**: For critical alerts
- **CloudWatch Alarms**: CPU utilization and status check monitoring
- **Elastic IP** (optional): Static IP address

## Cost Estimates

### t3.micro (Testing)
- EC2: ~$7.50/month
- EBS (20GB): ~$2/month
- Data transfer: ~$1-5/month
- **Total: ~$10-15/month**

### c7i.large (Production)
- EC2: ~$70/month
- EBS (20GB): ~$2/month
- Data transfer: ~$5-10/month
- **Total: ~$75-85/month**

Additional costs:
- CloudWatch Logs: ~$0.50/GB ingested
- SNS: $0.50 per 1M requests
- Secrets Manager: $0.40/secret/month

## Security Best Practices

1. **Restrict SSH Access**: Set `ssh_allowed_cidrs` to your specific IP
2. **Use Elastic IP**: Enable for production to maintain consistent IP
3. **Rotate Keys**: Regularly update secrets in Secrets Manager
4. **Monitor Alerts**: Ensure SNS email subscription is confirmed
5. **Enable MFA**: Use MFA on AWS account
6. **Review IAM Policies**: Ensure least-privilege access
7. **Enable CloudTrail**: Track all API calls for audit

## Troubleshooting

### Instance Not Starting
- Check CloudWatch Logs: `/var/log/user-data.log`
- Verify IAM role has correct permissions
- Ensure subnet has internet access (NAT gateway or public subnet)

### Cannot SSH
- Verify security group allows your IP
- Check key pair name matches
- Ensure instance is in public subnet or use bastion host

### Bot Not Running
- Check systemd service: `sudo systemctl status polymarket-bot`
- View logs: `sudo journalctl -u polymarket-bot -f`
- Verify secrets are configured in Secrets Manager
- Check environment variables in `/home/botuser/polymarket-bot/.env`

### High Costs
- Use t3.micro for testing/development
- Set up billing alerts in AWS
- Monitor CloudWatch Logs ingestion
- Consider Reserved Instances for long-term production use

## Support

For issues or questions:
1. Check the main README.md
2. Review CloudWatch logs
3. Check GitHub issues
4. Contact support team
