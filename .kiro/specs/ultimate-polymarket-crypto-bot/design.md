# Ultimate Polymarket Crypto Trading Bot - Design Document

## 1. System Architecture

### 1.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Main Orchestrator                            │
│  - Lifecycle management                                          │
│  - Component coordination                                        │
│  - Health monitoring                                             │
└──────────────────┬──────────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┬──────────────┬──────────────┐
        │                     │              │              │
┌───────▼────────┐  ┌────────▼────────┐  ┌─▼──────────┐  ┌▼──────────┐
│ 15-Min Crypto  │  │  Risk Manager   │  │  Order     │  │  Fund     │
│   Strategy     │  │  - Portfolio    │  │  Manager   │  │  Manager  │
│  - BTC/ETH/    │  │  - Position     │  │  - CLOB    │  │  - Balance│
│    SOL/XRP     │  │  - Circuit      │  │  - FOK     │  │  - Bridge │
│  - Ensemble    │  │    Breakers     │  │  - Atomic  │  │           │
└────────────────┘  └─────────────────┘  └────────────┘  └───────────┘
```

### 1.2 Core Components

1. **Main Orchestrator** (`main_orchestrator.py`)
   - Initializes all components
   - Runs main event loop (scan → decide → execute)
   - Performs heartbeat checks every 60s
   - Manages graceful shutdown

2. **15-Minute Crypto Strategy** (`fifteen_min_crypto_strategy.py`)
   - Fetches 15-min & 1-hour crypto markets (BTC, ETH, SOL, XRP)
   - Implements 3 strategies: sum-to-one, latency, directional
   - Manages positions and exit conditions
   - Integrates with ensemble decision engine

3. **Ensemble Decision Engine** (`ensemble_decision_engine.py`)
   - Combines 4 models: LLM (40%), RL (25%), Historical (20%), Technical (15%)
   - Weighted voting with consensus threshold
   - Returns action + confidence + reasoning

4. **Portfolio Risk Manager** (`portfolio_risk_manager.py`)
   - Tracks portfolio heat (% capital deployed)
   - Enforces position limits and circuit breakers
   - Calculates max position size dynamically
   - Adapts to balance size (SMART mode)

5. **Order Manager** (`order_manager.py`)
   - Creates FOK orders with correct token_id and neg_risk
   - Submits orders to CLOB API
   - Validates fill prices and slippage
   - Handles atomic YES/NO pairs


## 2. Critical Fix: Sell/Exit Mechanism

### 2.1 Problem Analysis

**Root Cause**: Positions are opened but never closed due to multiple issues:

1. **Exit check not called consistently**: `_check_all_positions_for_exit()` must run FIRST in every cycle
2. **Wrong token_id**: Using `market_id` instead of actual `token_id` for sell orders
3. **Missing neg_risk flag**: Not tracked per position, causes order rejection
4. **Position matching fails**: Matching by `market_id` (changes every 15 min) instead of ASSET
5. **Size rounding**: Not rounding to 2 decimals causes "invalid size" errors

### 2.2 Solution Design

#### 2.2.1 Exit Check Flow

```python
async def run_cycle():
    # STEP 1: Check ALL positions for exit (BEFORE market fetch)
    await self._check_all_positions_for_exit()
    
    # STEP 2: Fetch current markets
    markets = await self.fetch_15min_markets()
    
    # STEP 3: Check exit conditions with fresh market data
    for market in markets:
        await self.check_exit_conditions(market)
    
    # STEP 4: Look for new entry opportunities
    for market in markets:
        await self.check_sum_to_one_arbitrage(market)
        await self.check_latency_arbitrage(market)
        await self.check_directional_trading(market)
```

#### 2.2.2 Position Data Structure

```python
@dataclass
class Position:
    token_id: str          # CRITICAL: Actual token ID for sell orders
    side: str              # "UP" or "DOWN"
    entry_price: Decimal
    size: Decimal
    entry_time: datetime
    market_id: str         # For reference only
    asset: str             # BTC, ETH, SOL, XRP (for matching)
    strategy: str          # "sum_to_one", "latency", "directional"
    neg_risk: bool         # CRITICAL: Must match market's neg_risk flag
    highest_price: Decimal # For trailing stop-loss
