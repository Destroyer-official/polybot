# 🚀 AWS Bot Control Commands - Quick Reference

**All commands tested and verified working! ✅**

---

## 📋 Basic Service Control

### Start the Bot
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl start polybot"
```
✅ **Tested:** Starts the bot service successfully

### Stop the Bot
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl stop polybot"
```
✅ **Tested:** Stops the bot gracefully with exit code 0

### Restart the Bot
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"
```
✅ **Tested:** Restarts the bot (useful after config changes)

### Check Status
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot"
```
✅ **Tested:** Shows current status, uptime, memory, CPU usage

---

## 📊 Log Viewing Commands

### View Live Logs (Real-time)
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -f"
```
✅ **Tested:** Shows live streaming logs (press Ctrl+C to exit)

### View Last 50 Lines
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 50 --no-pager"
```

### View Last 100 Lines
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 100 --no-pager"
```

### View Logs Since Time
```bash
# Last 10 minutes
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '10 minutes ago' --no-pager"

# Last hour
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '1 hour ago' --no-pager"

# Today
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since today --no-pager"
```

---

## 🔍 Filtered Log Searches

### Check LLM V2 Activity
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '10 minutes ago' --no-pager | grep -E 'V2|PERFECT|Decision Engine'"
```

### Check Balance
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 100 --no-pager | grep -i balance"
```

### Check Active Positions
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 100 --no-pager | grep -E 'WATCHING.*position|Checking exit'"
```

### Check Errors
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 200 --no-pager | grep -i error"
```

### Check Trades (when live)
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 200 --no-pager | grep -E 'TRADE|ORDER'"
```

---

## ⚙️ Configuration Management

### View Current .env Settings
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cat /home/ubuntu/polybot/.env"
```

### Check DRY_RUN Status
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cat /home/ubuntu/polybot/.env | grep DRY_RUN"
```

### Edit .env File (Interactive)
```bash
ssh -i money.pem ubuntu@35.76.113.47 "nano /home/ubuntu/polybot/.env"
```
**After editing:** Run `sudo systemctl restart polybot` to apply changes

---

## 🔄 Update Bot Code

### Pull Latest Code from Git
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && git pull"
```

### Restart After Update
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && git pull && sudo systemctl restart polybot"
```

---

## 📈 Quick Health Check

### One-Command Status Check
```bash
ssh -i money.pem ubuntu@35.76.113.47 "echo '=== SERVICE STATUS ===' && sudo systemctl status polybot --no-pager | head -10 && echo '' && echo '=== RECENT ACTIVITY ===' && sudo journalctl -u polybot -n 20 --no-pager"
```

### Check if Bot is Running
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl is-active polybot"
```
Returns: `active` or `inactive`

---

## 🛠️ Troubleshooting Commands

### View Full Service Configuration
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl cat polybot"
```

### Check Service Failures
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot --no-pager -l"
```

### View All Logs (No Limit)
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --no-pager"
```

### Clear Journal Logs (if too large)
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl --vacuum-time=1d"
```

---

## 🎯 Common Workflows

### After Changing .env
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot && sleep 3 && sudo journalctl -u polybot -n 30 --no-pager"
```

### Quick Status + Recent Logs
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot --no-pager | head -15 && echo '' && sudo journalctl -u polybot -n 20 --no-pager"
```

### Monitor for Errors
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -f | grep -i error"
```

---

## 📝 Notes

- **All commands tested:** February 9, 2026, 09:49 UTC ✅
- **Service name:** `polybot`
- **Working directory:** `/home/ubuntu/polybot`
- **Python environment:** `/home/ubuntu/polybot/venv`
- **Auto-restart:** Enabled (bot restarts automatically on failure)
- **DRY_RUN:** Currently set to `true` (safe mode)

---

## 🚨 Emergency Commands

### Force Stop
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl kill polybot"
```

### Disable Auto-Start
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl disable polybot"
```

### Enable Auto-Start
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl enable polybot"
```

---

**All commands verified working! Use these for easy bot management. 🎉**
