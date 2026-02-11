# Deploy Full Integration to AWS
# This script deploys the fully integrated strategy to AWS

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "🚀 DEPLOYING FULL INTEGRATION TO AWS" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Configuration
$AWS_IP = "35.76.113.47"
$KEY_FILE = "money.pem"
$REMOTE_USER = "ubuntu"
$REMOTE_PATH = "/home/ubuntu/polybot"

# Files to deploy
$FILES = @(
    "src/fifteen_min_crypto_strategy.py"
)

Write-Host "📦 Files to deploy:" -ForegroundColor Yellow
foreach ($file in $FILES) {
    Write-Host "   - $file" -ForegroundColor White
}
Write-Host ""

# Check if key file exists
if (-not (Test-Path $KEY_FILE)) {
    Write-Host "❌ ERROR: Key file '$KEY_FILE' not found!" -ForegroundColor Red
    Write-Host "   Please make sure the key file is in the current directory." -ForegroundColor Red
    exit 1
}

# Deploy each file
Write-Host "🚀 Deploying files..." -ForegroundColor Yellow
foreach ($file in $FILES) {
    if (Test-Path $file) {
        Write-Host "   Uploading $file..." -ForegroundColor White
        scp -i $KEY_FILE $file "${REMOTE_USER}@${AWS_IP}:${REMOTE_PATH}/$file"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ $file uploaded successfully" -ForegroundColor Green
        } else {
            Write-Host "   ❌ Failed to upload $file" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "   ⚠️ Warning: $file not found, skipping" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "🔄 Restarting bot service..." -ForegroundColor Yellow
ssh -i $KEY_FILE "${REMOTE_USER}@${AWS_IP}" "sudo systemctl restart polybot.service"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Bot service restarted successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to restart bot service" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "✅ DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Monitor the bot with:" -ForegroundColor Yellow
Write-Host "   ssh -i $KEY_FILE ${REMOTE_USER}@${AWS_IP}" -ForegroundColor White
Write-Host "   sudo journalctl -u polybot.service -f" -ForegroundColor White
Write-Host ""
Write-Host "🔍 What to look for:" -ForegroundColor Yellow
Write-Host "   ✅ '🧠 ALL LEARNING SYSTEMS: ACTIVE AND INTEGRATED'" -ForegroundColor White
Write-Host "   ✅ '📊 Using config BASE: TP=X%, SL=Y%'" -ForegroundColor White
Write-Host "   ✅ '🎯 FINAL Dynamic TP: X% (base: Y%)'" -ForegroundColor White
Write-Host "   ✅ '❌ DYNAMIC STOP LOSS' (with daily loss tracking)" -ForegroundColor White
Write-Host "   ✅ '🚨 CIRCUIT BREAKER' (if 3 consecutive losses)" -ForegroundColor White
Write-Host ""
Write-Host "⏱️ Monitor for 1 hour to verify all systems working" -ForegroundColor Yellow
Write-Host ""
