# Deploy Ensemble Integration Fix to AWS
# Fixes the data format compatibility issue between ensemble and LLM engine

$ErrorActionPreference = "Stop"

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "🚀 DEPLOYING ENSEMBLE INTEGRATION FIX" -ForegroundColor Cyan
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host ""

# Configuration
$AWS_HOST = "ubuntu@35.76.113.47"
$KEY_FILE = "money.pem"
$REMOTE_DIR = "/home/ubuntu/polybot"

# Files to deploy
$FILES_TO_DEPLOY = @(
    "src/fifteen_min_crypto_strategy.py",
    "src/ensemble_decision_engine.py"
)

Write-Host "📋 Changes being deployed:" -ForegroundColor Yellow
Write-Host "  1. Fixed ensemble to accept both Dict and object types" -ForegroundColor White
Write-Host "  2. Strategy now passes PortfolioStateV2 object instead of dict" -ForegroundColor White
Write-Host "  3. Ensemble converts objects to dict for RL engine" -ForegroundColor White
Write-Host ""

# Verify files exist locally
Write-Host "🔍 Verifying local files..." -ForegroundColor Yellow
foreach ($file in $FILES_TO_DEPLOY) {
    if (Test-Path $file) {
        Write-Host "  ✅ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file NOT FOUND!" -ForegroundColor Red
        exit 1
    }
}
Write-Host ""

# Create backup on AWS
Write-Host "💾 Creating backup on AWS..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup_cmd = "mkdir -p $REMOTE_DIR/backups/backup_ensemble_fix_$timestamp && " +
              "cp $REMOTE_DIR/src/fifteen_min_crypto_strategy.py $REMOTE_DIR/backups/backup_ensemble_fix_$timestamp/ && " +
              "cp $REMOTE_DIR/src/ensemble_decision_engine.py $REMOTE_DIR/backups/backup_ensemble_fix_$timestamp/"

ssh -i $KEY_FILE $AWS_HOST $backup_cmd
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Backup created: backup_ensemble_fix_$timestamp" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ Backup failed, but continuing..." -ForegroundColor Yellow
}
Write-Host ""

# Upload files
Write-Host "📤 Uploading fixed files to AWS..." -ForegroundColor Yellow
foreach ($file in $FILES_TO_DEPLOY) {
    Write-Host "  Uploading $file..." -ForegroundColor White
    scp -i $KEY_FILE $file "${AWS_HOST}:${REMOTE_DIR}/$file"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    ✅ Uploaded successfully" -ForegroundColor Green
    } else {
        Write-Host "    ❌ Upload failed!" -ForegroundColor Red
        exit 1
    }
}
Write-Host ""

# Restart the service
Write-Host "🔄 Restarting polybot service..." -ForegroundColor Yellow
ssh -i $KEY_FILE $AWS_HOST "sudo systemctl restart polybot.service"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Service restarted successfully" -ForegroundColor Green
} else {
    Write-Host "  ❌ Service restart failed!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Wait for service to start
Write-Host "⏳ Waiting 5 seconds for service to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
Write-Host ""

# Check service status
Write-Host "📊 Checking service status..." -ForegroundColor Yellow
ssh -i $KEY_FILE $AWS_HOST "sudo systemctl status polybot.service --no-pager -l | head -20"
Write-Host ""

# Show recent logs
Write-Host "📜 Recent logs (30 lines)..." -ForegroundColor Yellow
ssh -i $KEY_FILE $AWS_HOST "sudo journalctl -u polybot.service -n 30 --no-pager"
Write-Host ""

Write-Host "=" -NoNewline -ForegroundColor Green
Write-Host ("=" * 59) -ForegroundColor Green
Write-Host "✅ DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Green
Write-Host ("=" * 59) -ForegroundColor Green
Write-Host ""

Write-Host "🎯 What to monitor:" -ForegroundColor Cyan
Write-Host "  1. Look for ENSEMBLE APPROVED in logs" -ForegroundColor White
Write-Host "  2. Should see 4 model votes: LLM, RL, Historical, Technical" -ForegroundColor White
Write-Host "  3. No more dict object has no attribute errors" -ForegroundColor White
Write-Host "  4. No more MarketContext object has no attribute get errors" -ForegroundColor White
Write-Host ""

Write-Host "📊 To monitor live logs, run:" -ForegroundColor Cyan
Write-Host "  ssh -i money.pem ubuntu@35.76.113.47" -ForegroundColor Yellow
Write-Host "  sudo journalctl -u polybot.service -f" -ForegroundColor Yellow
Write-Host ""
