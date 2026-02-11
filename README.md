# Polymarket Arbitrage Trading Bot

An automated trading bot for Polymarket that uses AI-powered decision making, reinforcement learning, and multiple arbitrage strategies to execute profitable trades on 15-minute crypto markets.

## 🚀 Features

- **AI-Powered Trading**: Ensemble decision engine combining LLM, RL, Historical, and Technical analysis
- **Multiple Strategies**:
  - Sum-to-one arbitrage (guaranteed profit when YES + NO < $1.00)
  - Latency arbitrage (front-running using Binance price feed)
  - Directional trading (AI-predicted price movements)
- **Risk Management**: Portfolio risk manager, circuit breakers, daily loss limits
- **Learning Engines**: Adaptive learning that improves over time
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## 📋 Prerequisites

- Python 3.10+
- Polymarket account with USDC balance
- Private key for wallet
- NVIDIA API key (for LLM)
- AWS EC2 instance (for deployment)

## 🛠️ Installation

### Local Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd polybot

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Environment Variables

Create a `.env` file with:

```env
# Polymarket Configuration
PRIVATE_KEY=your_private_key_here
CHAIN_ID=137
CLOB_API_URL=https://clob.polymarket.com

# AI Configuration
NVIDIA_API_KEY=your_nvidia_api_key_here

# Trading Configuration
DRY_RUN=false
TRADE_SIZE=3.0
MAX_POSITIONS=2
SCAN_INTERVAL_SECONDS=5
```

## 🚀 Usage

### Run Locally

```bash
# Dry run (no real trades)
python bot.py --dry-run

# Live trading
python bot.py
```

### Deploy to AWS

```bash
# 1. Update SERVER_IP in deploy_to_aws.sh
nano deploy_to_aws.sh

# 2. Deploy
chmod +x deploy_to_aws.sh
./deploy_to_aws.sh

# 3. Monitor logs
ssh -i money.pem ubuntu@YOUR_SERVER_IP
sudo journalctl -u polybot -f
```

## 📊 Trading Strategies

### 1. Sum-to-One Arbitrage
- Detects when YES + NO prices < $1.00
- Buys both sides for guaranteed profit
- Risk-free arbitrage opportunity

### 2. Latency Arbitrage
- Monitors Binance for price movements
- Front-runs Polymarket price updates
- Uses multi-timeframe technical analysis

### 3. Directional Trading
- AI ensemble decision (LLM + RL + Historical + Technical)
- Predicts price direction
- Requires 15% consensus to execute

## 🧠 AI Decision Engine

The bot uses an ensemble of 4 models:

1. **LLM (40% weight)**: Meta Llama 3.1 70B for market analysis
2. **RL Engine (35% weight)**: Q-learning for strategy optimization
3. **Historical Tracker (20% weight)**: Pattern recognition from past trades
4. **Technical Analysis (15% weight)**: Multi-timeframe indicators

Trades are executed when consensus reaches 15% threshold.

## 📁 Project Structure

```
polybot/
├── src/                              # Source code
│   ├── main_orchestrator.py          # Main trading loop
│   ├── fifteen_min_crypto_strategy.py # 15-min strategy
│   ├── ensemble_decision_engine.py   # AI ensemble
│   ├── llm_decision_engine_v2.py     # LLM integration
│   ├── reinforcement_learning_engine.py # RL engine
│   ├── portfolio_risk_manager.py     # Risk management
│   └── ...                           # Other modules
├── tests/                            # Test files
├── config/                           # Configuration
├── data/                             # Runtime data
├── logs/                             # Log files
├── deployment/                       # Deployment scripts
├── bot.py                            # Entry point
├── requirements.txt                  # Dependencies
└── README.md                         # This file
```

## 🔧 Configuration

### Trading Parameters

Edit `src/fifteen_min_crypto_strategy.py`:

```python
trade_size = 3.0              # USD per trade
max_positions = 2             # Max concurrent positions
take_profit_pct = 0.01        # 1% profit target
stop_loss_pct = 0.02          # 2% stop loss
min_consensus = 15.0          # 15% ensemble consensus required
```

### Risk Management

Edit `src/portfolio_risk_manager.py`:

```python
max_position_size_pct = 0.5   # 50% of capital per position
max_daily_loss = -10.0        # Stop trading if down $10/day
max_daily_trades = 50         # Max trades per day
```

## 📈 Monitoring

### Check Bot Status

```bash
# On AWS server
sudo systemctl status polybot
sudo journalctl -u polybot -f
```

### Key Metrics to Monitor

- **Gas Price**: Should see "Gas price: XXX gwei"
- **Ensemble Votes**: "LLM: buy_yes (65%), RL: buy_yes (55%)..."
- **Trade Approvals**: "ENSEMBLE APPROVED: buy_yes"
- **Order Placements**: "ORDER PLACED SUCCESSFULLY"

## 🐛 Troubleshooting

### Bot Not Trading

1. Check ensemble consensus in logs
2. Verify balance is sufficient (min $1.00 per trade)
3. Check if learning engines are blocking trades
4. Verify Binance price feed is working

### Orders Failing

1. Check Polymarket balance
2. Verify order size meets $1.00 minimum
3. Check for API rate limits
4. Verify CLOB client authentication

## 📚 Documentation

- [Deployment Guide](DEPLOY_NOW.md) - Complete deployment instructions
- [Trading Fixes](COMPREHENSIVE_TRADING_FIXES.md) - Recent fixes and improvements
- [API Documentation](docs/) - Detailed API documentation

## 🔒 Security

- Never commit `.env` file or private keys
- Use environment variables for sensitive data
- Keep `money.pem` secure (SSH key for AWS)
- Regularly rotate API keys

## 📝 License

Private - All rights reserved

## 🤝 Contributing

This is a private project. Contact the owner for contribution guidelines.

## ⚠️ Disclaimer

This bot is for educational purposes. Trading cryptocurrencies and prediction markets involves risk. Use at your own risk. The authors are not responsible for any financial losses.

## 📞 Support

For issues or questions, check the logs first:
```bash
sudo journalctl -u polybot -n 100
```

Common issues are documented in `COMPREHENSIVE_TRADING_FIXES.md`.

---

**Status**: ✅ Production Ready - All critical fixes applied

**Last Updated**: February 11, 2026
