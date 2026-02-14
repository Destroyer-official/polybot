"""
Latency Arbitrage Engine for Polymarket Arbitrage Bot.

Exploits lag between CEX price movements and Polymarket updates.
Implements Requirements 4.2, 4.3, 4.4, 4.6.
"""

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, AsyncIterator

from src.models import Market, Opportunity, TradeResult
from src.ai_safety_guard import AISafetyGuard
from src.kelly_position_sizer import KellyPositionSizer
from src.order_manager import OrderManager

logger = logging.getLogger(__name__)


@dataclass
class PriceMovement:
    """Represents a CEX price movement"""
    asset: str  # BTC, ETH, SOL, XRP
    old_price: Decimal
    new_price: Decimal
    timestamp: datetime
    exchange: str  # Binance, Coinbase, Kraken
    
    @property
    def change_percentage(self) -> Decimal:
        """Calculate percentage change"""
        if self.old_price == 0:
            return Decimal('0')
        return abs(self.new_price - self.old_price) / self.old_price
    
    @property
    def direction(self) -> str:
        """Get price movement direction"""
        return "UP" if self.new_price > self.old_price else "DOWN"


class LatencyArbitrageEngine:
    """
    Detects and executes latency arbitrage opportunities.
    
    Latency arbitrage occurs when:
    1. CEX price moves significantly (>$100 for BTC, equivalent for others)
    2. Polymarket prices lag behind CEX by >1%
    3. We can predict Polymarket will catch up
    
    The strategy:
    1. Monitor CEX WebSocket feeds in real-time
    2. Detect significant price movements
    3. Check if Polymarket markets lag
    4. Execute trades in the direction of CEX movement
    5. Exit when Polymarket catches up
    
    Validates Requirements:
    - 4.2: Check Polymarket when CEX moves >$100 (BTC) or equivalent
    - 4.3: Calculate expected market direction from CEX movement
    - 4.4: Execute with sub-150ms target latency
    - 4.6: Skip when volatility > 5% in 1 minute
    """
    
    # Price movement thresholds for triggering checks (Requirement 4.2)
    MOVEMENT_THRESHOLDS = {
        'BTC': Decimal('100'),    # $100 for BTC
        'ETH': Decimal('5'),      # $5 for ETH
        'SOL': Decimal('2'),      # $2 for SOL
        'XRP': Decimal('0.05')    # $0.05 for XRP
    }
    
    # Minimum lag percentage to identify opportunity (Requirement 4.3)
    MIN_LAG_PERCENTAGE = Decimal('0.01')  # 1%
    
    # Maximum volatility before skipping (Requirement 4.6)
    MAX_VOLATILITY = Decimal('0.05')  # 5%
    
    # Target execution latency (Requirement 4.4)
    TARGET_LATENCY_MS = 150
    
    def __init__(
        self,
        cex_feeds: Dict[str, 'WebSocketFeed'],  # Type hint as string to avoid import
        clob_client,
        order_manager: OrderManager,
        ai_safety_guard: AISafetyGuard,
        kelly_sizer: KellyPositionSizer,
        min_profit_threshold: Decimal = Decimal('0.005'),  # 0.5%
        current_balance_getter=None,
        current_gas_price_getter=None,
        pending_tx_count_getter=None
    ):
        """
        Initialize Latency Arbitrage Engine.
        
        Args:
            cex_feeds: Dictionary of CEX WebSocket feeds {exchange_name: feed}
            clob_client: CLOB client for Polymarket market data
            order_manager: Order manager for trade execution
            ai_safety_guard: AI safety guard for validation
            kelly_sizer: Kelly position sizer for optimal sizing
            min_profit_threshold: Minimum profit percentage (default 0.5%)
            current_balance_getter: Function to get current balance
            current_gas_price_getter: Function to get current gas price in gwei
            pending_tx_count_getter: Function to get pending transaction count
        """
        self.cex_feeds = cex_feeds
        self.clob_client = clob_client
        self.order_manager = order_manager
        self.ai_safety_guard = ai_safety_guard
        self.kelly_sizer = kelly_sizer
        self.min_profit_threshold = min_profit_threshold
        
        # Getters for safety checks
        self._get_balance = current_balance_getter or (lambda: Decimal('100.0'))
        self._get_gas_price = current_gas_price_getter or (lambda: 50)
        self._get_pending_tx_count = pending_tx_count_getter or (lambda: 0)
        
        # Price history for volatility calculation (last 60 seconds)
        self._price_history: Dict[str, deque] = {
            'BTC': deque(maxlen=60),
            'ETH': deque(maxlen=60),
            'SOL': deque(maxlen=60),
            'XRP': deque(maxlen=60)
        }
        
        # Last known prices for movement detection
        self._last_prices: Dict[str, Decimal] = {}
        
        logger.info(
            f"LatencyArbitrageEngine initialized: "
            f"min_profit_threshold={min_profit_threshold * 100}%, "
            f"target_latency={self.TARGET_LATENCY_MS}ms"
        )
    
    async def monitor_price_movements(self) -> AsyncIterator[PriceMovement]:
        """
        Stream CEX price movements in real-time.
        
        Monitors WebSocket feeds from multiple CEXs and yields significant
        price movements that exceed the configured thresholds.
        
        Validates Requirement 4.2: Monitor CEX price movements
        
        Yields:
            PriceMovement objects for significant price changes
        """
        logger.info("Starting CEX price monitoring...")
        
        # Create tasks for each CEX feed
        tasks = []
        for exchange, feed in self.cex_feeds.items():
            task = asyncio.create_task(
                self._monitor_single_feed(exchange, feed)
            )
            tasks.append(task)
        
        # Monitor all feeds concurrently
        try:
            async for movement in self._merge_feeds(tasks):
                yield movement
        finally:
            # Cancel all tasks on shutdown
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _monitor_single_feed(
        self,
        exchange: str,
        feed: 'WebSocketFeed'
    ) -> AsyncIterator[PriceMovement]:
        """
        Monitor a single CEX WebSocket feed.
        
        Args:
            exchange: Exchange name (Binance, Coinbase, Kraken)
            feed: WebSocket feed instance
            
        Yields:
            PriceMovement objects for this exchange
        """
        logger.info(f"Monitoring {exchange} feed...")
        
        try:
            async for price_update in feed.stream_prices():
                asset = price_update['asset']
                new_price = Decimal(str(price_update['price']))
                timestamp = datetime.now()
                
                # Update price history for volatility calculation
                self._price_history[asset].append({
                    'price': new_price,
                    'timestamp': timestamp
                })
                
                # Check if we have a previous price
                if asset not in self._last_prices:
                    self._last_prices[asset] = new_price
                    continue
                
                old_price = self._last_prices[asset]
                
                # Calculate absolute price change
                price_change = abs(new_price - old_price)
                
                # Check if movement exceeds threshold (Requirement 4.2)
                threshold = self.MOVEMENT_THRESHOLDS.get(asset, Decimal('0'))
                if price_change >= threshold:
                    movement = PriceMovement(
                        asset=asset,
                        old_price=old_price,
                        new_price=new_price,
                        timestamp=timestamp,
                        exchange=exchange
                    )
                    
                    logger.info(
                        f"Significant {asset} movement on {exchange}: "
                        f"${old_price} -> ${new_price} "
                        f"({movement.change_percentage*100:.2f}% {movement.direction})"
                    )
                    
                    yield movement
                
                # Update last known price
                self._last_prices[asset] = new_price
                
        except asyncio.CancelledError:
            logger.info(f"Stopped monitoring {exchange} feed")
            raise
        except Exception as e:
            logger.error(f"Error monitoring {exchange} feed: {e}", exc_info=True)
    
    async def _merge_feeds(
        self,
        tasks: List[asyncio.Task]
    ) -> AsyncIterator[PriceMovement]:
        """
        Merge multiple feed tasks into a single stream.
        
        Args:
            tasks: List of monitoring tasks
            
        Yields:
            PriceMovement objects from any feed
        """
        # Create a queue to collect movements from all feeds
        queue = asyncio.Queue()
        
        async def collect_from_task(task):
            try:
                async for movement in task:
                    await queue.put(movement)
            except asyncio.CancelledError:
                pass
        
        # Start collectors
        collectors = [
            asyncio.create_task(collect_from_task(task))
            for task in tasks
        ]
        
        try:
            while True:
                movement = await queue.get()
                yield movement
        finally:
            for collector in collectors:
                collector.cancel()
            await asyncio.gather(*collectors, return_exceptions=True)
    
    async def check_polymarket_lag(
        self,
        movement: PriceMovement
    ) -> Optional[Opportunity]:
        """
        Check if Polymarket prices lag CEX movement.
        
        Validates Requirements:
        - 3.3: Multi-timeframe signal confirmation (1m, 5m, 15m)
        - 4.3: Calculate expected market direction
        - 4.6: Skip when volatility > 5%
        
        Args:
            movement: CEX price movement to check
            
        Returns:
            Opportunity if lag detected, None otherwise
        """
        start_time = datetime.now()
        
        try:
            # Multi-timeframe signal confirmation (Requirement 3.3)
            timeframes = {
                '1m': 60,    # 1 minute
                '5m': 300,   # 5 minutes
                '15m': 900   # 15 minutes
            }
            
            timeframe_signals = {}
            for tf_name, seconds in timeframes.items():
                # Get price history for this timeframe
                price_history = self._price_history.get(movement.asset, deque())
                if not price_history:
                    timeframe_signals[tf_name] = None
                    continue
                
                # Calculate price change over this timeframe
                cutoff_time = datetime.now() - timedelta(seconds=seconds)
                relevant_prices = [
                    (ts, price) for ts, price in price_history
                    if ts >= cutoff_time
                ]
                
                if len(relevant_prices) < 2:
                    timeframe_signals[tf_name] = None
                    continue
                
                old_price = relevant_prices[0][1]
                new_price = relevant_prices[-1][1]
                
                if old_price == 0:
                    timeframe_signals[tf_name] = None
                    continue
                
                change_pct = abs(new_price - old_price) / old_price
                
                # Determine signal direction
                if change_pct > Decimal('0.01'):  # 1% threshold
                    if new_price > old_price:
                        timeframe_signals[tf_name] = 'UP'
                    else:
                        timeframe_signals[tf_name] = 'DOWN'
                else:
                    timeframe_signals[tf_name] = 'NEUTRAL'
            
            # Count agreeing timeframes (Requirement 3.3: require 2+ agreeing)
            up_count = sum(1 for sig in timeframe_signals.values() if sig == 'UP')
            down_count = sum(1 for sig in timeframe_signals.values() if sig == 'DOWN')
            
            # Log timeframe signals
            logger.info(
                f"Multi-timeframe signals for {movement.asset}: "
                f"1m={timeframe_signals.get('1m', 'N/A')}, "
                f"5m={timeframe_signals.get('5m', 'N/A')}, "
                f"15m={timeframe_signals.get('15m', 'N/A')} | "
                f"UP={up_count}, DOWN={down_count}"
            )
            
            # Require at least 2 timeframes agreeing
            if up_count < 2 and down_count < 2:
                logger.debug(
                    f"Skipping {movement.asset}: insufficient timeframe agreement "
                    f"(need 2+, got UP={up_count}, DOWN={down_count})"
                )
                return None
            
            # Determine consensus direction
            consensus_direction = 'UP' if up_count >= 2 else 'DOWN'
            
            # Check volatility first (Requirement 4.6)
            volatility = self._calculate_volatility(movement.asset)
            if volatility > self.MAX_VOLATILITY:
                logger.debug(
                    f"Skipping {movement.asset}: volatility {volatility*100:.2f}% "
                    f"> max {self.MAX_VOLATILITY*100}%"
                )
                return None
            
            # Fetch relevant Polymarket markets
            markets = await self._get_markets_for_asset(movement.asset)
            
            if not markets:
                logger.debug(f"No Polymarket markets found for {movement.asset}")
                return None
            
            # Check each market for lag
            for market in markets:
                # Calculate expected price based on CEX movement
                expected_price = self._calculate_expected_price(
                    movement=movement,
                    market=market
                )
                
                if expected_price is None:
                    continue
                
                # Determine which side to trade based on consensus direction
                if consensus_direction == "UP":
                    # CEX went up, expect YES price to rise
                    current_price = market.yes_price
                    trade_side = "YES"
                else:
                    # CEX went down, expect NO price to rise
                    current_price = market.no_price
                    trade_side = "NO"
                
                # Calculate lag percentage (Requirement 4.3)
                if expected_price == 0:
                    continue
                
                lag_percentage = abs(expected_price - current_price) / expected_price
                
                # Check if lag exceeds minimum threshold
                if lag_percentage < self.MIN_LAG_PERCENTAGE:
                    continue
                
                # Calculate expected profit
                # If Polymarket catches up, we profit from the price difference
                expected_profit = expected_price - current_price
                
                # Account for fees
                fee = self._estimate_fee(current_price)
                fee_amount = current_price * fee
                expected_profit -= fee_amount
                
                # Check if profitable
                if expected_profit <= 0:
                    continue
                
                profit_percentage = expected_profit / current_price
                
                if profit_percentage < self.min_profit_threshold:
                    continue
                
                # Estimate gas cost
                gas_estimate = self._estimate_gas_cost()
                
                # Create opportunity
                opportunity = Opportunity(
                    opportunity_id=f"latency_{uuid.uuid4().hex[:12]}",
                    market_id=market.market_id,
                    strategy="latency_arbitrage",
                    timestamp=datetime.now(),
                    yes_price=market.yes_price if trade_side == "YES" else Decimal('0'),
                    no_price=market.no_price if trade_side == "NO" else Decimal('0'),
                    yes_fee=fee if trade_side == "YES" else Decimal('0'),
                    no_fee=fee if trade_side == "NO" else Decimal('0'),
                    total_cost=current_price,
                    expected_profit=expected_profit,
                    profit_percentage=profit_percentage,
                    position_size=Decimal('0'),  # Will be calculated during execution
                    gas_estimate=gas_estimate
                )
                
                # Check latency (Requirement 4.4)
                latency_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                logger.info(
                    f"Found latency arbitrage: {market.market_id} | "
                    f"{movement.asset} {consensus_direction} (timeframes: "
                    f"1m={timeframe_signals.get('1m', 'N/A')}, "
                    f"5m={timeframe_signals.get('5m', 'N/A')}, "
                    f"15m={timeframe_signals.get('15m', 'N/A')}) | "
                    f"Lag: {lag_percentage*100:.2f}% | "
                    f"Profit: ${expected_profit} ({profit_percentage*100:.2f}%) | "
                    f"Latency: {latency_ms:.0f}ms"
                )
                
                if latency_ms > self.TARGET_LATENCY_MS:
                    logger.warning(
                        f"Latency {latency_ms:.0f}ms exceeds target {self.TARGET_LATENCY_MS}ms"
                    )
                
                return opportunity
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking Polymarket lag: {e}", exc_info=True)
            return None
    
    async def execute(
        self,
        opportunity: Opportunity,
        market: Market,
        bankroll: Decimal
    ) -> TradeResult:
        """
        Execute latency arbitrage trade with sub-150ms target latency.
        
        Validates Requirements:
        - 4.4: Execute with sub-150ms target latency
        - 7.1-7.6: AI safety checks
        - 11.1-11.4: Kelly position sizing
        
        Args:
            opportunity: The arbitrage opportunity to execute
            market: The market associated with the opportunity
            bankroll: Current bankroll for position sizing
            
        Returns:
            TradeResult with execution details
        """
        trade_id = f"trade_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now()
        start_time = datetime.now()
        
        logger.info(f"Executing latency arbitrage: {trade_id} | {market.market_id}")
        
        try:
            # Step 1: AI Safety Check
            logger.debug("Running AI safety checks...")
            safety_decision = await self.ai_safety_guard.validate_trade(
                opportunity=opportunity,
                market=market,
                current_balance=self._get_balance(),
                current_gas_price_gwei=self._get_gas_price(),
                pending_tx_count=self._get_pending_tx_count()
            )
            
            if not safety_decision.approved:
                logger.warning(
                    f"Trade rejected by AI safety guard: {safety_decision.reason}"
                )
                return self._create_failed_result(
                    trade_id, opportunity, timestamp,
                    f"AI safety check failed: {safety_decision.reason}"
                )
            
            # Step 2: Calculate Position Size
            logger.debug("Calculating position size using Kelly Criterion...")
            position_size = self.kelly_sizer.calculate_position_size(
                opportunity=opportunity,
                bankroll=bankroll
            )
            
            logger.info(f"Position size: ${position_size} (bankroll: ${bankroll})")
            
            # Update opportunity with position size
            opportunity.position_size = position_size
            
            # Step 3: Determine trade side
            trade_side = "YES" if opportunity.yes_price > 0 else "NO"
            trade_price = opportunity.yes_price if trade_side == "YES" else opportunity.no_price
            
            # Step 4: Create and submit FOK order
            logger.debug(f"Creating FOK order: {trade_side} @ ${trade_price}...")
            order = self.order_manager.create_fok_order(
                market_id=market.market_id,
                side=trade_side,
                price=trade_price,
                size=position_size
            )
            
            # Submit order
            filled = await self.order_manager.submit_order(order)
            
            # Check latency (Requirement 4.4)
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"Execution latency: {latency_ms:.0f}ms")
            
            if not filled:
                logger.warning("FOK order failed to fill")
                return self._create_failed_result(
                    trade_id, opportunity, timestamp,
                    "FOK order failed to fill",
                    order_id=order.order_id,
                    tx_hash=order.tx_hash
                )
            
            logger.info("Order filled successfully")
            
            # Step 5: Calculate actual results
            actual_cost = order.fill_price * position_size
            fee_amount = actual_cost * (opportunity.yes_fee if trade_side == "YES" else opportunity.no_fee)
            total_cost = actual_cost + fee_amount
            
            # For latency arbitrage, profit comes from price convergence
            # This is a simplified calculation - actual profit realized on exit
            actual_profit = opportunity.expected_profit
            
            # Estimate gas cost
            gas_cost = Decimal('0.02')  # Placeholder
            net_profit = actual_profit - gas_cost
            
            logger.info(
                f"Trade completed: profit=${actual_profit}, gas=${gas_cost}, "
                f"net=${net_profit}, latency={latency_ms:.0f}ms"
            )
            
            return TradeResult(
                trade_id=trade_id,
                opportunity=opportunity,
                timestamp=timestamp,
                status="success",
                yes_order_id=order.order_id if trade_side == "YES" else None,
                no_order_id=order.order_id if trade_side == "NO" else None,
                yes_filled=trade_side == "YES",
                no_filled=trade_side == "NO",
                yes_fill_price=order.fill_price if trade_side == "YES" else None,
                no_fill_price=order.fill_price if trade_side == "NO" else None,
                actual_cost=total_cost,
                actual_profit=actual_profit,
                gas_cost=gas_cost,
                net_profit=net_profit,
                yes_tx_hash=order.tx_hash if trade_side == "YES" else None,
                no_tx_hash=order.tx_hash if trade_side == "NO" else None
            )
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}", exc_info=True)
            return self._create_failed_result(
                trade_id, opportunity, timestamp, str(e)
            )
    
    def _calculate_volatility(self, asset: str) -> Decimal:
        """
        Calculate 1-minute volatility for an asset.
        
        Validates Requirement 4.6: Calculate volatility over 1 minute
        
        Args:
            asset: Asset symbol (BTC, ETH, SOL, XRP)
            
        Returns:
            Volatility as a decimal (e.g., 0.05 = 5%)
        """
        history = self._price_history.get(asset, deque())
        
        if len(history) < 2:
            return Decimal('0')
        
        # Get prices from last 60 seconds
        now = datetime.now()
        one_minute_ago = now - timedelta(seconds=60)
        
        recent_prices = [
            entry['price']
            for entry in history
            if entry['timestamp'] >= one_minute_ago
        ]
        
        if len(recent_prices) < 2:
            return Decimal('0')
        
        # Calculate volatility as max percentage change in the period
        min_price = min(recent_prices)
        max_price = max(recent_prices)
        
        if min_price == 0:
            return Decimal('0')
        
        volatility = (max_price - min_price) / min_price
        return volatility
    
    async def _get_markets_for_asset(self, asset: str) -> List[Market]:
        """
        Get Polymarket markets for a specific asset.
        
        Args:
            asset: Asset symbol (BTC, ETH, SOL, XRP)
            
        Returns:
            List of relevant markets
        """
        try:
            # Fetch all markets from CLOB
            all_markets = await self.clob_client.get_markets()
            
            # Filter to crypto 15-minute markets for this asset
            relevant_markets = [
                market for market in all_markets
                if market.is_crypto_15min() and asset in market.question.upper()
            ]
            
            return relevant_markets
            
        except Exception as e:
            logger.error(f"Error fetching markets for {asset}: {e}")
            return []
    
    def _calculate_expected_price(
        self,
        movement: PriceMovement,
        market: Market
    ) -> Optional[Decimal]:
        """
        Calculate expected Polymarket price based on CEX movement.
        
        Validates Requirement 4.3: Calculate expected market direction
        
        Args:
            movement: CEX price movement
            market: Polymarket market
            
        Returns:
            Expected price, or None if cannot calculate
        """
        try:
            # Parse strike price from market question
            strike_price = market.parse_strike_price()
            
            if strike_price is None:
                return None
            
            # Determine market type (above/below)
            question_lower = market.question.lower()
            
            # Use a small threshold to handle floating point comparison
            threshold = Decimal('0.01')  # $0.01 threshold
            
            if "above" in question_lower:
                # Market resolves YES if price > strike
                if movement.new_price > strike_price + threshold:
                    # Price clearly above strike, YES should be high
                    return Decimal('0.95')  # Expect 95% probability
                elif movement.new_price < strike_price - threshold:
                    # Price clearly below strike, NO should be high
                    return Decimal('0.05')  # Expect 5% probability for YES
                else:
                    # Price too close to strike, uncertain
                    return None
                    
            elif "below" in question_lower:
                # Market resolves YES if price < strike
                if movement.new_price < strike_price - threshold:
                    # Price clearly below strike, YES should be high
                    return Decimal('0.95')
                elif movement.new_price > strike_price + threshold:
                    # Price clearly above strike, NO should be high
                    return Decimal('0.05')
                else:
                    # Price too close to strike, uncertain
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating expected price: {e}")
            return None
    
    def _estimate_fee(self, price: Decimal) -> Decimal:
        """
        Estimate fee for a given price.
        
        Uses simplified fee calculation (actual calculation in Rust module).
        
        Args:
            price: Position price
            
        Returns:
            Estimated fee as decimal
        """
        # Simplified fee calculation
        # Actual: fee = max(0.001, 0.03 * (1.0 - abs(2.0 * price - 1.0)))
        certainty = abs(Decimal('2.0') * price - Decimal('1.0'))
        fee = max(Decimal('0.001'), Decimal('0.03') * (Decimal('1.0') - certainty))
        return fee
    
    def _estimate_gas_cost(self) -> int:
        """
        Estimate gas cost for the trade.
        
        Returns:
            Estimated gas units
        """
        # Single order = ~150k gas
        return 150000
    
    def _create_failed_result(
        self,
        trade_id: str,
        opportunity: Opportunity,
        timestamp: datetime,
        error_message: str,
        order_id: Optional[str] = None,
        tx_hash: Optional[str] = None
    ) -> TradeResult:
        """
        Create a failed TradeResult.
        
        Args:
            trade_id: Trade ID
            opportunity: The opportunity
            timestamp: Trade timestamp
            error_message: Error message
            order_id: Optional order ID
            tx_hash: Optional transaction hash
            
        Returns:
            TradeResult with failed status
        """
        return TradeResult(
            trade_id=trade_id,
            opportunity=opportunity,
            timestamp=timestamp,
            status="failed",
            yes_order_id=order_id if opportunity.yes_price > 0 else None,
            no_order_id=order_id if opportunity.no_price > 0 else None,
            yes_filled=False,
            no_filled=False,
            yes_fill_price=None,
            no_fill_price=None,
            actual_cost=Decimal('0'),
            actual_profit=Decimal('0'),
            gas_cost=Decimal('0'),
            net_profit=Decimal('0'),
            yes_tx_hash=tx_hash if opportunity.yes_price > 0 else None,
            no_tx_hash=tx_hash if opportunity.no_price > 0 else None,
            error_message=error_message
        )
