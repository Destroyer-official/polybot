# Deploy comprehensive fixes to AWS EC2
# This fixes ALL critical bugs that caused the $20 loss

$SERVER = "35.76.113.47"
$KEY = "money.pem"
$USER = "ubuntu"
$REMOTE_DIR = "/home/ubuntu/polybot"

Write-Host ""
Write-Host "🚨 DEPLOYING CRITICAL FIXES - $20 Loss Prevention" -ForegroundColor Red
Write-Host "=" * 80 -ForegroundColor Red
Write-Host ""

# Check if key file exists
if (-not (Test-Path $KEY)) {
    Write-Host "❌ Error: Key file '$KEY' not found" -ForegroundColor Red
    exit 1
}

# Display what will be fixed
Write-Host "🔧 CRITICAL BUGS BEING FIXED:" -ForegroundColor Yellow
Write-Host "   1. Position size mismatch (tracked wrong size)" -ForegroundColor White
Write-Host "   2. Risk manager size mismatch (wrong exposure)" -ForegroundColor White
Write-Host "   3. No balance validation (orders without funds)" -ForegroundColor White
Write-Host "   4. Order value precision error" -ForegroundColor White
Write-Host "   5. No error response handling" -ForegroundColor White
Write-Host ""

# Ask for confirmation
Write-Host "⚠️  This will restart the bot service" -ForegroundColor Yellow
$confirmation = Read-Host "Continue with deployment? (yes/no)"
if ($confirmation -ne "yes") {
    Write-Host "❌ Deployment cancelled" -ForegroundColor Red
    exit 0
}

Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "STARTING DEPLOYMENT" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Step 1: Create backup
Write-Host "📦 Step 1/5: Creating backup..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
ssh -i $KEY "${USER}@${SERVER}" "cd $REMOTE_DIR && mkdir -p backups/backup_$timestamp && cp src/fifteen_min_crypto_strategy.py backups/backup_$timestamp/"

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Backup created: backups/backup_$timestamp" -ForegroundColor Green
} else {
    Write-Host "   ❌ Backup failed" -ForegroundColor Red
    exit 1
}

# Step 2: Upload fixed file
Write-Host ""
Write-Host "📤 Step 2/5: Uploading fixed strategy file..." -ForegroundColor Yellow
scp -i $KEY "src/fifteen_min_crypto_strategy.py" "${USER}@${SERVER}:${REMOTE_DIR}/src/"

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ File uploaded successfully" -ForegroundColor Green
} else {
    Write-Host "   ❌ Upload failed" -ForegroundColor Red
    exit 1
}

# Step 3: Verify file
Write-Host ""
Write-Host "🔍 Step 3/5: Verifying uploaded file..." -ForegroundColor Yellow
$fileSize = ssh -i $KEY "${USER}@${SERVER}" "wc -c < $REMOTE_DIR/src/fifteen_min_crypto_strategy.py"
Write-Host "   File size: $fileSize bytes" -ForegroundColor White

if ($fileSize -gt 50000) {
    Write-Host "   ✅ File verification passed" -ForegroundColor Green
} else {
    Write-Host "   ❌ File seems too small, may be corrupted" -ForegroundColor Red
    exit 1
}

# Step 4: Restart service
Write-Host ""
Write-Host "🔄 Step 4/5: Restarting polybot service..." -ForegroundColor Yellow
ssh -i $KEY "${USER}@${SERVER}" "sudo systemctl restart polybot"

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ Service restarted" -ForegroundColor Green
} else {
    Write-Host "   ❌ Service restart failed" -ForegroundColor Red
    exit 1
}

# Wait for service to start
Write-Host "   ⏳ Waiting for service to start..." -ForegroundColor White
Start-Sleep -Seconds 5

# Step 5: Check service status
Write-Host ""
Write-Host "📊 Step 5/5: Checking service status..." -ForegroundColor Yellow
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
ssh -i $KEY "${USER}@${SERVER}" "sudo systemctl status polybot --no-pager -l | head -20"
Write-Host "=" * 80 -ForegroundColor Cyan

