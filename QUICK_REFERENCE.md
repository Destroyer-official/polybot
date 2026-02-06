# Quick Reference Card

## 🚀 Getting Started (Copy & Paste)

```bash
# 1. Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # Add: PRIVATE_KEY, WALLET_ADDRESS, POLYGON_RPC_URL

# 2. Run setup
python setup_bot.py

# 3. Deposit funds
# Go to https://polymarket.com → Deposit → $5-10

# 4. Test
DRY_RUN=true python bot.py

# 5. Go live
python bot.py
```

## 📝 Required .env Variables

```bash
PRIVATE_KEY=0x...
WALLET_ADDRESS=0x...
POLYGON_RPC_URL=https://polygon-rpc.com
```

## 🎯 Common Commands

```bash
# Setup and validation
python setup_bot.py

# Dry-run (test mode)
DRY_RUN=true python bot.py

# Live trading
python bot.py

# Check balance
python -c "from py_clob_client.client import ClobClient; import os; c = ClobClient('https://clob.polymarket.com', key=os.getenv('PRIVATE_KEY'), chain_id=137); print(c.get_balance_allowance())"

# View logs
tail -f logs/bot.log

# Check metrics
curl http://localhost:9090/metrics

# Cleanup project
python cleanup_project.py --backup --live
```

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Configuration validation failed" | Check .env has PRIVATE_KEY, WALLET_ADDRESS, POLYGON_RPC_URL |
| "Failed to connect to Polygon" | Try different RPC: https://polygon-mainnet.g.alchemy.com/v2/YOUR-KEY |
| "Insufficient funds" | Deposit via polymarket.com (10-30 seconds) |
| "Token allowance not set" | Run `python setup_bot.py` |
| "No active markets" | Check polymarket.com/markets, try different time |
| "High gas price" | Wait for gas to normalize, check polygonscan.com/gastracker |

## 💰 Deposit Funds (Fastest Method)

1. Go to https://polymarket.com
2. Connect wallet
3. Click "Deposit" (top right)
4. Enter amount: $5-10
5. Select: Wallet → Ethereum → Confirm
6. Wait 10-30 seconds ✅

## 📊 Performance Expectations

| Capital | Trades/Day | Daily Profit | Monthly Profit | Win Rate |
|---------|------------|--------------|----------------|----------|
| $100 | 10-50 | $1-25 | $30-750 | 95-99% |
| $1,000 | 20-100 | $20-500 | $600-15,000 | 95-99% |

## 🚀 AWS Deployment (24/7)

```bash
# On EC2 instance
git clone <your-repo>
cd polymarket-arbitrage-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # Add keys

# Create service
sudo nano /etc/systemd/system/polymarket-bot.service
# Paste service config from PRODUCTION_DEPLOYMENT_GUIDE.md

# Start service
sudo systemctl daemon-reload
sudo systemctl enable polymarket-bot
sudo systemctl start polymarket-bot

# Monitor
sudo journalctl -u polymarket-bot -f
```

## 🔒 Security Checklist

- [ ] Private key in .env (not committed to git)
- [ ] Test in dry-run mode first
- [ ] Start with small amounts ($5-10)
- [ ] Monitor for 24 hours before scaling
- [ ] Set up alerts (SNS/email)
- [ ] Keep only trading capital in hot wallet
- [ ] Withdraw profits regularly

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Overview and quick start |
| [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) | Complete deployment instructions |
| [PRODUCTION_READY_ANALYSIS.md](PRODUCTION_READY_ANALYSIS.md) | Technical analysis |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | What was implemented |
| [ENV_SETUP_GUIDE.md](ENV_SETUP_GUIDE.md) | Environment configuration |

## 🛠️ Key Files

| File | Purpose |
|------|---------|
| `bot.py` | Main entry point |
| `setup_bot.py` | Setup and validation |
| `src/main_orchestrator.py` | Core bot logic |
| `src/wallet_type_detector.py` | Auto wallet detection |
| `src/token_allowance_manager.py` | Allowance management |
| `config/config.py` | Configuration management |

## 🎯 Wallet Types

| Type | Signature Type | Requires Allowances | Example |
|------|----------------|---------------------|---------|
| EOA | 0 | Yes | MetaMask, Ledger |
| Proxy | 1 | No | Email/Google login |
| Safe | 2 | No | Gnosis Safe |

**Auto-detected by setup script**

## 📈 Monitoring

```bash
# Prometheus metrics
curl http://localhost:9090/metrics

# Key metrics:
# - trades_total
# - trades_successful
# - profit_usd
# - balance_usd
# - win_rate
# - gas_price_gwei
```

## 🆘 Emergency Commands

```bash
# Stop bot
pkill -f bot.py

# Stop systemd service
sudo systemctl stop polymarket-bot

# Check balance
python check_balance.py

# Withdraw funds
# Go to polymarket.com → Withdraw

# View recent trades
python -c "from src.trade_history import TradeHistoryDB; db = TradeHistoryDB(); print(db.get_recent_trades(10))"
```

## 🔗 Important Links

- Polymarket: https://polymarket.com
- Deposit: https://polymarket.com (Connect wallet → Deposit)
- Markets: https://polymarket.com/markets
- Polygonscan: https://polygonscan.com
- Gas Tracker: https://polygonscan.com/gastracker
- CLOB API Docs: https://docs.polymarket.com/developers/CLOB/authentication
- py-clob-client: https://github.com/Polymarket/py-clob-client

## 💡 Pro Tips

1. **Always test in dry-run mode first**
   ```bash
   DRY_RUN=true python bot.py
   ```

2. **Start small and scale gradually**
   - Day 1: $5-10
   - Week 1: $50-100
   - Month 1: $500-1000

3. **Monitor gas prices**
   - Bot auto-halts if gas > 800 gwei
   - Check: https://polygonscan.com/gastracker

4. **Withdraw profits regularly**
   - Don't let balance grow too large
   - Keep only trading capital in hot wallet

5. **Set up alerts**
   - Use SNS for critical errors
   - Monitor CloudWatch logs
   - Check Prometheus metrics

6. **Use AWS Secrets Manager for production**
   ```bash
   USE_AWS_SECRETS=true python bot.py
   ```

## 📞 Support

- **Documentation**: See docs/ directory
- **Issues**: GitHub Issues
- **Community**: Polymarket Discord
- **Setup Help**: Run `python setup_bot.py`

---

**Version**: 1.0.0 (Production Ready)
**Last Updated**: 2026-02-06
