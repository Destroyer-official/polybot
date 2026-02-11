# Deployment Guide

## Quick Deployment (Your Workflow)

### 1. Commit and Push Changes
```bash
# On local machine
git add .
git commit -m "Your commit message"
git push origin main
```

### 2. Deploy to AWS
```bash
# SSH to server
ssh -i money.pem ubuntu@YOUR_SERVER_IP

# Pull latest changes
cd /home/ubuntu/polybot
git fetch --all
git reset --hard origin/main

# Clear Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Restart bot
sudo systemctl restart polybot

# Monitor logs
sudo journalctl -u polybot -f
```

## What to Look For in Logs

### ✅ Good Signs (Bot Working):
```
✅ Gas price: XXX gwei
✅ Ensemble votes visible (LLM, RL, Historical, Technical)
✅ "buy_both not applicable for directional trade - skipping"
✅ "ENSEMBLE APPROVED: buy_yes" (for real trades)
✅ "ORDER PLACED SUCCESSFULLY"
```

### ⚠️ Expected Behavior (Bot Being Conservative):
```
⚠️ "ENSEMBLE REJECTED" - Low consensus (normal, waiting for better signals)
⚠️ "Excessive slippage" - Protecting capital (good!)
⚠️ "Rate limited" - Preventing spam (normal)
⚠️ "SUM-TO-ONE CHECK: ... = $1.000" - No arbitrage opportunity (normal)
```

### ❌ Bad Signs (Need to Fix):
```
❌ AttributeError - Missing methods
❌ RuntimeWarning: coroutine was never awaited
❌ Connection errors
❌ Authentication errors
```

## Recent Fixes Applied

### 1. Async/Await Fix ✅
- Fixed `_check_gas_price()` being called without await
- Gas price monitoring now works correctly

### 2. Missing Methods ✅
- Added `_check_circuit_breaker()`
- Added `_check_daily_loss_limit()`

### 3. Consensus Threshold ✅
- Lowered from 60% to 15%
- More trades will be approved

### 4. Slippage Fix ✅
- Fixed "buy_both" handling in directional trading
- Bot now correctly skips inappropriate actions
- No more false 98% slippage errors

## Current Bot Behavior

The bot is **working correctly** but being conservative:

1. **Sum-to-one arbitrage**: Not triggering because YES + NO = $1.00 (not < $1.02)
2. **Latency arbitrage**: Waiting for stronger Binance signals (>40% confidence)
3. **Directional trading**: Waiting for clear buy_yes or buy_no signals

This is **good** - the bot is protecting your capital by not trading on low-quality signals.

## To Make Bot More Aggressive (Optional)

If you want more trades, you can adjust these parameters:

### Option 1: Lower Latency Threshold
Edit `src/fifteen_min_crypto_strategy.py` line ~1095:
```python
# Change from:
if direction == "bullish" and confidence >= 40.0:

# To:
if direction == "bullish" and confidence >= 20.0:
```

### Option 2: Lower Consensus Threshold
Edit `src/fifteen_min_crypto_strategy.py` line ~349:
```python
# Change from:
min_consensus=15.0

# To:
min_consensus=10.0  # Even more aggressive
```

### Option 3: Increase Scan Frequency
Edit `.env` file:
```env
SCAN_INTERVAL_SECONDS=2  # Instead of 5
```

## Monitoring Commands

```bash
# View logs in real-time
sudo journalctl -u polybot -f

# View last 100 lines
sudo journalctl -u polybot -n 100

# Search for specific patterns
sudo journalctl -u polybot | grep "ENSEMBLE"
sudo journalctl -u polybot | grep "ORDER PLACED"
sudo journalctl -u polybot | grep -i error

# Check bot status
sudo systemctl status polybot

# Restart bot
sudo systemctl restart polybot

# Stop bot
sudo systemctl stop polybot
```

## Troubleshooting

### Bot Not Trading
1. Check ensemble consensus in logs (should be >15%)
2. Verify balance is sufficient (min $1.00 per trade)
3. Check if slippage is too high (>50%)
4. Verify Binance price feed is working

### Orders Failing
1. Check Polymarket balance
2. Verify order size meets $1.00 minimum
3. Check API rate limits
4. Verify CLOB client authentication

### High Slippage
- This is normal for low-liquidity markets
- Bot correctly rejects trades with >50% slippage
- Wait for better market conditions

## Files Structure

```
polybot/
├── src/                              # Source code
│   ├── main_orchestrator.py          # Main loop (fixed async/await)
│   ├── fifteen_min_crypto_strategy.py # Strategy (fixed slippage)
│   ├── ensemble_decision_engine.py   # AI ensemble (added logging)
│   └── ...
├── .env                              # Configuration
├── bot.py                            # Entry point
├── requirements.txt                  # Dependencies
└── README.md                         # Documentation
```

## Support

For issues:
1. Check logs first: `sudo journalctl -u polybot -n 100`
2. Review this guide
3. Check `SLIPPAGE_FIX.md` for recent fixes
4. Check `COMPREHENSIVE_TRADING_FIXES.md` for all fixes

---

**Status**: ✅ All Fixes Applied - Ready for Production

**Last Updated**: February 11, 2026
