# Deploy Liquidity & Strategy Fixes to AWS
# Fixes: 98% slippage blocking, wrong strategies running, positions not closing

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "DEPLOYING LIQUIDITY & STRATEGY FIXES" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Fixes Applied:" -ForegroundColor Yellow
Write-Host "  ✅ Increased slippage tolerance (5% → 50%)" -ForegroundColor Green
Write-Host "  ✅ Disabled all strategies except 15-min crypto" -ForegroundColor Green
Write-Host "  ✅ Faster position exits (10 min, 2 min before close)" -ForegroundColor Green
Write-Host "  ✅ Bot now ONLY trades BTC/ETH/SOL/XRP 15-min markets" -ForegroundColor Green
Write-Host ""

# Configuration
$AWS_HOST = "ubuntu@35.76.113.47"
$SSH_KEY = "money.pem"
$REMOTE_DIR = "/home/ubuntu/polybot"

# Check if SSH key exists
if (-not (Test-Path $SSH_KEY)) {
    Write-Host "ERROR: SSH key not found: $SSH_KEY" -ForegroundColor Red
    exit 1
}

Write-Host "Step 1: Testing SSH connection..." -ForegroundColor Yellow
$sshTest = ssh -i $SSH_KEY -o ConnectTimeout=10 $AWS_HOST "echo 'SSH connection successful'" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ SSH connection successful" -ForegroundColor Green
} else {
    Write-Host "❌ SSH connection failed" -ForegroundColor Red
    Write-Host $sshTest -ForegroundColor Red
    exit 1
}

Write-Host "Step 2: Backing up current code on AWS..." -ForegroundColor Yellow
$BACKUP_NAME = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
ssh -i $SSH_KEY $AWS_HOST "cd $REMOTE_DIR && mkdir -p backups && cp -r src backups/$BACKUP_NAME || true"
Write-Host "✅ Backup created: backups/$BACKUP_NAME" -ForegroundColor Green

Write-Host "Step 3: Uploading fixed files..." -ForegroundColor Yellow

# Upload the fixed strategy file (main fix for slippage + exits)
Write-Host "  → Uploading fifteen_min_crypto_strategy.py..."
scp -i $SSH_KEY src/fifteen_min_crypto_strategy.py "${AWS_HOST}:${REMOTE_DIR}/src/"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Uploaded fifteen_min_crypto_strategy.py" -ForegroundColor Green
} else {
    Write-Host "  ❌ Failed to upload fifteen_min_crypto_strategy.py" -ForegroundColor Red
    exit 1
}

# Upload the fixed orchestrator file (disables other strategies)
Write-Host "  → Uploading main_orchestrator.py..."
scp -i $SSH_KEY src/main_orchestrator.py "${AWS_HOST}:${REMOTE_DIR}/src/"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Uploaded main_orchestrator.py" -ForegroundColor Green
} else {
    Write-Host "  ❌ Failed to upload main_orchestrator.py" -ForegroundColor Red
    exit 1
}

# Upload order book analyzer (slippage calculation)
Write-Host "  → Uploading order_book_analyzer.py..."
scp -i $SSH_KEY src/order_book_analyzer.py "${AWS_HOST}:${REMOTE_DIR}/src/"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Uploaded order_book_analyzer.py" -ForegroundColor Green
} else {
    Write-Host "  ❌ Failed to upload order_book_analyzer.py" -ForegroundColor Red
    exit 1
}

Write-Host "Step 4: Stopping bot service..." -ForegroundColor Yellow
ssh -i $SSH_KEY $AWS_HOST "sudo systemctl stop polybot || true"
Start-Sleep -Seconds 2
Write-Host "✅ Bot stopped" -ForegroundColor Green

Write-Host "Step 5: Starting bot service..." -ForegroundColor Yellow
ssh -i $SSH_KEY $AWS_HOST "sudo systemctl start polybot"
Start-Sleep -Seconds 3
Write-Host "✅ Bot started" -ForegroundColor Green

Write-Host "Step 6: Checking bot status..." -ForegroundColor Yellow
ssh -i $SSH_KEY $AWS_HOST "sudo systemctl status polybot --no-pager | head -20"

Write-Host "Step 7: Showing recent logs (last 30 lines)..." -ForegroundColor Yellow
Write-Host ""
ssh -i $SSH_KEY $AWS_HOST "sudo journalctl -u polybot -n 30 --no-pager"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "What to look for in logs:" -ForegroundColor Yellow
Write-Host "  ✅ '⏱️ Running 15-Minute Crypto Strategy (BTC, ETH, SOL, XRP)...'" -ForegroundColor Green
Write-Host "  ✅ '🧠 LLM APPROVED' when trades are approved" -ForegroundColor Green
Write-Host "  ✅ '⚠️ Low liquidity, proceeding with market order' (this is GOOD!)" -ForegroundColor Green
Write-Host "  ✅ '📉 CLOSING POSITION' when selling" -ForegroundColor Green
Write-Host "  ✅ '⏰ TIME EXIT' or '🚨 MARKET CLOSING' for forced exits" -ForegroundColor Green
Write-Host ""
Write-Host "❌ Should NOT see:" -ForegroundColor Yellow
Write-Host "  ❌ '🔥 Running Flash Crash Strategy...'" -ForegroundColor Red
Write-Host "  ❌ '🎯 Scanning NegRisk markets...'" -ForegroundColor Red
Write-Host "  ❌ '⏭️ Skipping directional (illiquid): Excessive slippage'" -ForegroundColor Red
Write-Host ""
Write-Host "Monitor live logs:" -ForegroundColor Yellow
Write-Host "  ssh -i $SSH_KEY $AWS_HOST 'sudo journalctl -u polybot -f'" -ForegroundColor Cyan
Write-Host ""
Write-Host "Check active positions:" -ForegroundColor Yellow
Write-Host "  ssh -i $SSH_KEY $AWS_HOST 'cd $REMOTE_DIR && grep ""Active positions"" bot_debug.log | tail -10'" -ForegroundColor Cyan
Write-Host ""
Write-Host "To rollback if needed:" -ForegroundColor Yellow
Write-Host "  ssh -i $SSH_KEY $AWS_HOST 'cd $REMOTE_DIR && sudo systemctl stop polybot && cp -r backups/$BACKUP_NAME/* src/ && sudo systemctl start polybot'" -ForegroundColor Cyan
Write-Host ""
