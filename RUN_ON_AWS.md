# RUN BOT ON AWS - 24/7 AUTONOMOUS TRADING

## Main Program for AWS:

The main program that runs 24/7 is:
```bash
python -m src.main_orchestrator
```

OR use the test script (same thing):
```bash
python test_autonomous_bot.py
```

Both run the same autonomous bot with 24/7 trading.

---

## Current Status:

The bot just ran and detected:
```
✓ Checked all networks
✓ Found $4.63 USDC on Ethereum
✗ Found 0.000339 ETH (need 0.002 ETH for gas)
✗ Cannot bridge automatically without ETH
✗ Stopped to protect your money
```

---

## To Deploy to AWS:

### Step 1: Bridge USDC to Polygon First

**You MUST do this before AWS deployment:**

**Option A: Add ETH (Bot bridges automatically)**
- Send 0.002 ETH to: `0x1A821E4488732156cC9B3580efe3984F9B6C0116`
- Network: Ethereum
- Bot will bridge automatically

**Option B: Manual Bridge (Polymarket pays gas)**
- Go to: https://polymarket.com
- Click: Deposit → Connect Wallet
- Bridge: $4.63 USDC from Ethereum to Polygon
- Wait: 5-15 minutes

### Step 2: Deploy to AWS

Once USDC is on Polygon, deploy to AWS:

```bash
# Upload files to AWS
scp -i money.pem -r . ubuntu@<your-aws-ip>:/home/ubuntu/polybot/

# SSH into AWS
ssh -i money.pem ubuntu@<your-aws-ip>

# Install dependencies
cd /home/ubuntu/polybot
pip install -r requirements.txt

# Run bot 24/7 with nohup
nohup python test_autonomous_bot.py > bot.log 2>&1 &

# Check if running
ps aux | grep python

# View logs
tail -f bot.log
```

### Step 3: Bot Runs 24/7 Automatically

Once started, the bot will:
- ✓ Scan 1000+ markets every 2 seconds
- ✓ Execute trades automatically
- ✓ Deposit funds when needed
- ✓ Withdraw profits when balance high
- ✓ Adjust position sizes dynamically
- ✓ Run 24/7 without stopping
- ✓ NO human intervention needed

---

## Alternative: Use Systemd Service (Better for AWS)

Create a systemd service for automatic restart:

```bash
# Create service file
sudo nano /etc/systemd/system/polybot.service
```

Add this content:
```ini
[Unit]
Description=Polymarket Arbitrage Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/polybot
ExecStart=/usr/bin/python3 test_autonomous_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/polybot/bot.log
StandardError=append:/home/ubuntu/polybot/bot.log

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable polybot
sudo systemctl start polybot
sudo systemctl status polybot
```

View logs:
```bash
sudo journalctl -u polybot -f
```

---

## What Happens on AWS:

### Bot Startup:
```
POLYMARKET ARBITRAGE BOT STARTED
Wallet: 0x1A821E4488732156cC9B3580efe3984F9B6C0116
DRY RUN: False (LIVE TRADING)
Scan interval: 2s

Checking for cross-chain funds...
✓ Polygon USDC: $4.63
✓ Funds verified - proceeding with autonomous trading

Fetching markets from CLOB API...
Found 1247 total active markets
Scanning for opportunities...
```

### Continuous Trading:
```
[Every 2 seconds]
Scanning markets...
Found 3 opportunities
Executing trade...
✓ Trade successful - Profit: $0.0026

[Every 60 seconds]
Heartbeat: Balance=$4.63, Gas=25gwei, Healthy=True
Checking fund management...
```

### 24/7 Operation:
- Runs continuously
- Auto-restarts if crashes
- Logs everything
- No human intervention needed

---

## Monitoring on AWS:

### Check if bot is running:
```bash
ps aux | grep python
sudo systemctl status polybot
```

### View real-time logs:
```bash
tail -f bot.log
sudo journalctl -u polybot -f
```

### Check balance:
```bash
python check_all_networks.py
```

### Stop bot:
```bash
sudo systemctl stop polybot
```

### Restart bot:
```bash
sudo systemctl restart polybot
```

---

## Summary:

**Main Program:** `python test_autonomous_bot.py` or `python -m src.main_orchestrator`

**Current Blocker:** USDC is on Ethereum, needs to be on Polygon

**After Bridging:** Deploy to AWS and bot runs 24/7 automatically

**No Human Intervention:** Bot does everything - trading, deposits, withdrawals, position sizing

---

**Ready to deploy to AWS once USDC is on Polygon!**