```

#### 2.2.3 Exit Priority Order

1. **Trailing Stop-Loss** (if activated): Drop >2% from peak
2. **Take-Profit**: P&L >= 2%
3. **Stop-Loss**: P&L <= -2%
4. **Time Exit**: Age > 13 minutes
5. **Emergency Exit**: Age > 15 minutes (force remove)


### 2.3 Sell Order Implementation

```python
async def _close_position(self, position: Position, current_price: Decimal) -> bool:
    """Close position with comprehensive validation."""
    
    # STEP 1: Calculate size (round to 2 decimals)
    size_f = float(position.size)
    size_rounded = math.floor(size_f * 100) / 100  # CRITICAL: 2 decimal places
    
    # STEP 2: Validate minimum size (Polymarket requires 5 shares)
    if size_rounded < 5.0:
        logger.warning(f"Size {size_rounded} below minimum 5 shares")
        return False
    
    # STEP 3: Create sell order with CORRECT parameters
    from py_clob_client.clob_types import OrderArgs
    from py_clob_client.order_builder.constants import SELL
    from types import SimpleNamespace
    
    order_args = OrderArgs(
        price=float(current_price),
        size=size_rounded,
        side=SELL,  # CRITICAL: SELL not BUY
        token_id=position.token_id,  # CRITICAL: Use position's token_id
    )
    
    # STEP 4: Set options with neg_risk flag
    options = SimpleNamespace(
        tick_size="0.01",
        neg_risk=position.neg_risk  # CRITICAL: Must match position
    )
    
    # STEP 5: Submit order
    signed_order = self.clob_client.create_order(order_args, options=options)
    resp = self.clob_client.post_order(signed_order)
    
    # STEP 6: Verify order was accepted
    if resp and (resp.get("orderID") or resp.get("success")):
        logger.info(f"✅ Sell order submitted: {resp}")
        return True
    else:
        logger.error(f"❌ Sell order rejected: {resp}")
        return False
```

## 3. Ensemble Decision System

### 3.1 Model Weights

- **LLM (40%)**: AI reasoning with chain-of-thought
- **RL (25%)**: Learned patterns from Q-learning
- **Historical (20%)**: Past performance by strategy/asset
- **Technical (15%)**: Multi-timeframe analysis

### 3.2 Consensus Calculation

```python
def _calculate_ensemble(self, model_votes: Dict[str, ModelDecision]) -> EnsembleDecision:
    action_scores = {"buy_yes": 0.0, "buy_no": 0.0, "skip": 0.0}
    
    for model_name, vote in model_votes.items():
        weight = get_model_weight(model_name)  # 0.40, 0.25, 0.20, 0.15
        confidence_weight = vote.confidence / 100.0  # 0-1
        action_scores[vote.action] += weight * confidence_weight
    
    # Normalize and select winner
    final_action = max(action_scores, key=action_scores.get)
    consensus_score = action_scores[final_action] * 100
    
    return EnsembleDecision(
        action=final_action,
        confidence=weighted_avg_confidence,
        consensus_score=consensus_score,
        model_votes=model_votes
    )
```

### 3.3 Execution Criteria

```python
def should_execute(self, decision: EnsembleDecision) -> bool:
    if decision.action == "skip":
        return False
    
    # Require minimum consensus (35-50%)
    if decision.consensus_score < self.min_consensus:
        return False
    
    # Require minimum confidence (>1%)
    if decision.confidence < 1.0:
        return False
    
    return True
