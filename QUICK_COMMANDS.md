# 🎮 QUICK COMMANDS - Super Smart Bot

## 📊 Check Bot Status
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot"
```

## 📈 Watch Live Logs
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -f"
```

## 🧠 Watch Bot Learn
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -f | grep '🧠'"
```

## 📊 Check Learning Data
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json | jq '.'"
```

## 🎯 Check Win Rate
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json | jq '{trades: .total_trades, wins: .total_wins, win_rate: (if .total_trades > 0 then (.total_wins / .total_trades * 100) else 0 end)}'"
```

## 💰 Check Balance
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -n 1000 --no-pager | grep 'Total Available' | tail -1"
```

## 🔄 Restart Bot
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"
```

## 📋 Check Current Parameters
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json | jq '.optimal_params'"
```

## 📊 Check Strategy Performance
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json | jq '.strategy_stats'"
```

## 🎯 Check Asset Performance
```bash
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && cat data/super_smart_learning.json | jq '.asset_performance'"
```

## 🔥 Check Recent Trades
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '1 hour ago' --no-pager | grep 'LEARNED FROM TRADE'"
```

## ⚠️ Check for Errors
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '10 minutes ago' --no-pager | grep -i error"
```

## 🎮 Switch to Live Trading (After Testing!)
```bash
ssh -i money.pem ubuntu@35.76.113.47
cd /home/ubuntu/polybot
nano .env
# Change DRY_RUN=true to DRY_RUN=false
# Save: Ctrl+X, Y, Enter
sudo systemctl restart polybot
```

---

## 📱 ONE-LINE STATUS CHECK
```bash
ssh -i money.pem ubuntu@35.76.113.47 "echo '=== BOT STATUS ===' && sudo systemctl status polybot | grep Active && echo '' && echo '=== BALANCE ===' && sudo journalctl -u polybot -n 1000 --no-pager | grep 'Total Available' | tail -1 && echo '' && echo '=== LEARNING ===' && cd /home/ubuntu/polybot && cat data/super_smart_learning.json | jq '{trades: .total_trades, wins: .total_wins, win_rate: (if .total_trades > 0 then (.total_wins / .total_trades * 100) else 0 end), best_strategy: .strategy_stats}'"
```

---

**Tip**: Bookmark this file for quick access to all commands!
