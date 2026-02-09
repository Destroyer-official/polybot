#!/bin/bash
# Monitor bot for 1 hour and generate report

echo "========================================="
echo "STARTING 1-HOUR DRY RUN TEST"
echo "========================================="
echo "Start time: $(date)"
echo ""

# Record start time
START_TIME=$(date +%s)
END_TIME=$((START_TIME + 3600))  # 1 hour from now

echo "Bot will run until: $(date -d @$END_TIME)"
echo ""
echo "Monitoring bot activity..."
echo "Press Ctrl+C to stop early and generate report"
echo ""

# Monitor for 1 hour
while [ $(date +%s) -lt $END_TIME ]; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    REMAINING=$((END_TIME - CURRENT_TIME))
    
    # Show progress every 5 minutes
    if [ $((ELAPSED % 300)) -eq 0 ]; then
        echo "=== $(date) - Elapsed: $((ELAPSED/60)) min, Remaining: $((REMAINING/60)) min ==="
        
        # Check for trades
        ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '5 minutes ago' --no-pager | grep -E 'LEARNED FROM TRADE|ORDER PLACED|position closed' | tail -5"
        
        # Check learning progress
        echo "Learning status:"
        ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && if [ -f data/super_smart_learning.json ]; then cat data/super_smart_learning.json | jq '{trades: .total_trades, wins: .total_wins, profit: .total_profit}'; else echo 'No trades yet'; fi"
        echo ""
    fi
    
    sleep 60  # Check every minute
done

echo ""
echo "========================================="
echo "1-HOUR TEST COMPLETE!"
echo "========================================="
echo "End time: $(date)"
echo ""

# Generate final report
echo "Generating final report..."
echo ""

ssh -i money.pem ubuntu@35.76.113.47 << 'ENDSSH'
cd /home/ubuntu/polybot

echo "=== FINAL REPORT ==="
echo ""

# Check if learning file exists
if [ -f data/super_smart_learning.json ]; then
    echo "Learning Data:"
    cat data/super_smart_learning.json | jq '.'
    echo ""
    
    echo "Summary:"
    cat data/super_smart_learning.json | jq '{
        total_trades: .total_trades,
        total_wins: .total_wins,
        total_losses: (.total_trades - .total_wins),
        win_rate: (if .total_trades > 0 then (.total_wins / .total_trades * 100) else 0 end),
        total_profit_pct: .total_profit,
        best_win_streak: .best_win_streak,
        worst_loss_streak: .worst_loss_streak,
        optimal_params: .optimal_params
    }'
else
    echo "No trades were executed during the test period."
    echo "This could mean:"
    echo "1. No profitable opportunities were found"
    echo "2. Bot is waiting for better market conditions"
    echo "3. Confidence thresholds not met"
fi

echo ""
echo "Recent bot activity:"
sudo journalctl -u polybot --since '1 hour ago' --no-pager | grep -E 'LEARNED|ORDER|position|SIGNAL' | tail -20

ENDSSH

echo ""
echo "========================================="
echo "Report complete!"
echo "========================================="
