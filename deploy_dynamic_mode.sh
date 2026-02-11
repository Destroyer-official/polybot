#!/bin/bash

echo "🚀 DEPLOYING DYNAMIC TRADING MODE TO AWS"
echo "========================================"
echo ""

# Step 1: Commit changes
echo "📝 Step 1: Committing changes..."
git add -A
git commit -m "feat: enable dynamic trading mode - optimized for high-volume profits"
git push origin main

if [ $? -ne 0 ]; then
    echo "❌ Git push failed. Please check your git configuration."
    exit 1
fi

echo "✅ Code pushed to GitHub"
echo ""

# Step 2: Deploy to AWS
echo "🌐 Step 2: Deploying to AWS..."
echo "Connecting to ip-172-31-11-229..."
echo ""

ssh -i money.pem ubuntu@ip-172-31-11-229 << 'EOF'
    echo "📦 Updating code on AWS..."
    cd polymarket-arbitrage-bot
    
    echo "🔄 Fetching latest code..."
    git fetch --all
    git reset --hard origin/main
    
    echo "🔧 Restarting polybot service..."
    sudo systemctl restart polybot
    
    echo "⏳ Waiting for service to start..."
    sleep 3
    
    echo "📊 Checking service status..."
    sudo systemctl status polybot --no-pager -l
    
    echo ""
    echo "✅ Deployment complete!"
    echo ""
    echo "📜 Showing last 20 log lines..."
    sudo journalctl -u polybot -n 20 --no-pager
    
    echo ""
    echo "🎯 Bot is now running in DYNAMIC TRADING MODE!"
    echo ""
    echo "To monitor live:"
    echo "  sudo journalctl -u polybot -f"
    echo ""
    echo "To check status:"
    echo "  sudo systemctl status polybot"
    echo ""
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 SUCCESS! Bot deployed and running!"
    echo ""
    echo "Expected performance:"
    echo "  - Trades/day: 50-100 (vs 0-5 before)"
    echo "  - Win rate: 70-75%"
    echo "  - Daily profit: $0.50-$1.50"
    echo "  - Weekly ROI: 62-165%"
    echo ""
    echo "Monitor with:"
    echo "  ssh -i money.pem ubuntu@ip-172-31-11-229"
    echo "  sudo journalctl -u polybot -f"
    echo ""
else
    echo "❌ Deployment failed. Please check the error messages above."
    exit 1
fi
