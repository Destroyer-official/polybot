# Deploy order value precision fix to AWS EC2
# This fixes the "invalid amount for a marketable BUY order ($0.9982), min size: $1" error

$SERVER = "35.76.113.47"
$KEY = "money.pem"
$USER = "ubuntu"
$REMOTE_DIR = "/home/ubuntu/polybot"

Write-Host "🚀 Deploying Order Value Precision Fix..." -ForegroundColor Cyan
Write-Host ""

# Check if key file exists
if (-not (Test-Path $KEY)) {
    Write-Host "❌ Error: Key file '$KEY' not found" -ForegroundColor Red
    exit 1
}

# Create backup on server
Write-Host "📦 Creating backup..." -ForegroundColor Yellow
ssh -i $KEY "${USER}@${SERVER}" "cd $REMOTE_DIR && mkdir -p backups/backup_`$(date +%Y%m%d_%H%M%S) && cp src/fifteen_min_crypto_strategy.py backups/backup_`$(date +%Y%m%d_%H%M%S)/"

# Upload fixed file
Write-Host "📤 Uploading fixed strategy file..." -ForegroundColor Yellow
scp -i $KEY "src/fifteen_min_crypto_strategy.py" "${USER}@${SERVER}:${REMOTE_DIR}/src/"

# Restart the bot service
Write-Host "🔄 Restarting polybot service..." -ForegroundColor Yellow
ssh -i $KEY "${USER}@${SERVER}" "sudo systemctl restart polybot"

# Wait for service to start
Write-Host "⏳ Waiting for service to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Check service status
Write-Host ""
Write-Host "📊 Service Status:" -ForegroundColor Cyan
ssh -i $KEY "${USER}@${SERVER}" "sudo systemctl status polybot --no-pager -l"

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 To view logs, run:" -ForegroundColor Cyan
Write-Host "   ssh -i $KEY ${USER}@${SERVER} 'sudo journalctl -u polybot -f'" -ForegroundColor White
Write-Host ""
Write-Host "🔧 What was fixed:" -ForegroundColor Cyan
Write-Host "   • Order value calculation now uses math.ceil() to round UP shares" -ForegroundColor White
Write-Host "   • Ensures price × shares >= `$1.00 after all rounding" -ForegroundColor White
Write-Host "   • Fixes '$0.9982 < $1.00' API rejection error" -ForegroundColor White
Write-Host ""
