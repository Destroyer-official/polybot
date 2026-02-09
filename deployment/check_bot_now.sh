#!/bin/bash
# Quick Bot Status Check

echo "========================================="
echo "🤖 BOT STATUS - $(date +%H:%M:%S)"
echo "========================================="

# Bot running?
echo "📊 Service Status:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl is-active polybot" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Bot is RUNNING"
else
    echo "❌ Bot is STOPPED"
    exit 1
fi

# Current markets
echo ""
echo "🎯 Current Markets:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 50 --no-pager | grep 'CURRENT.*market' | tail -4"

# Learning data
echo ""
echo "🧠 Learning Progress:"
if ssh -i money.pem ubuntu@35.76.113.47 "test -f /home/ubuntu/polybot/data/super_smart_learning.json"; then
    ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json | jq '{trades: .total_trades, wins: .total_wins, win_rate: (if .total_trades > 0 then (.total_wins / .total_trades * 100) else 0 end), profit: .total_profit, params: .optimal_params}'"
else
    echo "No trades yet - bot is waiting for opportunities"
fi

# Recent activity
echo ""
echo "🔥 Recent Activity (last 2 min):"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '2 minutes ago' --no-pager | grep -E 'LEARNED|ORDER PLACED|SIGNAL|ARBITRAGE' | tail -5" || echo "No recent trades"

echo ""
echo "========================================="
