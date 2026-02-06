# Quick Start Guide - Polymarket Arbitrage Bot

## Prerequisites Checklist

- [ ] Python 3.8+ installed
- [ ] `.env` file configured with your keys
- [ ] Wallet has some MATIC for gas (0.1 MATIC minimum)
- [ ] Wallet has USDC on Polygon (minimum $0.50)

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Configure Environment

Edit `.env` file with your actual values:

```bash
# Required
PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
WALLET_ADDRESS=0xYOUR_WALLET_ADDRESS_HERE
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY

# Optional but recommended
NVIDIA_API_KEY=nvapi-YOUR_KEY_HERE
```

## Step 3: Run Integration Test

```bash
python test_integration.py
```

Expected output:
```
✅ config.config imported
✅ WalletTypeDetector imported
✅ TokenAllowanceManager imported
✅ MainOrchestrator imported
✅ Configuration loaded
✅ ALL TESTS PASSED
```

## Step 4: Run Setup Script

```bash
python setup_bot.py
```

This will:
1. ✅ Load and validate configuration
2. ✅ Connect to Polygon network
3. ✅ Detect your wallet type (EOA/Proxy/Safe)
4. ✅ Check token allowances (EOA only)
5. ✅ Offer to set allowances if missing
6. ✅ Check your balance
7. ✅ Test market data fetching

### If You Have EOA Wallet (MetaMask)

The setup script will ask:
```
Would you like to set allowances now? (yes/no):
```

Type `yes` to approve tokens for trading.

### If You Have Proxy/Safe Wallet

Allowances are managed automatically - skip to next step.

## Step 5: Test in Dry-Run Mode (IMPORTANT!)

**Always test for 24 hours before real trading:**

```bash
DRY_RUN=true python bot.py
```

This will:
- Scan markets and find opportunities
- Log what trades it would make
- NOT execute any real transactions
- NOT spend any money

Monitor the logs to verify:
- ✅ Markets are being scanned
- ✅ Opportunities are being found
- ✅ No errors in logs
- ✅ Balance checks work

## Step 6: Start Real Trading

**Only after 24 hours of successful dry-run testing:**

```bash
python bot.py
```

Or to run in background:

```bash
nohup python bot.py > bot.log 2>&1 &
```

## Monitoring

### View Logs (Real-time)
```bash
tail -f bot.log
```

### Check Status
The bot logs every 60 seconds:
```
Heartbeat: Balance=$XX.XX, Gas=XXgwei, Healthy=True
```

### Stop Bot
```bash
# Find process ID
ps aux | grep bot.py

# Kill gracefully
kill -SIGTERM <PID>
```

Or press `Ctrl+C` if running in foreground.

## Troubleshooting

### "Insufficient funds" Error

**Solution**: Deposit USDC to Polymarket
1. Go to https://polymarket.com
2. Connect your wallet
3. Click "Deposit"
4. Enter amount (minimum $0.50)
5. Confirm transaction

### "Token allowances not set" Error

**Solution**: Run setup script
```bash
python setup_bot.py
```

When asked "Would you like to set allowances now?", type `yes`.

### "Failed to connect to Polygon" Error

**Solution**: Check your RPC URL
1. Verify `POLYGON_RPC_URL` in `.env`
2. Try backup RPC: `https://polygon-rpc.com`
3. Get free Alchemy key: https://www.alchemy.com/

### "Gas price too high" Error

**Solution**: Wait for gas to normalize
- Bot automatically halts trading when gas > 800 gwei
- Will resume automatically when gas drops
- This is normal during network congestion

### "Circuit breaker is open" Error

**Solution**: Check for repeated failures
- Bot stops after 10 consecutive failed trades
- Review logs to identify issue
- Fix issue and restart bot

## Configuration Tips

### For Small Capital ($5-$50)

