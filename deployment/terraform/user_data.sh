#!/bin/bash
# User data script for EC2 instance initialization
# This script runs on first boot to set up the Polymarket Arbitrage Bot

set -e

# Variables from Terraform
AWS_REGION="${aws_region}"
SECRET_NAME="${secret_name}"
SNS_TOPIC_ARN="${sns_topic_arn}"
CLOUDWATCH_LOG_GROUP="${cloudwatch_log_group}"
GITHUB_REPO="${github_repo}"
GITHUB_BRANCH="${github_branch}"
DRY_RUN="${dry_run}"

# Log everything
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=== Starting Polymarket Arbitrage Bot Setup ==="
echo "Timestamp: $(date)"

# Update system
echo "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install required packages
echo "Installing system dependencies..."
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    build-essential \
    libssl-dev \
    pkg-config \
    awscli \
    jq

# Install Rust
echo "Installing Rust toolchain..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source $HOME/.cargo/env

# Create bot user
echo "Creating bot user..."
useradd -m -s /bin/bash botuser || true

# Clone repository
echo "Cloning repository..."
cd /home/botuser
sudo -u botuser git clone -b "$GITHUB_BRANCH" "$GITHUB_REPO" polymarket-bot || true
cd polymarket-bot

# Create Python virtual environment
echo "Setting up Python virtual environment..."
sudo -u botuser python3.11 -m venv venv
sudo -u botuser /home/botuser/polymarket-bot/venv/bin/pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies..."
sudo -u botuser /home/botuser/polymarket-bot/venv/bin/pip install -r requirements.txt

# Build Rust core module
echo "Building Rust core module..."
cd rust_core
sudo -u botuser /home/botuser/polymarket-bot/venv/bin/maturin develop --release
cd ..

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs
chown botuser:botuser logs

# Set AWS region
echo "Configuring AWS CLI..."
sudo -u botuser aws configure set region "$AWS_REGION"

# Create environment file
echo "Creating environment configuration..."
cat > /home/botuser/polymarket-bot/.env << EOF
# AWS Configuration
AWS_REGION=$AWS_REGION
SNS_ALERT_TOPIC=$SNS_TOPIC_ARN
CLOUDWATCH_LOG_GROUP=$CLOUDWATCH_LOG_GROUP

# Bot Configuration
DRY_RUN=$DRY_RUN
USE_AWS_SECRETS=true
SECRET_NAME=$SECRET_NAME

# Monitoring
PROMETHEUS_PORT=9090
EOF

chown botuser:botuser /home/botuser/polymarket-bot/.env

# Note: Actual deployment script will be created in subtask 24.2
echo "Setup complete. Deployment script will configure systemd service."
echo "=== Setup Complete ==="
