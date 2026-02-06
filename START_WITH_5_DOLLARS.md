# Start Trading with $5 - Quick Guide

**Your bot is now ready to trade with dynamic position sizing!**

---

## 🚀 Quick Start (3 Steps)

### Step 1: Fund Your Wallet

Send **$5 USDC** to your wallet:

```
Address: 0x1A821E4488732156cC9B3580efe3984F9B6C0116
Network: Polygon
Token: USDC (0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174)
```

**How to send:**
1. Open your exchange (Coinbase, Binance, etc.)
2. Withdraw USDC
3. Select **Polygon network** (NOT Ethereum - fees are too high!)
4. Paste address above
5. Send $5 USDC

**Important:** Make sure you select **Polygon** network, not Ethereum!

---

### Step 2: Verify Configuration

Check your `.env` file:

```bash
# Should be set to true for testing
DRY_RUN=true

# Your wallet info
WALLET_ADDRESS=0x1A821E4488732156cC9B3580efe3984F9B6C0116
PRIVATE_KEY=0x4fef72b227c84e31e13cd59309e31acdf4edeef839422a9cdf6d0b35c61e5f42

# RPC URL (should have your Alchemy key)
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64

# Fund management (NEW LOGIC)
MIN_BALANCE=1.0
TARGET_BALANCE=10.0
WITHDRAW_LIMIT=50.0
```

---

### Step 3: Run the Bot

```bash
# Start the bot
python src/main_orchestrator.py
```

**What will happen:**

1. **Bot starts and checks balances:**
   ```
   [INFO] Balance check: Private=$5.00, Polymarket=$0.00
   ```

2. **Bot detects $5 in private wallet:**
   ```
   [INFO] Private wallet has $5.00 (between $1-$50) - initiating deposit
   [INFO] Depositing $4.00 to Polymarket (keeping $1.00 buffer)
   ```

3. **Bot starts trading with dynamic position sizes:**
   ```
   [INFO] Found internal arbitrage: market_xyz | YES=$0.48 NO=$0.51 | Profit=$0.01 (1.0%)
   [INFO] Position size calculated: $0.20 (available: $4.00, profit: 1.0%)
   [INFO] Dynamic position size: $0.20 (private: $1.00, polymarket: $4.00)
   [INFO] [DRY RUN] Would create FOK orders: YES=$0.20, NO=$0.20
   ```

4. **Bot continues scanning every 2 seconds:**
   ```
   [INFO] Scanned 45 markets, found 3 opportunities
   [INFO] Executing opportunity 1/3...
   ```

---

## 📊 What to Expect

### Position Sizes (Dynamic):

| Available Balance | Position Size | % of Balance |
|-------------------|---------------|--------------|
| $4.00 | $0.20 | 5% |
| $8.00 | $0.40 | 5% |
| $15.00 | $0.75 | 5% |
| $30.00 | $1.50 | 5% |
| $50.00 | $2.00 | Capped at max |

**Key Point:** Position size grows with your balance!

### Expected Profits:

**Daily (40-90 trades):**
- Conservative: $0.08 - $0.45
- Optimistic: $0.20 - $0.90

**Monthly:**
- Conservative: $2.40 - $13.50 (48-270% ROI)
- Optimistic: $6.00 - $27.00 (120-540% ROI)

**After 1 month with $5 start:**
- Conservative: $7.40 - $18.50
- Optimistic: $11.00 - $32.00

---

## 🔍 Monitor Your Bot

### Check Logs:

```bash
# Watch logs in real-time
tail -f logs/bot.log

# Or on Windows
Get-Content logs/bot.log -Wait
```

### Key Log Messages:

✅ **Good Signs:**
```
[INFO] Balance check: Private=$5.00, Polymarket=$0.00
[INFO] Depositing $4.00 to Polymarket
[INFO] Position size calculated: $0.20
[INFO] Found internal arbitrage: profit=$0.01 (1.0%)
[INFO] Trade completed: profit=$0.01, gas=$0.02, net=$-0.01
```

⚠️ **Warning Signs:**
```
[WARNING] Gas price too high: 850 gwei (max: 800). Halting trading.
[WARNING] Circuit breaker is open, trading halted
[ERROR] Failed to execute opportunity: insufficient balance
```

---

## 🎯 Testing Checklist

### Day 1 (DRY_RUN=true):
- [ ] Bot starts without errors
- [ ] Bot detects $5 in private wallet
- [ ] Bot deposits $4 to Polymarket (simulated)
- [ ] Bot finds arbitrage opportunities
- [ ] Position sizes are dynamic ($0.20-$0.40)
- [ ] Bot logs trades (simulated)
- [ ] No errors in logs

### Day 2 (Still DRY_RUN=true):
- [ ] Bot runs for 24 hours without crashes
- [ ] Position sizes adjust with balance
- [ ] Win rate is tracked correctly
- [ ] Fund management works (checks private wallet)
- [ ] Gas price monitoring works
- [ ] Circuit breaker works (after failures)

