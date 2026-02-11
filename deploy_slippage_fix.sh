#!/bin/bash
# Deploy slippage fix to AWS server

SERVER_IP="your-server-ip-here"  # UPDATE THIS
KEY_FILE="money.pem"

echo "========================================="
echo "Deploying Slippage Fix"
echo "========================================="

if [ "$SERVER_IP" == "your-server-ip-here" ]; then
    echo "❌ Error: Please update SERVER_IP in this script!"
    exit 1
fi

# Copy fixed file
echo "📤 Copying fixed file to server..."
scp -i "$KEY_FILE" src/fifteen_min_crypto_strategy.py ubuntu@$SERVER_IP:/home/ubuntu/polybot/src/

# Restart bot
echo "🔄 Restarting bot..."
ssh -i "$KEY_FILE" ubuntu@$SERVER_IP << 'ENDSSH'
cd /home/ubuntu/polybot
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
sudo systemctl restart polybot
sleep 2
echo ""
echo "========================================="
echo "Recent Logs:"
echo "========================================="
sudo journalctl -u polybot -n 30 --no-pager
ENDSSH

echo ""
echo "========================================="
echo "✅ Deployment Complete!"
echo "========================================="
echo ""
echo "Monitor with: ssh -i $KEY_FILE ubuntu@$SERVER_IP 'sudo journalctl -u polybot -f'"
echo ""
echo "Look for:"
echo "  ✅ 'buy_both not applicable for directional trade - skipping'"
echo "  ✅ 'ENSEMBLE APPROVED: buy_yes' (for real trades)"
echo "  ✅ No more 98% slippage errors on buy_both"
echo ""
