# Design Document: Ultimate Polymarket Crypto Bot

## Overview

This design transforms an existing Polymarket trading bot into the world's most powerful, profitable, and fastest crypto trading bot. The bot trades BTC, ETH, SOL, and XRP on 15-minute and 1-hour Polymarket crypto markets using multiple advanced strategies.

### Current State Analysis

The existing bot has a sophisticated foundation with:
- Multiple strategy engines (latency arbitrage, sum-to-one arbitrage, NegRisk arbitrage)
- AI decision making (LLM Engine V2, Reinforcement Learning, Ensemble voting)
- Risk management (Portfolio Risk Manager, Circuit Breaker, Kelly/Dynamic position sizing)
- Real-time data feeds (Binance WebSocket, Polymarket CLOB WebSocket)
- Adaptive learning (SuperSmart Learning, Adaptive Learning Engine)

### Critical Issues Identified

Through deep analysis of the codebase and audit reports, the following critical issues prevent profitability:

1. **Sell Logic Bug**: Exit conditions only check when markets are fetched, causing delayed exits
2. **Hardcoded Parameters**: Take-profit (1%), stop-loss (2%), and other values don't adapt to market conditions
3. **Missing 2026 Algorithms**: Advanced strategies from research not fully implemented
4. **Slow Execution**: 3-5 second scan intervals miss fast-moving opportunities
5. **Conservative Risk Management**: Portfolio heat limit (30%) and position size (5%) too restrictive
6. **Incomplete Exit Strategy**: Trailing stops exist but not optimally configured

### Design Goals

1. **Fix Critical Bugs**: Ensure all positions exit correctly and quickly
2. **Dynamic Everything**: All parameters adapt to market conditions in real-time
3. **Sub-Second Execution**: Detect and execute trades in <1 second
4. **Smart Profit Taking**: Multiple exit strategies with optimal timing
5. **Production Ready**: Robust error handling, logging, and recovery

### Target Performance

Based on research of successful bots:
- **Win Rate**: 70-90% (currently ~50%)
- **Monthly ROI**: 5-15% (currently negative)
- **Execution Speed**: <1 second (currently 3-5 seconds)
- **Daily Trades**: 50-200 (currently 5-20)

## Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Orchestrator                         │
│  - Event loop (1-second intervals)                          │
│  - Health monitoring                                         │
│  - State persistence                                         │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼──────┐  ┌────────▼────────┐
│  Data Layer    │  │  Strategy   │  │  Risk & Safety  │
│                │  │  Engines    │  │                 │
│ - Binance WS   │  │ - Latency   │  │ - Portfolio Mgr │
│ - CLOB WS      │  │ - Sum-to-1  │  │ - Circuit Break │
│ - Market Cache │  │ - NegRisk   │  │ - AI Safety     │
│ - Order Books  │  │ - Flash     │  │ - Kelly Sizer   │
└────────────────┘  └─────────────┘  └─────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐  ┌──────▼──────┐  ┌────────▼────────┐
│  AI Decision   │  │  Exit Logic │  │  Learning       │
│                │  │             │  │                 │
│ - LLM Engine   │  │ - Take Prof │  │ - RL Engine     │
│ - RL Engine    │  │ - Stop Loss │  │ - Adaptive      │
│ - Ensemble     │  │ - Trailing  │  │ - SuperSmart    │
│ - Multi-TF     │  │ - Time Exit │  │ - Historical    │
└────────────────┘  └─────────────┘  └─────────────────┘
```

### Data Flow

1. **Price Updates** (WebSocket) → **Strategy Engines** → **AI Decision** → **Risk Check** → **Order Execution**
2. **Exit Monitoring** (continuous) → **Exit Logic** → **Order Execution** → **Learning Update**
3. **Trade Outcomes** → **Learning Engines** → **Parameter Updates** → **Strategy Engines**

## Components and Interfaces

### 1. Ultra-Fast Exit Logic System

**Purpose**: Monitor all positions continuously and execute exits within 10 seconds of trigger

**Current Implementation Issues**:
- Exit checks only run when markets are fetched (every 3-5 seconds)
- Uses mid-price instead of executable orderbook price
- No retry logic for failed exits
- Orphan positions not properly tracked

**New Design**:

```python
class UltraFastExitMonitor:
    """
    Continuous exit monitoring with sub-10-second execution.
    
    Runs independently of market fetching to ensure fast exits.
    """
    
    def __init__(self, check_interval_seconds: float = 1.0):
        self.check_interval = check_interval_seconds
        self.positions: Dict[str, Position] = {}
        self.exit_queue: asyncio.Queue = asyncio.Queue()
        self.retry_queue: asyncio.Queue = asyncio.Queue()
        
    async def monitor_loop(self):
        """
        Main monitoring loop - runs every 1 second.
        
        Checks all positions against exit conditions:
        1. Take-profit (2% default, dynamic)
        2. Stop-loss (2% default, dynamic)
        3. Trailing stop (2% from peak after 0.5% profit)
        4. Time exit (13 minutes)
        5. Market closing (2 minutes before close)
        """
        while True:
            try:
                await self._check_all_positions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Exit monitor error: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_all_positions(self):
        """Check all positions for exit conditions."""
        for position_id, position in list(self.positions.items()):
            # Get current executable price from orderbook
            current_price = await self._get_executable_price(position)
            
            if current_price is None:
                continue
            
            # Check all exit conditions
            exit_reason = self._evaluate_exit_conditions(
                position, current_price
            )
            
            if exit_reason:
                await self.exit_queue.put((position, current_price, exit_reason))
    
    async def _get_executable_price(self, position: Position) -> Optional[Decimal]:
        """
        Get executable exit price from orderbook.
        
        Uses best bid (for selling) instead of mid-price.
        """
        try:
            orderbook = await self.order_book_analyzer.get_order_book(
                position.token_id, force_refresh=True
            )
            
            if orderbook and orderbook.bids:
                return orderbook.bids[0].price  # Best bid
            
            # Fallback to cached market price
            return position.current_price
            
        except Exception as e:
            logger.error(f"Failed to get executable price: {e}")
            return None
    
    def _evaluate_exit_conditions(
        self, position: Position, current_price: Decimal
    ) -> Optional[str]:
        """
        Evaluate all exit conditions for a position.
        
        Returns exit reason if any condition is met, None otherwise.
        """
        # Calculate P&L
        pnl_pct = (current_price - position.entry_price) / position.entry_price
        
        # Update peak price for trailing stop
        if current_price > position.highest_price:
            position.highest_price = current_price
        
        # 1. Trailing stop (after 0.5% profit)
        if pnl_pct >= Decimal("0.005"):
            drop_from_peak = (position.highest_price - current_price) / position.highest_price
            if drop_from_peak >= position.trailing_stop_pct:
                return f"trailing_stop (dropped {drop_from_peak*100:.2f}% from peak)"
        
        # 2. Take profit
        if pnl_pct >= position.take_profit_pct:
            return f"take_profit ({pnl_pct*100:.2f}%)"
        
        # 3. Stop loss
        if pnl_pct <= -position.stop_loss_pct:
            return f"stop_loss ({pnl_pct*100:.2f}%)"
        
        # 4. Time exit (13 minutes)
        position_age_minutes = (datetime.now() - position.entry_time).total_seconds() / 60
        if position_age_minutes > 13:
            return f"time_exit ({position_age_minutes:.1f} minutes)"
        
        # 5. Market closing (2 minutes before close)
        if position.market_end_time:
            time_to_close_minutes = (position.market_end_time - datetime.now()).total_seconds() / 60
            if time_to_close_minutes < 2:
                return f"market_closing ({time_to_close_minutes:.1f} minutes remaining)"
        
        return None
    
    async def exit_executor_loop(self):
        """
        Execute exits from queue with retry logic.
        
        Runs concurrently with monitor loop.
        """
        while True:
            try:
                position, price, reason = await self.exit_queue.get()
                
                success = await self._execute_exit(position, price, reason)
                
                if not success:
                    # Add to retry queue
                    await self.retry_queue.put((position, price, reason, 0))
                    
            except Exception as e:
                logger.error(f"Exit executor error: {e}")
    
    async def _execute_exit(
        self, position: Position, price: Decimal, reason: str
    ) -> bool:
        """
        Execute exit order with verification.
        
        Returns True if successful, False if failed.
        """
        try:
            logger.info(f"🚪 Exiting position: {position.asset} {position.side} | Reason: {reason}")
            
            # Create sell order
            order_args = OrderArgs(
                token_id=position.token_id,
                price=float(price),
                size=float(position.size),
                side=SELL
            )
            
            # Sign and post order
            signed_order = self.clob_client.create_order(order_args)
            response = self.clob_client.post_order(signed_order)
            
            # Verify order was placed
            if response and response.get("success"):
                logger.info(f"✅ Exit successful: {position.asset} {position.side}")
                
                # Update risk manager
                self.risk_manager.close_position(position.market_id, price)
                
                # Remove from positions
                del self.positions[position.token_id]
                
                # Save positions to disk
                self._save_positions()
                
                # Record outcome for learning
                self._record_trade_outcome(position, price, reason)
                
                return True
            else:
                logger.error(f"❌ Exit failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Exit execution error: {e}")
            return False
    
    async def retry_executor_loop(self):
        """
        Retry failed exits with exponential backoff.
        
        Retries up to 3 times with 1s, 2s, 4s delays.
        """
        while True:
            try:
                position, price, reason, retry_count = await self.retry_queue.get()
                
                if retry_count >= 3:
                    logger.error(f"❌ Exit failed after 3 retries: {position.asset} {position.side}")
                    continue
                
                # Exponential backoff
                delay = 2 ** retry_count
                await asyncio.sleep(delay)
                
                # Retry with slightly worse price (1% worse per retry)
                adjusted_price = price * (Decimal("0.99") ** (retry_count + 1))
                
                success = await self._execute_exit(position, adjusted_price, f"{reason} (retry {retry_count + 1})")
                
                if not success:
                    await self.retry_queue.put((position, price, reason, retry_count + 1))
                    
            except Exception as e:
                logger.error(f"Retry executor error: {e}")
