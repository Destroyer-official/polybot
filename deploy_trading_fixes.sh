#!/bin/bash
# Deploy trading fixes to the server

echo "========================================="
echo "Deploying Trading Fixes"
echo "========================================="

# Stop the bot
echo "Stopping polybot service..."
sudo systemctl stop polybot

# Backup current files
echo "Creating backup..."
BACKUP_DIR="backups/backup_trading_fixes_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp src/main_orchestrator.py "$BACKUP_DIR/"
cp src/fifteen_min_crypto_strategy.py "$BACKUP_DIR/"
cp src/ensemble_decision_engine.py "$BACKUP_DIR/"
echo "Backup created in $BACKUP_DIR"

# The files should already be updated in your local repo
# If you're running this on the server after git pull, the files are already updated

# Restart the bot
echo "Starting polybot service..."
sudo systemctl start polybot

# Wait a moment for startup
sleep 3

# Show status
echo ""
echo "========================================="
echo "Service Status:"
echo "========================================="
sudo systemctl status polybot --no-pager -l

echo ""
echo "========================================="
echo "Recent Logs (last 50 lines):"
echo "========================================="
sudo journalctl -u polybot -n 50 --no-pager

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Monitor logs with:"
echo "  sudo journalctl -u polybot -f"
echo ""
echo "Look for:"
echo "  1. Gas price checks working (should see gwei values)"
echo "  2. Ensemble model votes (LLM, RL, Historical, Technical)"
echo "  3. ENSEMBLE APPROVED messages"
echo "  4. Order placement messages"
echo ""