```


## 4. SMART Risk Manager

### 4.1 Adaptive Position Limits

```python
def check_can_trade(self, proposed_size: Decimal, market_id: str) -> RiskMetrics:
    # SMART: Adapt limits based on balance size
    if self.current_capital < Decimal('5.0'):
        max_position = self.current_capital * Decimal('0.80')  # 80% for tiny balance
    elif self.current_capital < Decimal('10.0'):
        max_position = self.current_capital * Decimal('0.60')  # 60% for small
    elif self.current_capital < Decimal('20.0'):
        max_position = self.current_capital * Decimal('0.40')  # 40% for medium
    else:
        max_position = self.current_capital * Decimal('0.05')  # 5% for large
    
    # CRITICAL: Always allow Polymarket minimum (5 shares ≈ $2.50-$4.25)
    POLYMARKET_MIN = Decimal('3.50')
    if max_position < POLYMARKET_MIN and self.current_capital >= POLYMARKET_MIN:
        max_position = POLYMARKET_MIN
    
    # Check constraints...
    return RiskMetrics(can_trade=True, max_position_size=max_position)
```

### 4.2 Circuit Breakers

1. **Consecutive Losses**: Halt after 5 losses (was 3)
2. **Daily Drawdown**: Halt at 15% loss (was 10%)
3. **Portfolio Heat**: Max 30-90% deployed (adaptive)
4. **Per-Asset Limit**: Max 2 positions per asset

### 4.3 Progressive Position Sizing

```python
def _calculate_position_size(self) -> Decimal:
    multiplier = Decimal("1.0")
    
    if self.consecutive_losses >= 3:
        multiplier = Decimal("0.5")  # Reduce after losses
    elif self.consecutive_wins >= 3:
        multiplier = Decimal("1.5")  # Increase after wins
    
    desired_size = self.trade_size * multiplier
    
    # Get risk manager's max allowed
    risk_metrics = self.risk_manager.check_can_trade(desired_size, "temp")
    final_size = min(desired_size, risk_metrics.max_position_size)
    
    # Ensure minimum ($0.10-$3.00 range)
    MIN_ORDER = Decimal("0.10")
    if final_size < MIN_ORDER:
        if risk_metrics.max_position_size >= MIN_ORDER:
            final_size = MIN_ORDER
        else:
            return Decimal("0")  # Skip trade
    
    return final_size
```

## 5. Execution Optimization

### 5.1 Parallel Order Submission

```python
async def execute_sum_to_one(self, market: CryptoMarket):
    # Create both orders
    up_order = self.create_order(market.up_token_id, "BUY", market.up_price, shares)
    down_order = self.create_order(market.down_token_id, "BUY", market.down_price, shares)
    
    # Submit in parallel
    results = await asyncio.gather(
        self._submit_order(up_order),
        self._submit_order(down_order),
        return_exceptions=True
    )
    
    # Verify both filled
    if all(r.get("filled") for r in results):
        logger.info("✅ Both orders filled")
        return True
    else:
        logger.error("❌ Atomic execution failed")
        return False
```

### 5.2 Market Data Caching

```python
class FifteenMinuteCryptoStrategy:
    def __init__(self):
        self._market_cache: Optional[List] = None
        self._market_cache_time: float = 0
        self._market_cache_ttl: float = 5.0  # 5 second cache
    
    async def fetch_15min_markets(self) -> List[CryptoMarket]:
        current_time = time.time()
        
        # Check cache
        if (self._market_cache and 
            current_time - self._market_cache_time < self._market_cache_ttl):
            return self._market_cache
        
        # Fetch fresh data
        markets = await self._fetch_from_api()
        
        # Update cache
        self._market_cache = markets
        self._market_cache_time = current_time
        
        return markets
```

### 5.3 Decision Caching

```python
class EnsembleDecisionEngine:
    def __init__(self):
        self._decision_cache: Dict[str, Tuple[EnsembleDecision, float]] = {}
        self._cache_ttl = 10.0  # 10 seconds
    
    async def make_decision(self, asset: str, market_context, portfolio_state):
        cache_key = f"{asset}_{market_context.yes_price}_{market_context.no_price}"
        
        # Check cache
        if cache_key in self._decision_cache:
            decision, timestamp = self._decision_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return decision
        
        # Make fresh decision
        decision = await self._calculate_ensemble(...)
        
        # Update cache
        self._decision_cache[cache_key] = (decision, time.time())
        
        return decision
