# Deploy Critical Fixes to AWS
# Run this script to deploy the fixes to your AWS EC2 instance

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "DEPLOYING CRITICAL FIXES TO AWS" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Configuration
$AWS_HOST = "35.76.113.47"
$AWS_USER = "ubuntu"
$KEY_FILE = "money.pem"
$REMOTE_PATH = "~/polymarket-trading-bot"

# Files to deploy
$FILES = @(
    "src/fifteen_min_crypto_strategy.py",
    "src/portfolio_risk_manager.py"
)

Write-Host "📋 Fixes to deploy:" -ForegroundColor Yellow
Write-Host "  1. Risk manager - relaxed limits for small balances" -ForegroundColor White
Write-Host "  2. Learning engines - disabled (were breaking dynamic TP)" -ForegroundColor White
Write-Host "  3. Minimum size check - added pre-check before orders" -ForegroundColor White
Write-Host "  4. Slippage protection - skip trades with >50% slippage" -ForegroundColor White
Write-Host ""

# Confirm deployment
$confirm = Read-Host "Deploy these fixes to AWS? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "❌ Deployment cancelled" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🚀 Starting deployment..." -ForegroundColor Green
Write-Host ""

# Step 1: Copy files to AWS
Write-Host "📤 Step 1: Copying files to AWS..." -ForegroundColor Cyan
foreach ($file in $FILES) {
    Write-Host "   Copying $file..." -ForegroundColor White
    scp -i $KEY_FILE $file "${AWS_USER}@${AWS_HOST}:${REMOTE_PATH}/$file"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to copy $file" -ForegroundColor Red
        exit 1
    }
}
Write-Host "✅ Files copied successfully" -ForegroundColor Green
Write-Host ""

# Step 2: Restart bot service
Write-Host "🔄 Step 2: Restarting bot service..." -ForegroundColor Cyan
ssh -i $KEY_FILE "${AWS_USER}@${AWS_HOST}" "sudo systemctl restart polybot.service"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to restart service" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Service restarted successfully" -ForegroundColor Green
Write-Host ""

# Step 3: Check service status
Write-Host "📊 Step 3: Checking service status..." -ForegroundColor Cyan
ssh -i $KEY_FILE "${AWS_USER}@${AWS_HOST}" "sudo systemctl status polybot.service --no-pager -l"
Write-Host ""

# Step 4: Show recent logs
Write-Host "📜 Step 4: Showing recent logs..." -ForegroundColor Cyan
Write-Host "   (Press Ctrl+C to stop watching logs)" -ForegroundColor Yellow
Write-Host ""
ssh -i $KEY_FILE "${AWS_USER}@${AWS_HOST}" "sudo journalctl -u polybot.service -n 50 --no-pager"

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "✅ DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Next steps:" -ForegroundColor Yellow
Write-Host "  1. Monitor logs for 30 minutes: ssh -i money.pem ubuntu@35.76.113.47 'sudo journalctl -u polybot.service -f'" -ForegroundColor White
Write-Host "  2. Verify bot places trades successfully" -ForegroundColor White
Write-Host "  3. Check that risk manager allows trades" -ForegroundColor White
Write-Host "  4. Confirm bot skips high-slippage trades" -ForegroundColor White
Write-Host "  5. Watch for dynamic take profit working correctly" -ForegroundColor White
Write-Host ""
Write-Host "🎯 Expected behavior:" -ForegroundColor Yellow
Write-Host "  ✅ Bot should place orders within 30 minutes" -ForegroundColor White
Write-Host "  ✅ Risk manager should NOT block trades" -ForegroundColor White
Write-Host "  ✅ Bot should skip trades with >50% slippage" -ForegroundColor White
Write-Host "  ✅ Dynamic take profit should work (0.2% - 1% based on conditions)" -ForegroundColor White
Write-Host "  ✅ Bot should buy AND sell automatically" -ForegroundColor White
Write-Host ""
