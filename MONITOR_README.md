# 🤖 Bot Monitoring System

Beautiful terminal GUI for real-time monitoring of the Polymarket trading bot.

## Features

- **Live Metrics**: Gas price, markets scanned, opportunities found, active positions, trades placed
- **Ensemble Voting**: See all 4 AI models (LLM, RL, Historical, Technical) with their votes and confidence
- **Binance Prices**: Real-time prices for BTC, ETH, SOL, XRP
- **Recent Logs**: Color-coded log stream with error highlighting
- **Status Panel**: Shows errors and bot health
- **Fast & Responsive**: Updates every 0.5 seconds

## Installation

```bash
# Install the rich library
pip install rich>=13.0.0

# Or install all requirements
pip install -r requirements.txt
```

## Usage

### Option 1: Live Monitor (Recommended for AWS)
Reads real-time logs from journalctl - shows everything the bot is doing:

```bash
python monitor_live.py
```

This requires:
- Bot running as systemd service named "polybot"
- Access to journalctl (sudo permissions)
- Best for AWS/production monitoring

### Option 2: Test Mode (Local Testing)
Test the monitor locally using log files:

```bash
python monitor_live.py --test
# or
python monitor_live.py -t
```

This reads from `logs/bot_debug.log` or `logs/bot_8hr_full_aws.log` - great for testing the UI.

### Option 3: File-Based Monitor (Local Development)
Reads from data files (bot_state.json, active_positions.json):

```bash
python monitor.py
```

This requires:
- Bot writing to data files
- Best for local development

## Controls

- Press `Ctrl+C` to exit

## What You'll See

```
┌─────────────────────────────────────────────────────────────┐
│ 🤖 LIVE BOT MONITOR  |  15:23:45                            │
└─────────────────────────────────────────────────────────────┘

📊 Live Metrics              🎯 Ensemble Decision
⛽ Gas Price: 45 gwei        🧠 LLM: buy_both (100%)
📊 Markets: 77               🤖 RL: skip (50%)
🔍 Opportunities: 12         📊 Historical: neutral (50%)
📈 Positions: 0              📈 Technical: skip (0%)
💰 Trades: 0                 
                             Consensus: 40.0% ✅ buy_both

📈 Binance Prices            Status
BTC: $95,234.50              ✅ Bot running smoothly
ETH: $3,456.78
SOL: $145.23
XRP: $1.35

📜 Recent Logs
2026-02-11 15:23:12 - ENSEMBLE APPROVED: buy_both
2026-02-11 15:23:12 - Confidence: 83.3%
2026-02-11 15:23:12 - SUM-TO-ONE CHECK: SOL | UP=$0.715...
```

## Log Parsing

The monitor automatically extracts:
- Gas prices from "Gas price: X gwei"
- Market counts from "Parsed X tradeable markets"
- Ensemble votes from "Ensemble vote: LLM: action (X%), ..."
- Consensus from "Consensus: X%"
- Actions from "ENSEMBLE APPROVED/REJECTED"
- Binance prices from "Binance=$X.XX"
- Errors from ERROR/CRITICAL log levels

## Troubleshooting

### "Permission denied" when running monitor_live.py
You need sudo access to read journalctl:
```bash
sudo python monitor_live.py
```

Or add your user to the systemd-journal group:
```bash
sudo usermod -a -G systemd-journal $USER
# Log out and back in
```

### No data showing
- Check that the bot is running: `sudo systemctl status polybot`
- Check logs manually: `sudo journalctl -u polybot -f`
- Verify service name matches (default: "polybot")

### Monitor is slow/laggy
- Reduce refresh rate in the code (change `refresh_per_second` or `time.sleep()`)
- Check system resources: `htop`

## Customization

Edit the scripts to:
- Change refresh rate (default: 0.5s)
- Adjust log history (default: 50 lines)
- Modify color schemes
- Add/remove panels
- Change service name (default: "polybot")

## Tips

- Run in a dedicated terminal window
- Use tmux/screen for persistent sessions on AWS
- Monitor during trading hours for best visibility
- Watch for red ERROR messages in logs
- Check consensus % to see if trades are being approved (need >= 15%)
