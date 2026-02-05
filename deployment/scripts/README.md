# Deployment Scripts

This directory contains scripts for deploying, managing, and maintaining the Polymarket Arbitrage Bot.

## Scripts Overview

### install.sh
Complete installation script for fresh Ubuntu 22.04 instances.

**Usage:**
```bash
sudo bash deployment/scripts/install.sh
```

**What it does:**
- Updates system packages
- Installs Python 3.11, Rust, and system dependencies
- Creates bot user
- Clones repository
- Sets up Python virtual environment
- Builds Rust core module
- Creates configuration files
- Runs deployment script

**Environment Variables:**
- `GITHUB_REPO`: Repository URL (default: https://github.com/yourusername/polymarket-arbitrage-bot.git)
- `GITHUB_BRANCH`: Branch to deploy (default: main)

**Example:**
```bash
export GITHUB_REPO="https://github.com/myuser/my-bot.git"
export GITHUB_BRANCH="production"
sudo bash deployment/scripts/install.sh
```

### deploy.sh
Deployment script that configures systemd service and log rotation.

**Usage:**
```bash
sudo bash deployment/scripts/deploy.sh
```

**What it does:**
- Installs system dependencies
- Installs Rust toolchain
- Creates bot user
- Installs Python dependencies
- Builds Rust core module
- Configures systemd service
- Sets up log rotation
- Starts bot service

**Requirements:**
- Must be run as root
- Bot code must be in `/home/botuser/polymarket-bot`
- `.env` file must be configured

### update.sh
Update script for pulling latest code and restarting the service.

**Usage:**
```bash
sudo bash deployment/scripts/update.sh
```

**What it does:**
- Stops bot service
- Creates backup of current configuration
- Pulls latest code from git
- Updates Python dependencies
- Rebuilds Rust core module
- Restarts bot service
- Rolls back on failure

**Safety:**
- Creates timestamped backup before update
- Automatically rolls back if service fails to start
- Preserves `.env` configuration

### uninstall.sh
Uninstall script that removes the bot and related files.

**Usage:**
```bash
sudo bash deployment/scripts/uninstall.sh
```

**What it does:**
- Stops and disables systemd service
- Removes log rotation configuration
- Removes bot directory
- Optionally removes bot user
- Optionally cleans up system packages

**Note:** Does NOT remove AWS resources (Secrets Manager, CloudWatch, SNS, EC2)

### health_check.sh
Health check script for verifying bot status (created in task 24.3).

**Usage:**
```bash
bash deployment/scripts/health_check.sh
```

**What it checks:**
- Service status
- API connectivity
- Wallet balance
- Log errors
- System resources

## Quick Start

### New Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/polymarket-arbitrage-bot.git
cd polymarket-arbitrage-bot

# 2. Run installation script
sudo bash deployment/scripts/install.sh

# 3. Configure AWS Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id polymarket-bot-credentials \
  --secret-string '{
    "private_key": "your_private_key",
    "wallet_address": "0xYourAddress",
    "nvidia_api_key": "your_nvidia_key",
    "kalshi_api_key": "your_kalshi_key"
  }'

# 4. Check service status
sudo systemctl status polymarket-bot

# 5. View logs
sudo journalctl -u polymarket-bot -f
```

### Update Existing Installation

```bash
# Pull latest code and restart
sudo bash deployment/scripts/update.sh

# Check service status
sudo systemctl status polymarket-bot
```

### Manual Deployment

If you already have the code and dependencies installed:

```bash
# Just configure and start the service
sudo bash deployment/scripts/deploy.sh
```

## Service Management

### Start Service
```bash
sudo systemctl start polymarket-bot
```

### Stop Service
```bash
sudo systemctl stop polymarket-bot
```

### Restart Service
```bash
sudo systemctl restart polymarket-bot
```

### Check Status
```bash
sudo systemctl status polymarket-bot
```

### Enable Auto-Start
```bash
sudo systemctl enable polymarket-bot
```

### Disable Auto-Start
```bash
sudo systemctl disable polymarket-bot
```

## Log Management

### View Live Logs
```bash
sudo journalctl -u polymarket-bot -f
```

### View Recent Logs
```bash
sudo journalctl -u polymarket-bot -n 100
```

### View Logs Since Time
```bash
sudo journalctl -u polymarket-bot --since "1 hour ago"
```

### View Logs for Date
```bash
sudo journalctl -u polymarket-bot --since "2024-01-01" --until "2024-01-02"
```

### Export Logs
```bash
sudo journalctl -u polymarket-bot > bot-logs.txt
```

## Log Rotation

Logs are automatically rotated daily with the following configuration:
- Retention: 30 days
- Compression: Enabled
- Location: `/home/botuser/polymarket-bot/logs/`

Manual log rotation:
```bash
sudo logrotate -f /etc/logrotate.d/polymarket-bot
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status polymarket-bot

