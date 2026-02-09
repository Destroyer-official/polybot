#!/bin/bash
# Upgrade bot to advanced 95%+ win rate strategy

echo "=========================================="
echo "UPGRADING TO ADVANCED STRATEGY"
echo "Target: 95%+ Win Rate, 4-6 Trades/Hour"
echo "=========================================="
echo ""

echo "Step 1: Deploying advanced momentum detector..."
scp -i money.pem src/advanced_momentum_detector.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/

echo "Step 2: Deploying high-probability bonding strategy..."
scp -i money.pem src/high_probability_bonding.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/

echo "Step 3: Restarting bot with new strategies..."
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"

echo ""
echo "✅ Upgrade complete!"
echo ""
echo "Monitoring logs for 30 seconds..."
sleep 5
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 50 --no-pager | tail -30"

echo ""
echo "=========================================="
echo "NEXT STEPS:"
echo "1. Monitor for 'CONFIRMED SIGNAL' messages"
echo "2. Check win rate after 2 hours"
echo "3. If win rate >90%, consider enabling real trading"
echo "=========================================="
