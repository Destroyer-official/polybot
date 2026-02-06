# Fully Autonomous Polymarket Bot

## 🤖 100% Autonomous Operation - Zero Human Intervention

This bot is designed to operate **completely autonomously** with **no human in the loop**. It handles everything automatically:

### ✅ What the Bot Does Automatically

1. **Cross-Chain Fund Management**
   - Detects USDC on Ethereum
   - Automatically bridges to Polygon using official Polygon Bridge
   - Waits for bridge completion (5-15 minutes)
   - Verifies funds arrived on Polygon

2. **Trading Operations**
   - Scans 1000+ markets every 2 seconds
   - Identifies arbitrage opportunities
   - Executes trades automatically
   - Merges positions for profit
   - Manages gas prices

3. **Fund Management**
   - Monitors balances continuously
   - Auto-deposits to Polymarket when needed
   - Auto-withdraws profits when threshold reached
   - Keeps optimal balance for trading

4. **Risk Management**
   - AI safety guard (if NVIDIA API configured)
   - Circuit breaker (stops after 10 consecutive failures)
   - Gas price monitoring (halts if > 800 gwei)
   - Dynamic position sizing based on win rate

5. **Error Recovery**
   - Automatic retry on network errors
   - Transaction monitoring and resubmission
   - State persistence across restarts
   - Graceful shutdown handling

## 🚀 Quick Start

### Option 1: Windows Batch File (Easiest)

```bash
START_AUTONOMOUS_BOT.bat
```

Double-click the file or run from command prompt.

### Option 2: Python Script

```bash
python test_autonomous_bot.py
```

### Option 3: Main Orchestrator

```bash
python src/main_orchestrator.py
```

## 📋 Prerequisites

### 1. USDC on Ethereum or Polygon

The bot needs USDC to trade. It accepts USDC on either network:

- **Ethereum**: Bot will automatically bridge to Polygon
- **Polygon**: Ready to trade immediately

**Minimum**: $1.00 USDC
**Recommended**: $4-20 USDC

### 2. ETH for Gas (if bridging from Ethereum)

If you have USDC on Ethereum, you need ETH for gas:

- **Minimum**: 0.002 ETH (~$5)
- **Recommended**: 0.005 ETH (~$12)

### 3. MATIC for Gas (on Polygon)

For trading on Polygon:

- **Minimum**: 0.01 MATIC (~$0.01)
- **Recommended**: 0.1 MATIC (~$0.10)

### 4. Configuration

Edit `.env` file:

```env
# Required
PRIVATE_KEY=your_private_key_here
WALLET_ADDRESS=your_wallet_address_here
POLYGON_RPC_URL=your_alchemy_or_infura_url_here

# Trading mode
DRY_RUN=false  # Set to false for real trading

# Optional but recommended
NVIDIA_API_KEY=your_nvidia_api_key_here
```

## 🔄 How Autonomous Bridging Works

### Step 1: Detection
```
Bot starts → Checks Polygon USDC balance
└─ If < $1.00 → Check Ethereum USDC balance
```

### Step 2: Automatic Bridging
```
Found USDC on Ethereum
├─ Check ETH balance for gas
├─ Approve USDC to Polygon Bridge
├─ Deposit to Polygon Bridge
└─ Wait for arrival (5-15 minutes)
```

### Step 3: Verification
```
USDC arrives on Polygon
├─ Verify balance
├─ Log success
└─ Start trading
```

### Step 4: Trading
```
Continuous loop:
├─ Scan markets (every 2 seconds)
├─ Find opportunities
├─ Execute trades
├─ Manage funds
└─ Repeat forever
```

## 📊 What to Expect

### First 30 Minutes

1. **Minutes 0-2**: Bot starts, checks balances
2. **Minutes 2-17**: If bridging needed, waits for bridge completion
3. **Minutes 17-30**: Starts scanning markets, may find 0-2 opportunities

### First Hour

- **Markets scanned**: ~1,800 (1000+ markets × 2 scans/minute × 60 minutes)
- **Opportunities found**: 0-5 (depends on market conditions)
- **Trades executed**: 0-3 (only profitable opportunities)
- **Expected profit**: $0.05-0.50 (if opportunities found)

### First 24 Hours

- **Markets scanned**: ~43,200
- **Opportunities found**: 5-50 (varies with volatility)
- **Trades executed**: 3-30
- **Expected profit**: $1-10 (depends on capital and opportunities)
- **Win rate target**: >80%

## 💰 Profitability

### With $4 Capital

