# Pre-Launch Checklist

Use this checklist before deploying your Polymarket arbitrage bot to production.

## ✅ Phase 1: Initial Setup (Required)

### Environment Setup
- [ ] Python 3.9+ installed
- [ ] Virtual environment created (`python3 -m venv venv`)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created from `.env.example`
- [ ] Required variables set in `.env`:
  - [ ] `PRIVATE_KEY`
  - [ ] `WALLET_ADDRESS`
  - [ ] `POLYGON_RPC_URL`

### Wallet Configuration
- [ ] Wallet has private key access
- [ ] Wallet address matches private key
- [ ] Wallet type detected (run `python setup_bot.py`)
- [ ] Token allowances set (EOA wallets only)
- [ ] Minimum $0.50 USDC deposited (recommended: $5-10)

### Connectivity Tests
- [ ] Polygon RPC connection working
- [ ] Polymarket API accessible
- [ ] Markets data fetching successfully
- [ ] API credentials derived

## ✅ Phase 2: Testing (Strongly Recommended)

### Dry-Run Testing
- [ ] Dry-run mode tested (`DRY_RUN=true python bot.py`)
- [ ] Markets scanning working
- [ ] Opportunities detected
- [ ] No errors in logs
- [ ] Simulated trades executing

### Small Amount Testing
- [ ] Started with $5-10 capital
- [ ] Position size set to $0.50-1.00
- [ ] Monitored for 1-2 hours
- [ ] Verified trades executing
- [ ] Checked profitability
- [ ] No unexpected errors

### Performance Validation
- [ ] Win rate > 90%
- [ ] Profit per trade > gas costs
- [ ] No failed transactions
- [ ] Balance tracking accurate
- [ ] Metrics collecting properly

## ✅ Phase 3: Security (Critical)

### Private Key Security
- [ ] Private key stored in `.env` (not in code)
- [ ] `.env` added to `.gitignore`
- [ ] Private key never committed to git
- [ ] Consider AWS Secrets Manager for production
- [ ] Backup private key stored securely offline

### Wallet Security
- [ ] Using separate hot wallet for trading
- [ ] Cold wallet set up for profits
- [ ] Withdrawal limits configured
- [ ] Auto-withdraw enabled (optional)
- [ ] Only trading capital in hot wallet

### Operational Security
- [ ] Dry-run mode tested first
- [ ] Small amounts tested first
- [ ] Monitoring set up
- [ ] Alerts configured
- [ ] Backup RPC endpoints configured

## ✅ Phase 4: Monitoring (Recommended)

### Logging
- [ ] Logs directory created
- [ ] Log rotation configured
- [ ] Log level appropriate (INFO for production)
- [ ] Structured logging working
- [ ] CloudWatch logs set up (optional)

### Metrics
- [ ] Prometheus metrics exposed
- [ ] Key metrics tracked:
  - [ ] Total trades
  - [ ] Win rate
  - [ ] Profit
  - [ ] Balance
  - [ ] Gas price
- [ ] Metrics dashboard set up (optional)

### Alerts
- [ ] SNS alerts configured (optional)
- [ ] Email notifications set up
- [ ] Alert triggers defined:
  - [ ] Low balance
  - [ ] High gas price
  - [ ] Circuit breaker open
  - [ ] System errors

## ✅ Phase 5: Production Deployment (Optional)

### AWS EC2 Setup
- [ ] EC2 instance launched (t3.small or larger)
- [ ] Security group configured
- [ ] SSH access working
- [ ] Dependencies installed
- [ ] Repository cloned
- [ ] Environment configured

### Systemd Service
- [ ] Service file created
- [ ] Service enabled
- [ ] Service started
- [ ] Service auto-restart configured
- [ ] Logs accessible via journalctl

### Monitoring & Maintenance
- [ ] CloudWatch logs streaming
- [ ] SNS alerts working
- [ ] Prometheus metrics accessible
- [ ] Daily balance checks scheduled
- [ ] Weekly profit reports scheduled

