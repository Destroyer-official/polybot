#!/bin/bash
# Deploy trading fixes to AWS server

# Configuration
SERVER_IP="your-server-ip-here"  # UPDATE THIS
KEY_FILE="money.pem"
REMOTE_USER="ubuntu"
REMOTE_PATH="/home/ubuntu/polybot"

echo "========================================="
echo "Deploying Trading Fixes to AWS"
echo "========================================="

# Check if key file exists
if [ ! -f "$KEY_FILE" ]; then
    echo "❌ Error: Key file $KEY_FILE not found!"
    exit 1
fi

# Check if server IP is set
if [ "$SERVER_IP" == "your-server-ip-here" ]; then
    echo "❌ Error: Please update SERVER_IP in this script!"
    exit 1
fi

# Copy files to server
echo "📤 Copying files to server..."
scp -i "$KEY_FILE" src/main_orchestrator.py "$REMOTE_USER@$SERVER_IP:$REMOTE_PATH/src/"
scp -i "$KEY_FILE" src/fifteen_min_crypto_strategy.py "$REMOTE_USER@$SERVER_IP:$REMOTE_PATH/src/"
scp -i "$KEY_FILE" src/ensemble_decision_engine.py "$REMOTE_USER@$SERVER_IP:$REMOTE_PATH/src/"

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to copy files to server!"
    exit 1
fi

echo "✅ Files copied successfully"

# Execute commands on server
echo ""
echo "🔄 Restarting bot on server..."
ssh -i "$KEY_FILE" "$REMOTE_USER@$SERVER_IP" << 'ENDSSH'
cd /home/ubuntu/polybot

# Create backup
echo "📦 Creating backup..."
BACKUP_DIR="backups/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp src/main_orchestrator.py "$BACKUP_DIR/" 2>/dev/null || true
cp src/fifteen_min_crypto_strategy.py "$BACKUP_DIR/" 2>/dev/null || true
cp src/ensemble_decision_engine.py "$BACKUP_DIR/" 2>/dev/null || true
echo "✅ Backup created in $BACKUP_DIR"

# Clear Python cache
echo "🧹 Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "✅ Cache cleared"

# Restart bot
echo "🔄 Restarting polybot service..."
sudo systemctl restart polybot

# Wait for startup
sleep 3

# Show status
echo ""
echo "========================================="
echo "Service Status:"
echo "========================================="
sudo systemctl status polybot --no-pager -l | head -20

echo ""
echo "========================================="
echo "Recent Logs (last 30 lines):"
echo "========================================="
sudo journalctl -u polybot -n 30 --no-pager

ENDSSH

echo ""
echo "========================================="
echo "✅ Deployment Complete!"
echo "========================================="
echo ""
echo "Monitor logs with:"
echo "  ssh -i $KEY_FILE $REMOTE_USER@$SERVER_IP"
echo "  sudo journalctl -u polybot -f"
echo ""
echo "Look for:"
echo "  ✅ Gas price checks: 'Gas price: XXX gwei'"
echo "  ✅ Ensemble votes: 'LLM: buy_yes (XX%)'"
echo "  ✅ Trade approvals: 'ENSEMBLE APPROVED'"
echo "  ✅ Order placements: 'ORDER PLACED SUCCESSFULLY'"
echo ""
