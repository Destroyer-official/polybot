#!/bin/bash
# Quick bot status checker
# Usage: ./check_bot_status.sh

echo "========================================="
echo "POLYMARKET BOT STATUS"
echo "========================================="
echo ""

# Check if bot is running
echo "🤖 Bot Service Status:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot | grep Active"
echo ""

# Check balance
echo "💰 Balance:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 1000 --no-pager | grep 'Total Available' | tail -1"
echo ""

# Check active positions
echo "📊 Active Positions:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 100 --no-pager | grep 'Active positions' | tail -1"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 100 --no-pager | grep 'entry=' | tail -5"
echo ""

# Check learning progress
echo "🧠 Learning Progress:"
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/adaptive_learning.json | grep -E 'total_trades|winning_trades|losing_trades|total_profit' | head -4"
echo ""

# Check recent activity
echo "📈 Recent Activity (last 5 minutes):"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '5 minutes ago' --no-pager | grep -E 'TAKE PROFIT|STOP LOSS|TIME EXIT|MARKET CLOSING|ORDER PLACED|position closed' | tail -10"
echo ""

# Check for errors
echo "⚠️ Recent Errors:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '5 minutes ago' --no-pager | grep -i error | tail -5"
echo ""

echo "========================================="
echo "✅ Status check complete!"
echo "========================================="
