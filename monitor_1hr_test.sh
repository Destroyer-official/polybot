#!/bin/bash
# 1-Hour Bot Performance Monitor
# Tracks trades, profits, and learning progress

echo "========================================="
echo "🤖 1-HOUR BOT PERFORMANCE TEST"
echo "========================================="
echo "Start Time: $(date)"
echo ""

# Record start time
START_TIME=$(date +%s)
END_TIME=$((START_TIME + 3600))  # 1 hour from now

echo "📊 Monitoring bot for 1 hour..."
echo "Will check every 5 minutes"
echo ""

# Function to get current stats
get_stats() {
    echo "=== $(date +%H:%M:%S) ==="
    
    # Check if bot is running
    ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl is-active polybot" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ Bot Status: RUNNING"
    else
        echo "❌ Bot Status: STOPPED"
        return
    fi
    
    # Get learning data
    echo ""
    echo "🧠 Learning Progress:"
    ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json 2>/dev/null | jq -r '\"Trades: \" + (.total_trades | tostring) + \" | Wins: \" + (.total_wins | tostring) + \" | Win Rate: \" + (if .total_trades > 0 then ((.total_wins / .total_trades * 100) | tostring | .[0:5]) + \"%\" else \"N/A\" end)'" 2>/dev/null || echo "No trades yet"
    
    # Get optimal parameters
    echo ""
    echo "⚙️ Current Parameters:"
    ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json 2>/dev/null | jq -r '.optimal_params | \"Take-Profit: \" + (.take_profit_pct | tonumber * 100 | tostring | .[0:4]) + \"% | Stop-Loss: \" + (.stop_loss_pct | tonumber * 100 | tostring | .[0:4]) + \"% | Position Size: \" + (.position_size_multiplier | tostring) + \"x\"'" 2>/dev/null || echo "Using defaults: TP=5%, SL=3%, Size=1.0x"
    
    # Get strategy performance
    echo ""
    echo "📈 Strategy Performance:"
    ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json 2>/dev/null | jq -r '.strategy_stats | to_entries[] | \"  \" + .key + \": \" + (.value.trades | tostring) + \" trades, \" + (if .value.trades > 0 then ((.value.wins / .value.trades * 100) | tostring | .[0:5]) + \"% win rate\" else \"N/A\" end)'" 2>/dev/null || echo "No strategy data yet"
    
    # Check recent activity
    echo ""
    echo "🔥 Recent Activity (last 5 min):"
    ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '5 minutes ago' --no-pager | grep -E 'LEARNED FROM TRADE|ORDER PLACED|TAKE PROFIT|STOP LOSS' | tail -5" 2>/dev/null || echo "No recent trades"
    
    echo ""
    echo "---"
    echo ""
}

# Initial stats
get_stats

# Monitor every 5 minutes
INTERVAL=300  # 5 minutes
CHECKS=12     # 12 checks = 1 hour

for i in $(seq 1 $CHECKS); do
    sleep $INTERVAL
    get_stats
done

# Final summary
echo "========================================="
echo "📊 FINAL 1-HOUR SUMMARY"
echo "========================================="
echo "End Time: $(date)"
echo ""

# Get final stats
echo "🧠 Final Learning Data:"
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json 2>/dev/null | jq '{
    total_trades,
    total_wins,
    win_rate: (if .total_trades > 0 then (.total_wins / .total_trades * 100) else 0 end),
    total_profit: .total_profit,
    best_win_streak,
    worst_loss_streak,
    optimal_params: {
        take_profit_pct: (.optimal_params.take_profit_pct | tonumber * 100),
        stop_loss_pct: (.optimal_params.stop_loss_pct | tonumber * 100),
        position_size_multiplier: .optimal_params.position_size_multiplier
    },
    strategy_stats
}'" 2>/dev/null || echo "No data available"

echo ""
echo "========================================="
echo "✅ 1-Hour Test Complete!"
echo "========================================="
