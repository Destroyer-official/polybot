#!/bin/bash
# Uninstall script for Polymarket Arbitrage Bot
# This script removes the bot and all related files

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
SERVICE_NAME="polymarket-bot"

echo -e "${RED}=== Polymarket Arbitrage Bot Uninstall ===${NC}"
echo "This will remove the bot and all related files"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo "Usage: sudo $0"
    exit 1
fi

# Confirm uninstall
read -p "Are you sure you want to uninstall? (type 'yes' to confirm): " -r
echo
if [ "$REPLY" != "yes" ]; then
    echo "Uninstall cancelled"
    exit 0
fi

# Stop and disable service
echo -e "${YELLOW}[1/5] Stopping and disabling service...${NC}"
if systemctl is-active --quiet $SERVICE_NAME; then
    systemctl stop $SERVICE_NAME
fi
if systemctl is-enabled --quiet $SERVICE_NAME; then
    systemctl disable $SERVICE_NAME
fi
rm -f /etc/systemd/system/$SERVICE_NAME.service
systemctl daemon-reload
echo -e "${GREEN}✓ Service removed${NC}"

# Remove log rotation
echo -e "${YELLOW}[2/5] Removing log rotation...${NC}"
rm -f /etc/logrotate.d/$SERVICE_NAME
echo -e "${GREEN}✓ Log rotation removed${NC}"

# Remove bot directory
echo -e "${YELLOW}[3/5] Removing bot directory...${NC}"
if [ -d "$BOT_DIR" ]; then
    rm -rf "$BOT_DIR"
    echo -e "${GREEN}✓ Bot directory removed${NC}"
else
    echo -e "${YELLOW}⚠ Bot directory not found${NC}"
fi

# Remove bot user (optional)
echo -e "${YELLOW}[4/5] Removing bot user...${NC}"
read -p "Remove bot user '$BOT_USER'? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if id "$BOT_USER" &>/dev/null; then
        userdel -r $BOT_USER 2>/dev/null || userdel $BOT_USER
        echo -e "${GREEN}✓ Bot user removed${NC}"
    else
        echo -e "${YELLOW}⚠ Bot user not found${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Bot user kept${NC}"
fi

# Clean up system packages (optional)
echo -e "${YELLOW}[5/5] Cleaning up...${NC}"
read -p "Remove installed system packages? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    apt-get autoremove -y
    echo -e "${GREEN}✓ System packages cleaned${NC}"
else
    echo -e "${YELLOW}⚠ System packages kept${NC}"
fi

echo ""
echo -e "${GREEN}=== Uninstall Complete ===${NC}"
echo ""
echo "Note: The following were NOT removed:"
echo "  - AWS Secrets Manager secrets"
echo "  - CloudWatch log groups"
echo "  - SNS topics"
echo "  - EC2 infrastructure (if deployed via Terraform/CloudFormation)"
echo ""
echo "To remove AWS resources, use:"
echo "  - Terraform: terraform destroy"
echo "  - CloudFormation: aws cloudformation delete-stack --stack-name <stack-name>"
echo ""
