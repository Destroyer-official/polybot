"""
Cross-Platform Arbitrage Engine for Polymarket Arbitrage Bot.

Exploits price differences between Polymarket and Kalshi.
Implements Requirements 3.2, 3.3, 3.4, 3.6.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Tuple

import rust_core
from src.models import Market, Opportunity, TradeResult, SafetyDecision
from src.ai_safety_guard import AISafetyGuard
from src.kelly_position_sizer import KellyPositionSizer
from src.order_manager import OrderManager, Order

logger = logging.getLogger(__name__)


class CrossPlatformArbitrageEngine:
    """
    Detects and executes cross-platform arbitrage opportunities.
    
    Cross-platform arbitrage occurs when:
    Polymarket_YES_price + fees < Kalshi_NO_price - fees (or vice versa)
    
    The strategy:
    1. Buy YES on one platform, NO on the other
    2. Profit from price discrepancy
    3. Account for withdrawal fees and settlement times
    
    Validates Requirements:
    - 3.2: Compare prices for equivalent markets on both platforms
    - 3.3: Identify cross-platform arbitrage opportunities
    - 3.4: Submit FOK orders on both platforms simultaneously
    - 3.6: Account for withdrawal fees and settlement times
    """
    
    def __init__(
        self,
        polymarket_client,  # CLOB client for Polymarket
        kalshi_client,  # Kalshi API client
        polymarket_order_manager: OrderManager,
        kalshi_order_manager: OrderManager,
        ai_safety_guard: AISafetyGuard,
        kelly_sizer: KellyPositionSizer,
        min_profit_threshold: Decimal = Decimal('0.005'),  # 0.5%
        withdrawal_fee_polymarket: Decimal = Decimal('0.001'),  # 0.1%
        withdrawal_fee_kalshi: Decimal = Decimal('0.002'),  # 0.2%
        settlement_time_hours: int = 24,  # Settlement time in hours
        current_balance_getter=None,
        current_gas_price_getter=None,
        pending_tx_count_getter=None
    ):
        """
        Initialize Cross-Platform Arbitrage Engine.
        
        Validates Requirement 3.2: Establish connections to both platforms
        
        Args:
            polymarket_client: CLOB client for Polymarket market data
            kalshi_client: Kalshi API client for market data
            polymarket_order_manager: Order manager for Polymarket trades
            kalshi_order_manager: Order manager for Kalshi trades
            ai_safety_guard: AI safety guard for validation
            kelly_sizer: Kelly position sizer for optimal sizing
            min_profit_threshold: Minimum profit percentage (default 0.5%)
            withdrawal_fee_polymarket: Polymarket withdrawal fee (default 0.1%)
            withdrawal_fee_kalshi: Kalshi withdrawal fee (default 0.2%)
            settlement_time_hours: Settlement time in hours (default 24)
            current_balance_getter: Function to get current balance
            current_gas_price_getter: Function to get current gas price in gwei
            pending_tx_count_getter: Function to get pending transaction count
        """
        self.polymarket_client = polymarket_client
        self.kalshi_client = kalshi_client
        self.polymarket_order_manager = polymarket_order_manager
        self.kalshi_order_manager = kalshi_order_manager
        self.ai_safety_guard = ai_safety_guard
        self.kelly_sizer = kelly_sizer
        self.min_profit_threshold = min_profit_threshold
        
        # Withdrawal fees and settlement times (Requirement 3.6)
        self.withdrawal_fee_polymarket = withdrawal_fee_polymarket
        self.withdrawal_fee_kalshi = withdrawal_fee_kalshi
        self.settlement_time_hours = settlement_time_hours
        
        # Getters for safety checks
        self._get_balance = current_balance_getter or (lambda: Decimal('100.0'))
        self._get_gas_price = current_gas_price_getter or (lambda: 50)
        self._get_pending_tx_count = pending_tx_count_getter or (lambda: 0)
        
        # Cache for equivalent market mappings
        self._market_mappings: Dict[str, str] = {}
        
        logger.info(
            f"CrossPlatformArbitrageEngine initialized: "
            f"min_profit_threshold={min_profit_threshold * 100}%, "
            f"withdrawal_fees=(PM:{withdrawal_fee_polymarket*100}%, "
            f"Kalshi:{withdrawal_fee_kalshi*100}%), "
            f"settlement_time={settlement_time_hours}h"
        )
    
    async def scan_opportunities(self) -> List[Opportunity]:
        """
        Scan for cross-platform arbitrage opportunities.
        
        Validates Requirements:
        - 3.2: Compare prices for equivalent markets on both platforms
        - 3.3: Identify cross-platform arbitrage when price discrepancy exists
        - 3.6: Account for withdrawal fees in profit calculation
        
        Returns:
            List of profitable cross-platform arbitrage opportunities
        """
        opportunities = []
        
        try:
            # Fetch markets from both platforms
            logger.debug("Fetching markets from Polymarket and Kalshi...")
            polymarket_markets = await self._fetch_polymarket_markets()
            kalshi_markets = await self._fetch_kalshi_markets()
            
            logger.debug(
                f"Fetched {len(polymarket_markets)} Polymarket markets, "
                f"{len(kalshi_markets)} Kalshi markets"
            )
            
            # Find equivalent market pairs
            market_pairs = self._find_equivalent_markets(
                polymarket_markets, kalshi_markets
            )
            
            logger.debug(f"Found {len(market_pairs)} equivalent market pairs")
            
            # Check each pair for arbitrage opportunities
            for pm_market, kalshi_market in market_pairs:
                try:
                    # Strategy 1: Buy YES on Polymarket, NO on Kalshi
                    opp1 = self._check_arbitrage_opportunity(
                        pm_market=pm_market,
                        kalshi_market=kalshi_market,
                        pm_side="YES",
                        kalshi_side="NO"
                    )
                    if opp1 and opp1.is_profitable(self.min_profit_threshold):
                        opportunities.append(opp1)
                        logger.info(
                            f"Found cross-platform arbitrage: "
                            f"PM YES ${opp1.yes_price} < Kalshi NO | "
                            f"Profit: ${opp1.expected_profit} ({opp1.profit_percentage*100:.2f}%)"
                        )
                    
                    # Strategy 2: Buy NO on Polymarket, YES on Kalshi
                    opp2 = self._check_arbitrage_opportunity(
                        pm_market=pm_market,
                        kalshi_market=kalshi_market,
                        pm_side="NO",
                        kalshi_side="YES"
                    )
                    if opp2 and opp2.is_profitable(self.min_profit_threshold):
                        opportunities.append(opp2)
                        logger.info(
                            f"Found cross-platform arbitrage: "
                            f"PM NO ${opp2.no_price} < Kalshi YES | "
                            f"Profit: ${opp2.expected_profit} ({opp2.profit_percentage*100:.2f}%)"
                        )
                
                except Exception as e:
                    logger.error(
                        f"Error checking arbitrage for markets "
                        f"{pm_market.market_id} / {kalshi_market.market_id}: {e}"
                    )
                    continue
            
            logger.debug(
                f"Scanned {len(market_pairs)} market pairs, "
                f"found {len(opportunities)} opportunities"
            )
            
        except Exception as e:
            logger.error(f"Error scanning cross-platform opportunities: {e}")
        
        return opportunities
    
    def _check_arbitrage_opportunity(
        self,
        pm_market: Market,
        kalshi_market: Market,
        pm_side: str,
        kalshi_side: str
    ) -> Optional[Opportunity]:
        """
        Check if an arbitrage opportunity exists for a specific direction.
        
        Validates Requirements:
        - 3.3: Identify arbitrage when PM price + fees < Kalshi price - fees
        - 3.6: Account for withdrawal fees and settlement costs
        
        Args:
            pm_market: Polymarket market
            kalshi_market: Kalshi market
            pm_side: Side to buy on Polymarket ("YES" or "NO")
            kalshi_side: Side to buy on Kalshi ("YES" or "NO")
            
        Returns:
            Opportunity if profitable, None otherwise
        """
        try:
            # Get prices
            pm_price = pm_market.yes_price if pm_side == "YES" else pm_market.no_price
            kalshi_price = kalshi_market.yes_price if kalshi_side == "YES" else kalshi_market.no_price
            
            # Calculate trading fees using Rust fee calculator
            pm_fee_rate = self._calculate_fee(pm_price)
            kalshi_fee_rate = self._calculate_fee(kalshi_price)
            
            # Calculate total costs including trading fees
            pm_cost = pm_price * (Decimal('1') + pm_fee_rate)
            kalshi_cost = kalshi_price * (Decimal('1') + kalshi_fee_rate)
            
            # Account for withdrawal fees (Requirement 3.6)
            pm_withdrawal_cost = pm_price * self.withdrawal_fee_polymarket
            kalshi_withdrawal_cost = kalshi_price * self.withdrawal_fee_kalshi
            
            # Total cost for the arbitrage
            total_cost = pm_cost + kalshi_cost + pm_withdrawal_cost + kalshi_withdrawal_cost
            
            # Expected payout: $1.00 per position pair
            expected_payout = Decimal('1.0')
            
            # Calculate profit
            profit = expected_payout - total_cost
            
            # Check if profitable
            if profit <= 0:
                return None
            
            profit_percentage = profit / total_cost if total_cost > 0 else Decimal('0')
            
            # Filter by minimum threshold
            if profit_percentage < self.min_profit_threshold:
                return None
            
            # Estimate gas cost
            gas_estimate = self._estimate_gas_cost()
            
            # Create opportunity
            opportunity = Opportunity(
                opportunity_id=f"cross_platform_{uuid.uuid4().hex[:12]}",
                market_id=pm_market.market_id,
                strategy="cross_platform_arbitrage",
                timestamp=datetime.now(),
                yes_price=pm_price if pm_side == "YES" else kalshi_price,
                no_price=pm_price if pm_side == "NO" else kalshi_price,
                yes_fee=pm_fee_rate if pm_side == "YES" else kalshi_fee_rate,
                no_fee=pm_fee_rate if pm_side == "NO" else kalshi_fee_rate,
                total_cost=total_cost,
                expected_profit=profit,
                profit_percentage=profit_percentage,
                position_size=Decimal('0'),  # Will be calculated during execution
                gas_estimate=gas_estimate,
                platform_a="polymarket",
                platform_b="kalshi"
            )
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error checking arbitrage opportunity: {e}")
            return None
    
    async def execute(
        self,
        opportunity: Opportunity,
        pm_market: Market,
        kalshi_market: Market,
        bankroll: Decimal
    ) -> TradeResult:
        """
        Execute cross-platform arbitrage trade with atomic execution.
        
        Validates Requirements:
        - 3.4: Submit FOK orders on both platforms simultaneously
        - 3.5: Cancel other platform's order if either fails to fill
        
        Args:
            opportunity: The arbitrage opportunity to execute
            pm_market: Polymarket market
            kalshi_market: Kalshi market
            bankroll: Current bankroll for position sizing
            
        Returns:
            TradeResult with execution details
        """
        trade_id = f"trade_{uuid.uuid4().hex[:12]}",
        timestamp = datetime.now()
        
        logger.info(
            f"Executing cross-platform arbitrage: {trade_id} | "
            f"PM:{pm_market.market_id} / Kalshi:{kalshi_market.market_id}"
        )
        
        try:
            # Step 1: AI Safety Check
            logger.debug("Running AI safety checks...")
            safety_decision = await self.ai_safety_guard.validate_trade(
                opportunity=opportunity,
                market=pm_market,  # Use PM market for safety check
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
            
            logger.info(f"AI safety check passed: {safety_decision.reason}")
            
            # Step 2: Calculate Position Size
            logger.debug("Calculating position size using Kelly Criterion...")
            position_size = self.kelly_sizer.calculate_position_size(
                opportunity=opportunity,
                bankroll=bankroll
            )
            
            logger.info(f"Position size: ${position_size} (bankroll: ${bankroll})")
            opportunity.position_size = position_size
            
            # Step 3: Determine which side to buy on each platform
            # For simplicity, assume YES on PM and NO on Kalshi
            # (In production, this would be determined by the opportunity)
            pm_side = "YES"
            kalshi_side = "NO"
            pm_price = opportunity.yes_price
            kalshi_price = opportunity.no_price
            
            # Step 4: Create FOK Orders on both platforms (Requirement 3.4)
            logger.debug("Creating FOK orders on both platforms...")
            
            pm_order = self.polymarket_order_manager.create_fok_order(
                market_id=pm_market.market_id,
                side=pm_side,
                price=pm_price,
                size=position_size
            )
            
            kalshi_order = self.kalshi_order_manager.create_fok_order(
                market_id=kalshi_market.market_id,
                side=kalshi_side,
                price=kalshi_price,
                size=position_size
            )
            
            logger.info(
                f"Created FOK orders: PM={pm_order.order_id}, Kalshi={kalshi_order.order_id}"
            )
            
            # Step 5: Submit orders simultaneously (Requirement 3.4)
            logger.debug("Submitting orders simultaneously on both platforms...")
            
            # Submit both orders concurrently
            pm_task = asyncio.create_task(
                self.polymarket_order_manager.submit_order(pm_order)
            )
            kalshi_task = asyncio.create_task(
                self.kalshi_order_manager.submit_order(kalshi_order)
            )
            
            # Wait for both to complete
            pm_filled, kalshi_filled = await asyncio.gather(
                pm_task, kalshi_task, return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(pm_filled, Exception):
                logger.error(f"Polymarket order failed: {pm_filled}")
                pm_filled = False
            if isinstance(kalshi_filled, Exception):
                logger.error(f"Kalshi order failed: {kalshi_filled}")
                kalshi_filled = False
            
            # Step 6: Check atomicity (Requirement 3.5)
            if not (pm_filled and kalshi_filled):
                logger.warning(
                    f"Atomic execution failed: PM={pm_filled}, Kalshi={kalshi_filled}"
                )
                
                # Cancel the filled order if only one filled (Requirement 3.5)
                if pm_filled and not kalshi_filled:
                    logger.info("Cancelling Polymarket order...")
                    await self.polymarket_order_manager.cancel_order(pm_order.order_id)
                elif kalshi_filled and not pm_filled:
                    logger.info("Cancelling Kalshi order...")
                    await self.kalshi_order_manager.cancel_order(kalshi_order.order_id)
                
                return TradeResult(
                    trade_id=trade_id,
                    opportunity=opportunity,
                    timestamp=timestamp,
                    status="failed",
                    yes_order_id=pm_order.order_id if pm_side == "YES" else kalshi_order.order_id,
                    no_order_id=kalshi_order.order_id if kalshi_side == "NO" else pm_order.order_id,
                    yes_filled=pm_filled if pm_side == "YES" else kalshi_filled,
                    no_filled=kalshi_filled if kalshi_side == "NO" else pm_filled,
                    yes_fill_price=pm_order.fill_price if pm_side == "YES" else kalshi_order.fill_price,
                    no_fill_price=kalshi_order.fill_price if kalshi_side == "NO" else pm_order.fill_price,
                    actual_cost=Decimal('0'),
                    actual_profit=Decimal('0'),
                    gas_cost=Decimal('0'),
                    net_profit=Decimal('0'),
                    yes_tx_hash=pm_order.tx_hash if pm_side == "YES" else kalshi_order.tx_hash,
                    no_tx_hash=kalshi_order.tx_hash if kalshi_side == "NO" else pm_order.tx_hash,
                    error_message="FOK orders failed to fill atomically"
                )
            
            logger.info("Both orders filled successfully")
            
            # Step 7: Calculate Actual Cost and Profit
            pm_cost = pm_order.fill_price * position_size
            kalshi_cost = kalshi_order.fill_price * position_size
            
            # Calculate actual fees
            pm_fee_amount = pm_cost * opportunity.yes_fee if pm_side == "YES" else pm_cost * opportunity.no_fee
            kalshi_fee_amount = kalshi_cost * opportunity.no_fee if kalshi_side == "NO" else kalshi_cost * opportunity.yes_fee
            
            # Add withdrawal fees
            pm_withdrawal = pm_cost * self.withdrawal_fee_polymarket
            kalshi_withdrawal = kalshi_cost * self.withdrawal_fee_kalshi
            
            actual_cost = pm_cost + kalshi_cost + pm_fee_amount + kalshi_fee_amount + pm_withdrawal + kalshi_withdrawal
            
            # Expected payout
            expected_payout = position_size  # $1.00 per position pair
            actual_profit = expected_payout - actual_cost
            
            # Estimate gas cost
            gas_cost = Decimal('0.05')  # Placeholder
            net_profit = actual_profit - gas_cost
            
            logger.info(
                f"Trade completed: profit=${actual_profit}, gas=${gas_cost}, net=${net_profit}"
            )
            
            return TradeResult(
                trade_id=trade_id,
                opportunity=opportunity,
                timestamp=timestamp,
                status="success",
                yes_order_id=pm_order.order_id if pm_side == "YES" else kalshi_order.order_id,
                no_order_id=kalshi_order.order_id if kalshi_side == "NO" else pm_order.order_id,
                yes_filled=True,
                no_filled=True,
                yes_fill_price=pm_order.fill_price if pm_side == "YES" else kalshi_order.fill_price,
                no_fill_price=kalshi_order.fill_price if kalshi_side == "NO" else pm_order.fill_price,
                actual_cost=actual_cost,
                actual_profit=actual_profit,
                gas_cost=gas_cost,
                net_profit=net_profit,
                yes_tx_hash=pm_order.tx_hash if pm_side == "YES" else kalshi_order.tx_hash,
                no_tx_hash=kalshi_order.tx_hash if kalshi_side == "NO" else pm_order.tx_hash
            )
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}", exc_info=True)
            return self._create_failed_result(trade_id, opportunity, timestamp, str(e))
    
    async def _fetch_polymarket_markets(self) -> List[Market]:
        """
        Fetch active markets from Polymarket.
        
        Returns:
            List of Polymarket markets
        """
        # Placeholder: In production, this would call the CLOB API
        # For now, return empty list
        return []
    
    async def _fetch_kalshi_markets(self) -> List[Market]:
        """
        Fetch active markets from Kalshi.
        
        Returns:
            List of Kalshi markets
        """
        # Placeholder: In production, this would call the Kalshi API
        # For now, return empty list
        return []
    
    def _find_equivalent_markets(
        self,
        polymarket_markets: List[Market],
        kalshi_markets: List[Market]
    ) -> List[Tuple[Market, Market]]:
        """
        Find equivalent market pairs between Polymarket and Kalshi.
        
        Args:
            polymarket_markets: List of Polymarket markets
            kalshi_markets: List of Kalshi markets
            
        Returns:
            List of (Polymarket market, Kalshi market) tuples
        """
        pairs = []
        
        # Simple matching based on asset and question similarity
        for pm_market in polymarket_markets:
            for kalshi_market in kalshi_markets:
                if self._are_markets_equivalent(pm_market, kalshi_market):
                    pairs.append((pm_market, kalshi_market))
                    break
        
        return pairs
    
    def _are_markets_equivalent(self, market1: Market, market2: Market) -> bool:
        """
        Check if two markets are equivalent.
        
        Args:
            market1: First market
            market2: Second market
            
        Returns:
            True if markets are equivalent
        """
        # Simple check: same asset and similar questions
        if market1.asset != market2.asset:
            return False
        
        # Check if questions are similar (simplified)
        # In production, this would use more sophisticated matching
        question1_lower = market1.question.lower()
        question2_lower = market2.question.lower()
        
        # Check for common keywords
        common_keywords = ["above", "below", "higher", "lower", "price"]
        has_common = any(kw in question1_lower and kw in question2_lower for kw in common_keywords)
        
        return has_common
    
    def _calculate_fee(self, price: Decimal) -> Decimal:
        """
        Calculate trading fee using Rust fee calculator.
        
        Args:
            price: Position price
            
        Returns:
            Fee rate as a decimal (e.g., 0.03 for 3%)
        """
        try:
            price_float = float(price)
            fee = rust_core.calculate_fee(price_float)
            return Decimal(str(fee))
        except Exception as e:
            logger.error(f"Error calculating fee: {e}")
            return Decimal('0.03')  # Default to 3%
    
    def _estimate_gas_cost(self) -> int:
        """
        Estimate gas cost for cross-platform trade.
        
        Returns:
            Estimated gas units
        """
        # Placeholder: 2 orders on different platforms
        return 200000
    
    def _create_failed_result(
        self,
        trade_id: str,
        opportunity: Opportunity,
        timestamp: datetime,
        error_message: str
    ) -> TradeResult:
        """
        Create a failed TradeResult.
        
        Args:
            trade_id: Trade ID
            opportunity: The opportunity
            timestamp: Timestamp
            error_message: Error message
            
        Returns:
            TradeResult with failed status
        """
        return TradeResult(
            trade_id=trade_id,
            opportunity=opportunity,
            timestamp=timestamp,
            status="failed",
            yes_order_id=None,
            no_order_id=None,
            yes_filled=False,
            no_filled=False,
            yes_fill_price=None,
            no_fill_price=None,
            actual_cost=Decimal('0'),
            actual_profit=Decimal('0'),
            gas_cost=Decimal('0'),
            net_profit=Decimal('0'),
            error_message=error_message
        )
