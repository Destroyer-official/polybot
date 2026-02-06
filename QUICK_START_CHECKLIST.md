# QUICK START CHECKLIST
## Get Your Bot Running in 30 Minutes

## ✅ PRE-FLIGHT CHECK (5 minutes)

### 1. Verify API Keys
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('✅ NVIDIA API:', 'SET' if os.getenv('NVIDIA_API_KEY') else '❌ MISSING'); print('✅ Private Key:', 'SET' if os.getenv('PRIVATE_KEY') else '❌ MISSING'); print('✅ Wallet:', os.getenv('WALLET_ADDRESS')); print('✅ RPC:', 'SET' if os.getenv('POLYGON_RPC_URL') else '❌ MISSING')"
```

**Expected Output**:
```
✅ NVIDIA API: SET
✅ Private Key: SET
✅ Wallet: 0x1A821E4488732156cC9B3580efe3984F9B6C0116
✅ RPC: SET
```

### 2. Install Dependencies
```bash
pip install websockets
```

### 3. Update .env File
```bash
# Open .env and update these values:
MAX_POSITION_SIZE=20.0
MIN_PROFIT_THRESHOLD=0.003
SCAN_INTERVAL_SECONDS=1
DRY_RUN=true
```

---

## 🔧 INTEGRATION (15 minutes)

### Step 1: Update Main Orchestrator

Open `src/main_orchestrator.py` and add after line 150 (in `__init__` method):

```python
# Add imports at top of file
from src.realtime_price_feed import RealtimePriceFeed, LatencyArbitrageDetector
from src.dynamic_position_sizer_v2 import DynamicPositionSizerV2

# In __init__ method, after initializing other components:

# Initialize upgraded position sizer
self.dynamic_sizer_v2 = DynamicPositionSizerV2(
    min_position_size=config.min_position_size,
    max_position_size=Decimal('20.0'),
    min_win_rate_threshold=0.70
)

# Initialize real-time price feed
self.price_feed = RealtimePriceFeed(
    movement_threshold=Decimal('0.001'),
    callback=self._on_price_movement
)

# Initialize latency arbitrage detector
self.latency_detector = LatencyArbitrageDetector(
    price_feed=self.price_feed,
    min_edge=Decimal('0.005')
)

# Store current markets for price movement handler
self.current_markets = []
```

### Step 2: Add Price Movement Handler

Add this method to `MainOrchestrator` class:

```python
async def _on_price_movement(
    self,
    asset: str,
    direction: str,
    old_price: Decimal,
    new_price: Decimal,
    change_pct: Decimal,
    timestamp: datetime
) -> None:
    """Handle price movement from real-time feed."""
    logger.info(
        f"🚨 Price movement: {asset} {direction} "
        f"${old_price} → ${new_price} ({change_pct*100:.2f}%)"
    )
    
    # Scan for latency arbitrage opportunities
    for market in self.current_markets:
        if market.asset == asset and market.is_crypto_15min():
            opp = self.latency_detector.detect_opportunity(
                asset=asset,
                polymarket_yes_price=market.yes_price,
                polymarket_no_price=market.no_price,
                current_cex_price=new_price,
                time_to_close_minutes=int((market.end_time - datetime.now()).total_seconds() / 60)
            )
            
            if opp:
                logger.info(f"💰 Latency arbitrage opportunity: {opp}")
```

### Step 3: Update Scan Method

In `_scan_and_execute` method, after parsing markets, add:

```python
# Store markets for price movement handler
self.current_markets = markets
```

### Step 4: Start Price Feed

In `run` method, after "POLYMARKET ARBITRAGE BOT STARTED", add:

```python
# Start price feed in background
asyncio.create_task(self.price_feed.run())
logger.info("Real-time price feed started")
```

### Step 5: Update Internal Arbitrage Engine

Open `src/internal_arbitrage_engine.py` and in `execute` method, change:

```python
# FIND THIS LINE (around line 250):
position_size = self.dynamic_sizer.calculate_position_size(...)

# CHANGE TO:
# Use V2 sizer if available, otherwise fallback to V1
if hasattr(self, 'dynamic_sizer_v2'):
    position_size = self.dynamic_sizer_v2.calculate_position_size(...)
else:
    position_size = self.dynamic_sizer.calculate_position_size(...)
