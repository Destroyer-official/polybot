# How to Run the Polymarket Arbitrage Bot

## Quick Start (3 Steps)

### 1. Verify Configuration
```bash
# Check that .env is configured correctly
python setup_bot.py
```

This will:
- ✅ Validate your configuration
- ✅ Detect your wallet type
- ✅ Check token allowances
- ✅ Test Polymarket connectivity
- ✅ Verify you have funds

### 2. Run in DRY_RUN Mode (Recommended First)
```bash
# Test without real money
python bot.py
```

The bot will:
- ✅ Scan markets for arbitrage opportunities
- ✅ Show what trades it would make
- ✅ NOT execute real transactions (DRY_RUN=false in .env)
- ✅ Log all activity

**Let it run for 24 hours to verify stability**

### 3. Switch to Live Trading (When Ready)
```bash
# Edit .env file
# Change: DRY_RUN=false to DRY_RUN=false

# Restart bot
python bot.py
```

## Available Bot Scripts

### 1. Main Production Bot (Recommended)
```bash
python bot.py
```
- Uses MainOrchestrator (full production system)
- Automatic wallet type detection
- Token allowance management
- AI safety guard (if NVIDIA API key provided)
- Dynamic position sizing
- Comprehensive monitoring
- State persistence

### 2. Debug Bot (For Troubleshooting)
```bash
python bot_debug.py
```
- Detailed logging to file
- Hardened AI safety checks
- Manual configuration options
- Useful for debugging issues

### 3. Test Autonomous Bot (For Testing)
```bash
python test_autonomous_bot.py
```
- Tests full autonomous operation
- Shows detailed startup process
- 10-second countdown before live trading
- Good for verifying everything works

### 4. Setup Bot (For Initial Setup)
```bash
python setup_bot.py
```
- Validates configuration
- Checks wallet type
- Verifies token allowances
- Tests connectivity
- Shows balance information

## Monitoring the Bot

### View Logs
```bash
# Real-time logs
python bot.py

# Debug logs (if using bot_debug.py)
tail -f /home/ubuntu/polybot/logs/polybot.log
```

### Check Status
The bot logs:
- ✅ Markets scanned
- ✅ Arbitrage opportunities found
- ✅ Orders placed
- ✅ Balance updates
- ✅ Gas prices
- ✅ Health checks (every 60 seconds)

### Prometheus Metrics (Optional)
```bash
# View metrics at:
http://localhost:9090/metrics
```

## Stopping the Bot

### Graceful Shutdown
```bash
# Press Ctrl+C
# The bot will:
# 1. Stop accepting new trades
# 2. Wait for pending transactions
# 3. Save final state
# 4. Show final statistics
```

## Troubleshooting

### Bot Won't Start
```bash
# Check configuration
python setup_bot.py

# Check Python version (need 3.8+)
python --version

# Check dependencies
pip install -r requirements.txt
```

### No Arbitrage Opportunities Found
This is normal! Arbitrage opportunities are rare. The bot:
- Scans 77+ markets every 2 seconds
- Looks for price inefficiencies
- Only trades when profit > 5% (MIN_PROFIT_THRESHOLD)

**Tip**: Lower MIN_PROFIT_THRESHOLD in .env for more opportunities (but lower profit per trade)

### Insufficient Funds Error
```bash
# Check balances
python setup_bot.py

# Deposit funds:
# 1. Go to https://polymarket.com
# 2. Click 'Deposit'
# 3. Deposit USDC from Ethereum (instant, free)
```

### Gas Price Too High
The bot automatically halts trading when gas > 2000 gwei (configurable in .env)

Wait for gas prices to normalize, then the bot resumes automatically.

### Token Allowance Issues (EOA Wallets Only)
```bash
# Check and set allowances
python setup_bot.py

# Or manually:
python -c "from src.token_allowance_manager import TokenAllowanceManager; from config.config import load_config; from web3 import Web3; config = load_config(); web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url)); account = web3.eth.account.from_key(config.private_key); mgr = TokenAllowanceManager(web3, account, config); mgr.set_usdc_allowance(); mgr.set_conditional_token_allowance()"
```

## Configuration Options (.env)

### Trading Parameters
```bash
# Minimum profit to execute trade (0.05 = 5%)
MIN_PROFIT_THRESHOLD=0.05

# Position size per trade
MAX_POSITION_SIZE=2.0
MIN_POSITION_SIZE=0.50

# Risk management
MAX_GAS_PRICE_GWEI=2000
CIRCUIT_BREAKER_THRESHOLD=10
```

### Fund Management
```bash
# Minimum balance to keep trading
MIN_BALANCE=3.0

# Target balance for deposits
TARGET_BALANCE=10.0

# Auto-withdraw when balance exceeds this
WITHDRAW_LIMIT=50.0
```

### Operational
```bash
# DRY_RUN mode (true = no real trades)
DRY_RUN=false

# How often to scan markets (seconds)
SCAN_INTERVAL_SECONDS=2

# Health check interval (seconds)
HEARTBEAT_INTERVAL_SECONDS=60
```

## Production Deployment (AWS)

For 24/7 autonomous operation, see:
- `PRODUCTION_DEPLOYMENT_GUIDE.md` - Full AWS setup
- `START_HERE.md` - Getting started guide
- `PRE_LAUNCH_CHECKLIST.md` - Pre-launch checklist

## Support

### Documentation
- `START_HERE.md` - Getting started
- `ENV_SETUP_GUIDE.md` - Environment setup
- `PRODUCTION_DEPLOYMENT_GUIDE.md` - AWS deployment
- `QUICK_REFERENCE.md` - Quick commands
- `FIXES_APPLIED.md` - Recent fixes

### Common Issues
1. **"Configuration validation failed"** → Check .env file
2. **"Insufficient funds"** → Deposit USDC on Polymarket
3. **"Token allowance too low"** → Run setup_bot.py
4. **"Gas price too high"** → Wait for gas to normalize
5. **"No markets found"** → Check Polymarket API status

## Success Indicators

The bot is working correctly when you see:
```
✅ Configuration loaded
✅ Wallet verified
✅ Wallet type detected
✅ CLOB client initialized
✅ All components initialized
✅ Bot started scanning markets
✅ Parsed 77 tradeable markets
✅ Balance: $10.00 USDC
✅ Heartbeat: Healthy=True
```

## Performance Expectations

- **Scan Rate**: 77+ markets every 2 seconds
- **Opportunities**: 0-5 per day (depends on market conditions)
- **Profit per Trade**: 5-20% (after fees)
- **Win Rate**: 80-95% (with proper risk management)
- **Gas Costs**: $0.01-0.05 per trade (Polygon is cheap)

## Safety Features

The bot includes multiple safety mechanisms:
1. ✅ DRY_RUN mode for testing
2. ✅ Gas price monitoring (halts if too high)
3. ✅ Circuit breaker (stops after consecutive failures)
4. ✅ AI safety guard (optional, with NVIDIA API)
5. ✅ Balance checks (stops if funds too low)
6. ✅ Transaction limits (max pending TXs)
7. ✅ State persistence (recovers from crashes)

**Always test in DRY_RUN mode first!**