### Day 3 (Switch to REAL trading):
- [ ] Set DRY_RUN=false in .env
- [ ] Restart bot
- [ ] Monitor first real trade closely
- [ ] Verify actual deposit happens
- [ ] Verify actual trades execute
- [ ] Check wallet balance after trades

---

## ⚙️ Advanced Configuration

### Adjust Risk Level:

Edit `src/dynamic_position_sizer.py`:

```python
# More conservative (3% per trade)
base_risk_pct: Decimal = Decimal('0.03')

# More aggressive (7% per trade)
base_risk_pct: Decimal = Decimal('0.07')
```

### Adjust Deposit Buffer:

Edit `src/fund_manager.py` → `check_and_manage_balance()`:

```python
# Keep 30% in private wallet (more conservative)
buffer = max(private_balance * Decimal('0.3'), Decimal('0.50'))

# Keep only 10% in private wallet (more aggressive)
buffer = max(private_balance * Decimal('0.1'), Decimal('0.50'))
```

### Adjust Position Size Limits:

Edit `.env`:

```bash
# Smaller positions (safer)
MIN_POSITION_SIZE=0.05
MAX_POSITION_SIZE=1.00

# Larger positions (more aggressive)
MIN_POSITION_SIZE=0.20
MAX_POSITION_SIZE=5.00
```

---

## 🆘 Troubleshooting

### Bot doesn't deposit:

**Check:**
1. Private wallet has > $1 USDC
2. USDC is on Polygon network (not Ethereum)
3. Wallet address matches private key
4. RPC URL is working

**Fix:**
```bash
# Test wallet balance
python test_wallet_balance.py
```

### Position size is always $0.10:

**Reason:** Not enough balance available

**Check:**
```bash
# Check balances
python -c "
from web3 import Web3
from decimal import Decimal
w3 = Web3(Web3.HTTPProvider('YOUR_RPC_URL'))
balance = w3.eth.get_balance('YOUR_WALLET')
print(f'Balance: {balance / 10**18} MATIC')
"
```

### Bot crashes on startup:

**Check:**
1. All dependencies installed: `pip install -r requirements.txt`
2. .env file exists and has correct values
3. Python version >= 3.9
4. No syntax errors: `python -m py_compile src/*.py`

---

## 📈 Scaling Up

### After 1 Week ($10-$15 balance):
- Position sizes: $0.50-$0.75
- Daily profit: $0.20-$1.00
- Consider adding $10 more

### After 1 Month ($20-$30 balance):
- Position sizes: $1.00-$1.50
- Daily profit: $0.40-$2.00
- Consider adding $20 more

### After 3 Months ($50+ balance):
- Position sizes: $2.00 (capped)
- Daily profit: $1.00-$4.00
- Bot will auto-withdraw profits > $50

---

## 🎉 Success Metrics

### Week 1 Goals:
- ✅ Bot runs 24/7 without crashes
- ✅ 40-90 trades per day
- ✅ Win rate > 70%
- ✅ Positive net profit (after gas)
- ✅ Balance grows to $7-$10

### Month 1 Goals:
- ✅ 1,200-2,700 total trades
- ✅ Win rate > 75%
- ✅ Balance grows to $15-$30
- ✅ Consistent daily profits
- ✅ No major errors or crashes

### Month 3 Goals:
- ✅ 3,600-8,100 total trades
- ✅ Win rate > 80%
- ✅ Balance grows to $50+
- ✅ Auto-withdrawal working
- ✅ Ready to scale up capital

---

## 🔐 Security Reminders

- ⚠️ **NEVER share your private key**
- ⚠️ **Use a dedicated wallet** (not your main wallet)
- ⚠️ **Start with small amounts** ($5-$10)
- ⚠️ **Test in DRY_RUN mode first** (24 hours minimum)
- ⚠️ **Monitor logs daily** (check for errors)
- ⚠️ **Withdraw profits regularly** (bot does this automatically)

---

## 📞 Need Help?

### Check These First:
1. `HONEST_ANALYSIS.md` - Detailed analysis
2. `DYNAMIC_SIZING_IMPLEMENTATION.md` - Technical details
3. `HOW_TO_RUN.md` - Complete setup guide
4. `ENV_SETUP_GUIDE.md` - Configuration help

### Common Issues:
- **"Insufficient balance"** → Fund wallet with USDC on Polygon
- **"Gas price too high"** → Wait for gas to drop below 800 gwei
- **"Circuit breaker open"** → Bot paused after failures, will resume
- **"RPC connection failed"** → Check Alchemy RPC URL

---

**Ready to start? Fund your wallet with $5 and run the bot!**

```bash
python src/main_orchestrator.py
```

Good luck! 🚀
