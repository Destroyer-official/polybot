#!/bin/bash
# Deployment script for Polymarket Arbitrage Bot
# This script installs dependencies, builds the Rust module, and configures the systemd service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BOT_USER="botuser"
BOT_HOME="/home/$BOT_USER"
BOT_DIR="$BOT_HOME/polymarket-bot"
VENV_DIR="$BOT_DIR/venv"
SERVICE_NAME="polymarket-bot"
LOG_DIR="$BOT_DIR/logs"

echo -e "${GREEN}=== Polymarket Arbitrage Bot Deployment ===${NC}"
echo "Timestamp: $(date)"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Step 1: Install system dependencies
echo -e "${YELLOW}[1/8] Installing system dependencies...${NC}"
apt-get update
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
    jq \
    logrotate

echo -e "${GREEN}✓ System dependencies installed${NC}"

# Step 2: Install Rust toolchain
echo -e "${YELLOW}[2/8] Installing Rust toolchain...${NC}"
if ! command -v rustc &> /dev/null; then
    # Install for root user
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
    
    # Install for bot user
    sudo -u $BOT_USER bash -c 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'
    echo -e "${GREEN}✓ Rust toolchain installed${NC}"
else
    echo -e "${GREEN}✓ Rust toolchain already installed${NC}"
fi

# Step 3: Create bot user if not exists
echo -e "${YELLOW}[3/8] Setting up bot user...${NC}"
if ! id "$BOT_USER" &>/dev/null; then
    useradd -m -s /bin/bash $BOT_USER
    echo -e "${GREEN}✓ Bot user created${NC}"
else
    echo -e "${GREEN}✓ Bot user already exists${NC}"
fi

# Step 4: Install Python dependencies
echo -e "${YELLOW}[4/8] Installing Python dependencies...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    sudo -u $BOT_USER python3.11 -m venv $VENV_DIR
fi

sudo -u $BOT_USER $VENV_DIR/bin/pip install --upgrade pip
sudo -u $BOT_USER $VENV_DIR/bin/pip install -r $BOT_DIR/requirements.txt

echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Step 5: Build Rust core module
echo -e "${YELLOW}[5/8] Building Rust core module...${NC}"
cd $BOT_DIR/rust_core
sudo -u $BOT_USER bash -c "source $BOT_HOME/.cargo/env && $VENV_DIR/bin/maturin develop --release"
cd $BOT_DIR

echo -e "${GREEN}✓ Rust core module built${NC}"

# Step 6: Configure systemd service
echo -e "${YELLOW}[6/8] Configuring systemd service...${NC}"

cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=Polymarket Arbitrage Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$BOT_USER
Group=$BOT_USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=$BOT_DIR/.env
ExecStart=$VENV_DIR/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$LOG_DIR

# Resource limits
LimitNOFILE=65536
MemoryMax=2G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo -e "${GREEN}✓ Systemd service configured${NC}"

# Step 7: Set up log rotation
echo -e "${YELLOW}[7/8] Setting up log rotation...${NC}"

# Create logs directory if not exists
mkdir -p $LOG_DIR
chown $BOT_USER:$BOT_USER $LOG_DIR

cat > /etc/logrotate.d/$SERVICE_NAME << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0644 $BOT_USER $BOT_USER
    sharedscripts
    postrotate
        systemctl reload $SERVICE_NAME > /dev/null 2>&1 || true
    endscript
}
EOF

echo -e "${GREEN}✓ Log rotation configured${NC}"

# Step 8: Enable and start service
echo -e "${YELLOW}[8/8] Starting bot service...${NC}"

systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

# Wait a moment for service to start
sleep 3

# Check service status
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✓ Bot service started successfully${NC}"
else
    echo -e "${RED}✗ Bot service failed to start${NC}"
    echo "Check logs with: sudo journalctl -u $SERVICE_NAME -f"
    exit 1
fi

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Service Status:"
systemctl status $SERVICE_NAME --no-pager -l
echo ""
echo "Useful Commands:"
echo "  View logs:        sudo journalctl -u $SERVICE_NAME -f"
echo "  Restart service:  sudo systemctl restart $SERVICE_NAME"
echo "  Stop service:     sudo systemctl stop $SERVICE_NAME"
echo "  Service status:   sudo systemctl status $SERVICE_NAME"
echo "  View metrics:     curl http://localhost:9090/metrics"
echo ""
echo -e "${YELLOW}Note: Ensure credentials are configured in AWS Secrets Manager${NC}"
echo ""
