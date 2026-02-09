# Trading Bot Quick Reference Guide

## 🚀 Quick Start

### Deploy Fixes to AWS
```bash
# Make scripts executable
chmod +x deploy_fixes_to_aws.sh monitor_bot_performance.sh

# Deploy fixes
./deploy_fixes_to_aws.sh

# Monitor performance
./monitor_bot_performance.sh
```

### Manual Deployment
```bash
# SSH into AWS
ssh -i money.pem ubuntu@35.76.113.47

# Navigate to bot directory
cd /home/ubuntu/polybot

# Pull latest code (if using git)
git pull origin main

# Restart bot
sudo systemctl restart polybot

# Check status
sudo systemctl status polybot

# Watch logs
sudo journalctl -u polybot -f
```

## 📊 Monitoring Commands

### Check Bot Status
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot"
```

### View Live Logs
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -f"
```

### Check Active Positions
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep 'Active positions' bot_debug.log | tail -20"
```

### Check Recent Trades
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && sqlite3 data/trade_history.db 'SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;'"
```

### Check Trade Statistics
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && sqlite3 data/trade_history.db 'SELECT COUNT(*) as total, SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins, SUM(profit) as total_profit FROM trades;'"
```

### Check Exit Conditions
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep -E 'TAKE PROFIT|STOP LOSS|TIME EXIT|MARKET CLOSING' bot_debug.log | tail -20"
```

## 🔧 Troubleshooting

### Bot Not Starting
```bash
# Check service status
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot"

# Check logs for errors
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 100"

# Restart service
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"
```

### Bot Not Buying
```bash
# Check if markets are found
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep 'Found.*CURRENT.*markets' bot_debug.log | tail -10"

# Check if opportunities are detected
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep -E 'SUM-TO-ONE|BINANCE.*SIGNAL' bot_debug.log | tail -10"

# Check order placement
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep -E 'ORDER PLACED|ORDER FAILED' bot_debug.log | tail -10"
```

### Bot Not Selling
```bash
# Check if exit conditions are being checked
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep 'Checking exit for' bot_debug.log | tail -20"

# Check if positions are tracked
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep 'Active positions' bot_debug.log | tail -10"

# Check if exits are triggered
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep -E 'TAKE PROFIT|STOP LOSS|TIME EXIT|MARKET CLOSING' bot_debug.log | tail -20"
```

### Bot Losing Money
```bash
# Check win rate
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && sqlite3 data/trade_history.db 'SELECT COUNT(*) as total, SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins, SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses FROM trades;'"

# Check average profit per trade
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && sqlite3 data/trade_history.db 'SELECT AVG(profit) as avg_profit FROM trades;'"

# Check recent losing trades
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && sqlite3 data/trade_history.db 'SELECT * FROM trades WHERE profit < 0 ORDER BY timestamp DESC LIMIT 10;'"
```

## ⚙️ Configuration

### Current Settings (FIXED)
- **Take-Profit**: 1% (realistic for 15-min trades)
- **Stop-Loss**: 2% (tight control)
- **Time-Based Exit**: 12 minutes (before market closes)
- **Market Closing Exit**: 2 minutes before close
- **Trade Size**: $5 per trade
- **Max Positions**: 3 concurrent

### Adjust Settings (if needed)
Edit `src/main_orchestrator.py`:
```python
self.fifteen_min_strategy = FifteenMinuteCryptoStrategy(
    clob_client=self.clob_client,
    trade_size=5.0,           # Change trade size
    take_profit_pct=0.01,     # Change take-profit (0.01 = 1%)
    stop_loss_pct=0.02,       # Change stop-loss (0.02 = 2%)
    max_positions=3,          # Change max positions
    sum_to_one_threshold=1.01,# Change arbitrage threshold
    dry_run=config.dry_run,
    llm_decision_engine=self.llm_decision_engine
)
```

Then redeploy:
```bash
./deploy_fixes_to_aws.sh
```

## 📈 Performance Metrics

### Key Metrics to Track
1. **Win Rate**: % of profitable trades
2. **Average Profit**: Average profit per trade
3. **Total Profit**: Cumulative profit
4. **Max Drawdown**: Largest loss
5. **Position Age**: How long positions are held
6. **Exit Reasons**: Why positions are closed

### Expected Performance
- **Win Rate**: 60-70% (with tight stop-loss)
- **Average Profit**: 0.5-1.5% per trade
- **Position Age**: 5-12 minutes average
- **Exit Reasons**: 
  - Take-Profit: 40-50%
  - Stop-Loss: 20-30%
  - Time-Based: 20-30%
  - Market Closing: 5-10%

## 🔐 Security

### SSH Key Management
```bash
# Set correct permissions
chmod 600 money.pem

# Test connection
ssh -i money.pem ubuntu@35.76.113.47 "echo 'Connection successful'"
```

### Environment Variables
Check `.env` file for:
- `POLY_API_KEY`: Polymarket API key
- `POLY_API_SECRET`: Polymarket API secret
- `POLY_API_PASSPHRASE`: Polymarket API passphrase
- `PRIVATE_KEY`: Wallet private key
- `WALLET_ADDRESS`: Wallet address

## 📞 Support

### Common Issues

**Issue**: Bot not connecting to Binance
**Solution**: Check if Binance is blocked (451 error). Bot will auto-switch to Binance.US

**Issue**: No markets found
**Solution**: 15-minute markets only exist for BTC, ETH, SOL, XRP. Check if markets are active.

**Issue**: Orders failing
**Solution**: Check balance, check allowances, check API credentials

**Issue**: Positions not closing
**Solution**: Verify fixes are applied: `python test_trading_fixes.py`

### Get Help
1. Run tests: `python test_trading_fixes.py`
2. Check logs: `./monitor_bot_performance.sh`
3. Review documentation: `CRITICAL_FIXES_APPLIED.md`

## 📝 Useful Aliases

Add to `~/.bashrc` for quick access:
```bash
alias bot-status='ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot"'
alias bot-logs='ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -f"'
alias bot-restart='ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"'
alias bot-positions='ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep \"Active positions\" bot_debug.log | tail -20"'
alias bot-trades='ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && sqlite3 data/trade_history.db \"SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;\""'
```

Then use:
```bash
bot-status      # Check status
bot-logs        # Watch logs
bot-restart     # Restart bot
bot-positions   # Check positions
bot-trades      # Check trades
```

---

**Last Updated**: February 9, 2026
**Version**: 2.0 (Fixed)
