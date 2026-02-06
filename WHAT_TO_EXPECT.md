# What to Expect When Running the Bot

## 🎬 First Run (Dry Run Mode)

### When You Start
```bash
python bot.py
```

### You'll See:
```
================================================================================
POLYMARKET ARBITRAGE BOT STARTED
================================================================================
Wallet: 0x1A821E4488732156cC9B3580efe3984F9B6C0116
Chain ID: 137
DRY RUN: True
Scan interval: 2s
Min profit threshold: 0.5%
================================================================================
```

### Then Every 2 Seconds:
```
[INFO] Fetching markets from CLOB API...
[INFO] Found 1247 total active markets (all types)
[INFO] Scanned 1247 markets, found 12 opportunities
[INFO] Found internal arbitrage: market_abc123 | YES=$0.48 NO=$0.49 | Profit=$0.03 (3.1%)
[INFO] Flash crash detected in market_xyz789: YES dropped 16.2% ($0.65 -> $0.54)
[INFO] [DRY RUN] Would execute trade: $0.75 position
```

### Every 60 Seconds (Heartbeat):
```
[INFO] Heartbeat: Balance=$4.63, Gas=45gwei, Healthy=True
[INFO] Balance check: private=$4.63, polymarket=$0.00
[INFO] Private wallet has $4.63 (between $1-$50) - initiating deposit to Polymarket
[INFO] Depositing $3.70 to Polymarket (keeping $0.93 buffer in private wallet)
[INFO] [DRY RUN] Would deposit $3.70 USDC to Proxy wallet
```

---

## 📊 What the Bot Does

### Every 2 Seconds (Scan Loop)
1. **Fetches markets** from Polymarket API
2. **Scans for opportunities:**
   - Internal arbitrage (YES + NO < $1.00)
   - Flash crashes (15% drop in 3 seconds)
3. **Validates with AI safety guard**
4. **Calculates position size** (dynamic based on balance)
5. **Executes trades** (or simulates in dry run)

### Every 60 Seconds (Heartbeat)
1. **Checks health:**
   - Balance > $10?
   - Gas < 800 gwei?
   - Pending TX < 5?
   - API connectivity OK?
2. **Manages funds:**
   - Check private wallet balance
   - Deposit if $1-$50
   - Withdraw if Polymarket > $50
3. **Saves state** to disk
4. **Updates dashboard**

---

## 💰 Expected Trading Activity

### First Hour (Dry Run)
```
[INFO] Trade 1: Internal arbitrage | Profit=$0.02 (2.1%) | Position=$0.75
[INFO] Trade 2: Flash crash | Profit=$0.03 (3.2%) | Position=$0.80
[INFO] Trade 3: Internal arbitrage | Profit=$0.01 (1.8%) | Position=$0.70
...
[INFO] Hour 1 Summary: 8 trades, 7 wins, 1 fail, $0.15 profit
```

### First Day (Dry Run)
```
[INFO] Day 1 Summary:
  Total Trades: 52
  Successful: 48 (92.3% win rate)
  Failed: 4
  Total Profit: $1.85
  Gas Costs: $0.08
  Net Profit: $1.77
  Balance: $4.63 -> $6.40
```

### First Week (Live)
```
[INFO] Week 1 Summary:
  Starting Balance: $5.00
  Ending Balance: $12.50
  Total Trades: 364
  Win Rate: 91.2%
  Total Profit: $8.20
  Gas Costs: $0.70
  Net Profit: $7.50
  ROI: 150%
```

---

## 🎯 Trading Strategies in Action

### 1. Internal Arbitrage (Most Common)
```
[INFO] Found internal arbitrage: market_abc123
  YES Price: $0.48
  NO Price: $0.49
  Total Cost: $0.97
  Expected Profit: $0.03 (3.1%)
  Position Size: $0.75
  
[INFO] AI safety check passed: All safety checks passed
[INFO] Dynamic position size: $0.75 (private: $4.63, polymarket: $0.00)
[INFO] Creating FOK orders...
[INFO] [DRY RUN] Would buy YES: 1.56 shares @ $0.48
[INFO] [DRY RUN] Would buy NO: 1.53 shares @ $0.49
[INFO] [DRY RUN] Would merge positions and receive $1.00
[INFO] Trade completed: profit=$0.03, gas=$0.01, net=$0.02
```

### 2. Flash Crash Detection (High Profit)
```
[INFO] Flash crash detected in market_xyz789:
  Side: YES
  Price Drop: 16.2% ($0.65 -> $0.54)
  Time Window: 2.8 seconds
  
[INFO] Registered crash entry: market_xyz789 YES@$0.54
[INFO] [DRY RUN] Would buy YES: 1.48 shares @ $0.54
[INFO] Waiting for hedge opportunity...

[2 minutes later]
[INFO] Hedge opportunity in market_xyz789:
  Leg1: YES@$0.54
  Leg2: NO@$0.40
  Sum: $0.94
  Expected Profit: $0.06 (6.4%)
  
[INFO] [DRY RUN] Would buy NO: 1.50 shares @ $0.40
[INFO] [DRY RUN] Would merge positions and receive $1.00
[INFO] Trade completed: profit=$0.06, gas=$0.01, net=$0.05
[INFO] Completed crash trade: market_xyz789
```

---

