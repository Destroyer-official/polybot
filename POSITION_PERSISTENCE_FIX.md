# CRITICAL FIX: Position Persistence

## The REAL Problem

**Bot loses ALL positions when it restarts!**

### What Happened:
1. Bot bought XRP UP @ $0.49 at 11:16
2. I restarted bot at 11:20 (to deploy minimum size fix)
3. Bot FORGOT about the XRP position (stored in memory only)
4. Market ended at 11:30, position auto-resolved
5. Bot never sold because it didn't know it had a position

### Root Cause:
- Positions stored in `self.positions` dictionary (memory only)
- NO persistence to disk
- Every restart = complete memory loss
- Bot can't sell positions it doesn't remember

## The Fix

Added position persistence:

1. **Save positions to disk** after every change
2. **Load positions from disk** on startup
3. **File**: `data/active_positions.json`

### New Methods:
```python
def _load_positions(self):
    """Load positions from disk on startup"""
    # Reads data/active_positions.json
    # Restores all Position objects
    
def _save_positions(self):
    """Save positions to disk after changes"""
    # Writes to data/active_positions.json
    # Called after: buy, sell, position close
```

### When Positions Are Saved:
- After placing order (buy)
- After closing position (sell)
- After removing expired positions

## Expected Behavior

### Before Fix:
```
11:16 - Bot buys XRP @ $0.49
11:20 - Bot restarts
11:21 - Bot has NO memory of XRP position
11:30 - Market ends, position auto-resolves
       - Bot never tried to sell (didn't know about it)
```

### After Fix:
```
11:16 - Bot buys XRP @ $0.49
       - Saves to data/active_positions.json
11:20 - Bot restarts
       - Loads from data/active_positions.json
11:21 - Bot REMEMBERS XRP position
       - Checks exit conditions
       - Sells when profitable or market closes
```

## Files Modified

- `src/fifteen_min_crypto_strategy.py`
  - Added `_load_positions()` method
  - Added `_save_positions()` method
  - Call `_load_positions()` in `__init__`
  - Call `_save_positions()` after position changes

## Deployment

```powershell
scp -i money.pem src/fifteen_min_crypto_strategy.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"
```

## Benefits

1. **Survives restarts** - Bot remembers all positions
2. **Survives crashes** - Positions saved to disk
3. **Can sell properly** - Bot knows what it owns
4. **Audit trail** - Can see positions in JSON file

## Check Your Account

The XRP position from 11:16 likely auto-resolved when the market ended at 11:30.

Check your Polymarket web interface to see:
- If XRP went UP → Position resolved to $1.00/share = PROFIT
- If XRP went DOWN → Position resolved to $0.00/share = LOSS

The bot couldn't manually sell because it forgot about the position after restart.

## Next Steps

1. Deploy this fix NOW
2. Bot will persist positions going forward
3. Check Polymarket web to see if that XRP trade was profitable
4. Bot will now properly sell positions even after restarts
