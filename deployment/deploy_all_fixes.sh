#!/bin/bash
# Deploy ALL Recent Fixes to AWS
# Pushes the complete set of test & engine fixes from the audit session
# Date: 2026-02-10

set -e

echo "============================================"
echo "  DEPLOYING ALL FIXES TO AWS"
echo "============================================"
echo ""

# Configuration
AWS_HOST="ubuntu@35.76.113.47"
SSH_KEY="money.pem"
REMOTE_DIR="/home/ubuntu/polybot"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check SSH key
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}ERROR: SSH key not found: $SSH_KEY${NC}"
    exit 1
fi
chmod 600 "$SSH_KEY"

# Step 1: Test SSH
echo -e "${YELLOW}[1/6] Testing SSH connection...${NC}"
if ssh -i "$SSH_KEY" -o ConnectTimeout=10 "$AWS_HOST" "echo 'Connected'"; then
    echo -e "${GREEN}  ✅ SSH OK${NC}"
else
    echo -e "${RED}  ❌ SSH failed${NC}"
    exit 1
fi

# Step 2: Backup on AWS
echo ""
echo -e "${YELLOW}[2/6] Backing up current code on AWS...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "cd $REMOTE_DIR && cp -r src src.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true"
echo -e "${GREEN}  ✅ Backup created${NC}"

# Step 3: Upload all changed source files
echo ""
echo -e "${YELLOW}[3/6] Uploading fixed source files...${NC}"

# Core engine files (modified during audit)
scp -i "$SSH_KEY" src/llm_decision_engine.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}  ✅ llm_decision_engine.py (V1 compatibility shim - NEW)${NC}"

scp -i "$SSH_KEY" src/llm_decision_engine_v2.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}  ✅ llm_decision_engine_v2.py${NC}"

scp -i "$SSH_KEY" src/main_orchestrator.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}  ✅ main_orchestrator.py${NC}"

scp -i "$SSH_KEY" src/fifteen_min_crypto_strategy.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}  ✅ fifteen_min_crypto_strategy.py${NC}"

scp -i "$SSH_KEY" src/fund_manager.py "$AWS_HOST:$REMOTE_DIR/src/"
echo -e "${GREEN}  ✅ fund_manager.py${NC}"

# Upload config
scp -i "$SSH_KEY" config/config.py "$AWS_HOST:$REMOTE_DIR/config/"
echo -e "${GREEN}  ✅ config/config.py${NC}"

# Upload bot entry point
scp -i "$SSH_KEY" bot.py "$AWS_HOST:$REMOTE_DIR/"
echo -e "${GREEN}  ✅ bot.py${NC}"

# Upload .env (contains DRY_RUN=true)
scp -i "$SSH_KEY" .env "$AWS_HOST:$REMOTE_DIR/"
echo -e "${GREEN}  ✅ .env (DRY_RUN=true)${NC}"

# Step 4: Upload test files
echo ""
echo -e "${YELLOW}[4/6] Uploading tests...${NC}"
scp -i "$SSH_KEY" -r tests/ "$AWS_HOST:$REMOTE_DIR/tests/"
echo -e "${GREEN}  ✅ All test files uploaded${NC}"

# Step 5: Clear cache and restart
echo ""
echo -e "${YELLOW}[5/6] Clearing cache and restarting...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "cd $REMOTE_DIR && find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
echo -e "${GREEN}  ✅ Cache cleared${NC}"

ssh -i "$SSH_KEY" "$AWS_HOST" "sudo systemctl restart polybot"
sleep 5
echo -e "${GREEN}  ✅ Bot restarted${NC}"

# Step 6: Verify
echo ""
echo -e "${YELLOW}[6/6] Verifying...${NC}"
ssh -i "$SSH_KEY" "$AWS_HOST" "sudo systemctl status polybot --no-pager | head -15"

echo ""
echo "============================================"
echo -e "${GREEN}  ✅ DEPLOYMENT COMPLETE${NC}"
echo "============================================"
echo ""
echo "Monitor:  ssh -i $SSH_KEY $AWS_HOST 'sudo journalctl -u polybot -f'"
echo "Status:   ssh -i $SSH_KEY $AWS_HOST 'sudo systemctl status polybot'"
echo "Rollback: ssh -i $SSH_KEY $AWS_HOST 'cd $REMOTE_DIR && sudo systemctl stop polybot && cp -r src.backup.* src/ && sudo systemctl start polybot'"
echo ""