Edit `.env`:
```bash
MIN_PROFIT_THRESHOLD=0.003  # 0.3% minimum profit
MAX_POSITION_SIZE=2.0       # $2 max per trade
MIN_POSITION_SIZE=0.50      # $0.50 min per trade
MIN_BALANCE=1.0             # $1 minimum balance
```

### For Medium Capital ($50-$500)

Edit `.env`:
```bash
MIN_PROFIT_THRESHOLD=0.005  # 0.5% minimum profit
MAX_POSITION_SIZE=10.0      # $10 max per trade
MIN_POSITION_SIZE=1.0       # $1 min per trade
MIN_BALANCE=10.0            # $10 minimum balance
```

### For Large Capital ($500+)

Edit `.env`:
```bash
MIN_PROFIT_THRESHOLD=0.01   # 1% minimum profit
MAX_POSITION_SIZE=50.0      # $50 max per trade
MIN_POSITION_SIZE=5.0       # $5 min per trade
MIN_BALANCE=50.0            # $50 minimum balance
```

## Safety Features

### Automatic Protections
- ✅ Gas price monitoring (halts if > 800 gwei)
- ✅ Circuit breaker (stops after 10 failures)
- ✅ Balance checks (stops if < minimum)
- ✅ AI safety guard (optional, with NVIDIA API)
- ✅ Dry-run mode (test without risk)

### Manual Controls
- Set `DRY_RUN=true` to test without real trades
- Set `MAX_GAS_PRICE_GWEI` to control gas costs
- Set `CIRCUIT_BREAKER_THRESHOLD` to control risk
- Press `Ctrl+C` for graceful shutdown

## Performance Monitoring

### Key Metrics to Watch

1. **Win Rate**: Should be > 80%
2. **Average Profit**: Should be > gas costs
3. **Opportunities Found**: Should be > 0 per hour
4. **Failed Trades**: Should be < 10%

### View Statistics

Check logs for:
```
FINAL STATISTICS
Total Trades: XX
Win Rate: XX.XX%
Total Profit: $XX.XX
Net Profit: $XX.XX
```

## Production Deployment

### AWS EC2 (Recommended)

1. Launch t3.micro instance (Ubuntu 22.04)
2. Install Python and dependencies
3. Copy `.env` file
4. Run setup script
5. Start bot with systemd

See `PRODUCTION_DEPLOYMENT_GUIDE.md` for details.

### Local Machine

1. Run in background: `nohup python bot.py > bot.log 2>&1 &`
2. Monitor logs: `tail -f bot.log`
3. Keep computer running 24/7

## Support

### Documentation
- `README.md` - Overview and features
- `ENV_SETUP_GUIDE.md` - Environment setup
- `PRODUCTION_DEPLOYMENT_GUIDE.md` - AWS deployment
- `FIXES_APPLIED.md` - Recent fixes
- `HOW_TO_RUN.md` - Detailed instructions

### Common Commands
```bash
# Test integration
python test_integration.py

# Run setup
python setup_bot.py

# Test (dry-run)
DRY_RUN=true python bot.py

# Start trading
python bot.py

# View logs
tail -f bot.log

# Stop bot
kill -SIGTERM <PID>
```

## Success Checklist

Before going live, verify:

- [ ] Integration test passes
- [ ] Setup script completes successfully
- [ ] Token allowances set (EOA wallets)
- [ ] Balance > $0.50 USDC
- [ ] Dry-run mode works for 24 hours
- [ ] No errors in logs
- [ ] Opportunities being found
- [ ] Gas price monitoring works

**Once all checked, you're ready to trade!**

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python test_integration.py` | Test all components |
| `python setup_bot.py` | Configure bot |
| `DRY_RUN=true python bot.py` | Test without risk |
| `python bot.py` | Start real trading |
| `tail -f bot.log` | Monitor logs |
| `Ctrl+C` | Stop bot |

---

**Remember**: Always start with dry-run mode and test for 24 hours before real trading!
