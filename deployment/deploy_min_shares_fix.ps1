# Deploy minimum shares fix to AWS
# This removes the hardcoded 5-share minimum and uses $1 minimum order value instead

$ErrorActionPreference = "Stop"

Write-Host "=" * 80
Write-Host "DEPLOYING MINIMUM SHARES FIX TO AWS"
Write-Host "=" * 80

# Configuration
$SSH_KEY = "money.pem"
$SSH_HOST = "ubuntu@35.76.113.47"
$REMOTE_DIR = "/home/ubuntu/polybot"
$BACKUP_DIR = "backups/backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

# Create backup directory
Write-Host "`n[1/5] Creating backup directory..."
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null

# Files to upload
$FILES_TO_UPLOAD = @(
    "src/fifteen_min_crypto_strategy.py",
    "src/portfolio_risk_manager.py"
)

# Backup files from AWS
Write-Host "`n[2/5] Backing up current files from AWS..."
foreach ($file in $FILES_TO_UPLOAD) {
    $filename = Split-Path $file -Leaf
    Write-Host "  Backing up: $file"
    scp -i $SSH_KEY "${SSH_HOST}:${REMOTE_DIR}/${file}" "${BACKUP_DIR}/${filename}.bak" 2>$null
}

# Upload fixed files
Write-Host "`n[3/5] Uploading fixed files to AWS..."
foreach ($file in $FILES_TO_UPLOAD) {
    Write-Host "  Uploading: $file"
    scp -i $SSH_KEY $file "${SSH_HOST}:${REMOTE_DIR}/${file}"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to upload $file" -ForegroundColor Red
        exit 1
    }
}

# Restart the bot
Write-Host "`n[4/5] Restarting polybot service..."
ssh -i $SSH_KEY $SSH_HOST "sudo systemctl restart polybot"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to restart polybot service" -ForegroundColor Red
    exit 1
}

Write-Host "  Waiting for service to start..."
Start-Sleep -Seconds 5

# Check service status
Write-Host "`n[5/5] Checking service status..."
ssh -i $SSH_KEY $SSH_HOST "sudo systemctl status polybot --no-pager -l | head -20"

Write-Host "`n" + ("=" * 80)
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host ("=" * 80)
Write-Host ""
Write-Host "CHANGES DEPLOYED:"
Write-Host "  ✅ Removed hardcoded 5-share minimum"
Write-Host "  ✅ Using $1 minimum order value (Polymarket requirement)"
Write-Host "  ✅ Dynamic shares calculation based on price"
Write-Host ""
Write-Host "IMPORTANT: With $3.96 balance, bot can only place ~2 orders at $1 each"
Write-Host "Consider adding more funds to enable more trading"
Write-Host ""
Write-Host "BACKUP LOCATION: $BACKUP_DIR"
Write-Host ""
Write-Host "To check logs:"
Write-Host "  ssh -i $SSH_KEY $SSH_HOST 'journalctl -u polybot -f'"
Write-Host ""