```

**Key Improvements**:
1. **Independent monitoring**: Runs every 1 second regardless of market fetching
2. **Executable prices**: Uses orderbook best bid instead of mid-price
3. **Retry logic**: Up to 3 retries with exponential backoff and price adjustment
4. **Comprehensive logging**: All exit attempts logged with timestamps
5. **Queue-based execution**: Separates monitoring from execution for better performance



### 2. Dynamic Parameter Adaptation System

**Purpose**: Adapt all trading parameters to market conditions in real-time

**Current Implementation Issues**:
- Take-profit and stop-loss are hardcoded (1% and 2%)
- Position sizing doesn't adapt to recent performance
- Sum-to-one threshold is fixed
- No volatility-based adjustments

**New Design**:

```python
class DynamicParameterAdapter:
    """
    Adapts all trading parameters based on market conditions and performance.
    
    Updates parameters every 10 trades or when conditions change significantly.
    """
    
    def __init__(self):
        # Current parameters (start with defaults)
        self.take_profit_pct = Decimal("0.02")  # 2%
        self.stop_loss_pct = Decimal("0.02")  # 2%
        self.sum_to_one_threshold = Decimal("1.02")  # $1.02
        self.base_position_size = Decimal("1.0")  # $1.00
        
        # Performance tracking
        self.recent_trades: deque = deque(maxlen=50)
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.trades_since_update = 0
        
        # Market condition tracking
        self.current_volatility: Dict[str, Decimal] = {}
        self.current_liquidity: Dict[str, Decimal] = {}
        
    def update_on_trade_complete(self, trade_result: TradeResult):
        """
        Update parameters after each trade.
        
        Adjusts based on:
        1. Win/loss outcome
        2. Consecutive streaks
        3. Recent win rate
        4. Market volatility
        """
        self.recent_trades.append(trade_result)
        self.trades_since_update += 1
        
        # Update consecutive counters
        if trade_result.status == "success" and trade_result.net_profit > 0:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        # Immediate adjustments for streaks
        self._adjust_for_streaks()
        
        # Full recalculation every 10 trades
        if self.trades_since_update >= 10:
            self._recalculate_all_parameters()
            self.trades_since_update = 0
    
    def _adjust_for_streaks(self):
        """
        Immediate position size adjustments based on streaks.
        
        Requirement 2.5: Reduce 50% after 3 consecutive losses
        Requirement 2.6: Increase 25% after 5 consecutive wins
        """
        if self.consecutive_losses >= 3:
            self.base_position_size *= Decimal("0.5")
            logger.info(f"📉 Reduced position size 50% after {self.consecutive_losses} losses: ${self.base_position_size}")
        
        if self.consecutive_wins >= 5:
            self.base_position_size *= Decimal("1.25")
            logger.info(f"📈 Increased position size 25% after {self.consecutive_wins} wins: ${self.base_position_size}")
    
    def _recalculate_all_parameters(self):
        """
        Recalculate optimal parameters from recent trade history.
        
        Requirements 2.7, 2.8: Recalculate take-profit and stop-loss every 10 trades
        """
        if len(self.recent_trades) < 10:
            return
        
        logger.info("🔄 Recalculating optimal parameters from last 50 trades...")
        
        # Calculate win rate
        wins = sum(1 for t in self.recent_trades if t.status == "success" and t.net_profit > 0)
        win_rate = wins / len(self.recent_trades)
        
        # Adjust position size based on win rate (Requirements 2.2, 2.3)
        if win_rate < 0.60:
            self.base_position_size *= Decimal("0.75")  # Reduce 25%
            logger.info(f"📉 Win rate {win_rate*100:.1f}% < 60%, reduced position size: ${self.base_position_size}")
        elif win_rate > 0.80:
            self.base_position_size *= Decimal("1.25")  # Increase 25%
            logger.info(f"📈 Win rate {win_rate*100:.1f}% > 80%, increased position size: ${self.base_position_size}")
        
        # Calculate optimal take-profit from winning trades
        winning_trades = [t for t in self.recent_trades if t.status == "success" and t.net_profit > 0]
        if winning_trades:
            avg_profit_pct = sum(
                (t.actual_profit / t.actual_cost) for t in winning_trades
            ) / len(winning_trades)
            
            # Set take-profit to 80% of average winning profit (leave room for variance)
            self.take_profit_pct = avg_profit_pct * Decimal("0.8")
            self.take_profit_pct = max(Decimal("0.01"), min(Decimal("0.05"), self.take_profit_pct))
            logger.info(f"🎯 Optimal take-profit: {self.take_profit_pct*100:.2f}%")
        
        # Calculate optimal stop-loss from losing trades
        losing_trades = [t for t in self.recent_trades if t.status == "failed" or t.net_profit < 0]
        if losing_trades:
            avg_loss_pct = sum(
                abs(t.net_profit / t.actual_cost) for t in losing_trades if t.actual_cost > 0
            ) / len(losing_trades)
            
            # Set stop-loss to 120% of average loss (tighter control)
            self.stop_loss_pct = avg_loss_pct * Decimal("1.2")
            self.stop_loss_pct = max(Decimal("0.01"), min(Decimal("0.05"), self.stop_loss_pct))
            logger.info(f"🛑 Optimal stop-loss: {self.stop_loss_pct*100:.2f}%")
        
        # Adjust sum-to-one threshold based on arbitrage success (Requirement 2.9)
        arbitrage_trades = [t for t in self.recent_trades if t.opportunity and t.opportunity.strategy == "sum_to_one"]
        if arbitrage_trades:
            arb_win_rate = sum(1 for t in arbitrage_trades if t.status == "success") / len(arbitrage_trades)
            
            if arb_win_rate > 0.90:
                # High success, can be more aggressive
                self.sum_to_one_threshold = Decimal("1.03")
            elif arb_win_rate < 0.70:
                # Low success, be more conservative
                self.sum_to_one_threshold = Decimal("1.01")
            else:
                # Moderate success
                self.sum_to_one_threshold = Decimal("1.02")
            
            logger.info(f"⚖️ Sum-to-one threshold: ${self.sum_to_one_threshold} (win rate: {arb_win_rate*100:.1f}%)")
    
    def adjust_for_volatility(self, asset: str, volatility: Decimal):
        """
        Adjust position sizing based on market volatility.
        
        Requirement 2.1: Adjust within 30 seconds of volatility change
        """
        self.current_volatility[asset] = volatility
        
        # High volatility = smaller positions
        if volatility > Decimal("0.05"):  # >5% volatility
            volatility_multiplier = Decimal("0.5")  # 50% size
            logger.info(f"⚠️ High volatility {volatility*100:.1f}% for {asset}, reducing position size 50%")
        elif volatility > Decimal("0.03"):  # >3% volatility
            volatility_multiplier = Decimal("0.75")  # 75% size
            logger.info(f"⚠️ Moderate volatility {volatility*100:.1f}% for {asset}, reducing position size 25%")
        else:
            volatility_multiplier = Decimal("1.0")  # Full size
        
        return self.base_position_size * volatility_multiplier
    
    def adjust_for_liquidity(self, order_book_depth: Decimal) -> Decimal:
        """
        Adjust trade size based on order book depth.
        
        Requirement 2.4: Reduce size when depth is low
        """
        if order_book_depth < Decimal("50"):
            # Very low liquidity, skip trade
            return Decimal("0")
        elif order_book_depth < Decimal("100"):
            # Low liquidity, reduce size 50%
            return self.base_position_size * Decimal("0.5")
        elif order_book_depth < Decimal("200"):
            # Moderate liquidity, reduce size 25%
            return self.base_position_size * Decimal("0.75")
        else:
            # Good liquidity, full size
            return self.base_position_size
    
    def get_current_parameters(self) -> Dict[str, Decimal]:
        """Get current parameter values."""
        return {
            "take_profit_pct": self.take_profit_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "sum_to_one_threshold": self.sum_to_one_threshold,
            "base_position_size": self.base_position_size,
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses
        }