```


## 6. Fee Structure & Profit Calculation

### 6.1 Polymarket 15-Min Crypto Market Fees (2026)

**Taker Fee Curve** (based on market odds):
- At 50% odds: **3.0% fee** (highest)
- At 40% or 60% odds: **2.0% fee**
- At 30% or 70% odds: **1.0% fee**
- At 20% or 80% odds: **0.5% fee**
- At 10% or 90% odds: **0.2% fee**
- At 0% or 100% odds: **0.0% fee** (lowest)

**Formula**: `fee_pct = 3.0 * (1 - 2 * abs(price - 0.5))`

### 6.2 Profit Calculation

```python
def calculate_expected_profit(self, entry_price: Decimal, exit_price: Decimal, size: Decimal) -> Decimal:
    # Calculate raw P&L
    raw_pnl = (exit_price - entry_price) * size
    
    # Calculate fees (both entry and exit)
    entry_fee = self._calculate_fee(entry_price, size)
    exit_fee = self._calculate_fee(exit_price, size)
    total_fees = entry_fee + exit_fee
    
    # Net profit after fees
    net_profit = raw_pnl - total_fees
    
    return net_profit

def _calculate_fee(self, price: Decimal, size: Decimal) -> Decimal:
    # Fee curve: 3% at 50% odds, 0% at extremes
    distance_from_50 = abs(price - Decimal("0.5"))
    fee_pct = Decimal("0.03") * (Decimal("1.0") - Decimal("2.0") * distance_from_50)
    fee_amount = price * size * fee_pct
    return fee_amount
```

### 6.3 Minimum Profit Thresholds

- **Sum-to-One Arbitrage**: Require 0.5% profit after fees
- **Latency Arbitrage**: Require 1.0% profit after fees
- **Directional Trading**: Require 2.0% profit after fees (higher risk)

## 7. Testing Strategy

### 7.1 Unit Tests

```python
# Test exit conditions
async def test_take_profit_exit():
    position = create_test_position(entry_price=0.50, size=10)
    current_price = Decimal("0.51")  # 2% profit
    
    should_exit = await strategy._check_take_profit(position, current_price, ...)
    assert should_exit == True

async def test_stop_loss_exit():
    position = create_test_position(entry_price=0.50, size=10)
    current_price = Decimal("0.49")  # 2% loss
    
    should_exit = await strategy._check_stop_loss(position, current_price, ...)
    assert should_exit == True

async def test_time_exit():
    position = create_test_position(entry_time=datetime.now() - timedelta(minutes=14))
    
    should_exit = await strategy._check_time_exit(position, ...)
    assert should_exit == True
```

### 7.2 Integration Tests

```python
async def test_full_trade_cycle():
    # 1. Buy position
    market = await strategy.fetch_15min_markets()[0]
    await strategy._place_order(market, "UP", market.up_price, 10)
    
    assert len(strategy.positions) == 1
    
    # 2. Simulate price increase
    await asyncio.sleep(1)
    
    # 3. Check exit (should trigger take-profit)
    await strategy._check_all_positions_for_exit()
    
    assert len(strategy.positions) == 0  # Position closed
    assert strategy.stats["trades_won"] == 1
```

### 7.3 Property-Based Tests

```python
from hypothesis import given, strategies as st

@given(
    entry_price=st.decimals(min_value=0.01, max_value=0.99, places=2),
    size=st.decimals(min_value=5.0, max_value=100.0, places=2)
)
async def test_position_size_always_valid(entry_price, size):
    """Position size must always meet Polymarket minimums."""
    position = Position(
        token_id="test",
        side="UP",
        entry_price=entry_price,
        size=size,
        ...
    )
    
    # Size must be >= 5 shares
    assert position.size >= Decimal("5.0")
    
    # Size must be rounded to 2 decimals
    assert position.size == round(position.size, 2)
```

## 8. Monitoring & Alerting

### 8.1 Key Metrics

```python
class MonitoringSystem:
    def record_trade(self, result: TradeResult):
        # Win rate
        self.win_rate_gauge.set(self.calculate_win_rate())
        
        # P&L
        self.daily_pnl_gauge.set(float(self.daily_pnl))
        
        # Execution latency
        self.execution_latency_histogram.observe(result.execution_time_ms)
        
        # Order fill rate
        if result.was_successful():
            self.order_fill_counter.inc()
        else:
            self.order_reject_counter.inc()
