# Complete Error Fixes for Polymarket Bot

## Date: 2026-02-09
## Status: READY TO DEPLOY

---

## Summary

Fixed 3 critical errors identified in AWS deployment:

1. ✅ **LLM V2 Engine 404 Errors** - Removed non-existent model from fallback list
2. ✅ **Sum-to-One $0 Profit Bug** - Already fixed in local code, needs AWS sync
3. ⚠️  **Polymarket API 400 Bad Request** - Expected behavior (fallback works)

---

## Issue 1: LLM Decision Engine V2 - 404 Model Errors

### Problem
```
Model nvidia/llama-3.1-nemotron-70b-instruct failed: 404 Not Found
```

The first model in the fallback list doesn't exist on NVIDIA NIM API, causing unnecessary 404 errors before falling back to working model.

### Root Cause
AWS version of `src/llm_decision_engine_v2.py` still has old model list:
```python
models_to_try = [
    "nvidia/llama-3.1-nemotron-70b-instruct",  # ❌ DOESN'T EXIST
    "meta/llama-3.1-70b-instruct",  # ✅ WORKS
    ...
]
```

### Fix Applied
Updated model list to start with working model:
```python
models_to_try = [
    "meta/llama-3.1-70b-instruct",  # ✅ WORKING - Meta Llama 3.1 70B
    "meta/llama-3.1-8b-instruct",  # Smaller fallback
    "mistralai/mixtral-8x7b-instruct-v0.1",  # Mixtral fallback
]
```

### Files Changed
- `src/llm_decision_engine_v2.py` (line ~250)

### Verification
After deploying, check logs:
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '1 minute ago' | grep -E 'LLM|404'"
```

Should see:
- ✅ `LLM call successful with model: meta/llama-3.1-70b-instruct`
- ❌ NO 404 errors

---

## Issue 2: Sum-to-One Arbitrage $0 Profit Bug

### Problem
```
🎯 SUM-TO-ONE ARBITRAGE FOUND!
   Guaranteed profit: $0.0000 per share pair!
```

Bot was logging "arbitrage found" even when profit is $0 after fees.

### Root Cause
AWS version has OLD code that doesn't properly check profit_after_fees before logging.

Local version already has the fix:
```python
if total < self.sum_to_one_threshold:
    spread = Decimal("1.0") - total
    profit_after_fees = spread - Decimal("0.03")  # 3% fees
    
    # Only trade if profitable after fees
    if profit_after_fees > Decimal("0.005"):  # At least 0.5% profit
        logger.warning(f"🎯 SUM-TO-ONE ARBITRAGE FOUND!")
        logger.warning(f"   Spread: ${spread:.4f} | After fees: ${profit_after_fees:.4f}")
        # ... place orders ...
    else:
        logger.debug(f"⏭️ Skipping: profit ${profit_after_fees:.4f} too small")
```

### Fix Applied
The local `src/fifteen_min_crypto_strategy.py` already has correct logic. AWS just needs file sync.

### Files Changed
- `src/fifteen_min_crypto_strategy.py` (lines 455-490)

### Verification
After deploying, check logs:
```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot --since '1 minute ago' | grep 'SUM-TO-ONE'"
```

Should see:
- ✅ `SUM-TO-ONE CHECK: BTC | UP=$0.500 + DOWN=$0.500 = $1.000`
- ✅ `⏭️ Skipping: profit $-0.0300 too small` (when total = $1.00)
- ❌ NO "Guaranteed profit: $0.0000" messages

---

## Issue 3: Polymarket API 400 Bad Request

### Problem
```
HTTP Request: POST https://clob.polymarket.com/auth/api-key "HTTP/2 400 Bad Request"
```

### Analysis
This error comes from the `py_clob_client` library, not our code. The bot:
1. Tries primary endpoint `/auth/api-key` → 400 Bad Request
2. Falls back to `/auth/derive-api-key` → 200 OK ✅
3. Authentication succeeds, trading works

### Root Cause
The primary API key endpoint may be:
- Deprecated by Polymarket
- Requires different signature format
- Only works for certain wallet types

### Status: NOT A BUG
This is **expected behavior**. The fallback mechanism works correctly. The 400 error is just a warning from the library trying the primary endpoint first.

### Recommendation
**No fix needed.** The bot is working correctly. If you want to suppress the warning, you would need to:
1. Modify the `py_clob_client` library source code
2. Or contact Polymarket to understand why primary endpoint returns 400

For now, ignore these warnings - they don't affect trading.

---

## Deployment Instructions

### Step 1: Copy Fixed Files to AWS

```bash
# Copy LLM V2 engine fix
scp -i money.pem src/llm_decision_engine_v2.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/

