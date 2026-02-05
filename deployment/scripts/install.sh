#!/bin/bash
# Installation script for Polymarket Arbitrage Bot
# This script can be run on a fresh Ubuntu 22.04 instance

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Polymarket Arbitrage Bot Installation ===${NC}"
echo "This script will install all dependencies and set up the bot"
echo ""

# Check OS
if [ ! -f /etc/os-release ]; then
    echo -e "${RED}Error: Cannot detect OS${NC}"
    exit 1
fi

source /etc/os-release
if [ "$ID" != "ubuntu" ] || [ "${VERSION_ID%%.*}" -lt 22 ]; then
    echo -e "${RED}Error: This script requires Ubuntu 22.04 or later${NC}"
    exit 1
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Configuration
GITHUB_REPO="${GITHUB_REPO:-https://github.com/yourusername/polymarket-arbitrage-bot.git}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
BOT_USER="botuser"
BOT_HOME="/home/$BOT_USER"
BOT_DIR="$BOT_HOME/polymarket-bot"

echo "Configuration:"
echo "  Repository: $GITHUB_REPO"
echo "  Branch: $GITHUB_BRANCH"
echo "  Install directory: $BOT_DIR"
echo ""

read -p "Continue with installation? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled"
    exit 0
fi

# Update system
echo -e "${YELLOW}Updating system packages...${NC}"
apt-get update
apt-get upgrade -y

# Install dependencies
echo -e "${YELLOW}Installing system dependencies...${NC}"
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    wget \
    build-essential \
    libssl-dev \
    pkg-config \
    awscli \
    jq \
    logrotate \
    htop \
    vim

# Install Rust
echo -e "${YELLOW}Installing Rust toolchain...${NC}"
if ! command -v rustc &> /dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
fi

# Create bot user
echo -e "${YELLOW}Creating bot user...${NC}"
if ! id "$BOT_USER" &>/dev/null; then
    useradd -m -s /bin/bash $BOT_USER
    echo -e "${GREEN}✓ Bot user created${NC}"
else
    echo -e "${GREEN}✓ Bot user already exists${NC}"
fi

# Install Rust for bot user
echo -e "${YELLOW}Installing Rust for bot user...${NC}"
sudo -u $BOT_USER bash -c 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'

# Clone repository
echo -e "${YELLOW}Cloning repository...${NC}"
if [ -d "$BOT_DIR" ]; then
    echo "Directory $BOT_DIR already exists. Pulling latest changes..."
    cd $BOT_DIR
    sudo -u $BOT_USER git pull
else
    cd $BOT_HOME
    sudo -u $BOT_USER git clone -b "$GITHUB_BRANCH" "$GITHUB_REPO" polymarket-bot
fi

cd $BOT_DIR

# Create Python virtual environment
echo -e "${YELLOW}Setting up Python virtual environment...${NC}"
sudo -u $BOT_USER python3.11 -m venv venv
sudo -u $BOT_USER ./venv/bin/pip install --upgrade pip

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
sudo -u $BOT_USER ./venv/bin/pip install -r requirements.txt

# Build Rust core module
echo -e "${YELLOW}Building Rust core module...${NC}"
cd rust_core
sudo -u $BOT_USER bash -c "source $BOT_HOME/.cargo/env && ../venv/bin/maturin develop --release"
cd ..

# Create logs directory
echo -e "${YELLOW}Creating logs directory...${NC}"
mkdir -p logs
chown $BOT_USER:$BOT_USER logs

# Create .env file if not exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << 'EOF'
# AWS Configuration
AWS_REGION=us-east-1
USE_AWS_SECRETS=true
SECRET_NAME=polymarket-bot-credentials

# Bot Configuration
DRY_RUN=true
SCAN_INTERVAL_SECONDS=2
HEARTBEAT_INTERVAL_SECONDS=60

# Monitoring
PROMETHEUS_PORT=9090
CLOUDWATCH_LOG_GROUP=/polymarket-arbitrage-bot

# Trading Parameters
STAKE_AMOUNT=10.0
MIN_PROFIT_THRESHOLD=0.005
MAX_POSITION_SIZE=5.0
MIN_BALANCE=50.0
TARGET_BALANCE=100.0
WITHDRAW_LIMIT=500.0
MAX_GAS_PRICE_GWEI=800

# RPC Configuration
POLYGON_RPC_URL=https://polygon-rpc.com
EOF
    chown $BOT_USER:$BOT_USER .env
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}⚠ Please edit .env file with your configuration${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Run deployment script
echo -e "${YELLOW}Running deployment script...${NC}"
bash deployment/scripts/deploy.sh

echo ""
echo -e "${GREEN}=== Installation Complete ===${NC}"
echo ""
echo "Next Steps:"
echo "1. Configure AWS Secrets Manager with your credentials:"
echo "   aws secretsmanager put-secret-value \\"
echo "     --secret-id polymarket-bot-credentials \\"
echo "     --secret-string '{\"private_key\":\"...\",\"wallet_address\":\"...\"}'"
echo ""
echo "2. Edit configuration if needed:"
echo "   sudo nano $BOT_DIR/.env"
echo ""
echo "3. Check service status:"
echo "   sudo systemctl status polymarket-bot"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u polymarket-bot -f"
echo ""
echo "5. Access Prometheus metrics:"
echo "   curl http://localhost:9090/metrics"
echo ""
