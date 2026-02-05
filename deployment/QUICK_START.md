# Quick Start Guide - Polymarket Arbitrage Bot Deployment

## 🚀 5-Minute Deployment

### Option 1: Terraform (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/polymarket-arbitrage-bot.git
cd polymarket-arbitrage-bot/deployment/terraform

# 2. Create terraform.tfvars
cat > terraform.tfvars << EOF
aws_region     = "us-east-1"
instance_type  = "t3.micro"
key_pair_name  = "your-key-name"
vpc_id         = "vpc-xxxxx"
subnet_id      = "subnet-xxxxx"
alert_email    = "your-email@example.com"
dry_run_mode   = true
EOF

# 3. Deploy
terraform init
terraform apply -auto-approve

# 4. Configure secrets
SECRET_NAME=$(terraform output -raw secrets_manager_secret_name)
aws secretsmanager put-secret-value \
  --secret-id "$SECRET_NAME" \
  --secret-string '{
    "private_key": "your_private_key_here",
    "wallet_address": "0xYourWalletAddress"
  }'

# 5. Check status
ssh -i ~/.ssh/your-key.pem ubuntu@$(terraform output -raw instance_public_ip)
sudo systemctl status polymarket-bot
```

### Option 2: CloudFormation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/polymarket-arbitrage-bot.git
cd polymarket-arbitrage-bot/deployment/cloudformation

# 2. Create parameters.json (edit with your values)
cp parameters.example.json parameters.json

# 3. Deploy
aws cloudformation create-stack \
  --stack-name polymarket-bot \
  --template-body file://template.yaml \
  --parameters file://parameters.json \
  --capabilities CAPABILITY_NAMED_IAM

# 4. Wait for completion
aws cloudformation wait stack-create-complete --stack-name polymarket-bot

# 5. Configure secrets
SECRET_NAME=$(aws cloudformation describe-stacks \
  --stack-name polymarket-bot \
  --query 'Stacks[0].Outputs[?OutputKey==`SecretsManagerSecretName`].OutputValue' \
  --output text)

aws secretsmanager put-secret-value \
  --secret-id "$SECRET_NAME" \
  --secret-string '{
    "private_key": "your_private_key_here",
    "wallet_address": "0xYourWalletAddress"
  }'
```

### Option 3: Manual Installation

```bash
# On a fresh Ubuntu 22.04 instance
git clone https://github.com/yourusername/polymarket-arbitrage-bot.git
cd polymarket-arbitrage-bot
sudo bash deployment/scripts/install.sh
```

## ✅ Post-Deployment Checklist

- [ ] Confirm SNS email subscription
- [ ] Verify secrets in AWS Secrets Manager
- [ ] Check service status: `sudo systemctl status polymarket-bot`
- [ ] View logs: `sudo journalctl -u polymarket-bot -f`
- [ ] Run health check: `bash deployment/scripts/health_check.sh`
- [ ] Check Prometheus metrics: `curl http://localhost:9090/metrics`
- [ ] Monitor for 24 hours in DRY_RUN mode
- [ ] Review logs and metrics before enabling live trading

## 🔧 Common Commands

```bash
# Service management
sudo systemctl start polymarket-bot
sudo systemctl stop polymarket-bot
sudo systemctl restart polymarket-bot
sudo systemctl status polymarket-bot

# View logs
sudo journalctl -u polymarket-bot -f
sudo journalctl -u polymarket-bot -n 100

# Health check
bash deployment/scripts/health_check.sh
python3 deployment/scripts/health_check.py --json

# Update bot
sudo bash deployment/scripts/update.sh

# Check metrics
curl http://localhost:9090/metrics
```

## 🔐 Security Configuration

### AWS Secrets Manager Format

```json
{
  "private_key": "0x1234567890abcdef...",
  "wallet_address": "0xYourWalletAddress",
  "nvidia_api_key": "your_nvidia_api_key_optional",
  "kalshi_api_key": "your_kalshi_api_key_optional"
}
```

### Environment Variables (.env)

