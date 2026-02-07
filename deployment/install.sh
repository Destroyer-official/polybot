#!/bin/bash
# Polybot AWS Installation Script
# Run as: sudo bash install.sh

set -e

echo "================================================"
echo "   Polymarket Arbitrage Bot - AWS Installer"
echo "================================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root: sudo bash install.sh"
    exit 1
fi

# Update system
echo "[1/6] Updating system packages..."
apt update && apt upgrade -y

# Install Python 3.11+
echo "[2/6] Installing Python 3.11..."
apt install -y python3.11 python3.11-venv python3-pip

# Create virtual environment
echo "[3/6] Creating virtual environment..."
cd /home/ubuntu/polybot
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
echo "[4/6] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Set permissions
echo "[5/6] Setting file permissions..."
chown -R ubuntu:ubuntu /home/ubuntu/polybot
chmod 600 /home/ubuntu/polybot/.env

# Install systemd service
echo "[6/6] Installing systemd service..."
cp deployment/polybot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable polybot

echo ""
echo "================================================"
echo "   Installation Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your credentials:"
echo "     nano /home/ubuntu/polybot/.env"
echo ""
echo "  2. Start the bot:"
echo "     sudo systemctl start polybot"
echo ""
echo "  3. Check status:"
echo "     sudo systemctl status polybot"
echo ""
echo "  4. View logs:"
echo "     journalctl -u polybot -f"
echo ""
echo "Commands:"
echo "  Start:   sudo systemctl start polybot"
echo "  Stop:    sudo systemctl stop polybot"
echo "  Restart: sudo systemctl restart polybot"
echo "  Logs:    journalctl -u polybot -f"
echo ""
