# 🚀 Quick Start - Bot Monitor

## 1. Install (One Time)

```bash
pip install rich>=13.0.0
```

## 2. Run Monitor

### On AWS (Production)
```bash
python monitor_live.py
```

### On Local (Testing)
```bash
python monitor_live.py --test
```

## 3. What You'll See

```
🤖 LIVE BOT MONITOR  |  15:23:45

📊 Live Metrics              🎯 Ensemble Decision
⛽ Gas: 45 gwei              🧠 LLM: buy_both (100%)
📊 Markets: 77               🤖 RL: skip (50%)
🔍 Opportunities: 12         📊 Historical: neutral (50%)
📈 Positions: 0              📈 Technical: skip (0%)
💰 Trades: 0                 Consensus: 40.0% ✅

📈 Binance Prices            Status
BTC: $95,234.50              ✅ Running smoothly
ETH: $3,456.78
SOL: $145.23
XRP: $1.35

📜 Recent Logs (color-coded)
```

## 4. Exit

Press `Ctrl+C`

## 5. Deploy to AWS

```bash
# Local
git add .
git commit -m "Add monitoring system"
git push origin main

# AWS
git fetch --all
git reset --hard origin/main
pip install rich>=13.0.0

# Run in tmux (persistent)
tmux new -s monitor
python monitor_live.py
# Ctrl+B then D to detach
```

## That's It!

See MONITOR_README.md for full documentation.
