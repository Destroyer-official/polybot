# Ultimate Polymarket Crypto Trading Bot - Requirements

## Executive Summary

Transform the existing Polymarket trading bot into a **production-grade, autonomous, high-frequency 15-minute & 1-hour crypto trading system** that achieves:

- **Win Rate**: 90-99% (currently ~50%)
- **Monthly ROI**: 20-150% (currently negative)
- **Execution Speed**: <1 second (currently 3-5 seconds)
- **Daily Trades**: 100-500 (currently 5-20)
- **Markets**: ONLY 15-minute and 1-hour crypto markets (BTC, ETH, SOL, XRP)

## 1. Critical Issues to Fix (P0 - Immediate)

### 1.1 Sell/Exit Mechanism (BROKEN - HIGHEST PRIORITY)

**Current Problem**: Bot buys positions but NEVER sells them, even when:
- Take-profit targets are hit (+2% profit)
- Stop-loss triggers (-2% loss)
- Markets expire (15+ minutes)
- Positions become orphaned
check is all task complate and all work perfectly then test all heare all algrothms logics check carefully all truly work no simuliction no demo no false posetive all true and work perfectly  then clean remo move unncery files and folders in unncery foldewr cinnect aws with ssh -i money.pem ubuntu@35.76.113.47     and do upadte all programme file in aws then do dry run true  test all every thing is working perfectly then   do dry run off and  and run polybot again and check all working perfectly 
**Root Causes Identified**:
1. ✅ Exit logic exists in `_check_all_positions_for_exit()` but may not be called consistently
2. ✅ Order placement uses wrong `token_id` (market_id instead of actual token_id)
3. ✅ `neg_risk` flag not tracked per position (causes sell order rejection)
4. ✅ Minimum order size validation missing (Polymarket requires 5 shares minimum)
5. ✅ Position matching by `market_id` fails (changes every 15 minutes)

**Required Fixes**:
- [x] Call `_check_all_positions_for_exit()` at START of every cycle (before market fetch)
- [x] Track `neg_risk` flag per position for correct sell orders
- [x] Match positions by ASSET (BTC/ETH) not market_id
- [x] Implement size rounding: `math.floor(size * 100) / 100` for 2 decimal places
- [x] Add emergency exit for positions >15 minutes old
- [ ] **VERIFY**: Test all exit scenarios (TP, SL, time, emergency) with real orders
- [ ] **VERIFY**: Confirm sell orders are actually submitted to CLOB API
- [ ] **VERIFY**: Check order status after submission (filled/rejected)

### 1.2 API Usage Correctness

**Issues Found**:
- ✅ WebSocket URL was incorrect (now fixed to `wss://ws-subscriptions-clob.polymarket.com/ws/`)
- ✅ Order creation uses correct CLOB flow: `create_order()` → `post_order()`
- ⚠️ Token ID handling needs verification (using `token_id` from market data)
- ⚠️ Fee structure not accounted for (15-min markets have 3% taker fees at 50% odds)

**Required Fixes**:
- [ ] Verify token_id extraction from Gamma API (`clobTokenIds` field)
- [ ] Implement dynamic fee calculation based on market odds
- [ ] Add fee cost to profit calculations (subtract 3% at 50% odds, less at extremes)
- [ ] Test order submission with actual CLOB API (not just dry-run)

### 1.3 Hardcoded Values Removal

**Current Issues**:
- ✅ Trade size is dynamic (uses `_calculate_position_size()`)
- ✅ Take-profit/stop-loss are configurable
- ⚠️ Some thresholds still hardcoded (e.g., `sum_to_one_threshold=1.02`)
- ⚠️ Minimum order size hardcoded (`$0.10`)

**Required Fixes**:
- [ ] Make all thresholds configurable via config file
- [ ] Calculate minimum order size dynamically based on market prices
- [ ] Remove magic numbers from code (use named constants)

## 2. Strategy & Prediction (P1 - Core Functionality)

### 2.1 Ensemble Voting System

**Current Implementation**: ✅ Ensemble engine exists with weighted voting
- LLM: 40% weight
- RL: 25% weight  
- Historical: 20% weight
- Technical: 15% weight

**Issues**:
- ⚠️ Minimum consensus too low (5% - allows almost any trade)
- ⚠️ LLM sometimes votes "buy_both" for directional trades
- ⚠️ Historical tracker may block profitable trades

**Required Improvements**:
- [ ] Increase minimum consensus to 35-50% (balanced between opportunity and safety)
- [ ] Add confidence threshold per model (e.g., LLM must be >45% confident)
- [ ] Implement model performance tracking (disable underperforming models)
- [ ] Add ensemble decision logging for post-trade analysis

