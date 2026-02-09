#!/bin/bash
# Check bot performance after 8 hours of dry run
# Run this script: bash check_8hr_performance.sh

echo "=========================================="
echo "8-HOUR BOT PERFORMANCE CHECK"
echo "=========================================="
echo ""

# Check if bot is running
echo "1. Bot Status:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot --no-pager | head -5"
echo ""

# Get uptime
echo "2. Bot Uptime:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --no-pager | grep 'POLYMARKET ARBITRAGE BOT' | tail -1"
echo ""

# Check for trade statistics
echo "3. Trade Statistics:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --no-pager | grep -E '(trades_placed|trades_won|trades_lost|total_profit|PLACING ORDER|ORDER PLACED)' | tail -50"
echo ""

# Check for opportunities found
echo "4. Opportunities Detected:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --no-pager | grep -E '(ARBITRAGE FOUND|BULLISH SIGNAL|BEARISH SIGNAL|LLM SIGNAL)' | wc -l"
echo ""

# Check LLM decisions
echo "5. LLM Decisions Made:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --no-pager | grep 'LLM Decision' | tail -20"
echo ""

# Check for any errors
echo "6. Recent Errors:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --no-pager -p err | tail -20"
echo ""

# Get final statistics from logs
echo "7. Final Statistics Summary:"
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --no-pager | grep -A 10 'FINAL STATISTICS' | tail -15"
echo ""

echo "=========================================="
echo "Check complete!"
echo "=========================================="
