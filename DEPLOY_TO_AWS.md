# Deploy to AWS - Step by Step Guide

## 🎯 Quick Start (3 Commands)

### On Windows (PowerShell or Git Bash):
```bash
# 1. Set PEM permissions (if using Git Bash)
chmod 400 money.pem

# 2. SSH to AWS
ssh -i "money.pem" ubuntu@18.207.221.6

# 3. Once connected, run:
cd ~/polybot && source venv/bin/activate && ./run_bot.sh
```

## 📋 Detailed Step-by-Step

### Step 1: Connect to AWS Server

Open PowerShell or Git Bash and run:
```bash
ssh -i "money.pem" ubuntu@18.207.221.6
```

You should see:
```
Welcome to Ubuntu 24.04.3 LTS
...
ubuntu@ip-172-31-87-2:~$
```

### Step 2: Navigate to Bot Directory
```bash
cd ~/polybot
```

### Step 3: Update .env File (IMPORTANT!)

Your local .env has been updated with DRY_RUN=true. Update it on the server:

```bash
nano .env
```

Find this line:
```
DRY_RUN=true
```

Make sure it says `true` for testing!

Press `Ctrl+X`, then `Y`, then `Enter` to save.

### Step 4: Activate Virtual Environment
```bash
source venv/bin/activate
```

You should see `(venv)` appear in your prompt:
```
(venv) ubuntu@ip-172-31-87-2:~/polybot$
```

### Step 5: Install/Update Dependencies (Optional)
```bash
pip install -r requirements.txt
```

### Step 6: Run the Bot
```bash
./run_bot.sh
```

## ✅ What You Should See

The bot will start and display:
```
================================================================================
POLYMARKET ARBITRAGE BOT STARTED
================================================================================
Wallet: 0x1A821E4488732156cC9B3580efe3984F9B6C0116
Chain ID: 137
DRY RUN: True  ← IMPORTANT: This should say True!
Scan interval: 2s
Min profit threshold: 0.5%
================================================================================
```

Then you'll see:
- Market scanning every 2 seconds
- Heartbeat checks every 60 seconds
- Opportunity detection (if any found)
- Balance checks
- Gas price monitoring

## 📊 Monitor the Bot

### In the Same Terminal
You'll see real-time output as the bot runs.

### In a New Terminal (Recommended)
Open a second SSH connection to view logs:

```bash
# Terminal 2
ssh -i "money.pem" ubuntu@18.207.221.6
cd ~/polybot
tail -f logs/bot.log
```

### Check State File
```bash
cat state.json
```

## 🛑 Stop the Bot

Press `Ctrl+C` in the terminal where the bot is running.

The bot will:
1. Stop accepting new trades
2. Wait for pending transactions
3. Save final state
4. Display statistics
5. Shutdown gracefully

## 📝 Testing Checklist

Run for **2-4 hours** and verify:

- [ ] Bot starts without errors
- [ ] "DRY RUN: True" is displayed
- [ ] Connects to Polygon RPC
- [ ] Wallet address verified
- [ ] Scans markets every 2 seconds
- [ ] Heartbeat checks every 60 seconds
- [ ] No crashes or errors
- [ ] Logs written to `logs/bot.log`
- [ ] State saved to `state.json`

## 🔍 Troubleshooting

### "Permission denied" for money.pem
```bash
chmod 400 money.pem
```

### "polybot directory not found"
```bash
# Check if it exists
ls -la ~
# If not, you need to upload the bot files first
```

### ".env file not found"
```bash
# Create it from the example
cp .env.example .env
nano .env
# Add your actual keys
```

### "Virtual environment not found"
```bash
# Create it
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Bot crashes immediately
```bash
# Check logs
cat logs/bot.log
# Check for error messages
```

### "Failed to connect to RPC"
- Check your Alchemy API key in .env
- Verify internet connection
- Try backup RPC URLs

## ⏭️ After Testing

If everything works well after 2-4 hours:

1. **Stop the bot:** `Ctrl+C`
2. **Review logs:** `cat logs/bot.log | grep ERROR`
3. **Check statistics:** `cat state.json`
4. **Enable live trading:**
   ```bash
   nano .env
   # Change DRY_RUN=true to DRY_RUN=false
   ```
5. **Restart:** `./run_bot.sh`
6. **Monitor closely!**

## 🚀 Run as Background Service (Optional)

To keep the bot running even after you disconnect:

### Option 1: Using screen
```bash
# Start a screen session
screen -S polybot

# Run the bot
cd ~/polybot
source venv/bin/activate
./run_bot.sh

# Detach: Press Ctrl+A, then D
# Reattach later: screen -r polybot
```

### Option 2: Using systemd
```bash
# Create service file
sudo nano /etc/systemd/system/polybot.service
```

Paste:
```ini
[Unit]
Description=Polymarket Arbitrage Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/polybot
Environment="PATH=/home/ubuntu/polybot/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/home/ubuntu/polybot"
ExecStart=/home/ubuntu/polybot/venv/bin/python3 /home/ubuntu/polybot/src/main_orchestrator.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable polybot
sudo systemctl start polybot
sudo systemctl status polybot
sudo journalctl -u polybot -f
```

## 📞 Need Help?

Check these files:
- `TEST_RESULTS.md` - Test results
- `FINAL_STATUS.md` - Deployment status
- `HOW_TO_RUN.md` - Detailed guide
- `HOW_BOT_WORKS.md` - Strategy explanation

## ✅ Summary

**To start testing NOW:**
```bash
ssh -i "money.pem" ubuntu@18.207.221.6
cd ~/polybot
source venv/bin/activate
./run_bot.sh
```

That's it! The bot will start in DRY_RUN mode (safe testing). Monitor for 2-4 hours, then enable live trading if everything looks good.

Good luck! 🚀
