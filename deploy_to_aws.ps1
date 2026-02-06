# PowerShell Script to Deploy Bot to AWS
# Run this on your Windows machine

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DEPLOY POLYMARKET BOT TO AWS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if money.pem exists
if (-not (Test-Path "money.pem")) {
    Write-Host "ERROR: money.pem not found!" -ForegroundColor Red
    Write-Host "Please make sure money.pem is in the current directory" -ForegroundColor Yellow
    exit 1
}

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env not found!" -ForegroundColor Red
    Write-Host "Please make sure .env is in the current directory" -ForegroundColor Yellow
    exit 1
}

# Check if test_dry_run.sh exists
if (-not (Test-Path "test_dry_run.sh")) {
    Write-Host "ERROR: test_dry_run.sh not found!" -ForegroundColor Red
    Write-Host "Please make sure test_dry_run.sh is in the current directory" -ForegroundColor Yellow
    exit 1
}

Write-Host "Step 1: Copying .env file to AWS..." -ForegroundColor Green
scp -i "money.pem" .env ubuntu@18.207.221.6:~/polybot/.env
if ($LASTEXITCODE -eq 0) {
    Write-Host "  SUCCESS: .env copied" -ForegroundColor Green
} else {
    Write-Host "  FAILED: Could not copy .env" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 2: Copying test script to AWS..." -ForegroundColor Green
scp -i "money.pem" test_dry_run.sh ubuntu@18.207.221.6:~/polybot/test_dry_run.sh
if ($LASTEXITCODE -eq 0) {
    Write-Host "  SUCCESS: test_dry_run.sh copied" -ForegroundColor Green
} else {
    Write-Host "  FAILED: Could not copy test_dry_run.sh" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FILES DEPLOYED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. SSH to AWS: ssh -i `"money.pem`" ubuntu@18.207.221.6" -ForegroundColor White
Write-Host "2. Navigate: cd ~/polybot" -ForegroundColor White
Write-Host "3. Make executable: chmod +x test_dry_run.sh" -ForegroundColor White
Write-Host "4. Run test: ./test_dry_run.sh" -ForegroundColor White
Write-Host ""
Write-Host "Would you like to SSH to AWS now? (Y/N)" -ForegroundColor Yellow
$response = Read-Host

if ($response -eq "Y" -or $response -eq "y") {
    Write-Host ""
    Write-Host "Connecting to AWS..." -ForegroundColor Green
    ssh -i "money.pem" ubuntu@18.207.221.6
} else {
    Write-Host ""
    Write-Host "Deployment complete! SSH manually when ready." -ForegroundColor Cyan
}
