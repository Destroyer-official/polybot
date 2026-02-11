# ✅ POST-DEPLOYMENT CHECKLIST

Use this checklist after deploying the fixes to verify everything is working correctly.

---

## Immediate Checks (First 5 Minutes)

### 1. Service Status
```powershell
ssh -i money.pem ubuntu@35.76.113.47 'sudo systemctl status polybot.service'
```

- [ ] Service is `active (running)`
- [ ] No error messages in status
- [ ] Process ID is shown
- [ ] Started timestamp is recent

### 2. Recent Logs
```powershell
ssh -i money.pem ubuntu@35.76.113.47 'sudo journalctl -u polybot.service -n 50'
```

- [ ] Bot initialized successfully
- [ ] No Python syntax errors
- [ ] No import errors
- [ ] Binance feed connected
- [ ] Risk manager initialized

### 3. Error Check
```powershell
ssh -i money.pem ubuntu@35.76.113.47 'sudo journalctl -u polybot.service -n 100 | grep -i error'
```

- [ ] No critical errors
- [ ] No "Risk manager blocked" errors
- [ ] No "Minimum size not met" errors
- [ ] No syntax/import errors

---

## Short-Term Checks (First 30 Minutes)

### 4. Market Scanning
Look for these log messages:
```
📊 Found X CURRENT 15-minute markets (trading now!)
🎯 CURRENT BTC market: Up=$X.XX, Down=$X.XX
💰 SUM-TO-ONE CHECK: BTC | UP=$X.XX + DOWN=$X.XX = $X.XX
📊 LATENCY CHECK: BTC | Binance=$X.XX | 10s Change=X.XX%
```

- [ ] Bot is fetching markets
- [ ] Markets are being analyzed
- [ ] Sum-to-one checks running
- [ ] Latency checks running

### 5. Risk Manager Activity
Look for these log messages:
```
💰 Available balance: $X.XX
📊 Portfolio heat: X.X% (max: 80% for small balances)
✅ Risk manager allows trade
```

- [ ] Balance checks working
- [ ] Portfolio heat calculated correctly
- [ ] Risk manager NOT blocking trades
- [ ] Heat limit is 80% (not 30%)

### 6. Order Placement Attempts
Look for these log messages:
```
📈 PLACING ORDER
   Market: ...
   Side: UP/DOWN
   Price: $X.XX
   Shares (requested): X.XX
   Value (requested): $X.XX
```

- [ ] Bot is attempting to place orders
- [ ] Order parameters look correct
- [ ] Shares >= 1.0 (meets minimum)
- [ ] Value >= $1.00 (meets minimum)

### 7. Slippage Protection
Look for these log messages:
```
🚫 SKIPPING TRADE: Excessive slippage (XX%)
   High slippage causes losses - waiting for better conditions
```

- [ ] Bot is checking slippage
- [ ] High slippage trades are rejected
- [ ] Bot explains why trade was skipped

### 8. Market Minimum Checks
Look for these log messages:
```
⚠️ Could not check market minimum size
   Proceeding with X.XX shares (may fail if below market minimum)
```
OR
```
❌ Market requires minimum X shares, but we can only afford X.XX shares
   SKIPPING this trade - insufficient capital for market minimum
```

- [ ] Bot is checking market minimums
- [ ] Bot skips trades it can't afford
- [ ] No "minimum size not met" order failures

---

## Medium-Term Checks (First 1-2 Hours)

### 9. Successful Order Placement
Look for these log messages:
```
✅ ORDER PLACED SUCCESSFULLY: order_id
   Actual size placed: X.XX shares
   Actual value: $X.XX
```

- [ ] At least 1 order placed successfully
- [ ] Order ID is shown
- [ ] Size and value are correct
- [ ] No order failures

### 10. Position Tracking
Look for these log messages:
```
📝 Position tracked: X.XX shares @ $X.XX
📊 Active positions: X
   - BTC UP: entry=$X.XX, age=X.Xmin
```

- [ ] Positions are being tracked
- [ ] Position details are correct
- [ ] Multiple positions possible (not just 1)

### 11. Dynamic Take Profit
Look for these log messages:
```
🎯 Dynamic take profit calculation:
   - Time remaining: X min → X.X% target
   - Position age: X min → X.X% target
   - Binance momentum: ... → X.X% target
```

- [ ] Dynamic TP is calculating
- [ ] TP adjusts based on conditions
- [ ] TP is NOT fixed at 1.2%
- [ ] TP ranges from 0.2% to 1%

### 12. Position Exits
Look for these log messages:
```
🎉 DYNAMIC TAKE PROFIT on BTC UP!
   Target: X.XX% | Actual: X.XX%
   Entry: $X.XX -> Exit: $X.XX
   Profit: $X.XX
```
OR
```
❌ DYNAMIC STOP LOSS on BTC UP!
   Target: -X.XX% | Actual: -X.XX%
   Entry: $X.XX -> Exit: $X.XX
   Loss: $X.XX
```

