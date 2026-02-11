# Check Bot Status on AWS
# Quick script to check if bot is running and see recent activity

$AWS_HOST = "35.76.113.47"
$AWS_USER = "ubuntu"
$KEY_FILE = "money.pem"

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "BOT STATUS CHECK" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# Check service status
Write-Host "📊 Service Status:" -ForegroundColor Yellow
ssh -i $KEY_FILE "${AWS_USER}@${AWS_HOST}" "sudo systemctl status polybot.service --no-pager -l | head -20"
Write-Host ""

# Show recent logs (last 30 lines)
Write-Host "📜 Recent Logs (last 30 lines):" -ForegroundColor Yellow
ssh -i $KEY_FILE "${AWS_USER}@${AWS_HOST}" "sudo journalctl -u polybot.service -n 30 --no-pager"
Write-Host ""

# Check for errors
Write-Host "❌ Recent Errors:" -ForegroundColor Red
ssh -i $KEY_FILE "${AWS_USER}@${AWS_HOST}" "sudo journalctl -u polybot.service -n 100 --no-pager | grep -i 'error\|failed\|exception' | tail -10"
Write-Host ""

# Check for successful trades
Write-Host "✅ Recent Trades:" -ForegroundColor Green
ssh -i $KEY_FILE "${AWS_USER}@${AWS_HOST}" "sudo journalctl -u polybot.service -n 100 --no-pager | grep -i 'ORDER PLACED\|POSITION CLOSED\|TAKE PROFIT\|STOP LOSS' | tail -10"
Write-Host ""

# Check for risk manager blocks
Write-Host "🛡️ Risk Manager Activity:" -ForegroundColor Yellow
ssh -i $KEY_FILE "${AWS_USER}@${AWS_HOST}" "sudo journalctl -u polybot.service -n 100 --no-pager | grep -i 'RISK MANAGER' | tail -10"
Write-Host ""

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "To watch live logs, run:" -ForegroundColor Yellow
Write-Host "  ssh -i money.pem ubuntu@35.76.113.47 'sudo journalctl -u polybot.service -f'" -ForegroundColor White
Write-Host "=" * 80 -ForegroundColor Cyan