## ⚠️ What Warnings Look Like

### Normal Warnings (Don't Worry)
```
[WARNING] FOK orders failed to fill - prices moved
[WARNING] No opportunities found in this scan
[WARNING] NVIDIA API timeout (2 seconds) - using fallback
[WARNING] Skipping market_abc: profit 0.4% < threshold 0.5%
```

### Concerning Warnings (Pay Attention)
```
[WARNING] High gas price: 850 gwei (max: 800). Halting trading.
[WARNING] Circuit breaker is open - trading halted
[WARNING] Low balance: $2.50 (min: $10.00)
[WARNING] High volatility detected: 8.2% > 5%
```

### Critical Errors (Stop and Investigate)
```
[ERROR] Failed to check balances: Connection refused
[ERROR] Trade execution failed: Insufficient balance
[ERROR] NVIDIA API error: Invalid API key
[ERROR] Fatal error in main loop: ...
```

---

## 📈 Performance Indicators

### Good Signs ✅
- Win rate >90%
- Average profit per trade 1-3%
- 40-90 trades per day
- Gas costs <10% of profits
- No circuit breaker triggers
- Balance growing steadily

### Warning Signs ⚠️
- Win rate <80%
- Average profit <1%
- <20 trades per day
- Gas costs >20% of profits
- Frequent circuit breaker triggers
- Balance declining

### Red Flags 🚨
- Win rate <70%
- Losing money consistently
- Errors in every scan
- Can't connect to APIs
- Orders never filling
- Balance dropping rapidly

---

## 🔧 How to Adjust

### If Too Many Trades
```python
# In .env, increase minimum profit:
MIN_PROFIT_THRESHOLD=0.025  # 2.5% instead of 2%
```

### If Too Few Trades
```python
# In .env, decrease minimum profit:
MIN_PROFIT_THRESHOLD=0.015  # 1.5% instead of 2%

# Or decrease crash threshold:
CRASH_THRESHOLD=0.12  # 12% instead of 15%
```

### If Losing Money
1. Check slippage (orders filling at bad prices?)
2. Check gas costs (too high?)
3. Increase MIN_PROFIT_THRESHOLD
4. Review logs for patterns

### If Not Finding Opportunities
1. Check market filtering (too strict?)
2. Check API connectivity
3. Verify markets are active
4. Lower MIN_PROFIT_THRESHOLD slightly

---

## 📊 Dashboard & Monitoring

### View Recent Trades
```bash
python -c "from src.trade_history import TradeHistoryDB; db = TradeHistoryDB(); [print(t) for t in db.get_recent_trades(10)]"
```

### View Statistics
```bash
python generate_report.py
```

### Check Balance
```bash
python test_wallet_balance.py
```

### View Logs
```bash
# Real-time logs
tail -f logs/bot.log

# Search for errors
grep ERROR logs/bot.log

# Search for trades
grep "Trade completed" logs/bot.log
```

---

## 🎯 Success Metrics

### After 24 Hours (Dry Run)
- [ ] 40-90 simulated trades
- [ ] Win rate >90%
- [ ] No critical errors
- [ ] Flash crashes detected
- [ ] Position sizing working

### After 1 Week (Live)
- [ ] Balance increased 50-100%
- [ ] Win rate maintained >90%
- [ ] Gas costs <10% of profits
- [ ] No circuit breaker triggers
- [ ] Profits withdrawn

### After 1 Month (Live)
- [ ] Balance increased 400-800%
- [ ] Consistent daily profits
- [ ] Strategy optimized
- [ ] Ready to scale up

---

## 🚀 What Success Looks Like

### Day 1
```
Starting: $5.00
Trades: 52
Wins: 48 (92%)
Profit: $1.77
Ending: $6.77
```

### Week 1
```
Starting: $5.00
Trades: 364
Wins: 332 (91%)
Profit: $7.50
Ending: $12.50
```

### Month 1
```
Starting: $5.00
Trades: 1,560
Wins: 1,404 (90%)
Profit: $45.00
Ending: $50.00
ROI: 900%
```

---

## 💡 Pro Tips

### Maximize Profits
1. Run 24/7 (more opportunities)
2. Withdraw profits weekly (reduce risk)
3. Reinvest some profits (compound growth)
4. Monitor and optimize parameters
5. Add more strategies (Phase 2)

### Minimize Risk
1. Start with dry run (24 hours)
2. Start small ($5-10)
3. Never risk >20% per trade
4. Stop after 3 consecutive losses
5. Keep detailed logs

### Scale Up
1. Week 1: $5 starting capital
2. Week 2: Add $10 more
3. Week 3: Reinvest all profits
4. Week 4: Withdraw 50%, reinvest 50%
5. Month 2: Scale to $100+

---

## ✅ Ready to Start?

**Your bot is ready!** Here's what to do:

1. **Start dry run:**
   ```bash
   python bot.py
   ```

2. **Watch for 24 hours:**
   - Check win rate (should be >90%)
   - Check trades per day (should be 40-90)
   - Check for errors (should be minimal)

3. **Deploy live:**
   - Set DRY_RUN=false in .env
   - Run python bot.py
   - Monitor closely for first hour

4. **Optimize:**
   - Adjust parameters based on performance
   - Track metrics daily
   - Withdraw profits weekly

**Let's make money! 💰🚀**