## ✅ Phase 6: Ongoing Operations

### Daily Tasks
- [ ] Check bot status
- [ ] Review logs for errors
- [ ] Verify balance
- [ ] Check win rate
- [ ] Monitor gas prices

### Weekly Tasks
- [ ] Review performance metrics
- [ ] Calculate profit/loss
- [ ] Withdraw profits (if needed)
- [ ] Check for updates
- [ ] Review and adjust parameters

### Monthly Tasks
- [ ] Full performance review
- [ ] Security audit
- [ ] Update dependencies
- [ ] Rotate API keys
- [ ] Backup configuration

## 🚨 Emergency Procedures

### If Bot Stops Working
1. Check logs: `tail -f logs/bot.log`
2. Check balance: `python check_balance.py`
3. Check gas prices: https://polygonscan.com/gastracker
4. Restart bot: `python bot.py`
5. If persistent, run setup: `python setup_bot.py`

### If Losing Money
1. Stop bot immediately: `pkill -f bot.py`
2. Review recent trades
3. Check for configuration errors
4. Verify market conditions
5. Test in dry-run mode before restarting

### If Balance Too Low
1. Deposit via polymarket.com (fastest)
2. Or wait for auto-deposit (if configured)
3. Check minimum balance settings
4. Verify fund management working

### If Gas Prices High
1. Bot auto-halts if gas > 800 gwei
2. Wait for gas to normalize
3. Check: https://polygonscan.com/gastracker
4. Adjust `MAX_GAS_PRICE_GWEI` if needed

## 📊 Success Criteria

Before considering deployment successful:

- [ ] Bot running for 24+ hours without errors
- [ ] Win rate > 90%
- [ ] Positive net profit (after gas fees)
- [ ] No failed transactions
- [ ] Balance tracking accurate
- [ ] Monitoring working
- [ ] Alerts triggering correctly

## 🎯 Recommended Timeline

### Day 1: Setup & Testing
- Morning: Setup environment, run `setup_bot.py`
- Afternoon: Test in dry-run mode
- Evening: Start with $5-10, monitor closely

### Day 2-3: Small Scale Testing
- Monitor performance every few hours
- Verify profitability
- Check for errors
- Adjust parameters if needed

### Week 1: Scale Up Gradually
- Increase capital to $50-100
- Monitor daily
- Verify consistent profitability
- Fine-tune parameters

### Week 2-4: Production Scale
- Scale to target capital ($500-1000)
- Deploy to AWS for 24/7 operation
- Set up comprehensive monitoring
- Establish maintenance routine

## 📝 Notes

### Important Reminders
- Always test in dry-run mode first
- Start with small amounts
- Monitor closely for first 24-48 hours
- Withdraw profits regularly
- Keep only trading capital in hot wallet
- Never share private keys
- Rotate keys regularly

### Performance Expectations
- Win rate: 95-99%
- Profit per trade: $0.10-5.00
- Trades per day: 10-100
- Gas cost per trade: $0.10-0.50

### Risk Factors
- Gas fees can eat into profits
- Market availability varies
- Competition from other bots
- Slippage on large orders
- Network congestion

## ✅ Final Checklist

Before going live:

- [ ] All Phase 1 items complete
- [ ] All Phase 2 items complete
- [ ] All Phase 3 items complete
- [ ] Monitoring set up (Phase 4)
- [ ] Emergency procedures understood
- [ ] Success criteria defined
- [ ] Timeline planned

## 🚀 Ready to Launch?

If all critical items are checked:

```bash
# Final setup check
python setup_bot.py

# Start in dry-run mode
DRY_RUN=true python bot.py

# If dry-run successful, go live
python bot.py
```

**Good luck and trade safely! 🎯**

---

**Version**: 1.0.0
**Last Updated**: 2026-02-06