```bash
# AWS Configuration
AWS_REGION=us-east-1
USE_AWS_SECRETS=true
SECRET_NAME=polymarket-bot-credentials

# Bot Configuration
DRY_RUN=true
SCAN_INTERVAL_SECONDS=2
HEARTBEAT_INTERVAL_SECONDS=60

# Trading Parameters
STAKE_AMOUNT=10.0
MIN_PROFIT_THRESHOLD=0.005
MAX_POSITION_SIZE=5.0
MIN_BALANCE=50.0
WITHDRAW_LIMIT=500.0
MAX_GAS_PRICE_GWEI=800

# Monitoring
PROMETHEUS_PORT=9090
CLOUDWATCH_LOG_GROUP=/polymarket-arbitrage-bot
```

## 📊 Monitoring

### Prometheus Metrics
```bash
# View all metrics
curl http://localhost:9090/metrics

# Key metrics to monitor
curl http://localhost:9090/metrics | grep -E "(trades_total|win_rate|profit_usd|balance_usd)"
```

### CloudWatch Logs
```bash
# Tail logs
aws logs tail /polymarket-arbitrage-bot --follow

# Query logs
aws logs filter-log-events \
  --log-group-name /polymarket-arbitrage-bot \
  --start-time $(date -d '1 hour ago' +%s)000
```

## 🚨 Troubleshooting

### Service Won't Start
```bash
# Check service status
sudo systemctl status polymarket-bot

# View detailed logs
sudo journalctl -u polymarket-bot -n 50 --no-pager

# Check configuration
cat /home/botuser/polymarket-bot/.env

# Test manually
cd /home/botuser/polymarket-bot
sudo -u botuser ./venv/bin/python bot.py
```

### Secrets Not Found
```bash
# Verify secret exists
aws secretsmanager describe-secret --secret-id polymarket-bot-credentials

# Check IAM permissions
aws sts get-caller-identity
```

### High Resource Usage
```bash
# Check resources
htop
free -h
df -h

# Restart service
sudo systemctl restart polymarket-bot
```

## 💰 Cost Optimization

### Development/Testing
- Use `t3.micro` instance (~$7.50/month)
- Enable DRY_RUN mode
- Set log retention to 7 days
- Use on-demand pricing

### Production
- Use `c7i.large` for better performance (~$70/month)
- Consider Reserved Instances (up to 72% savings)
- Set log retention to 30 days
- Enable CloudWatch Logs Insights for analysis

## 🔄 Update Process

```bash
# 1. SSH to instance
ssh -i ~/.ssh/your-key.pem ubuntu@<instance-ip>

# 2. Run update script
sudo bash /home/botuser/polymarket-bot/deployment/scripts/update.sh

# 3. Verify service
sudo systemctl status polymarket-bot

# 4. Check logs
sudo journalctl -u polymarket-bot -f
```

## 🗑️ Cleanup

### Terraform
```bash
cd deployment/terraform
terraform destroy -auto-approve
```

### CloudFormation
```bash
aws cloudformation delete-stack --stack-name polymarket-bot
```

### Manual
```bash
sudo bash deployment/scripts/uninstall.sh
```

## 📚 Additional Resources

- [Full Deployment Guide](README.md)
- [Scripts Documentation](scripts/README.md)
- [Main README](../README.md)
- [Requirements Document](../.kiro/specs/polymarket-arbitrage-bot/requirements.md)
- [Design Document](../.kiro/specs/polymarket-arbitrage-bot/design.md)

## 🆘 Support

For issues:
1. Check health: `bash deployment/scripts/health_check.sh`
2. Review logs: `sudo journalctl -u polymarket-bot -f`
3. Check AWS resources in console
4. Review deployment documentation
5. Open GitHub issue with logs and error messages

## ⚠️ Important Notes

- **Always test in DRY_RUN mode first**
- **Never commit private keys to git**
- **Monitor costs in AWS Billing Dashboard**
- **Set up billing alerts**
- **Regularly update dependencies**
- **Rotate keys periodically**
- **Monitor win rate and profit metrics**
- **Keep backups of configuration**

---

**Ready to deploy?** Start with Option 1 (Terraform) for the easiest experience!
