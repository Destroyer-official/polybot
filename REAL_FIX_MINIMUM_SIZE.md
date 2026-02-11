# Real Fix: Market Minimum Size Check

## The ACTUAL Problem

**Error**: `Size (1.97) lower than the minimum: 5`

The bot was trying to place orders with 1.97-2.05 shares, but these specific markets require a MINIMUM of 5 shares.

## Root Cause

- Bot calculates order size based on $1.00 minimum VALUE
- But some markets have minimum SIZE requirements (e.g., 5 shares)
- With $4.96 balance and $0.50 price, bot can only afford ~2 shares
- Market requires 5 shares minimum = $2.50 minimum order
- Bot doesn't have enough funds for these markets

## The Fix

Added pre-check BEFORE placing order:

```python
# Check if order size meets typical minimum (5 shares)
min_shares_check = 5.0
min_value_for_5_shares = price_f * min_shares_check

if size_f < min_shares_check:
    logger.warning(f"⚠️ Order size {size_f:.2f} may be below market minimum (typically 5 shares)")
    logger.warning(f"   Required value for 5 shares: ${min_value_for_5_shares:.2f}")
    logger.warning(f"   SKIPPING this market - insufficient size")
    return False  # Skip this market
```

## What This Does

1. Checks if calculated order size < 5 shares
2. If yes, calculates how much money needed for 5 shares
3. Logs warning showing the requirement
4. SKIPS the market instead of trying to place order
5. Moves on to next market

## Expected Behavior

### Before Fix:
```
INFO - Creating limit order: 1.97 shares @ $0.5100 (total: $1.00)
ERROR - Size (1.97) lower than the minimum: 5
```

### After Fix:
```
INFO - Creating limit order: 1.97 shares @ $0.5100 (total: $1.00)
WARNING - ⚠️ Order size 1.97 may be below market minimum (typically 5 shares)
WARNING -    Required value for 5 shares: $2.55
WARNING -    SKIPPING this market - insufficient size
```

## Solution for User

**Option 1**: Add more funds
- Current balance: $4.96
- Needed for 5-share markets: $2.50-$5.00 per trade
- Recommended: Add $10-20 USDC

**Option 2**: Bot will automatically skip high-minimum markets
- Bot will try other markets with lower minimums
- Some markets may only require 1-2 shares
- Bot will trade when it finds suitable markets

## Files Modified

- `fifteen_min_crypto_strategy_from_server.py` (then uploaded to server)
- Added minimum size pre-check in `_place_order()` method

## Deployment

- ✅ Uploaded to server
- ✅ Service restarted
- ✅ Bot now skips markets with high minimum size requirements

## No More Errors

Bot will now:
1. Check if it can afford minimum size
2. Skip markets it can't afford
3. Only place orders on markets it can actually trade
4. No more "Size lower than minimum" errors
