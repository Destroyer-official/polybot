# 🔧 Quick Fix - Run the Bot Now!

**You're almost there! Just run these commands:**

---

## ✅ On Your AWS Server

You're already in the right directory (`~/polybot`). Just run:

```bash
# Make the run script executable
chmod +x run_bot.sh

# Run the bot
./run_bot.sh
```

**That's it!** The bot will start.

---

## 🎯 Alternative: Run Directly

If the script doesn't work, run this:

```bash
# Set PYTHONPATH and run
export PYTHONPATH=$PYTHONPATH:.
source venv/bin/activate
python3 src/main_orchestrator.py
```

---

## 📋 What Was Fixed

1. **PositionMerger initialization** - Added missing parameters (usdc_address, wallet)
2. **PYTHONPATH** - Set to include current directory so Python can find the `config` module
3. **Virtual environment** - Activated to use installed packages

---

## 🚀 What You'll See

When the bot starts successfully:

```
================================================================================
POLYMARKET ARBITRAGE BOT STARTED
================================================================================
Wallet: 0xYourWalletAddress
Chain ID: 137
DRY RUN: True
Scan interval: 2s
Min profit threshold: 0.5%
================================================================================
[INFO] Connecting to Polygon RPC...
[INFO] ✓ Wallet address verified
[INFO] Initializing CLOB client...
[INFO] Initializing core components...
[INFO] Initializing strategy engines...
[INFO] Initializing monitoring system...
[INFO] MainOrchestrator initialized successfully
[INFO] Performing heartbeat check...
[INFO] Scanning markets...
```

---

## ⚠️ If You See Errors

### "No .env file found"
```bash
# Create .env file
nano .env
# Paste your configuration with actual keys
# Save with Ctrl+X, Y, Enter
```

### "Invalid private key"
```bash
# Check your .env file
cat .env | grep PRIVATE_KEY
# Make sure it starts with 0x and is 66 characters long
```

### "RPC connection failed"
```bash
# Test your RPC URL
curl -X POST YOUR_RPC_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

---

## 🛑 To Stop the Bot

Press `Ctrl+C` in the terminal.

---

## 📊 Monitor the Bot

```bash
# In another terminal, watch the logs
tail -f logs/bot.log

# Or if using systemd (after setup)
sudo journalctl -u polymarket-bot -f
```

---

**Ready to run!** Execute: `./run_bot.sh` 🚀
