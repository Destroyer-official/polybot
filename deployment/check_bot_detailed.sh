#!/bin/bash
# Detailed bot status check

echo "========================================="
echo "BOT STATUS CHECK - $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "========================================="
echo ""

echo "1. SERVICE STATUS:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot --no-pager | head -10"
echo ""

echo "2. CURRENT MARKETS (last 30 seconds):"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '30 seconds ago' --no-pager | grep 'CURRENT.*market'"
echo ""

echo "3. BINANCE CONNECTION:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '5 minutes ago' --no-pager | grep -i 'binance' | tail -5"
echo ""

echo "4. LEARNING DATA:"
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && if [ -f data/super_smart_learning.json ]; then echo 'Learning file exists:'; cat data/super_smart_learning.json | head -20; else echo 'No learning data yet (0 trades)'; fi"
echo ""

echo "5. RECENT ACTIVITY (last 20 lines):"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 20 --no-pager"
echo ""

echo "========================================="
echo "CHECK COMPLETE"
echo "========================================="
