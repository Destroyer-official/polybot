# Deploy position sizing fix to AWS
# This fixes the bot trying to place $25 orders with only $3.96 balance

$ErrorActionPreference = "Stop"

Write-Host "=" * 80
Write-Host "DEPLOYING POSITION SIZING FIX TO AWS"
Write-Host "=" * 80

# Configuration
$SSH_KEY = "money.pem"
$SSH_HOST = "ubuntu@35.76.113.47"
$REMOTE_DIR = "/home/ubuntu/polybot"
$BACKUP_DIR = "backups/backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

# Create backup directory
Write-Host "`n[1/6] Creating backup directory..."
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null

# Files to upload
$FILES_TO_UPLOAD = @(
    "src/fifteen_min_crypto_strategy.py",
    "src/main_orchestrator.py"
)

# Backup files from AWS
Write-Host "`n[2/6] Backing up current files from AWS..."
foreach ($file in $FILES_TO_UPLOAD) {
    $filename = Split-Path $file -Leaf
    Write-Host "  Backing up: $file"
    scp -i $SSH_KEY "${SSH_HOST}:${REMOTE_DIR}/${file}" "${BACKUP_DIR}/${filename}.bak" 2>$null
}

# Upload fixed files
Write-Host "`n[3/6] Uploading fixed files to AWS..."
foreach ($file in $FILES_TO_UPLOAD) {
    Write-Host "  Uploading: $file"
    scp -i $SSH_KEY $file "${SSH_HOST}:${REMOTE_DIR}/${file}"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to upload $file" -ForegroundColor Red
        exit 1
    }
}

# Update .env file to set TARGET_BALANCE to actual balance
Write-Host "`n[4/6] Updating TARGET_BALANCE in .env to actual balance ($3.96)..."
ssh -i $SSH_KEY $SSH_HOST "cd $REMOTE_DIR && cp .env .env.bak && sed -i 's/^TARGET_BALANCE=.*/TARGET_BALANCE=3.96/' .env && echo 'Updated TARGET_BALANCE to 3.96' && grep TARGET_BALANCE .env"

# Restart the bot
Write-Host "`n[5/6] Restarting polybot service..."
ssh -i $SSH_KEY $SSH_HOST "sudo systemctl restart polybot"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to restart polybot service" -ForegroundColor Red
    exit 1
}

Write-Host "  Waiting for service to start..."
Start-Sleep -Seconds 5

# Check service status
Write-Host "`n[6/6] Checking service status..."
ssh -i $SSH_KEY $SSH_HOST "sudo systemctl status polybot --no-pager -l | head -20"

Write-Host "`n" + ("=" * 80)
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host ("=" * 80)
Write-Host ""
Write-Host "CHANGES DEPLOYED:"
Write-Host "  ✅ Dynamic position sizing based on actual balance"
Write-Host "  ✅ Risk manager respects available capital"
Write-Host "  ✅ TARGET_BALANCE set to $3.96 (actual balance)"
Write-Host "  ✅ Position sizes will be ~$1.19 per trade (30% of $3.96)"
Write-Host ""
Write-Host "BACKUP LOCATION: $BACKUP_DIR"
Write-Host ""
Write-Host "To check logs:"
Write-Host "  ssh -i $SSH_KEY $SSH_HOST 'journalctl -u polybot -f'"
Write-Host ""
Write-Host "To check recent trades:"
Write-Host "  ssh -i $SSH_KEY $SSH_HOST 'journalctl -u polybot --since \"5 minutes ago\" | grep -E \"PLACING ORDER|RISK MANAGER\"'"
Write-Host ""
