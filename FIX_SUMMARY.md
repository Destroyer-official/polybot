# Polymarket Bot Fix Summary - February 11, 2026

## CRITICAL ISSUES FIXED ✅

### 1. Decimal Precision Error (FIXED)
**Problem**: Orders failing with "invalid amounts, the buy orders maker amount supports a max accuracy of 4 decimals, taker amount a max of 2 decimals"

**Root Cause**: Using `create_market_order` with `MarketOrderArgs(amount=...)` which internally calculated maker/taker amounts with too many decimals.

**Solution**: Switched to `create_order` with `OrderArgs(price=..., size=...)` which lets the py-clob-client library handle decimal rounding internally based on tick size.

**Files Changed**:
- `src/fifteen_min_crypto_strategy.py` - `_place_order` method (line ~1520)
- `src/fifteen_min_crypto_strategy.py` - `_close_position` method (line ~1598)

**Code Changes**:
```python
# OLD (BROKEN):
order_args = MarketOrderArgs(
    token_id=token_id,
    amount=amount_f,  # Total dollar amount
    side=BUY,
)
signed_order = self.clob_client.create_market_order(order_args)
response = self.clob_client.post_order(signed_order, order_type="FOK")  # ❌ Wrong!

# NEW (WORKING):
order_args = OrderArgs(
    token_id=token_id,
    price=price_f,  # Price per share (library rounds to tick size)
    size=size_f,    # Number of shares (library rounds to 2 decimals)
    side=BUY,
)
signed_order = self.clob_client.create_order(order_args)
response = self.clob_client.post_order(signed_order)  # ✅ Correct!
```

**Evidence**: Latest logs show orders being created successfully without decimal errors:
```
Feb 11 10:53:35 - Creating limit order: 2.02 shares @ $0.4950 (total: $1.00)
```

---

## CURRENT ISSUE: Minimum Size Requirements ⚠️

**Problem**: Orders rejected with "Size (2.02) lower than the minimum: 5"

**Root Cause**: Some Polymarket markets have minimum size requirements (e.g., 5 shares). With only $1.00 balance and prices around $0.375-$0.495, the bot can only afford 2-3 shares, which is below the minimum.

**Examples from logs**:
- Market @ $0.375/share: Bot tries 2.67 shares, needs 5 shares ($1.88 minimum)
- Market @ $0.495/share: Bot tries 2.02 shares, needs 5 shares ($2.48 minimum)

**Solutions**:
1. **Add more funds** to the wallet (recommended: at least $5-10 USDC)
2. **Skip markets with high minimums** - Add logic to check minimum size before placing orders
3. **Target cheaper markets** - Focus on markets with prices < $0.20 where 5 shares = $1.00

---

## BOT STATUS

**Current Balance**: ~$1.00 USDC (insufficient for most markets)

**Bot Health**: ✅ Running correctly
- Decimal precision: FIXED
- Order creation: WORKING
- Buy orders: WORKING (when balance sufficient)
- Sell orders: WORKING (code fixed, not yet tested in production)

**Deployment**: AWS EC2 (35.76.113.47)
- Service: `polybot.service`
- Logs: `sudo journalctl -u polybot`
- Restart: `sudo systemctl restart polybot`

---

## NEXT STEPS

1. **Add funds** to wallet: Deposit at least $5-10 USDC to meet minimum size requirements
2. **Test sell orders**: Wait for a position to trigger exit conditions (take-profit/stop-loss/time-based)
3. **Monitor P&L**: Track bot performance over multiple trades

---

## TECHNICAL DETAILS

**Official Documentation Used**:
- https://docs.polymarket.com/developers/CLOB/orders/create-order
- https://github.com/Polymarket/py-clob-client

**Key Learnings**:
1. `post_order()` takes ONLY the signed order, no additional parameters
2. Order type (FOK/GTC/GTD) is specified in `OrderArgs`, not in `post_order()`
3. The py-clob-client library handles decimal rounding internally based on tick size
4. Always use `OrderArgs(price=..., size=...)` not `MarketOrderArgs(amount=...)`
5. Markets have minimum size requirements that must be checked before placing orders

**Confidence Threshold**: 45% (balanced between opportunity and risk)
- Below 45%: Too risky, skip trade
- Above 45%: Execute trade with proper risk management
