#!/bin/bash
# Setup script for Polymarket Bot systemd service
# This script configures the bot for fully autonomous operation

set -e

echo "=========================================="
echo "Polymarket Bot - Systemd Setup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Configuration
SERVICE_NAME="polybot"
SERVICE_FILE="polybot.service"
JOURNALD_CONF="journald-polybot.conf"
INSTALL_DIR="/home/ubuntu/polybot"
SERVICE_USER="ubuntu"

echo "Step 1: Validating files..."
if [ ! -f "$SERVICE_FILE" ]; then
    echo "ERROR: Service file $SERVICE_FILE not found"
    exit 1
fi

if [ ! -f "$JOURNALD_CONF" ]; then
    echo "ERROR: Journald config $JOURNALD_CONF not found"
    exit 1
fi

echo "Step 2: Creating required directories..."
sudo -u $SERVICE_USER mkdir -p "$INSTALL_DIR/logs"
sudo -u $SERVICE_USER mkdir -p "$INSTALL_DIR/data"
sudo -u $SERVICE_USER mkdir -p "$INSTALL_DIR/state"
echo "  ✓ Created logs, data, and state directories"

echo "Step 3: Installing systemd service..."
cp "$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME.service"
echo "  ✓ Copied service file to /etc/systemd/system/"

echo "Step 4: Installing journald configuration..."
mkdir -p /etc/systemd/journald.conf.d
cp "$JOURNALD_CONF" "/etc/systemd/journald.conf.d/polybot.conf"
echo "  ✓ Copied journald config to /etc/systemd/journald.conf.d/"

echo "Step 5: Reloading systemd daemon..."
systemctl daemon-reload
echo "  ✓ Systemd daemon reloaded"

echo "Step 6: Restarting journald (for log rotation config)..."
systemctl restart systemd-journald
echo "  ✓ Journald restarted"

echo "Step 7: Enabling service to start on boot..."
systemctl enable "$SERVICE_NAME.service"
echo "  ✓ Service enabled"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Service Status:"
systemctl status "$SERVICE_NAME.service" --no-pager || true
echo ""
echo "Available Commands:"
echo "  Start:   sudo systemctl start $SERVICE_NAME"
echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
echo "  Restart: sudo systemctl restart $SERVICE_NAME"
echo "  Status:  sudo systemctl status $SERVICE_NAME"
echo "  Logs:    sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "Configuration:"
echo "  - Auto-restart: ON (max 10 per hour)"
echo "  - Restart delay: 30 seconds"
echo "  - Memory limit: 2GB (high: 1.5GB)"
echo "  - CPU limit: 150%"
echo "  - Log retention: 30 days"
echo "  - Log max size: 1GB"
echo ""
echo "To start the bot now, run:"
echo "  sudo systemctl start $SERVICE_NAME"
echo ""
