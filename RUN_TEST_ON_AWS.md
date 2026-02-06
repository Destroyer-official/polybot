# Run DRY_RUN Test on AWS - Step by Step

## 📋 What You Need to Do

Follow these exact steps to run the bot in safe DRY_RUN mode on your AWS server.

---

## Step 1: Copy Files to AWS Server

First, you need to copy the updated `.env` file and test script to your AWS server.

### On Your Local Windows Machine (PowerShell):

```powershell
# Copy .env file to AWS
scp -i "money.pem" .env ubuntu@18.207.221.6:~/polybot/.env

# Copy test script to AWS
scp -i "money.pem" test_dry_run.sh ubuntu@18.207.221.6:~/polybot/test_dry_run.sh
```

---

## Step 2: SSH to AWS Server

```powershell
ssh -i "money.pem" ubuntu@18.207.221.6
```

You should now be connected to your AWS server.

---

## Step 3: Navigate to Bot Directory

```bash
cd ~/polybot
```

---

## Step 4: Make Test Script Executable

```bash
chmod +x test_dry_run.sh
```

---

## Step 5: Run the Test

```bash
./test_dry_run.sh
```

The script will:
- ✅ Check you're in the right directory
- ✅ Activate virtual environment
- ✅ Verify DRY_RUN is set to true
- ✅ Check dependencies are installed
- ✅ Start the bot in safe testing mode

---

## 📊 What You'll See

The bot will start and display:

```
================================================================================
POLYMARKET ARBITRAGE BOT STARTED
================================================================================
Wallet: 0x1A821E4488732156cC9B3580efe3984F9B6C0116
Chain ID: 137
DRY RUN: True  ← SAFE MODE!
Scan interval: 2s
Min profit threshold: 0.5%
================================================================================
```

Then you'll see continuous output like:
```
Fetching markets from CLOB API...
Found 23 active 15-min crypto markets
Found 0 total opportunities
Performing heartbeat check...
Balance: $5.00 USDC
Gas price: 45 gwei
System healthy
```

---

## ⏱️ How Long to Test

**Minimum:** 30 minutes  
**Recommended:** 2-4 hours  
**Ideal:** 24 hours

---

## ✅ What to Check

While the bot is running, verify:

1. **No Errors:** Bot runs without crashing
2. **Heartbeat:** Checks every 60 seconds
3. **Market Scanning:** Scans every 2 seconds
4. **Balance Check:** Shows your wallet balance
5. **Gas Price:** Shows current gas price
6. **DRY_RUN:** Confirms "DRY RUN: True"

---

## 🛑 How to Stop

Press `Ctrl+C` and the bot will shutdown gracefully:

```
================================================================================
SHUTTING DOWN GRACEFULLY
================================================================================
Waiting for pending transactions...
Saving final state...
Performing final heartbeat...
================================================================================
FINAL STATISTICS
================================================================================
Total Trades: 0 (simulated)
Win Rate: 0.00%
Total Profit: $0.00
Total Gas Cost: $0.00
Net Profit: $0.00
================================================================================
SHUTDOWN COMPLETE
================================================================================
```

---

## 📁 Check Logs

While bot is running, open another terminal and check logs:

```bash
# SSH to AWS in new terminal
ssh -i "money.pem" ubuntu@18.207.221.6

# View live logs
cd ~/polybot
tail -f logs/bot.log
```

Or check the state file:
```bash
cat state.json
```

---

## ⏭️ After Testing

If everything looks good after 2-4 hours:

### Option A: Enable Live Trading

```bash
# Stop the bot (Ctrl+C)

# Edit .env file
nano .env

# Change this line:
DRY_RUN=false

# Save and exit (Ctrl+X, Y, Enter)

# Restart bot
./test_dry_run.sh
```

### Option B: Keep Testing Longer

Just let it run for 24 hours to be extra safe!

---

## 🆘 Troubleshooting

### "Permission denied" when running script
```bash
chmod +x test_dry_run.sh
```

### "Module not found" errors
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "Failed to connect to RPC"
- Check internet connection
- Verify Alchemy API key in .env

### Bot crashes immediately
```bash
# Check logs
cat logs/bot.log

# Check Python errors
python3 src/main_orchestrator.py
```

---

## 📞 Need Help?

If you see any errors, copy the error message and I can help you fix it!

---

## ✅ Quick Command Summary

```bash
# 1. Copy files (on Windows)
scp -i "money.pem" .env ubuntu@18.207.221.6:~/polybot/.env
scp -i "money.pem" test_dry_run.sh ubuntu@18.207.221.6:~/polybot/test_dry_run.sh

# 2. SSH to AWS
ssh -i "money.pem" ubuntu@18.207.221.6

# 3. Navigate and run
cd ~/polybot
chmod +x test_dry_run.sh
./test_dry_run.sh

# 4. Stop when done
Ctrl+C
```

---

**Good luck with your testing!** 🚀
