#!/bin/bash

# Deploy Trading Bot Fixes to AWS
# This script uploads the fixed code to AWS and restarts the bot

set -e  # Exit on error

echo "=========================================="
echo "DEPLOYING TRADING BOT FIXES TO AWS"
echo "=========================================="

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
ssh -i "$SSH_KEY" "$AWS_HOST" "cd $REMOTE_DIR && cp -r src src.backup.$(date +%Y%m%d_%H%M%S) || true"
echo -e "${GREEN}✅ Backup created${NC}"

echo -e "${YELLOW}Step 3: Uploading fixed files...${NC}"
# Upload the fixed strategy file
scp -i "$SSH_KEY" src/fifteen_min_crypto_strategy.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}✅ Uploaded fifteen_min_crypto_strategy.py${NC}"

# Upload the fixed orchestrator file
scp -i "$SSH_KEY" src/main_orchestrator.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}✅ Uploaded main_orchestrator.py${NC}"

# Upload test file
scp -i "$SSH_KEY" test_trading_fixes.py "$AWS_HOST:$REMOTE_DIR/"
echo -e "${GREEN}✅ Uploaded test_trading_fixes.py${NC}"

# Upload documentation
scp -i "$SSH_KEY" CRITICAL_FIXES_APPLIED.md "$AWS_HOST:$REMOTE_DIR/"
echo -e "${GREEN}✅ Uploaded CRITICAL_FIXES_APPLIED.md${NC}"

echo -e "${YELLOW}Step 4: Running tests on AWS...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "cd $REMOTE_DIR && python3 test_trading_fixes.py"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed on AWS${NC}"
else
    echo -e "${RED}❌ Tests failed on AWS${NC}"
    echo -e "${YELLOW}Rolling back...${NC}"
    ssh -i "$SSH_KEY" "$AWS_HOST" "cd $REMOTE_DIR && cp -r src.backup.* src/ || true"
    exit 1
fi

echo -e "${YELLOW}Step 5: Stopping bot service...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "sudo systemctl stop polybot || true"
echo -e "${GREEN}✅ Bot stopped${NC}"

echo -e "${YELLOW}Step 6: Starting bot service...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "sudo systemctl start polybot"
sleep 3
echo -e "${GREEN}✅ Bot started${NC}"

echo -e "${YELLOW}Step 7: Checking bot status...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "sudo systemctl status polybot --no-pager"

echo -e "${YELLOW}Step 8: Showing recent logs...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "sudo journalctl -u polybot -n 50 --no-pager"

echo ""
echo "=========================================="
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Monitor logs: ssh -i $SSH_KEY $AWS_HOST 'sudo journalctl -u polybot -f'"
echo "2. Check positions: ssh -i $SSH_KEY $AWS_HOST 'cd $REMOTE_DIR && grep \"Active positions\" bot_debug.log | tail -20'"
echo "3. Check trades: ssh -i $SSH_KEY $AWS_HOST 'cd $REMOTE_DIR && sqlite3 data/trade_history.db \"SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;\"'"
echo ""
echo "To rollback if needed:"
echo "ssh -i $SSH_KEY $AWS_HOST 'cd $REMOTE_DIR && sudo systemctl stop polybot && cp -r src.backup.* src/ && sudo systemctl start polybot'"
echo ""