```

### 8.2 Alert Conditions

```python
async def check_alerts(self):
    # Critical: Trading halted
    if self.circuit_breaker.is_open:
        await self.send_alert("critical", "Trading halted: Circuit breaker open")
    
    # Warning: Low win rate
    if self.win_rate < 0.60 and self.total_trades >= 20:
        await self.send_alert("warning", f"Low win rate: {self.win_rate*100:.1f}%")
    
    # Warning: High execution latency
    if self.avg_execution_time > 2000:  # 2 seconds
        await self.send_alert("warning", f"High latency: {self.avg_execution_time}ms")
    
    # Info: Daily summary
    if self.is_end_of_day():
        await self.send_alert("info", f"Daily P&L: ${self.daily_pnl:.2f}")
```

## 9. Deployment Architecture

### 9.1 Systemd Service

```ini
[Unit]
Description=Polymarket Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/polymarket-bot
ExecStart=/home/ubuntu/polymarket-bot/venv/bin/python bot.py
Restart=on-failure
RestartSec=10
StartLimitInterval=3600
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
```

### 9.2 State Persistence

```python
def _save_state(self):
    state = {
        "timestamp": datetime.now().isoformat(),
        "positions": [p.to_dict() for p in self.positions.values()],
        "stats": self.stats,
        "risk_manager": self.risk_manager.get_state(),
    }
    
    # Atomic write
    temp_file = self.state_file.with_suffix('.tmp')
    with open(temp_file, 'w') as f:
        json.dump(state, f, indent=2)
    temp_file.replace(self.state_file)
```

### 9.3 Health Check Endpoint

```python
from aiohttp import web

async def health_check(request):
    health = await orchestrator.heartbeat_check()
    
    if health.is_healthy:
        return web.json_response({"status": "healthy", "details": health.to_dict()})
    else:
        return web.json_response(
            {"status": "unhealthy", "issues": health.issues},
            status=503
        )

app = web.Application()
app.router.add_get('/health', health_check)
web.run_app(app, port=8080)
```

## 10. Performance Targets

### 10.1 Latency Targets

- Market data fetch: <500ms (p95)
- Decision making: <1000ms (p95)
- Order submission: <500ms (p95)
- **Total execution**: <2000ms (p95)

### 10.2 Throughput Targets

- Market scans: 20-40 per minute (every 1.5-3 seconds)
- Decisions: 10-20 per minute
- Orders: 5-10 per minute
- **Daily trades**: 50-200 (realistic for 15-min markets)

### 10.3 Reliability Targets

- Uptime: >99% (max 7 hours downtime per month)
- Order success rate: >95%
- Exit success rate: >99% (critical)
- State recovery: <10 seconds after crash

## 11. Security Considerations

### 11.1 Private Key Management

- Store private key in environment variable (never in code)
- Use encrypted storage for production
- Rotate keys periodically
- Monitor for unauthorized access

### 11.2 API Key Security

- Derive API credentials from private key (don't hardcode)
- Use separate keys for testing and production
- Implement rate limiting to prevent abuse
- Log all API calls for audit trail

### 11.3 Order Validation

- Validate all order parameters before submission
- Check balance before placing orders
- Verify order responses (don't assume success)
- Implement order size limits (prevent fat-finger errors)

## 12. Future Enhancements

### 12.1 Machine Learning Improvements

- Train custom RL model on historical data
- Implement online learning (update model in real-time)
- Add sentiment analysis from social media
- Use transformer models for price prediction

### 12.2 Advanced Strategies

- Cross-market arbitrage (Polymarket vs Kalshi)
- Mempool monitoring (front-run large trades)
- Market making (provide liquidity for rebates)
- Options-style strategies (synthetic positions)

### 12.3 Scalability

- Multi-account support (distribute capital)
- Multi-region deployment (reduce latency)
- Horizontal scaling (multiple bot instances)
- Load balancing (distribute API calls)