# Copy sum-to-one arbitrage fix
scp -i money.pem src/fifteen_min_crypto_strategy.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/
```

### Step 2: Restart Bot

```bash
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"
```

### Step 3: Verify Fixes

```bash
# Check bot started successfully
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl status polybot"

# Watch logs for 30 seconds
ssh -i money.pem ubuntu@35.76.113.47 "sudo journalctl -u polybot -f"
```

Look for:
- ✅ `LLM call successful with model: meta/llama-3.1-70b-instruct`
- ✅ `⏭️ Skipping sum-to-one: profit $-0.0300 too small`
- ❌ NO `404 Not Found` errors
- ❌ NO `Guaranteed profit: $0.0000` messages

---

## Testing Checklist

After deployment, verify:

- [ ] Bot starts without errors
- [ ] LLM V2 engine makes decisions without 404 errors
- [ ] Sum-to-one arbitrage only triggers when profit > $0.005 after fees
- [ ] No "Guaranteed profit: $0.0000" messages in logs
- [ ] 15-minute crypto strategy still works (latency + directional + sum-to-one)
- [ ] Flash crash strategy still works
- [ ] NegRisk arbitrage still works
- [ ] DRY_RUN mode still active (no real trades)

---

## Expected Log Output (After Fixes)

### Good Logs ✅
```
2026-02-09 10:15:00 - src.llm_decision_engine_v2 - INFO - ✅ LLM call successful with model: meta/llama-3.1-70b-instruct
2026-02-09 10:15:01 - src.fifteen_min_crypto_strategy - INFO - 💰 SUM-TO-ONE CHECK: BTC | UP=$0.500 + DOWN=$0.500 = $1.000 (Target < $1.01)
2026-02-09 10:15:01 - src.fifteen_min_crypto_strategy - DEBUG - ⏭️ Skipping sum-to-one: profit $-0.0300 too small (need >$0.005)
2026-02-09 10:15:02 - src.fifteen_min_crypto_strategy - INFO - 📊 LATENCY CHECK: BTC | Binance=$95234.50 | 10s Change=0.023% (Threshold=±0.05%)
```

### Bad Logs ❌ (Should NOT appear after fix)
```
❌ Model nvidia/llama-3.1-nemotron-70b-instruct failed: 404 Not Found
❌ 🎯 SUM-TO-ONE ARBITRAGE FOUND!
❌    Guaranteed profit: $0.0000 per share pair!
```

---

## Rollback Plan

If deployment causes issues:

```bash
# Stop bot
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl stop polybot"

# Restore from git (if you committed before deploying)
ssh -i money.pem ubuntu@35.76.113.47 "cd /home/ubuntu/polybot && git checkout src/llm_decision_engine_v2.py src/fifteen_min_crypto_strategy.py"

# Restart bot
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl start polybot"
```

---

## Notes

1. **API 400 Errors**: These are expected and don't affect trading. Ignore them.

2. **DRY_RUN Mode**: Bot is still in DRY_RUN=true mode. No real trades will be placed.

3. **Balance**: Current balance is $0.45 USDC. Bot will continue to simulate trades.

4. **Strategies Active**:
   - ✅ Flash Crash Strategy
   - ✅ 15-Minute Crypto Strategy (Latency + Directional + Sum-to-One)
   - ✅ NegRisk Arbitrage Engine
   - ✅ LLM Decision Engine V2

5. **Performance**: After fixes, bot should:
   - Make faster LLM decisions (no 404 retries)
   - Stop logging false arbitrage opportunities
   - Continue monitoring markets every 5 seconds

---

## Contact

If issues persist after deployment, check:
1. Bot logs: `sudo journalctl -u polybot -f`
2. Bot status: `sudo systemctl status polybot`
3. File permissions: `ls -la /home/ubuntu/polybot/src/`

All fixes are ready to deploy! 🚀
