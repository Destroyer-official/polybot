#!/bin/bash

# Monitor Trading Bot Performance on AWS
# Shows real-time stats, positions, and trades

set -e

# Configuration
AWS_HOST="ubuntu@35.76.113.47"
SSH_KEY="money.pem"
REMOTE_DIR="/home/ubuntu/polybot"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check SSH key
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}ERROR: SSH key not found: $SSH_KEY${NC}"
    exit 1
fi

chmod 600 "$SSH_KEY"

echo "=========================================="
echo "TRADING BOT PERFORMANCE MONITOR"
echo "=========================================="
echo ""

# Function to run remote command
run_remote() {
    ssh -i "$SSH_KEY" "$AWS_HOST" "$1"
}

# 1. Bot Status
echo -e "${BLUE}1. BOT STATUS${NC}"
echo "----------------------------------------"
run_remote "sudo systemctl status polybot --no-pager | head -10"
echo ""

# 2. Active Positions
echo -e "${BLUE}2. ACTIVE POSITIONS${NC}"
echo "----------------------------------------"
run_remote "cd $REMOTE_DIR && grep 'Active positions' bot_debug.log | tail -5 || echo 'No active positions found'"
echo ""

# 3. Recent Trades
echo -e "${BLUE}3. RECENT TRADES (Last 10)${NC}"
echo "----------------------------------------"
run_remote "cd $REMOTE_DIR && sqlite3 data/trade_history.db 'SELECT timestamp, market_id, side, entry_price, exit_price, profit FROM trades ORDER BY timestamp DESC LIMIT 10;' 2>/dev/null || echo 'No trades found'"
echo ""

# 4. Trade Statistics
echo -e "${BLUE}4. TRADE STATISTICS${NC}"
echo "----------------------------------------"
run_remote "cd $REMOTE_DIR && sqlite3 data/trade_history.db 'SELECT COUNT(*) as total_trades, SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins, SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses, SUM(profit) as total_profit FROM trades;' 2>/dev/null || echo 'No statistics available'"
echo ""

# 5. Exit Conditions Triggered
echo -e "${BLUE}5. EXIT CONDITIONS (Last 20)${NC}"
echo "----------------------------------------"
run_remote "cd $REMOTE_DIR && grep -E 'TAKE PROFIT|STOP LOSS|TIME EXIT|MARKET CLOSING' bot_debug.log | tail -20 || echo 'No exits found'"
echo ""

# 6. Order Placement
echo -e "${BLUE}6. ORDER PLACEMENT (Last 10)${NC}"
echo "----------------------------------------"
run_remote "cd $REMOTE_DIR && grep -E 'ORDER PLACED|ORDER FAILED' bot_debug.log | tail -10 || echo 'No orders found'"
echo ""

# 7. Opportunities Detected
echo -e "${BLUE}7. OPPORTUNITIES DETECTED (Last 10)${NC}"
echo "----------------------------------------"
run_remote "cd $REMOTE_DIR && grep -E 'SUM-TO-ONE|BINANCE.*SIGNAL|LLM SIGNAL' bot_debug.log | tail -10 || echo 'No opportunities found'"
echo ""

# 8. Errors and Warnings
echo -e "${BLUE}8. ERRORS AND WARNINGS (Last 10)${NC}"
echo "----------------------------------------"
run_remote "cd $REMOTE_DIR && grep -E 'ERROR|WARNING' bot_debug.log | tail -10 || echo 'No errors found'"
echo ""

# 9. Current Configuration
echo -e "${BLUE}9. CURRENT CONFIGURATION${NC}"
echo "----------------------------------------"
run_remote "cd $REMOTE_DIR && grep -E 'Take profit:|Stop loss:|Time-based exit:|Market closing exit:' bot_debug.log | tail -4 || echo 'Configuration not found'"
echo ""

# 10. System Resources
echo -e "${BLUE}10. SYSTEM RESOURCES${NC}"
echo "----------------------------------------"
run_remote "free -h | head -2 && df -h / | tail -1 && uptime"
echo ""

echo "=========================================="
echo -e "${GREEN}MONITORING COMPLETE${NC}"
echo "=========================================="
echo ""
echo "To watch live logs:"
echo "ssh -i $SSH_KEY $AWS_HOST 'sudo journalctl -u polybot -f'"
echo ""
echo "To restart bot:"
echo "ssh -i $SSH_KEY $AWS_HOST 'sudo systemctl restart polybot'"
echo ""