# Check if service is running
$serviceStatus = ssh -i $KEY "${USER}@${SERVER}" "sudo systemctl is-active polybot"
Write-Host ""

if ($serviceStatus -eq "active") {
    Write-Host "✅ Service is ACTIVE and RUNNING" -ForegroundColor Green
} else {
    Write-Host "❌ Service is NOT running: $serviceStatus" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check logs with:" -ForegroundColor Yellow
    Write-Host "   ssh -i $KEY ${USER}@${SERVER} 'sudo journalctl -u polybot -n 50'" -ForegroundColor White
    exit 1
}

# Display recent logs
Write-Host ""
Write-Host "📋 Recent logs (last 20 lines):" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
ssh -i $KEY "${USER}@${SERVER}" "sudo journalctl -u polybot -n 20 --no-pager"
Write-Host "=" * 80 -ForegroundColor Cyan

# Success summary
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Green
Write-Host "✅ DEPLOYMENT SUCCESSFUL" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Green
Write-Host ""
Write-Host "🔧 FIXES APPLIED:" -ForegroundColor Cyan
Write-Host "   ✅ Position tracking now uses ACTUAL placed size" -ForegroundColor Green
Write-Host "   ✅ Risk manager now tracks ACTUAL exposure" -ForegroundColor Green
Write-Host "   ✅ Balance validated before placing orders" -ForegroundColor Green
Write-Host "   ✅ Order value precision fixed (no more $0.9982 errors)" -ForegroundColor Green
Write-Host "   ✅ Error responses properly handled" -ForegroundColor Green
Write-Host "   ✅ Enhanced logging for debugging" -ForegroundColor Green
Write-Host ""
Write-Host "📊 MONITORING:" -ForegroundColor Cyan
Write-Host "   Live logs: ssh -i $KEY ${USER}@${SERVER} 'sudo journalctl -u polybot -f'" -ForegroundColor White
Write-Host "   Service status: ssh -i $KEY ${USER}@${SERVER} 'sudo systemctl status polybot'" -ForegroundColor White
Write-Host "   Restart: ssh -i $KEY ${USER}@${SERVER} 'sudo systemctl restart polybot'" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  IMPORTANT:" -ForegroundColor Yellow
Write-Host "   • Bot needs at least $1.01 USDC per trade" -ForegroundColor White
Write-Host "   • Position sizes now match actual placed orders" -ForegroundColor White
Write-Host "   • Failed orders won't create ghost positions" -ForegroundColor White
Write-Host "   • Check logs for 'ORDER PLACED SUCCESSFULLY' messages" -ForegroundColor White
Write-Host ""
Write-Host "🎯 NEXT STEPS:" -ForegroundColor Cyan
Write-Host "   1. Monitor logs for next trade signal" -ForegroundColor White
Write-Host "   2. Verify 'ORDER PLACED SUCCESSFULLY' appears" -ForegroundColor White
Write-Host "   3. Check position tracking shows correct size" -ForegroundColor White
Write-Host "   4. Ensure no more $0.9982 errors" -ForegroundColor White
Write-Host ""
Write-Host "💰 If you see 'Insufficient balance' errors:" -ForegroundColor Yellow
Write-Host "   Add at least $5-10 USDC to your wallet" -ForegroundColor White
Write-Host ""
Write-Host "🔄 To rollback if needed:" -ForegroundColor Yellow
Write-Host "   ssh -i $KEY ${USER}@${SERVER}" -ForegroundColor White
Write-Host "   cp $REMOTE_DIR/backups/backup_$timestamp/fifteen_min_crypto_strategy.py $REMOTE_DIR/src/" -ForegroundColor White
Write-Host "   sudo systemctl restart polybot" -ForegroundColor White
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Green
Write-Host "Deployment completed at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
Write-Host "=" * 80 -ForegroundColor Green
Write-Host ""
