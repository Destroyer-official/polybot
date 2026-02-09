# 8-Hour Bot Performance Check

## When to Check
**Start Time**: February 9, 2026 10:03 UTC (when bot was restarted with fixes)
**Check Time**: February 9, 2026 18:03 UTC (8 hours later)

## Quick Check Command

Run this single command to get all statistics:

```bash
bash check_8hr_performance.sh
```

## Manual Check Commands

If you prefer to check manually:

### 1. Check Bot Status
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot"
```

### 2. Check Total Trades Placed
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '8 hours ago' --no-pager | grep 'PLACING ORDER' | wc -l"
```

### 3. Check Trade Statistics
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '8 hours ago' --no-pager | grep -E '(trades_placed|trades_won|trades_lost|total_profit)'"
```

### 4. Check Opportunities Found
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '8 hours ago' --no-pager | grep -E '(ARBITRAGE FOUND|BULLISH SIGNAL|BEARISH SIGNAL|LLM SIGNAL: buy)'"
```

### 5. Check LLM Decisions
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '8 hours ago' --no-pager | grep 'LLM Decision' | tail -50"
```

### 6. Check for Errors
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '8 hours ago' --no-pager -p err"
```

### 7. Get Performance Summary
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --no-pager | grep -A 10 'FINAL STATISTICS' | tail -15"
```

## What to Look For

### Expected Metrics:
- **Total Trades**: Number of orders placed (DRY_RUN simulated)
- **Trades Won**: Positions that hit take-profit
- **Trades Lost**: Positions that hit stop-loss
- **Total Profit**: Simulated profit/loss in USD
- **Arbitrage Opportunities**: How many sum-to-one or latency arb opportunities found
- **LLM Decisions**: How many directional trade signals generated

### Success Indicators:
✅ Bot running continuously for 8 hours
✅ No critical errors or crashes
✅ LLM calls successful (no 404 errors)
✅ Sum-to-one checks working (not trading on $0 profit)
✅ At least some opportunities detected (even if not traded)

### Potential Issues:
⚠️ Zero trades placed = markets may not have profitable opportunities
⚠️ High error rate = need to investigate logs
⚠️ Bot crashed/restarted = check systemd logs

## Analysis Questions

After checking the stats, consider:

1. **Trade Frequency**: How many trades per hour?
2. **Win Rate**: What % of trades were profitable?
3. **Strategy Performance**: Which strategy found the most opportunities?
   - Sum-to-one arbitrage
   - Latency arbitrage (Binance signals)
   - Directional trading (LLM decisions)
4. **LLM Behavior**: Is the LLM too conservative (skipping everything)?
5. **Market Conditions**: Were there any profitable opportunities at all?

## Next Steps Based on Results

### If Many Trades (>10):
- Analyze win rate and profit
- Consider enabling real trading if performance is good
- Review which strategies were most successful

### If Few Trades (1-10):
- Normal for conservative strategy
- Review opportunity thresholds
- Check if LLM confidence is too high

### If Zero Trades:
- Check if markets had any profitable opportunities
- Review logs for "ARBITRAGE FOUND" or "SIGNAL" messages
- Consider lowering thresholds (but carefully!)
- Verify Binance feed is working

### If Errors:
- Review error logs
- Check if fixes are still in place
- Investigate any new issues

## Report Template

After checking, create a report with:

```
# 8-Hour Bot Performance Report
Date: [Date]
Duration: 8 hours (10:03 - 18:03 UTC)

## Summary
- Bot Status: [Running/Stopped/Crashed]
- Total Trades: [Number]
- Win Rate: [Percentage]
- Total Profit (Simulated): $[Amount]

## Strategy Breakdown
- Sum-to-One Arbitrage: [Number] opportunities
- Latency Arbitrage: [Number] signals
- Directional Trading: [Number] LLM decisions

## Issues Found
- [List any errors or problems]

## Recommendations
- [Next steps based on results]
```