- [ ] Bot is closing positions
- [ ] Take profit is working
- [ ] Stop loss is working
- [ ] P&L is calculated correctly

### 13. Sell Orders
Look for these log messages:
```
📉 CLOSING POSITION
   Asset: BTC
   Side: UP
   Size: X.XX
   Entry: $X.XX
   Exit: $X.XX
   P&L: $X.XX (+X.X%)
```
AND
```
✅ POSITION CLOSED SUCCESSFULLY: order_id
   Sold X.XX shares @ $X.XX
   Realized P&L: $X.XX (+X.X%)
```

- [ ] Bot is selling positions
- [ ] Sell orders are successful
- [ ] P&L is positive (or small loss)
- [ ] Bot is not just buying

---

## Long-Term Checks (First 24 Hours)

### 14. Trading Statistics
Look for these log messages:
```
📊 Trading stats:
   Trades placed: X
   Trades won: X
   Trades lost: X
   Total profit: $X.XX
   Win rate: XX%
```

- [ ] Multiple trades completed
- [ ] Win rate > 50%
- [ ] Total profit > $0
- [ ] No massive losses (>10%)

### 15. Balance Changes
Check balance over time:
```
💰 Available balance: $6.00  (start)
💰 Available balance: $6.15  (after 1 hour)
💰 Available balance: $6.30  (after 2 hours)
```

- [ ] Balance is increasing
- [ ] No sudden large drops
- [ ] Profit is accumulating
- [ ] No 70% losses

### 16. Error Rate
Count errors over 24 hours:
```
Total log lines: ~10,000
Error lines: <100 (1%)
Critical errors: 0
```

- [ ] Error rate < 5%
- [ ] No critical errors
- [ ] No repeated failures
- [ ] Bot is stable

---

## Red Flags (Stop Bot Immediately If You See These)

### 🚨 Critical Errors
- [ ] `❌ Insufficient balance (< $1.00)` - Need to add funds
- [ ] `❌ ORDER FAILED` repeated 10+ times - API issue
- [ ] `🛡️ RISK MANAGER BLOCKED` repeated - Fix didn't work
- [ ] `❌ Cannot meet minimum order value` repeated - Balance too low
- [ ] Large loss (>10%) on single trade - Something wrong

### 🚨 Suspicious Behavior
- [ ] No trades after 2 hours - Bot not finding opportunities
- [ ] All trades losing money - Strategy not working
- [ ] Balance decreasing rapidly - Stop and investigate
- [ ] Repeated order failures - API or balance issue
- [ ] Bot restarting frequently - Crash loop

---

## Success Criteria

After 24 hours, bot should have:

- [ ] ✅ Placed 10+ trades
- [ ] ✅ Win rate > 50%
- [ ] ✅ Total profit > $0.50
- [ ] ✅ No losses > 2%
- [ ] ✅ Balance increased
- [ ] ✅ No critical errors
- [ ] ✅ Stable operation

---

## Troubleshooting

### If Bot Not Placing Trades
1. Check risk manager logs
2. Check market scanning logs
3. Check slippage rejection logs
4. Verify balance > $1.00

### If Orders Failing
1. Check balance
2. Check API credentials
3. Check market minimum size
4. Check order parameters

### If Bot Not Selling
1. Check exit conditions logs
2. Check dynamic TP calculation
3. Check position tracking
4. Verify positions are being monitored

### If Large Losses
1. Check slippage logs
2. Check order fill prices
3. Check stop loss settings
4. Consider stopping bot

---

## Contact Points

If you need help:
1. Share recent logs (last 100 lines)
2. Share error messages
3. Share trading statistics
4. Describe what you're seeing

---

## Quick Commands Reference

```powershell
# Check status
.\check_bot_status.ps1

# Watch live logs
ssh -i money.pem ubuntu@35.76.113.47 'sudo journalctl -u polybot.service -f'

# Check recent trades
ssh -i money.pem ubuntu@35.76.113.47 'sudo journalctl -u polybot.service -n 100 | grep "ORDER PLACED\|POSITION CLOSED"'

# Check errors
ssh -i money.pem ubuntu@35.76.113.47 'sudo journalctl -u polybot.service -n 100 | grep -i error'

# Restart bot
ssh -i money.pem ubuntu@35.76.113.47 'sudo systemctl restart polybot.service'

# Stop bot
ssh -i money.pem ubuntu@35.76.113.47 'sudo systemctl stop polybot.service'
```

---

**Good luck! Check off each item as you verify it.** ✅