### 2.2 Multi-Timeframe Confirmation

**Current Implementation**: ✅ Multi-timeframe analyzer exists (1m/5m/15m)

**Issues**:
- ⚠️ Requires alignment across all timeframes (too strict for 15-min markets)
- ⚠️ Not enough data for 5m/15m signals in short cycles

**Required Improvements**:
- [ ] Allow single strong 1m signal to trigger trades (with higher confidence requirement)
- [ ] Weight recent timeframes more heavily (1m: 50%, 5m: 30%, 15m: 20%)
- [ ] Add volume confirmation (require 2x average volume for strong signals)

### 2.3 Binance Momentum Check

**Current Implementation**: ✅ Binance WebSocket feed active

**Issues**:
- ⚠️ Threshold too low (0.05% = 0.0005) - generates too many false signals
- ⚠️ No volume confirmation
- ⚠️ Geo-blocking issues (451 errors)

**Required Improvements**:
- [ ] Increase momentum threshold to 0.1% (0.001) for clearer signals
- [ ] Add volume spike detection (>2x average volume)
- [ ] Implement automatic failover between Binance.com and Binance.US
- [ ] Add latency measurement (reject signals >500ms old)

## 3. Risk & Position Sizing (P1 - Critical for Profitability)

### 3.1 Kelly Criterion Implementation

**Current Implementation**: ✅ Kelly sizer exists but not fully integrated

**Issues**:
- ⚠️ Win probability hardcoded (99.5% - unrealistic)
- ⚠️ Not used for all strategies (only internal arbitrage)
- ⚠️ Doesn't account for actual win rate

**Required Improvements**:
- [ ] Calculate win probability from actual trade history (rolling 50 trades)
- [ ] Use fractional Kelly (25-50%) to reduce variance
- [ ] Apply Kelly sizing to ALL strategies (not just arbitrage)
- [ ] Add Kelly multiplier based on confidence (high confidence = higher Kelly fraction)

### 3.2 Dynamic Position Sizing

**Current Implementation**: ✅ Progressive sizing based on win/loss streaks

**Issues**:
- ⚠️ Risk manager limits too restrictive (blocks trades with small balance)
- ⚠️ Doesn't account for Polymarket minimum order size (5 shares)
- ⚠️ Position size can drop below minimum after reductions

**Required Improvements**:
- [ ] **SMART RISK MANAGER**: Adapt limits based on balance size
  - Balance <$5: Allow 80% per trade (need to meet minimums)
  - Balance $5-$10: Allow 60% per trade
  - Balance $10-$20: Allow 40% per trade
  - Balance >$20: Use standard 5% limit
- [ ] Always allow Polymarket minimum (5 shares ≈ $2.50-$4.25)
- [ ] Calculate minimum size dynamically: `5 shares * typical_price * 2` (allow for 50% reduction)
- [ ] Ensure position size after reductions still meets minimum

### 3.3 Volatility-Adjusted TP/SL

**Current Implementation**: ✅ Fixed TP (2%) and SL (2%)

**Issues**:
- ⚠️ Doesn't adapt to market conditions
- ⚠️ Too tight for volatile markets (gets stopped out)
- ⚠️ Too loose for calm markets (misses profit opportunities)

**Required Improvements**:
- [ ] Calculate volatility from Binance price history (rolling 1-hour)
- [ ] Adjust TP/SL based on volatility:
  - Low volatility (<1%): TP=1%, SL=1.5%
  - Medium volatility (1-3%): TP=2%, SL=2%
  - High volatility (>3%): TP=3%, SL=3%
- [ ] Implement trailing stop-loss (already exists, verify it works)
- [ ] Add time-decay adjustment (tighter stops as market approaches expiry)

### 3.4 Circuit Breakers

**Current Implementation**: ✅ Multiple circuit breakers exist

**Issues**:
- ⚠️ Too aggressive (halts after 3 consecutive losses)
- ⚠️ Daily drawdown limit too strict (10%)
- ⚠️ Doesn't distinguish between strategy types