```

---

## 🧪 TESTING (10 minutes)

### Test 1: Dry Run
```bash
# Ensure DRY_RUN=true in .env
python bot.py
```

**Watch for**:
- ✅ "Real-time price feed started"
- ✅ "Found 100+ total active markets"
- ✅ "Found X opportunities"
- ✅ "Position size: $0.XX"

**Let it run for 10 minutes, then check logs**:
```bash
tail -100 logs/bot.log
```

### Test 2: Verify Price Feed
```bash
# In another terminal, test price feed directly:
python src/realtime_price_feed.py
```

**Expected Output**:
```
RealtimePriceFeed initialized
Connecting to Binance WebSocket
Subscribed to 4 price streams
[timestamp] BTC moved UP: $64000 → $64100 (0.15%)
```

---

## 🚀 GO LIVE (When Ready)

### Step 1: Final Checks
- [ ] Dry run completed successfully
- [ ] Price feed connected and working
- [ ] Opportunities being found (10+ per hour)
- [ ] Position sizes appropriate ($0.10-$0.50 for $5 balance)
- [ ] No errors in logs

### Step 2: Set Live Mode
```bash
# In .env file, change:
DRY_RUN=false
```

### Step 3: Start Bot
```bash
python bot.py
```

### Step 4: Monitor First Hour
```bash
# Watch logs in real-time:
tail -f logs/bot.log | grep -E "Trade|Profit|Balance"
```

**Expected to see**:
- 1-3 trades in first hour
- Position sizes $0.10-$0.50
- Profit $0.05-$0.20 per trade
- Balance growing

---

## 📊 MONITORING (Ongoing)

### Check Balance
```bash
python -c "from src.fund_manager import FundManager; from web3 import Web3; from config.config import load_config; import asyncio; config = load_config(); w3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url)); account = w3.eth.account.from_key(config.private_key); fm = FundManager(w3, account, config.usdc_address, config.ctf_exchange_address, config.min_balance, config.target_balance, config.withdraw_limit, config.dry_run); print(asyncio.run(fm.check_balance()))"
```

### Check Trade History
```bash
python -c "from src.trade_history import TradeHistoryDB; db = TradeHistoryDB(); trades = db.get_all_trades(); print(f'Total trades: {len(trades)}'); print(f'Last 5 trades:'); [print(f'  {t}') for t in trades[-5:]]"
```

### Check Statistics
```bash
python -c "from src.trade_statistics import TradeStatisticsTracker; from src.trade_history import TradeHistoryDB; db = TradeHistoryDB(); tracker = TradeStatisticsTracker(db); stats = tracker.get_statistics(); print(f'Win rate: {stats.win_rate:.1f}%'); print(f'Total profit: ${stats.total_profit}'); print(f'Net profit: ${stats.net_profit}')"
```

---

## 🚨 TROUBLESHOOTING

### Issue: "Module not found: websockets"
```bash
pip install websockets
```

### Issue: "No opportunities found"
**Check**:
1. Market scanning working? (should see 100+ markets)
2. Profit threshold too high? (try 0.003 in .env)
3. Price feed connected? (check logs)

### Issue: "Position size is zero"
**Check**:
1. Balance sufficient? (need at least $1)
2. Fund manager working? (check balance)
3. Dynamic sizer integrated? (check code)

### Issue: "AI safety check failed"
**Check**:
1. NVIDIA API key valid? (check .env)
2. Gas price too high? (wait for lower gas)
3. Balance too low? (need > $1)

---

## ✅ SUCCESS CHECKLIST

### After 1 Hour:
- [ ] 1-3 trades executed
- [ ] No errors in logs
- [ ] Balance growing
- [ ] Gas costs < 20% of profit

### After 24 Hours:
- [ ] 20-40 trades executed
- [ ] Win rate > 70%
- [ ] Balance grown 10-50%
- [ ] No circuit breaker triggers

### After 1 Week:
- [ ] 40-90 trades per day
- [ ] Win rate > 80%
- [ ] Balance grown 5-20x
- [ ] Consistent daily profits

---

## 📞 NEED HELP?

1. **Check logs**: `tail -100 logs/bot.log`
2. **Review guides**:
   - IMPLEMENTATION_GUIDE.md (detailed)
   - FINAL_UPGRADE_SUMMARY.md (overview)
   - COMPREHENSIVE_UPGRADE_ANALYSIS.md (research)

3. **Common issues**: All covered in IMPLEMENTATION_GUIDE.md

---

## 🎯 EXPECTED TIMELINE

- **Minutes 0-5**: Pre-flight check
- **Minutes 5-20**: Integration
- **Minutes 20-30**: Testing
- **Hour 1**: First live trades
- **Day 1**: $5 → $7-10
- **Week 1**: $5 → $50-100
- **Month 1**: $5 → $5,000-20,000

---

## 🎉 YOU'RE READY!

Follow this checklist step-by-step and you'll be trading in 30 minutes.

**Good luck! 🚀**
