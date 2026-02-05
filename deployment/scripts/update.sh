#!/bin/bash
# Update script for Polymarket Arbitrage Bot
# This script pulls latest code and restarts the service

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BOT_USER="botuser"
BOT_HOME="/home/$BOT_USER"
BOT_DIR="$BOT_HOME/polymarket-bot"
VENV_DIR="$BOT_DIR/venv"
SERVICE_NAME="polymarket-bot"

echo -e "${GREEN}=== Polymarket Arbitrage Bot Update ===${NC}"
echo "Timestamp: $(date)"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Check if bot directory exists
if [ ! -d "$BOT_DIR" ]; then
    echo -e "${RED}Error: Bot directory not found: $BOT_DIR${NC}"
    echo "Run install.sh first"
    exit 1
fi

# Stop service
echo -e "${YELLOW}[1/6] Stopping bot service...${NC}"
systemctl stop $SERVICE_NAME
echo -e "${GREEN}✓ Service stopped${NC}"

# Backup current version
echo -e "${YELLOW}[2/6] Creating backup...${NC}"
BACKUP_DIR="$BOT_HOME/backups/$(date +%Y%m%d_%H%M%S)"
sudo -u $BOT_USER mkdir -p "$BACKUP_DIR"
sudo -u $BOT_USER cp -r $BOT_DIR/.env "$BACKUP_DIR/" 2>/dev/null || true
echo -e "${GREEN}✓ Backup created at $BACKUP_DIR${NC}"

# Pull latest code
echo -e "${YELLOW}[3/6] Pulling latest code...${NC}"
cd $BOT_DIR
sudo -u $BOT_USER git fetch --all
sudo -u $BOT_USER git pull
echo -e "${GREEN}✓ Code updated${NC}"

# Update Python dependencies
echo -e "${YELLOW}[4/6] Updating Python dependencies...${NC}"
sudo -u $BOT_USER $VENV_DIR/bin/pip install --upgrade pip
sudo -u $BOT_USER $VENV_DIR/bin/pip install -r requirements.txt --upgrade
echo -e "${GREEN}✓ Python dependencies updated${NC}"

# Rebuild Rust core module
echo -e "${YELLOW}[5/6] Rebuilding Rust core module...${NC}"
cd $BOT_DIR/rust_core
sudo -u $BOT_USER bash -c "source $BOT_HOME/.cargo/env && $VENV_DIR/bin/maturin develop --release"
cd $BOT_DIR
echo -e "${GREEN}✓ Rust core module rebuilt${NC}"

# Restart service
echo -e "${YELLOW}[6/6] Starting bot service...${NC}"
systemctl start $SERVICE_NAME

# Wait for service to start
sleep 3

# Check service status
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}✓ Bot service started successfully${NC}"
else
    echo -e "${RED}✗ Bot service failed to start${NC}"
    echo "Restoring from backup..."
    sudo -u $BOT_USER cp "$BACKUP_DIR/.env" $BOT_DIR/ 2>/dev/null || true
    systemctl start $SERVICE_NAME
    echo "Check logs with: sudo journalctl -u $SERVICE_NAME -f"
    exit 1
fi

echo ""
echo -e "${GREEN}=== Update Complete ===${NC}"
echo ""
echo "Service Status:"
systemctl status $SERVICE_NAME --no-pager -l
echo ""
echo "View logs: sudo journalctl -u $SERVICE_NAME -f"
echo ""
