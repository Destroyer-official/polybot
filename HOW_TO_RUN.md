# 🚀 How to Run the Polymarket Arbitrage Bot

**Quick guide to get your bot running in 5 minutes!**

---

## 📋 Prerequisites

Before running, make sure you have:
- ✅ Python 3.10 or higher installed
- ✅ Your `.env` file configured with your keys
- ✅ USDC in your Polygon wallet (start with $100-$200)

---

## 🖥️ Option 1: Run Locally (Testing)

### Step 1: Install Dependencies

Open your terminal and run:

```bash
# Install Python packages
pip install -r requirements.txt

# Build Rust fee calculator (one-time setup)
cd rust_core
cargo build --release
cd ..
```

### Step 2: Verify Your .env File

Make sure your `.env` file has:
- Your actual `PRIVATE_KEY`
- Your actual `WALLET_ADDRESS`
- Your actual `POLYGON_RPC_URL` (with Alchemy key)
- `DRY_RUN=true` (for testing)

### Step 3: Run the Bot

```bash
# Run in DRY_RUN mode (no real transactions)
python src/main_orchestrator.py
```

**What you'll see:**
```
🤖 Polymarket Arbitrage Bot Starting...
Mode: DRY_RUN (No real transactions)
Wallet: 0x742d35...
Balance: $150.00 USDC

✅ System initialized
🔍 Scanning markets...
💡 Found opportunity: Market ABC (profit: $0.15)
🛡️ AI Safety: APPROVED
📊 Position size: $1.00
🎯 DRY RUN: Would execute trade (not sending real transaction)
```

### Step 4: Monitor the Bot

The bot will:
- Scan markets every 2 seconds
- Find arbitrage opportunities
- Log everything (but not execute in DRY_RUN mode)
- Show you what it would do

**To stop the bot:**
- Press `Ctrl+C` in the terminal

---

## ☁️ Option 2: Run on AWS (Production)

### Step 1: Launch EC2 Instance

1. Log into AWS Console
2. Go to EC2 → Launch Instance
3. Choose **Ubuntu 22.04 LTS**
4. Instance type: **t3.micro** (for testing) or **c7i.large** (for production)
5. Create/select key pair for SSH access
6. Configure security group:
   - Allow SSH (port 22) from your IP
   - Allow port 9090 for Prometheus metrics
7. Launch instance

### Step 2: Connect to Your Instance

```bash
# SSH into your instance (replace with your key and IP)
ssh -i your-key.pem ubuntu@your-instance-ip
```

### Step 3: Install the Bot

```bash
# Clone your repository
git clone https://github.com/your-username/polymarket-arbitrage-bot.git
cd polymarket-arbitrage-bot

# Run installation script
sudo bash deployment/scripts/install.sh
```

**The script will:**
- Install Python 3.10+
- Install Rust and Cargo
- Install all dependencies
- Build the Rust fee calculator
- Create systemd service
- Set up log rotation

### Step 4: Configure Your .env File

```bash
# Create .env file on the server
nano /home/botuser/polymarket-bot/.env

# Paste your .env content (with your actual keys)
# Save with Ctrl+X, then Y, then Enter
```

**Or upload from your local machine:**
```bash
# From your local machine
scp -i your-key.pem .env ubuntu@your-instance-ip:/home/ubuntu/
ssh -i your-key.pem ubuntu@your-instance-ip
sudo mv /home/ubuntu/.env /home/botuser/polymarket-bot/.env
sudo chown botuser:botuser /home/botuser/polymarket-bot/.env
```

### Step 5: Start the Bot Service

```bash
# Start the bot
sudo systemctl start polymarket-bot

# Check status
sudo systemctl status polymarket-bot

# View live logs
sudo journalctl -u polymarket-bot -f
```

### Step 6: Verify It's Running

```bash
# Run health check
bash deployment/scripts/health_check.sh

# Check metrics
curl http://localhost:9090/metrics

# View recent logs
sudo journalctl -u polymarket-bot -n 100
```

---

## 📊 Monitoring Your Bot

### View Logs

```bash
# Live logs (follow mode)
sudo journalctl -u polymarket-bot -f

# Last 100 lines
sudo journalctl -u polymarket-bot -n 100

# Logs from last hour
sudo journalctl -u polymarket-bot --since "1 hour ago"

# Search for errors
sudo journalctl -u polymarket-bot | grep ERROR
```

### Check Metrics

```bash
# Prometheus metrics
curl http://localhost:9090/metrics

# Or open in browser
http://your-instance-ip:9090/metrics
```

### View Dashboard (Optional)

```bash
# Run status dashboard
python src/status_dashboard.py

# Open in browser
http://your-instance-ip:8050
```

---

## 🎮 Bot Control Commands

### Start/Stop/Restart

```bash
# Start bot
sudo systemctl start polymarket-bot

# Stop bot
sudo systemctl stop polymarket-bot

# Restart bot
sudo systemctl restart polymarket-bot

# Check status
sudo systemctl status polymarket-bot
```

### Enable/Disable Auto-Start

```bash
# Enable auto-start on boot
sudo systemctl enable polymarket-bot

# Disable auto-start
sudo systemctl disable polymarket-bot
```

---

## 🔄 Switching from DRY_RUN to Live Trading

