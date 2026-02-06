# SAFE TEST PLAN - Recommended Approach

## Phase 1: DRY RUN Test (5 minutes)

Test the bot with DRY_RUN=true to verify everything works:

1. **Set DRY_RUN=true in .env**
2. **Run bot:** `python test_autonomous_bot.py`
3. **Verify:** Bot scans markets, finds opportunities, simulates trades
4. **Check logs:** Everything working correctly

**Benefits:**
- No risk
- Verify bot functionality
- See what opportunities it finds
- Check performance metrics

## Phase 2: Bridge USDC (5-15 minutes)

While bot is testing in dry run, bridge your USDC:

1. **Go to:** https://polymarket.com
2. **Click:** Deposit → Connect Wallet
3. **Bridge:** $4.63 USDC from Ethereum to Polygon
4. **Wait:** 5-15 minutes for bridge completion

## Phase 3: LIVE Trading (Real Money)

After bridge completes:

1. **Set DRY_RUN=false in .env**
2. **Run bot:** `python test_autonomous_bot.py`
3. **Watch:** Real trades with real money
4. **Monitor:** Logs and performance

**This approach:**
- Tests bot safety first
- Gives you confidence
- Allows bridge time
- Minimizes risk

---

## OR - Skip to Live Trading:

If you want to go straight to live trading:

1. **Bridge USDC first** (use Polymarket website)
2. **Wait for bridge** (5-15 minutes)
3. **Run bot:** `python test_autonomous_bot.py`
4. **Real trading starts immediately**

**Your choice!**
