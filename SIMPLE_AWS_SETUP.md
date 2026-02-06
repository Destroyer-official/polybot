# 🚀 Simple AWS Setup - Step by Step

**You're already on your AWS server! Follow these exact commands:**

---

## ✅ You Are Here

```
ubuntu@ip-172-31-87-2:~/polybot$
```

Good! You're in the right directory.

---

## 📋 Step-by-Step Setup

### Step 1: Run the Installation Script

```bash
# Run the install script (this sets everything up)
sudo bash deployment/scripts/install.sh
```

**This will:**
- Install Python 3.10+
- Install Rust and Cargo
- Install all dependencies
- Build the Rust fee calculator
- Create systemd service
- Set up directories

**Wait for it to complete** (takes 5-10 minutes)

---

### Step 2: Create Your .env File

```bash
# Create .env file
nano .env
```

**Paste this and fill in YOUR actual keys:**

```bash
# REQUIRED - Replace with your actual values
PRIVATE_KEY=0xYOUR_ACTUAL_PRIVATE_KEY_HERE
WALLET_ADDRESS=0xYOUR_ACTUAL_WALLET_ADDRESS_HERE
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY_HERE

# RECOMMENDED
BACKUP_RPC_URLS=https://rpc-mainnet.matic.network,https://polygon-rpc.com
NVIDIA_API_KEY=YOUR_NVIDIA_KEY_HERE

# OPERATIONAL SETTINGS
DRY_RUN=true
STAKE_AMOUNT=1.0
MIN_PROFIT_THRESHOLD=0.005
MAX_POSITION_SIZE=5.0
MIN_BALANCE=50.0
WITHDRAW_LIMIT=500.0
MAX_GAS_PRICE_GWEI=800
SCAN_INTERVAL_SECONDS=2
HEARTBEAT_INTERVAL_SECONDS=60
CHAIN_ID=137

# CONTRACT ADDRESSES (Don't change)
USDC_ADDRESS=0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
CTF_EXCHANGE_ADDRESS=0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
CONDITIONAL_TOKEN_ADDRESS=0x4D97DCd97eC945f40cF65F87097ACe5EA0476045

# MONITORING
PROMETHEUS_PORT=9090
```

**Save and exit:**
- Press `Ctrl+X`
- Press `Y`
- Press `Enter`

---

### Step 3: Start the Bot

```bash
# Start the bot service
sudo systemctl start polymarket-bot

# Check if it's running
sudo systemctl status polymarket-bot
```

**You should see:**
```
● polymarket-bot.service - Polymarket Arbitrage Bot
   Loaded: loaded
   Active: active (running)
```

---

### Step 4: Watch the Logs

```bash
# View live logs
sudo journalctl -u polymarket-bot -f
```

**You should see:**
```
[INFO] Polymarket Arbitrage Bot Starting...
[INFO] Mode: DRY_RUN
[INFO] Wallet: 0xYourAddress
[INFO] Scanning markets...
```

**To stop viewing logs:** Press `Ctrl+C`

---

## 🎮 Control Commands

```bash
# Start bot
sudo systemctl start polymarket-bot

# Stop bot
sudo systemctl stop polymarket-bot

# Restart bot
sudo systemctl restart polymarket-bot

# Check status
sudo systemctl status polymarket-bot

# View logs
sudo journalctl -u polymarket-bot -f

# View last 100 lines
sudo journalctl -u polymarket-bot -n 100
```

---

## 🔧 Alternative: Run Directly (Without Systemd)

If you want to run it directly without systemd:

```bash
# Make sure you're in the polybot directory
cd ~/polybot

# Activate virtual environment (if created)
source venv/bin/activate

# Run the bot directly
python src/main_orchestrator.py
```

**To stop:** Press `Ctrl+C`

---

## 🧪 Quick Test

Before starting the bot, test if everything is installed:

```bash
# Check Python version
python3 --version

# Check if dependencies are installed
pip3 list | grep web3

# Check if Rust is installed
cargo --version

# Check if .env file exists
ls -la .env
```

---

## 📊 Monitor Your Bot

### Check if it's finding opportunities

```bash
# Search logs for opportunities
sudo journalctl -u polymarket-bot | grep "opportunity"

# Search for trades
sudo journalctl -u polymarket-bot | grep "trade"

# Search for errors
sudo journalctl -u polymarket-bot | grep "ERROR"
```

### Check metrics

```bash
# View Prometheus metrics
curl http://localhost:9090/metrics
```

---

## 🚨 Troubleshooting

### If install.sh fails:

```bash
# Install Python manually
sudo apt update
sudo apt install -y python3.10 python3-pip python3-venv

# Install Rust manually
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Install dependencies
pip3 install -r requirements.txt

# Build Rust calculator
cd rust_core
cargo build --release
cd ..
```

### If bot won't start:

```bash
# Check logs for errors
sudo journalctl -u polymarket-bot -n 50

# Check if .env file exists
cat .env

# Check if service file exists
ls -la /etc/systemd/system/polymarket-bot.service

# Reload systemd
sudo systemctl daemon-reload
```

### If you see "command not found":

```bash
# Use python3 instead of python
python3 src/main_orchestrator.py

# Use pip3 instead of pip
pip3 install -r requirements.txt
```

---

## ✅ Quick Checklist

- [ ] Run `sudo bash deployment/scripts/install.sh`
- [ ] Create `.env` file with your actual keys
- [ ] Set `DRY_RUN=true` for testing
- [ ] Run `sudo systemctl start polymarket-bot`
- [ ] Check logs with `sudo journalctl -u polymarket-bot -f`
- [ ] Monitor for 24 hours
- [ ] Change to `DRY_RUN=false` after testing

---

## 🎯 Next Steps

1. **Run the install script** (Step 1 above)
2. **Create .env file** (Step 2 above)
3. **Start the bot** (Step 3 above)
4. **Monitor logs** (Step 4 above)
5. **Wait 24 hours** in DRY_RUN mode
6. **Switch to live trading** (change DRY_RUN=false)

---

**You're ready!** Start with Step 1 above. 🚀