**After 24 hours of successful DRY_RUN testing:**

### Step 1: Stop the Bot

```bash
sudo systemctl stop polymarket-bot
```

### Step 2: Edit .env File

```bash
sudo nano /home/botuser/polymarket-bot/.env

# Change this line:
DRY_RUN=true

# To:
DRY_RUN=false

# Save with Ctrl+X, then Y, then Enter
```

### Step 3: Restart the Bot

```bash
sudo systemctl start polymarket-bot
```

### Step 4: Monitor Closely

```bash
# Watch logs for first hour
sudo journalctl -u polymarket-bot -f
```

**What to watch for:**
- ✅ Real transactions being sent
- ✅ Balance changes
- ✅ Successful trades
- ✅ Profit accumulation
- ❌ Any errors or failures

---

## 🧪 Testing Commands

### Test Configuration

```bash
# Test wallet connection
python -c "from src.wallet_verifier import verify_wallet; verify_wallet()"

# Test RPC connection
python -c "from web3 import Web3; w3 = Web3(Web3.HTTPProvider('YOUR_RPC_URL')); print(f'Connected: {w3.is_connected()}')"

# Test fee calculator
python test_rust_fee_calculator.py
```

### Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_internal_arbitrage_properties.py

# Run with coverage
pytest --cov=src --cov-report=html
```

---

## 📈 What to Expect

### DRY_RUN Mode (Testing)
- ✅ Scans 10-50 markets per minute
- ✅ Finds 5-20 opportunities per hour
- ✅ Logs show "DRY RUN MODE" prominently
- ✅ NO actual transactions
- ✅ NO balance changes

### Live Trading Mode
- ✅ Executes real trades
- ✅ Balance changes (increases with profit)
- ✅ Gas fees deducted
- ✅ Profits accumulate
- ✅ Auto-withdraw when balance > $500

---

## 🚨 Troubleshooting

### Bot Won't Start

```bash
# Check logs for errors
sudo journalctl -u polymarket-bot -n 50

# Common issues:
# 1. Missing .env file
# 2. Invalid private key
# 3. RPC connection failed
# 4. Insufficient balance
```

### No Opportunities Found

```bash
# Check if markets are being scanned
sudo journalctl -u polymarket-bot | grep "Scanning"

# Possible reasons:
# 1. Market conditions (no arbitrage available)
# 2. RPC connection issues
# 3. High gas prices (trading halted)
```

### High Gas Prices

```bash
# Check current gas price
curl http://localhost:9090/metrics | grep gas_price

# Bot automatically halts trading if gas > 800 gwei
# Wait for gas to drop, bot will resume automatically
```

### Balance Issues

```bash
# Check balance
python -c "from src.fund_manager import FundManager; fm = FundManager(); print(f'Balance: ${fm.get_balance()}')"

# Auto-deposit triggers at $50
# Auto-withdraw triggers at $500
```

---

## 🛑 Emergency Stop

### Stop Bot Immediately

```bash
# Stop service
sudo systemctl stop polymarket-bot

# Kill process (if service won't stop)
sudo pkill -f main_orchestrator
```

### Withdraw All Funds

```bash
# Run manual withdrawal
python -c "from src.fund_manager import FundManager; fm = FundManager(); fm.withdraw_all()"
```

---

## 📞 Quick Reference

### Essential Commands

```bash
# Start bot
sudo systemctl start polymarket-bot

# Stop bot
sudo systemctl stop polymarket-bot

# View logs
sudo journalctl -u polymarket-bot -f

# Check status
sudo systemctl status polymarket-bot

# Health check
bash deployment/scripts/health_check.sh

# View metrics
curl http://localhost:9090/metrics
```

### Important Files

```
/home/botuser/polymarket-bot/.env          # Configuration
/var/log/polymarket-bot/bot.log            # Application logs
/etc/systemd/system/polymarket-bot.service # Service config
```

---

## 🎯 Quick Start Summary

### Local Testing (5 minutes)
```bash
pip install -r requirements.txt
cd rust_core && cargo build --release && cd ..
python src/main_orchestrator.py
```

### AWS Deployment (10 minutes)
```bash
# On AWS instance
git clone <your-repo>
cd polymarket-arbitrage-bot
sudo bash deployment/scripts/install.sh
sudo nano /home/botuser/polymarket-bot/.env  # Add your keys
sudo systemctl start polymarket-bot
sudo journalctl -u polymarket-bot -f
```

---

## ✅ Deployment Checklist

- [ ] Python 3.10+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Rust fee calculator built (`cargo build --release`)
- [ ] `.env` file configured with actual keys
- [ ] `DRY_RUN=true` for testing
- [ ] USDC in wallet ($100-$200 minimum)
- [ ] Bot started and running
- [ ] Logs showing market scans
- [ ] Opportunities being detected
- [ ] Monitor for 24 hours
- [ ] Switch to `DRY_RUN=false` after testing
- [ ] Monitor live trading closely

---

**Need help?** Check these files:
- `DEPLOYMENT_READY.md` - Deployment overview
- `ENV_SETUP_GUIDE.md` - API keys guide
- `HOW_BOT_WORKS.md` - How the bot trades
- `VALIDATION_REPORT.md` - Test results

**Ready to run!** 🚀
