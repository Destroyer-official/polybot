#!/bin/bash

echo "🚀 UPLOADING FILES DIRECTLY TO AWS"
echo "==================================="
echo ""

AWS_HOST="ubuntu@35.76.113.47"
KEY_FILE="money.pem"
REMOTE_PATH="/home/ubuntu/polymarket-arbitrage-bot"

# First, check if directory exists and create if needed
echo "📁 Checking remote directory..."
ssh -i "$KEY_FILE" "$AWS_HOST" "mkdir -p $REMOTE_PATH/src"
echo "✅ Directory ready"
echo ""

# List of files to upload
FILES=(
    ".env"
    "src/fifteen_min_crypto_strategy.py"
    "src/main_orchestrator.py"
    "monitor_premium.py"
)

echo "📁 Files to upload:"
for file in "${FILES[@]}"; do
    echo "   - $file"
done
echo ""

# Upload each file
for file in "${FILES[@]}"; do
    echo "📤 Uploading $file..."
    
    remote_file="$REMOTE_PATH/$file"
    
    # Use SCP to upload
    scp -i "$KEY_FILE" "$file" "${AWS_HOST}:${remote_file}"
    
    if [ $? -eq 0 ]; then
        echo "   ✅ Uploaded successfully"
    else
        echo "   ❌ Upload failed"
        exit 1
    fi
done

echo ""
echo "🔄 Restarting bot on AWS..."

# Restart the bot
ssh -i "$KEY_FILE" "$AWS_HOST" "sudo systemctl restart polybot"

if [ $? -eq 0 ]; then
    echo "✅ Bot restarted successfully!"
else
    echo "❌ Restart failed"
    exit 1
fi

echo ""
echo "📊 Checking bot status..."
ssh -i "$KEY_FILE" "$AWS_HOST" "sudo systemctl status polybot --no-pager -l"

echo ""
echo "📜 Last 20 log lines:"
ssh -i "$KEY_FILE" "$AWS_HOST" "sudo journalctl -u polybot -n 20 --no-pager"

echo ""
echo "🎉 DEPLOYMENT COMPLETE!"
echo ""
echo "To monitor live logs, run:"
echo "   ssh -i money.pem ubuntu@35.76.113.47 'sudo journalctl -u polybot -f'"
echo ""
