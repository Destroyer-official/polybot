#!/bin/bash

# Deploy Liquidity & Strategy Fixes to AWS
# Fixes: 98% slippage blocking, wrong strategies running, positions not closing

set -e  # Exit on error

echo "=========================================="
echo "DEPLOYING LIQUIDITY & STRATEGY FIXES"
echo "=========================================="
echo ""
echo "Fixes Applied:"
echo "  ✅ Increased slippage tolerance (5% → 50%)"
echo "  ✅ Disabled all strategies except 15-min crypto"
echo "  ✅ Faster position exits (10 min, 2 min before close)"
echo "  ✅ Bot now ONLY trades BTC/ETH/SOL/XRP 15-min markets"
echo ""

# Configuration
AWS_HOST="ubuntu@35.76.113.47"
SSH_KEY="money.pem"
REMOTE_DIR="/home/ubuntu/polybot"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}ERROR: SSH key not found: $SSH_KEY${NC}"
    exit 1
fi

# Set correct permissions on SSH key
chmod 600 "$SSH_KEY"

echo -e "${YELLOW}Step 1: Testing SSH connection...${NC}"
if ssh -i "$SSH_KEY" -o ConnectTimeout=10 "$AWS_HOST" "echo 'SSH connection successful'"; then
    echo -e "${GREEN}✅ SSH connection successful${NC}"
else
    echo -e "${RED}❌ SSH connection failed${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 2: Backing up current code on AWS...${NC}"
BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S)"
ssh -i "$SSH_KEY" "$AWS_HOST" "cd $REMOTE_DIR && mkdir -p backups && cp -r src backups/$BACKUP_NAME || true"
echo -e "${GREEN}✅ Backup created: backups/$BACKUP_NAME${NC}"

echo -e "${YELLOW}Step 3: Uploading fixed files...${NC}"

# Upload the fixed strategy file (main fix for slippage + exits)
echo "  → Uploading fifteen_min_crypto_strategy.py..."
scp -i "$SSH_KEY" src/fifteen_min_crypto_strategy.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}  ✅ Uploaded fifteen_min_crypto_strategy.py${NC}"

# Upload the fixed orchestrator file (disables other strategies)
echo "  → Uploading main_orchestrator.py..."
scp -i "$SSH_KEY" src/main_orchestrator.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}  ✅ Uploaded main_orchestrator.py${NC}"

# Upload order book analyzer (slippage calculation)
echo "  → Uploading order_book_analyzer.py..."
scp -i "$SSH_KEY" src/order_book_analyzer.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}  ✅ Uploaded order_book_analyzer.py${NC}"

echo -e "${YELLOW}Step 4: Stopping bot service...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "sudo systemctl stop polybot || true"
sleep 2
echo -e "${GREEN}✅ Bot stopped${NC}"

echo -e "${YELLOW}Step 5: Starting bot service...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "sudo systemctl start polybot"
sleep 3
echo -e "${GREEN}✅ Bot started${NC}"

echo -e "${YELLOW}Step 6: Checking bot status...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "sudo systemctl status polybot --no-pager | head -20"

echo -e "${YELLOW}Step 7: Showing recent logs (last 30 lines)...${NC}"
echo ""
ssh -i "$SSH_KEY" "$AWS_HOST" "sudo journalctl -u polybot -n 30 --no-pager"

echo ""
echo "=========================================="
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE${NC}"
echo "=========================================="
echo ""
echo "What to look for in logs:"
echo "  ✅ '⏱️ Running 15-Minute Crypto Strategy (BTC, ETH, SOL, XRP)...'"
echo "  ✅ '🧠 LLM APPROVED' when trades are approved"
echo "  ✅ '⚠️ Low liquidity, proceeding with market order' (this is GOOD!)"
echo "  ✅ '📉 CLOSING POSITION' when selling"
echo "  ✅ '⏰ TIME EXIT' or '🚨 MARKET CLOSING' for forced exits"
echo ""
echo "❌ Should NOT see:"
echo "  ❌ '🔥 Running Flash Crash Strategy...'"
echo "  ❌ '🎯 Scanning NegRisk markets...'"
echo "  ❌ '⏭️ Skipping directional (illiquid): Excessive slippage'"
echo ""
echo "Monitor live logs:"
echo "  ssh -i $SSH_KEY $AWS_HOST 'sudo journalctl -u polybot -f'"
echo ""
echo "Check active positions:"
echo "  ssh -i $SSH_KEY $AWS_HOST 'cd $REMOTE_DIR && grep \"Active positions\" bot_debug.log | tail -10'"
echo ""
echo "To rollback if needed:"
echo "  ssh -i $SSH_KEY $AWS_HOST 'cd $REMOTE_DIR && sudo systemctl stop polybot && cp -r backups/$BACKUP_NAME/* src/ && sudo systemctl start polybot'"
echo ""