```

**Key Improvements**:
1. **Adaptive take-profit/stop-loss**: Calculated from recent trade outcomes
2. **Streak-based sizing**: Immediate adjustments for win/loss streaks
3. **Win-rate based sizing**: Scales with performance
4. **Volatility adjustments**: Reduces size in high volatility
5. **Liquidity adjustments**: Scales with order book depth
6. **Threshold adaptation**: Sum-to-one threshold adapts to success rate

### 3. Sub-Second Execution Engine

**Purpose**: Detect and execute trades in under 1 second

**Current Implementation Issues**:
- 3-5 second scan intervals miss fast opportunities
- Sequential processing of markets
- No WebSocket-driven execution
- LLM calls block execution

**New Design**:

```python
class SubSecondExecutionEngine:
    """
    Ultra-fast execution engine with sub-second latency.
    
    Uses WebSocket-driven event processing and parallel execution.
    """
    
    def __init__(self):
        self.binance_feed = BinancePriceFeed()
        self.clob_feed = CLOBWebSocketFeed()
        self.execution_queue = asyncio.PriorityQueue()  # Priority by urgency
        self.market_cache = TTLCache(maxsize=1000, ttl=2.0)  # 2-second cache
        
        # Performance tracking
        self.detection_latencies: deque = deque(maxlen=1000)
        self.execution_latencies: deque = deque(maxlen=1000)
        
    async def start(self):
        """
        Start all execution components.
        
        Runs multiple concurrent loops:
        1. Binance price monitoring
        2. CLOB orderbook monitoring
        3. Execution queue processor
        4. Market cache refresher
        """
        await asyncio.gather(
            self.binance_feed.start(),
            self.clob_feed.start(),
            self._binance_event_loop(),
            self._clob_event_loop(),
            self._execution_loop(),
            self._cache_refresh_loop()
        )
    
    async def _binance_event_loop(self):
        """
        Process Binance price updates in real-time.
        
        Requirement 3.1: Detect 0.3%+ moves within 500ms
        """
        async for price_update in self.binance_feed.stream_updates():
            detection_start = time.time()
            
            asset = price_update["asset"]
            price = price_update["price"]
            
            # Check if significant move (0.3%+)
            if self._is_significant_move(asset, price):
                # Add to execution queue with high priority
                opportunity = await self._check_latency_arbitrage(asset, price)
                
                if opportunity:
                    detection_latency = (time.time() - detection_start) * 1000
                    self.detection_latencies.append(detection_latency)
                    
                    if detection_latency > 500:
                        logger.warning(f"⚠️ Slow detection: {detection_latency:.0f}ms > 500ms")
                    
                    # Priority 1 = highest (latency arbitrage)
                    await self.execution_queue.put((1, opportunity))
    
    async def _clob_event_loop(self):
        """
        Process CLOB orderbook updates in real-time.
        
        Detects sum-to-one arbitrage opportunities instantly.
        """
        async for orderbook_update in self.clob_feed.stream_orderbooks():
            market_id = orderbook_update["market_id"]
            yes_price = orderbook_update["yes_price"]
            no_price = orderbook_update["no_price"]
            
            # Check sum-to-one arbitrage
            if yes_price + no_price < self.sum_to_one_threshold:
                opportunity = self._create_sum_to_one_opportunity(
                    market_id, yes_price, no_price
                )
                
                # Priority 2 = high (guaranteed profit)
                await self.execution_queue.put((2, opportunity))
    
    async def _execution_loop(self):
        """
        Execute opportunities from queue.
        
        Requirement 3.2: Place orders within 1 second of detection
        """
        while True:
            try:
                priority, opportunity = await self.execution_queue.get()
                
                execution_start = time.time()
                
                # Execute with timeout
                try:
                    result = await asyncio.wait_for(
                        self._execute_opportunity(opportunity),
                        timeout=1.0  # 1 second timeout
                    )
                    
                    execution_latency = (time.time() - execution_start) * 1000
                    self.execution_latencies.append(execution_latency)
                    
                    if execution_latency > 1000:
                        logger.warning(f"⚠️ Slow execution: {execution_latency:.0f}ms > 1000ms")
                    else:
                        logger.info(f"⚡ Fast execution: {execution_latency:.0f}ms")
                        
                except asyncio.TimeoutError:
                    logger.warning(f"⏱️ Execution timeout for {opportunity.strategy}")
                    
            except Exception as e:
                logger.error(f"Execution loop error: {e}")
    
    async def _cache_refresh_loop(self):
        """
        Refresh market cache in background.
        
        Requirement 3.4: Cache market data for 2 seconds
        """
        while True:
            try:
                # Fetch fresh market data
                markets = await self._fetch_markets_fast()
                
                # Update cache
                for market in markets:
                    self.market_cache[market.market_id] = market
                
                # Wait 2 seconds before next refresh
                await asyncio.sleep(2.0)
                
            except Exception as e:
                logger.error(f"Cache refresh error: {e}")
                await asyncio.sleep(2.0)
    
    async def _check_latency_arbitrage(
        self, asset: str, binance_price: Decimal
    ) -> Optional[Opportunity]:
        """
        Check for latency arbitrage opportunity.
        
        Uses cached market data for speed.
        """
        # Get relevant markets from cache
        markets = [
            m for m in self.market_cache.values()
            if asset in m.question.upper()
        ]
        
        for market in markets:
            # Quick check if Polymarket lags Binance
            lag = self._calculate_lag(binance_price, market)
            
            if lag > Decimal("0.005"):  # 0.5% lag
                return self._create_latency_opportunity(market, lag)
        
        return None
    
    def _is_significant_move(self, asset: str, new_price: Decimal) -> bool:
        """
        Check if price move is significant (0.3%+).
        
        Requirement 3.1: Detect 0.3%+ moves
        """
        if asset not in self.last_prices:
            self.last_prices[asset] = new_price
            return False
        
        old_price = self.last_prices[asset]
        change_pct = abs(new_price - old_price) / old_price
        
        if change_pct >= Decimal("0.003"):  # 0.3%
            self.last_prices[asset] = new_price
            return True
        
        return False
    
    async def _execute_opportunity(self, opportunity: Opportunity) -> TradeResult:
        """
        Execute opportunity with parallel order placement.
        
        Requirement 3.6: Use parallel execution for multiple positions
        """
        if opportunity.strategy == "sum_to_one":
            # Place both orders in parallel
            yes_task = asyncio.create_task(self._place_order(opportunity, "YES"))
            no_task = asyncio.create_task(self._place_order(opportunity, "NO"))
            
            yes_result, no_result = await asyncio.gather(yes_task, no_task)
            
            # Both must succeed
            if yes_result and no_result:
                return self._create_success_result(opportunity, yes_result, no_result)
            else:
                # Rollback if one failed
                await self._rollback_partial_fill(yes_result, no_result)
                return self._create_failed_result(opportunity, "Partial fill")
        else:
            # Single order
            result = await self._place_order(opportunity, opportunity.side)
            return self._create_result(opportunity, result)
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Get execution performance metrics."""
        if not self.detection_latencies or not self.execution_latencies:
            return {}
        
        return {
            "avg_detection_latency_ms": sum(self.detection_latencies) / len(self.detection_latencies),
            "p95_detection_latency_ms": sorted(self.detection_latencies)[int(len(self.detection_latencies) * 0.95)],
            "avg_execution_latency_ms": sum(self.execution_latencies) / len(self.execution_latencies),
            "p95_execution_latency_ms": sorted(self.execution_latencies)[int(len(self.execution_latencies) * 0.95)],
            "total_opportunities": len(self.detection_latencies)
        }
```

**Key Improvements**:
1. **WebSocket-driven**: Reacts to price updates instantly
2. **Priority queue**: Executes most urgent opportunities first
3. **Parallel execution**: Multiple orders placed simultaneously
4. **Market caching**: 2-second cache reduces API calls
5. **Latency tracking**: Monitors and logs performance
6. **Timeout handling**: Skips slow operations