- **Position size**: $0.50-2.00 per trade
- **Profit per trade**: $0.01-0.10 (0.5-5%)
- **Daily trades**: 3-10
- **Daily profit**: $0.10-1.00
- **Monthly profit**: $3-30 (75-750% ROI)

### With $20 Capital

- **Position size**: $2.00-10.00 per trade
- **Profit per trade**: $0.05-0.50
- **Daily trades**: 5-15
- **Daily profit**: $0.50-5.00
- **Monthly profit**: $15-150 (75-750% ROI)

**Note**: Actual results vary based on market conditions, volatility, and opportunity frequency.

## 🛡️ Safety Features

### 1. DRY_RUN Mode
- Test everything without real money
- Simulates all operations
- Safe for testing configuration

### 2. Circuit Breaker
- Stops after 10 consecutive failures
- Prevents runaway losses
- Auto-resumes after cooldown

### 3. Gas Price Monitoring
- Halts trading if gas > 800 gwei
- Prevents expensive transactions
- Auto-resumes when gas normalizes

### 4. AI Safety Guard (Optional)
- Checks market conditions
- Detects crashes and volatility
- Pauses trading during extreme events

### 5. Dynamic Position Sizing
- Adjusts size based on win rate
- Reduces size after losses
- Increases size after wins

## 📈 Monitoring

### Real-Time Logs

The bot logs everything:

```bash
# View live logs
Get-Content autonomous_bot.log -Wait -Tail 50
```

### Key Metrics

- Markets scanned
- Opportunities found
- Trades executed
- Win rate
- Total profit
- Gas costs
- Net profit

### Generate Reports

```bash
python generate_report.py
```

## 🔧 Troubleshooting

### Bot Won't Start

**Check 1**: Verify .env configuration
```bash
python pre_flight_check.py
```

**Check 2**: Verify USDC balance
```bash
python check_all_networks.py
```

**Check 3**: Check logs
```bash
type autonomous_bot.log
```

### Bridge Takes Too Long

- Normal: 5-15 minutes
- Maximum: 30 minutes
- If > 30 minutes: Check Ethereum transaction on Etherscan

### No Opportunities Found

- Normal! Arbitrage is rare
- More opportunities during:
  - High volatility
  - News events
  - Elections
  - Market hours (9am-4pm EST)

### Circuit Breaker Triggered

- Triggered after 10 consecutive failures
- Bot pauses for 5 minutes
- Auto-resumes after cooldown
- Check logs for failure reasons

## 🎯 Optimization Tips

### 1. Run 24/7
- More uptime = more opportunities
- Use AWS/VPS for continuous operation
- Bot handles restarts automatically

### 2. Optimal Capital
- Start: $4-10 (test and learn)
- Optimal: $20-100 (good opportunity coverage)
- Scale: $100-1000 (maximum opportunities)

### 3. Monitor Performance
- Check daily: Win rate should be >80%
- Check weekly: Net profit should be positive
- Adjust if needed: MIN_PROFIT_THRESHOLD in .env

### 4. Gas Optimization
- Trade during low gas periods
- Polygon gas is usually <50 gwei
- Bot automatically waits if gas too high

## 🚨 Important Notes

### Security

- ⚠️ Never share your PRIVATE_KEY
- ⚠️ Use a dedicated wallet for the bot
- ⚠️ Start with small amounts ($4-20)
- ⚠️ Test with DRY_RUN=true first

### Risks

- Market risk: Prices can change during execution
- Gas risk: High gas can eat profits
- Smart contract risk: Bugs in Polymarket contracts
- Bridge risk: Funds locked during bridging

### Limitations

- Requires USDC (not other stablecoins)
- Polygon network only (after bridging)
- Arbitrage opportunities are rare
- Profits depend on market conditions

## 📞 Support

### Check Status
```bash
python pre_flight_check.py
```

### View Logs
```bash
type autonomous_bot.log
```

### Generate Report
```bash
python generate_report.py
```

### Check Balances
```bash
python check_all_networks.py
```

## 🎉 Ready to Start!

### Test Mode (Recommended First)

1. Set `DRY_RUN=true` in .env
2. Run: `START_AUTONOMOUS_BOT.bat`
3. Watch logs for 1 hour
4. Verify everything works

### Live Mode

1. Set `DRY_RUN=false` in .env
2. Ensure you have USDC on Ethereum or Polygon
3. Run: `START_AUTONOMOUS_BOT.bat`
4. Bot handles everything automatically!

---

**The bot is now fully autonomous. No human intervention required!** 🤖🚀