# View detailed logs
sudo journalctl -u polymarket-bot -n 50

# Check configuration
cat /home/botuser/polymarket-bot/.env

# Verify secrets are configured
aws secretsmanager get-secret-value --secret-id polymarket-bot-credentials

# Test bot manually
cd /home/botuser/polymarket-bot
sudo -u botuser ./venv/bin/python bot.py
```

### Rust Build Fails

```bash
# Reinstall Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source $HOME/.cargo/env

# Rebuild Rust module
cd /home/botuser/polymarket-bot/rust_core
sudo -u botuser bash -c "source /home/botuser/.cargo/env && ../venv/bin/maturin develop --release"
```

### Python Dependencies Issues

```bash
# Recreate virtual environment
cd /home/botuser/polymarket-bot
sudo -u botuser rm -rf venv
sudo -u botuser python3.11 -m venv venv
sudo -u botuser ./venv/bin/pip install --upgrade pip
sudo -u botuser ./venv/bin/pip install -r requirements.txt
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R botuser:botuser /home/botuser/polymarket-bot

# Fix permissions
sudo chmod +x /home/botuser/polymarket-bot/deployment/scripts/*.sh
```

### High Memory Usage

```bash
# Check memory usage
free -h
ps aux | grep python

# Restart service
sudo systemctl restart polymarket-bot

# Adjust memory limits in systemd service
sudo nano /etc/systemd/system/polymarket-bot.service
# Change MemoryMax=2G to desired value
sudo systemctl daemon-reload
sudo systemctl restart polymarket-bot
```

## Monitoring

### Check Prometheus Metrics
```bash
curl http://localhost:9090/metrics
```

### Check System Resources
```bash
# CPU and memory
htop

# Disk usage
df -h

# Network connections
netstat -tulpn | grep python
```

### Check AWS Resources
```bash
# CloudWatch logs
aws logs tail /polymarket-arbitrage-bot --follow

# SNS topic
aws sns list-subscriptions-by-topic --topic-arn <topic-arn>

# Secrets Manager
aws secretsmanager describe-secret --secret-id polymarket-bot-credentials
```

## Security Best Practices

1. **Run as non-root user**: Service runs as `botuser`
2. **Restrict file permissions**: Only `botuser` can read `.env`
3. **Use AWS Secrets Manager**: Never store keys in files
4. **Enable systemd security**: NoNewPrivileges, PrivateTmp, ProtectSystem
5. **Rotate logs**: Automatic daily rotation with 30-day retention
6. **Monitor alerts**: Configure SNS email notifications
7. **Regular updates**: Run `update.sh` to get security patches

## Backup and Recovery

### Create Backup
```bash
# Backup configuration
sudo cp /home/botuser/polymarket-bot/.env /home/botuser/backups/env-$(date +%Y%m%d).bak

# Backup database (if applicable)
sudo cp /home/botuser/polymarket-bot/trades.db /home/botuser/backups/trades-$(date +%Y%m%d).db
```

### Restore from Backup
```bash
# Stop service
sudo systemctl stop polymarket-bot

# Restore configuration
sudo cp /home/botuser/backups/env-20240101.bak /home/botuser/polymarket-bot/.env

# Restore database
sudo cp /home/botuser/backups/trades-20240101.db /home/botuser/polymarket-bot/trades.db

# Fix permissions
sudo chown botuser:botuser /home/botuser/polymarket-bot/.env
sudo chown botuser:botuser /home/botuser/polymarket-bot/trades.db

# Start service
sudo systemctl start polymarket-bot
```

## Support

For issues or questions:
1. Check service logs: `sudo journalctl -u polymarket-bot -f`
2. Review deployment logs: `cat /var/log/user-data.log`
3. Check main README: `../README.md`
4. Review deployment guide: `../README.md`
