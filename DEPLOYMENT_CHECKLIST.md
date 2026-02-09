# Trading Bot Deployment Checklist

## ✅ Pre-Deployment Verification

### 1. Local Testing
- [ ] Run `python test_trading_fixes.py` - All tests pass
- [ ] Review `CRITICAL_FIXES_APPLIED.md` - Understand all changes
- [ ] Check `.env` file - All credentials present
- [ ] Verify SSH key - `money.pem` exists and has correct permissions

### 2. Code Review
- [ ] `src/fifteen_min_crypto_strategy.py` - Exit thresholds fixed (1%/2%)
- [ ] `src/fifteen_min_crypto_strategy.py` - Time-based exit fixed (12 min)
- [ ] `src/fifteen_min_crypto_strategy.py` - Market closing exit added (2 min)
- [ ] `src/main_orchestrator.py` - Strategy initialization updated

### 3. Configuration Review
- [ ] Trade size: $5 per trade (reasonable)
- [ ] Take-profit: 1% (realistic)
- [ ] Stop-loss: 2% (tight control)
- [ ] Max positions: 3 (manageable)
- [ ] Dry-run: False (live trading)

## 🚀 Deployment Steps

### Step 1: Backup Current Code
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cp -r src src.backup.$(date +%Y%m%d_%H%M%S)"
```
- [ ] Backup created successfully

### Step 2: Upload Fixed Files
```bash
# Option A: Use deployment script (recommended)
chmod +x deploy_fixes_to_aws.sh
./deploy_fixes_to_aws.sh

# Option B: Manual upload
scp -i money.pem src/fifteen_min_crypto_strategy.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/
scp -i money.pem src/main_orchestrator.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/
```
- [ ] Files uploaded successfully

### Step 3: Run Tests on AWS
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && python3 test_trading_fixes.py"
```
- [ ] All tests pass on AWS

### Step 4: Restart Bot Service
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"
```
- [ ] Service restarted successfully

### Step 5: Verify Bot is Running
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot"
```
- [ ] Service status: Active (running)
- [ ] No errors in status output

## 📊 Post-Deployment Monitoring

### First 5 Minutes
```bash
# Watch live logs
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -f"
```
- [ ] Bot starts without errors
- [ ] Binance feed connects successfully
- [ ] Markets are fetched successfully
- [ ] No critical errors in logs

### First 15 Minutes
```bash
# Check if opportunities are detected
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep -E 'SUM-TO-ONE|BINANCE.*SIGNAL' bot_debug.log | tail -10"
```
- [ ] Opportunities are being detected
- [ ] Orders are being placed (if opportunities exist)
- [ ] No order failures

### First Hour
```bash
# Check positions and exits
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && grep -E 'Active positions|TAKE PROFIT|STOP LOSS|TIME EXIT' bot_debug.log | tail -30"
```
- [ ] Positions are being opened
- [ ] Positions are being closed (within 12 minutes)
- [ ] Exit conditions are triggering correctly

### First 24 Hours
```bash
# Check trade statistics
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && sqlite3 data/trade_history.db 'SELECT COUNT(*) as total, SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins, SUM(profit) as total_profit FROM trades;'"
```
- [ ] Trades are being recorded
- [ ] Win rate is reasonable (>50%)
- [ ] Total profit is positive or near zero
- [ ] No massive losses (>$10)

## 🔍 Health Checks

### Every Hour
```bash
./monitor_bot_performance.sh
```
- [ ] Bot is running
- [ ] No orphaned positions (>12 minutes old)
- [ ] No repeated errors
- [ ] System resources are healthy

### Every 6 Hours
```bash
# Check trade statistics
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && sqlite3 data/trade_history.db 'SELECT * FROM trades ORDER BY timestamp DESC LIMIT 20;'"
```
- [ ] Trades are happening
- [ ] Profits and losses are balanced
- [ ] No pattern of consistent losses

### Daily
```bash
# Full performance review
./monitor_bot_performance.sh > daily_report_$(date +%Y%m%d).txt
```
- [ ] Review daily report
- [ ] Check win rate (target: 60-70%)
- [ ] Check average profit (target: 0.5-1.5%)
- [ ] Check max drawdown (target: <$10)
- [ ] Adjust settings if needed

## ⚠️ Warning Signs

### Immediate Action Required
- ❌ Bot crashes repeatedly
- ❌ All trades are losing
- ❌ Positions not closing (>15 minutes old)
- ❌ Orders failing consistently
- ❌ Balance dropping rapidly (>$20/day)

### Action: Stop Bot
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl stop polybot"
```

### Action: Review Logs
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 200 > /tmp/bot_logs.txt"
scp -i money.pem ubuntu@35.76.113.47:/tmp/bot_logs.txt ./
```

### Action: Rollback if Needed
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && sudo systemctl stop polybot && cp -r src.backup.* src/ && sudo systemctl start polybot"
```

## 🎯 Success Criteria

### Week 1
- [ ] Bot runs continuously without crashes
- [ ] Positions close within 12 minutes
- [ ] Win rate >50%
- [ ] No losses >$5 per trade
- [ ] Total profit >$0 (break-even or better)

### Week 2-4
- [ ] Win rate stabilizes at 60-70%
- [ ] Average profit per trade: $0.25-$0.75
- [ ] Total profit: $10-$50
- [ ] Max drawdown: <$10
- [ ] No manual intervention needed

### Month 1+
- [ ] Consistent profitability
- [ ] Win rate: 65-75%
- [ ] Monthly profit: $50-$200
- [ ] Sharpe ratio: >1.0
- [ ] Max drawdown: <5% of capital

## 📝 Rollback Plan

### If Bot Fails
1. Stop bot: `ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl stop polybot"`
2. Restore backup: `ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cp -r src.backup.* src/"`
3. Start bot: `ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl start polybot"`
4. Review logs: `ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 200"`

### If Losses Exceed $20
1. Stop bot immediately
2. Review all trades: `sqlite3 data/trade_history.db "SELECT * FROM trades;"`
3. Identify issue (exit logic, entry logic, market conditions)
4. Adjust settings or rollback
5. Test in dry-run mode before restarting

## 📞 Emergency Contacts

### Bot Issues
- Check logs: `./monitor_bot_performance.sh`
- Review documentation: `CRITICAL_FIXES_APPLIED.md`
- Run tests: `python test_trading_fixes.py`

### AWS Issues
- Check service: `ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot"`
- Check disk space: `ssh -i money.pem ubuntu@35.76.113.47 "df -h"`
- Check memory: `ssh -i money.pem ubuntu@35.76.113.47 "free -h"`

### Polymarket API Issues
- Check API status: https://polymarket.com/status
- Check credentials: `.env` file
- Check allowances: `python setup_bot.py`

## ✅ Final Checklist

Before considering deployment complete:
- [ ] All pre-deployment checks passed
- [ ] All deployment steps completed
- [ ] Bot running for at least 1 hour without errors
- [ ] At least 1 trade executed successfully
- [ ] Exit logic verified (position closed within 12 minutes)
- [ ] Monitoring scripts working
- [ ] Documentation reviewed
- [ ] Rollback plan tested
- [ ] Emergency procedures understood

---

**Deployment Date**: _____________
**Deployed By**: _____________
**Status**: ⬜ Pending | ⬜ In Progress | ⬜ Complete | ⬜ Failed
**Notes**: _____________________________________________

---

**Last Updated**: February 9, 2026
**Version**: 2.0 (Fixed)
