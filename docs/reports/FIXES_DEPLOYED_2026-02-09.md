# Fixes Deployed - February 9, 2026

## Summary
All critical errors have been fixed and deployed to AWS EC2 (35.76.113.47).

---

## ✅ FIXED: LLM Decision Engine V2 - 404 Errors

**Problem**: LLM was getting 404 errors from NVIDIA NIM API due to incorrect model ID `nvidia/llama-3.1-nemotron-70b-instruct`

**Root Cause**: Model list included a non-existent model as first choice

**Fix Applied**:
- Updated model list in `src/llm_decision_engine_v2.py` to start with working model `meta/llama-3.1-70b-instruct`
- Removed the failing `nvidia/llama-3.1-nemotron-70b-instruct` model from first position
- Added fallback models: `meta/llama-3.1-8b-instruct` and `mistralai/mixtral-8x7b-instruct-v0.1`

**Verification**:
```
✅ LLM call successful with model: meta/llama-3.1-70b-instruct
HTTP Request: POST https://integrate.api.nvidia.com/v1/chat/completions "HTTP/1.1 200 OK"
```

**Status**: ✅ WORKING - No more 404 errors, all LLM calls successful

---

## ✅ FIXED: Sum-to-One Arbitrage - Trading on $0 Profit

**Problem**: Bot was placing sum-to-one arbitrage trades even when profit was $0.0000 (UP=$0.115 + DOWN=$0.885 = $1.000)

**Root Cause**: Code checked if total < $1.01 but didn't account for 3% trading fees. When spread is $0, profit after fees is -$0.03 (a loss!)

**Fix Applied**:
- Added profit calculation after fees: `profit_after_fees = spread - Decimal("0.03")`
- Added minimum profit threshold check: only trade if `profit_after_fees > Decimal("0.005")` (0.5%)
- Updated `src/fifteen_min_crypto_strategy.py` method `check_sum_to_one_arbitrage()`

**Verification**:
```
💰 SUM-TO-ONE CHECK: BTC | UP=$0.525 + DOWN=$0.475 = $1.000 (Target < $1.01)
(No "ARBITRAGE FOUND" message = correctly skipping $0 profit)
```

**Status**: ✅ WORKING - Bot no longer trades on unprofitable opportunities

---

## ⚠️ KNOWN ISSUE: API Key 400 Errors (Non-Blocking)

**Problem**: Logs show repeated `HTTP Request: POST https://clob.polymarket.com/auth/api-key "HTTP/2 400 Bad Request"` followed by successful fallback to `/auth/derive-api-key`

**Current Behavior**: 
- Bot tries to use stored API key → gets 400 error
- Bot derives new key successfully → continues normally
- Not blocking functionality but creates noise in logs

**Impact**: Low - functionality works, just extra API calls and log noise

**Recommendation**: 
- Can be ignored for now (bot works fine)
- Future optimization: Skip the failing `/auth/api-key` attempt and go straight to `/auth/derive-api-key`
- Or: Investigate why stored API key is invalid/expired

**Status**: ⚠️ KNOWN ISSUE - Not blocking, can be optimized later

---

## Deployment Details

**Date**: February 9, 2026 10:03 UTC
**Server**: AWS EC2 35.76.113.47
**Method**: Direct file copy via SCP + systemctl restart

**Files Deployed**:
1. `src/llm_decision_engine_v2.py` - Fixed model list
2. `src/fifteen_min_crypto_strategy.py` - Fixed sum-to-one arbitrage logic

**Commands Used**:
```bash
scp -i money.pem src/llm_decision_engine_v2.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/
scp -i money.pem src/fifteen_min_crypto_strategy.py ubuntu@35.76.113.47:/home/ubuntu/polybot/src/
ssh -i money.pem ubuntu@35.76.113.47 "sudo systemctl restart polybot"
```

---

## Current Bot Status

**Mode**: DRY_RUN (active)
**Strategies Active**:
- ✅ Latency Arbitrage (Binance price feed)
- ✅ Directional Trading (LLM V2 decision engine)
- ✅ Sum-to-One Arbitrage (with profit validation)

**Performance**:
- LLM calls: Working (200 OK responses)
- Sum-to-one checks: Correctly skipping $0 profit
- Binance feed: Connected and receiving prices
- Markets: Scanning BTC, ETH, SOL, XRP 15-minute markets

**Next Steps**:
- Monitor for profitable opportunities
- Consider fixing API key 400 errors (optional optimization)
- Keep DRY_RUN mode active as requested
