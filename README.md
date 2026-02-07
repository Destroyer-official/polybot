# Polymarket Arbitrage Bot 🤖

A production-ready, autonomous trading bot for Polymarket 15-minute crypto prediction markets.

## Features

- **15-Minute Crypto Markets**: Trades BTC, ETH, SOL, XRP up/down markets
- **Binance Price Feed**: Real-time price signals for directional trading
- **Sum-to-One Arbitrage**: Guaranteed profit when UP + DOWN < $1.00
- **AI Safety Guard**: Optional DeepSeek v3.2 AI for trade validation
- **Auto-Recovery**: Circuit breaker, retry logic, and health monitoring
- **AWS Ready**: Systemd service for 24/7 automated trading

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/polybot.git
cd polybot
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
nano .env  # Fill in your credentials
```

**Required Settings:**

- `PRIVATE_KEY` - Your wallet private key
- `WALLET_ADDRESS` - Your Polygon wallet address
- `POLYGON_RPC_URL` - Alchemy or other RPC endpoint

### 3. Test (Dry Run)

```bash
python bot.py
```

This runs in DRY_RUN mode by default - no real trades.

### 4. Enable Live Trading

Edit `.env`:

```
DRY_RUN=false
```

## AWS Deployment

### Install on AWS EC2

```bash
cd polybot
sudo bash deployment/install.sh
```

### Commands

```bash
sudo systemctl start polybot    # Start bot
sudo systemctl stop polybot     # Stop bot
sudo systemctl restart polybot  # Restart bot
journalctl -u polybot -f        # View live logs
```

## Trading Strategy

The bot uses three strategies:

1. **Binance Latency Arbitrage**
   - Monitors Binance BTC/ETH prices
   - When price rises >0.2% → Buy "Up"
   - When price falls >0.2% → Buy "Down"

2. **Sum-to-One Arbitrage**
   - If Up_price + Down_price < $0.98
   - Buy both sides for guaranteed profit

3. **Auto Exit**
   - Take profit at +5% gain
   - Stop loss at -3% loss

## Project Structure

```
polybot/
├── bot.py              # Main entry point
├── src/                # Core source code
│   ├── main_orchestrator.py     # Bot orchestration
│   ├── fifteen_min_crypto_strategy.py  # Trading strategy
│   ├── fund_manager.py          # Balance management
│   ├── order_manager.py         # Order execution
│   └── ...
├── deployment/         # AWS deployment files
│   ├── polybot.service         # Systemd service
│   └── install.sh              # Setup script
├── config/             # Configuration files
└── tests/              # Test suite
```

## API Requirements

| API               | Purpose           | Required    |
| ----------------- | ----------------- | ----------- |
| Polygon RPC       | Blockchain access | ✅ Yes      |
| Polymarket CLOB   | Order placement   | ✅ Auto     |
| Binance WebSocket | Price feed        | ✅ Auto     |
| NVIDIA DeepSeek   | AI decisions      | ❌ Optional |

## No MetaMask Required

This bot does **NOT** require MetaMask browser extension:

- Signs transactions programmatically
- Uses private key from `.env`
- Works headlessly on servers

## License

MIT License - See LICENSE file