**Required Improvements**:
- [ ] Increase consecutive loss limit to 5-7 (allow for variance)
- [ ] Increase daily drawdown to 15-20% (more realistic for high-frequency trading)
- [ ] Implement per-strategy circuit breakers (don't halt all strategies for one failure)
- [ ] Add recovery mode (reduce position size by 50% instead of halting)

## 4. Execution & Performance (P1 - Speed is Critical)

### 4.1 Sub-Second Execution

**Current Issues**:
- ⚠️ Execution time 3-5 seconds (too slow for 15-min markets)
- ⚠️ Sequential order placement (not parallel)
- ⚠️ No order pre-signing

**Required Improvements**:
- [ ] Implement order pre-signing (sign orders before market conditions change)
- [ ] Use asyncio.gather() for parallel order submission
- [ ] Add order batching (submit multiple orders in single API call if supported)
- [ ] Measure and log execution time per trade
- [ ] Target: <1 second from signal to order submission

### 4.2 Market Data Caching

**Current Implementation**: ✅ 2-second cache for market data

**Issues**:
- ⚠️ Cache TTL too short (causes excessive API calls)
- ⚠️ No cache invalidation on market changes
- ⚠️ Orderbook data not cached

**Required Improvements**:
- [ ] Increase cache TTL to 5 seconds (balance freshness vs API load)
- [ ] Implement WebSocket-based cache invalidation (update cache on price changes)
- [ ] Cache orderbook snapshots (1-second TTL)
- [ ] Add cache hit rate monitoring

### 4.3 Decision Caching

**Current Issues**:
- ⚠️ LLM called on every cycle (slow and expensive)
- ⚠️ No rate limiting per asset
- ⚠️ Duplicate decisions for same market conditions

**Required Improvements**:
- [ ] Cache LLM decisions for 10 seconds (same market conditions = same decision)
- [ ] Implement rate limiting: max 1 LLM call per asset per 5 seconds
- [ ] Use ensemble decision cache (avoid recalculating if inputs unchanged)
- [ ] Add decision cache hit rate monitoring

## 5. Testing & Validation (P2 - Quality Assurance)

### 5.1 Unit Tests

**Required Coverage**:
- [ ] Exit logic tests (TP, SL, time, emergency)
- [ ] Order creation tests (correct token_id, neg_risk, size)
- [ ] Position sizing tests (Kelly, dynamic, minimums)
- [ ] Risk manager tests (limits, circuit breakers)
- [ ] Ensemble voting tests (consensus, confidence)

### 5.2 Integration Tests

**Required Tests**:
- [ ] Full trade cycle (buy → hold → sell)
- [ ] Market expiry handling (force exit before close)
- [ ] Orphan position cleanup (no market data available)
- [ ] API error handling (timeout, rate limit, rejection)
- [ ] Balance management (insufficient funds, auto-bridge)

### 5.3 Property-Based Tests

**Required Tests**:
- [ ] Position size always meets Polymarket minimums (5 shares)
- [ ] Exit conditions are mutually exclusive (no double-exit)
- [ ] Risk limits are never exceeded (portfolio heat, drawdown)
- [ ] Orders are always valid (price, size, token_id)
- [ ] P&L calculations are accurate (entry, exit, fees)

## 6. Monitoring & Ops (P2 - Production Readiness)

### 6.1 Metrics Dashboard

**Required Metrics**:
- [ ] Win rate (overall, per strategy, per asset)
- [ ] P&L (daily, weekly, monthly)
- [ ] Execution latency (p50, p95, p99)
- [ ] Order fill rate (% of orders filled)
- [ ] Position duration (average hold time)
- [ ] Circuit breaker triggers (count, reasons)

### 6.2 Alerting

**Required Alerts**:
- [ ] Critical: Trading halted (circuit breaker, insufficient funds)
- [ ] Warning: High execution latency (>2 seconds)
- [ ] Warning: Low win rate (<60% over 20 trades)
- [ ] Warning: High slippage (>5% on average)
- [ ] Info: Daily P&L summary

### 6.3 Logging

**Required Logs**:
- [ ] Structured JSON logs (timestamp, level, message, context)
- [ ] Trade lifecycle logs (signal → decision → order → fill → exit)
- [ ] Error logs with stack traces
- [ ] Performance logs (execution time, cache hits)
- [ ] Log rotation (daily, max 7 days)

## 7. Deployment (P3 - Automation)

### 7.1 Systemd Service

**Required Features**:
- [ ] Auto-start on boot
- [ ] Auto-restart on crash (max 5 restarts per hour)
- [ ] Graceful shutdown (wait for pending orders)
- [ ] Log to systemd journal
- [ ] Health check endpoint (HTTP /health)

### 7.2 State Persistence

**Required Features**:
- [ ] Save state every 5 seconds (positions, stats, config)
- [ ] Atomic writes (temp file + rename)
- [ ] State recovery on restart
- [ ] Backup state files (keep last 10)

### 7.3 Hot-Reload Config

**Required Features**:
- [ ] Reload config without restart (SIGHUP)
- [ ] Validate config before applying
- [ ] Log config changes
- [ ] Rollback on invalid config

## 8. Advanced Strategies (P3 - Future Enhancements)

### 8.1 Sum-to-One Arbitrage

**Current Implementation**: ✅ Exists but rarely triggers

**Improvements**:
- [ ] Use orderbook ask prices (not mid prices)
- [ ] Account for fees (3% at 50% odds)
- [ ] Require minimum profit after fees (0.5%)
- [ ] Check liquidity before entry

### 8.2 NegRisk Exploitation

**Current Implementation**: ✅ NegRisk engine exists

**Improvements**:
- [ ] Identify NegRisk markets automatically
- [ ] Calculate optimal entry/exit points
- [ ] Monitor for NegRisk arbitrage opportunities
- [ ] Track NegRisk-specific performance

### 8.3 Mempool/Same-Block Execution

**Future Enhancement**:
- [ ] Monitor Polygon mempool for large trades
- [ ] Submit orders in same block as detected trades
- [ ] Use flashbots-style bundles if available
- [ ] Measure and optimize block inclusion rate

## 9. Research References

Based on deep research of successful Polymarket bots and 2026 market conditions:

### 9.1 Kelly Criterion for Prediction Markets
- [Kelly Criterion with Prediction Markets](https://www.bettoredge.com/post/using-kelly-criterion-with-predicition-markets)
- [Binary Options, Kelly Criterion, and CLOB Pricing](https://navnoorbawa.substack.com/p/the-math-of-prediction-markets-binary)
- [Application of Kelly Criterion to Prediction Markets (arXiv)](https://arxiv.org/html/2412.14144v1)

### 9.2 Polymarket 15-Min Crypto Markets (2026)
- [Polymarket Fee Structure](https://sqmagazine.co.uk/polymarket-taker-fees-short-term-crypto/) - 3% taker fees at 50% odds
- [Automated Trading on Polymarket](https://www.daytradingcomputers.com/blog/automated-trading-polymarket)
- [Arbitrage Bots and Market Maturation](https://www.ainvest.com/news/arbitrage-bots-market-maturation-polymarket-era-prediction-market-profits-2601/)

### 9.3 Exit Strategy Best Practices
- [Stop Loss Strategies for Algorithmic Trading](https://blog.traderspost.io/article/stop-loss-strategies-algorithmic-trading)
- [Exit Optimization for Automated Trading](https://blog.pickmytrade.trade/exit-optimization-automated-trading-strategies/)
- [Optimizing Futures Trading Algorithms](https://quantstrategy.io/blog/optimizing-futures-trading-algorithms-the-role-of-strategy/)

### 9.4 Polymarket API Documentation
- [Developer Quickstart](https://docs.polymarket.com/quickstart/overview)
- [CLOB Trading](https://docs.polymarket.com/developers/market-makers/trading)
- [WebSocket Overview](https://docs.polymarket.com/developers/CLOB/websocket/wss-overview)
- [Endpoints Reference](https://docs.polymarket.com/quickstart/reference/endpoints)

## 10. Success Criteria

### 10.1 Functional Requirements
- [ ] Bot successfully buys AND sells positions (no orphaned positions)
- [ ] All exit conditions trigger correctly (TP, SL, time, emergency)
- [ ] Orders meet Polymarket minimums (5 shares, correct token_id, neg_risk)
- [ ] Execution time <1 second (95th percentile)
- [ ] Win rate >70% over 100 trades

### 10.2 Performance Requirements
- [ ] Daily trades: 50-200 (realistic for 15-min markets)
- [ ] Monthly ROI: 10-50% (realistic with 3% fees)
- [ ] Max drawdown: <20% (with circuit breakers)
- [ ] Uptime: >99% (with auto-restart)

### 10.3 Operational Requirements
- [ ] Zero manual intervention for 7 days
- [ ] Automatic balance management (bridge if needed)
- [ ] Graceful handling of API errors
- [ ] Complete audit trail (all trades logged)

## 11. Next Steps

1. **Immediate (Week 1)**:
   - Fix sell/exit mechanism (verify with real orders)
   - Test all exit scenarios (TP, SL, time, emergency)
   - Verify API usage (token_id, neg_risk, fees)

2. **Short-term (Week 2-3)**:
   - Implement SMART risk manager (adaptive limits)
   - Improve ensemble voting (higher consensus threshold)
   - Add execution speed optimizations (parallel orders, caching)

3. **Medium-term (Week 4-6)**:
   - Add comprehensive testing (unit, integration, property-based)
   - Implement monitoring dashboard (metrics, alerts)
   - Deploy to production (systemd, state persistence)

4. **Long-term (Month 2-3)**:
   - Optimize strategies (volatility-adjusted TP/SL, Kelly sizing)
   - Add advanced features (NegRisk, mempool monitoring)
   - Scale to higher trade volume (100-500 daily trades)
