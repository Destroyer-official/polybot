"""
Internal Arbitrage Engine for Polymarket Arbitrage Bot.

Detects and executes internal arbitrage opportunities where YES + NO < $1.00.
Implements Requirements 1.1, 1.2, 2.4.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import rust_core
from src.models import Market, Opportunity, TradeResult, SafetyDecision
from src.ai_safety_guard import AISafetyGuard
from src.kelly_position_sizer import KellyPositionSizer
from src.dynamic_position_sizer import DynamicPositionSizer
from src.order_manager import OrderManager, Order
from src.position_merger import PositionMerger

logger = logging.getLogger(__name__)


class InternalArbitrageEngine:
    """
    Detects and executes internal arbitrage opportunities.
    
    Internal arbitrage occurs when:
    YES_price + NO_price + YES_fee + NO_fee < $1.00
    
    The strategy:
    1. Buy both YES and NO positions
    2. Merge positions to redeem $1.00 USDC
    3. Profit = $1.00 - total_cost
    
    Validates Requirements:
    - 1.1: Calculate total cost as YES_price + NO_price + YES_fee + NO_fee
    - 1.2: Identify opportunities when total cost < $0.995 (0.5% minimum profit)
    - 2.4: Filter opportunities below 0.5% profit threshold
    """
    
    def __init__(
        self,
        clob_client,  # Type hint omitted to avoid import dependency
        order_manager: OrderManager,
        position_merger: PositionMerger,
        ai_safety_guard: AISafetyGuard,
        kelly_sizer: KellyPositionSizer,
        dynamic_sizer: Optional[DynamicPositionSizer] = None,
        min_profit_threshold: Decimal = Decimal('0.005'),  # 0.5%
        current_balance_getter=None,  # Callable to get current balance
        current_gas_price_getter=None,  # Callable to get current gas price
        pending_tx_count_getter=None  # Callable to get pending TX count
    ):
        """
        Initialize Internal Arbitrage Engine.
        
        Args:
            clob_client: CLOB client for market data
            order_manager: Order manager for trade execution
            position_merger: Position merger for redeeming positions
            ai_safety_guard: AI safety guard for validation
            kelly_sizer: Kelly position sizer for optimal sizing
            dynamic_sizer: Dynamic position sizer (optional, recommended)
            min_profit_threshold: Minimum profit percentage (default 0.5%)
            current_balance_getter: Function to get current balance
            current_gas_price_getter: Function to get current gas price in gwei
            pending_tx_count_getter: Function to get pending transaction count
        """
        self.clob_client = clob_client
        self.order_manager = order_manager
        self.position_merger = position_merger
        self.ai_safety_guard = ai_safety_guard
        self.kelly_sizer = kelly_sizer
        self.dynamic_sizer = dynamic_sizer or DynamicPositionSizer()
        self.min_profit_threshold = min_profit_threshold
        
        # Getters for safety checks
        self._get_balance = current_balance_getter or (lambda: Decimal('100.0'))
        self._get_gas_price = current_gas_price_getter or (lambda: 50)
        self._get_pending_tx_count = pending_tx_count_getter or (lambda: 0)
        
        logger.info(
            f"InternalArbitrageEngine initialized: "
            f"min_profit_threshold={min_profit_threshold * 100}%, "
            f"dynamic_sizing={'enabled' if dynamic_sizer else 'default'}"
        )
    
    async def scan_opportunities(self, markets: List[Market]) -> List[Opportunity]:
        """
        Scan markets for internal arbitrage opportunities.
        
        Uses Rust fee calculator for performance-critical fee calculations.
        
        Validates Requirements:
        - 1.1: Calculate total cost including dynamic fees
        - 1.2: Identify opportunities when total cost < $0.995
        - 2.4: Filter opportunities below 0.5% profit threshold
        
        Args:
            markets: List of markets to scan
            
        Returns:
            List of profitable arbitrage opportunities
        """
        opportunities = []
        
        for market in markets:
            try:
                # Skip if not a valid crypto 15-minute market
                if not market.is_crypto_15min():
                    continue
                
                # Get prices (already in Decimal from Market model)
                yes_price = market.yes_price
                no_price = market.no_price
                
                # Calculate profit using Rust fee calculator
                profit = self.calculate_profit(yes_price, no_price)
                
                # Check if profitable (Requirement 1.2, 2.4)
                if profit is None or profit <= 0:
                    continue
                
                # Calculate profit percentage
                yes_fee, no_fee, total_cost = self._calculate_fees_and_cost(
                    yes_price, no_price
                )
                profit_percentage = profit / total_cost if total_cost > 0 else Decimal('0')
                
                # Filter by minimum profit threshold (Requirement 2.4)
                if profit_percentage < self.min_profit_threshold:
                    logger.debug(
                        f"Skipping {market.market_id}: profit {profit_percentage*100:.2f}% "
                        f"< threshold {self.min_profit_threshold*100}%"
                    )
                    continue
                
                # Estimate gas cost for the trade
                gas_estimate = self._estimate_gas_cost()
                
                # Create opportunity
                opportunity = Opportunity(
                    opportunity_id=f"internal_{uuid.uuid4().hex[:12]}",
                    market_id=market.market_id,
                    strategy="internal_arbitrage",
                    timestamp=datetime.now(),
                    yes_price=yes_price,
                    no_price=no_price,
                    yes_fee=yes_fee,
                    no_fee=no_fee,
                    total_cost=total_cost,
                    expected_profit=profit,
                    profit_percentage=profit_percentage,
                    position_size=Decimal('0'),  # Will be calculated during execution
                    gas_estimate=gas_estimate
                )
                
                opportunities.append(opportunity)
                
                logger.info(
                    f"Found internal arbitrage: {market.market_id} | "
                    f"YES=${yes_price} NO=${no_price} | "
                    f"Profit=${profit} ({profit_percentage*100:.2f}%)"
                )
                
            except Exception as e:
                logger.error(f"Error scanning market {market.market_id}: {e}")
                continue
        
        logger.debug(f"Scanned {len(markets)} markets, found {len(opportunities)} opportunities")
        return opportunities
    
    def calculate_profit(self, yes_price: Decimal, no_price: Decimal) -> Optional[Decimal]:
        """
        Calculate expected profit after fees using Rust fee calculator.
        
        Validates Requirement 2.4: Calculate profit with fee accounting
        
        Formula:
        - total_cost = YES_price + NO_price + (YES_price * YES_fee) + (NO_price * NO_fee)
        - profit = $1.00 - total_cost
        
        Args:
            yes_price: YES position price
            no_price: NO position price
            
        Returns:
            Expected profit in USDC, or None if not profitable
        """
        try:
            # Convert Decimal to float for Rust
            yes_price_float = float(yes_price)
            no_price_float = float(no_price)
            
            # Use Rust fee calculator for performance (Requirement 2.5)
            yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(
                yes_price_float, no_price_float
            )
            
            # Calculate profit
            redemption_value = 1.0
            profit = redemption_value - total_cost
            
            # Return None if not profitable
            if profit <= 0:
                return None
            
            # Convert back to Decimal for precision
            return Decimal(str(profit))
            
        except Exception as e:
            logger.error(f"Error calculating profit: {e}")
            return None
    
    async def execute(
        self,
        opportunity: Opportunity,
        market: Market,
        bankroll: Decimal,
        private_wallet_balance: Optional[Decimal] = None,
        polymarket_balance: Optional[Decimal] = None,
        recent_win_rate: Optional[float] = None
    ) -> TradeResult:
        """
        Execute internal arbitrage trade with AI safety checks and dynamic sizing.
        
        Validates Requirements:
        - 1.3: Create FOK orders for both YES and NO
        - 1.4: Verify both orders fill or neither fills
        - 1.5: Merge positions after acquisition
        - 1.6: Receive $1.00 USDC per position pair
        - 7.1-7.6: AI safety checks
        - 11.1-11.4: Kelly position sizing
        - NEW: Dynamic position sizing based on available balance
        
        Args:
            opportunity: The arbitrage opportunity to execute
            market: The market associated with the opportunity
            bankroll: Current bankroll for position sizing
            private_wallet_balance: Private wallet USDC balance (optional)
            polymarket_balance: Polymarket USDC balance (optional)
            recent_win_rate: Recent win rate for dynamic sizing (optional)
            
        Returns:
            TradeResult with execution details
        """
        trade_id = f"trade_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now()
        
        logger.info(f"Executing internal arbitrage: {trade_id} | {market.market_id}")
        
        try:
            # Step 1: AI Safety Check (Requirements 7.1-7.6)
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
                    error_message=f"AI safety check failed: {safety_decision.reason}"
                )
            
            logger.info(f"AI safety check passed: {safety_decision.reason}")
            
            # Step 2: Calculate Position Size
            # Use dynamic sizer if balance info provided, otherwise use Kelly
            if private_wallet_balance is not None and polymarket_balance is not None:
                logger.debug("Calculating position size using dynamic sizer...")
                position_size = self.dynamic_sizer.calculate_position_size(
                    private_wallet_balance=private_wallet_balance,
                    polymarket_balance=polymarket_balance,
                    opportunity=opportunity,
                    market=market,
                    recent_win_rate=recent_win_rate,
                    pending_trades_value=Decimal('0')  # TODO: track pending trades
                )
                logger.info(
                    f"Dynamic position size: ${position_size} "
                    f"(private: ${private_wallet_balance}, polymarket: ${polymarket_balance})"
                )
            else:
                logger.debug("Calculating position size using Kelly Criterion...")
                position_size = self.kelly_sizer.calculate_position_size(
                    opportunity=opportunity,
                    bankroll=bankroll
                )
                logger.info(f"Kelly position size: ${position_size} (bankroll: ${bankroll})")
            
            # Validate position size
            if position_size <= 0:
                logger.warning("Position size is zero or negative, skipping trade")
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
                    error_message="Position size is zero or negative"
                )
            
            # Update opportunity with position size
            opportunity.position_size = position_size
            
            # Step 3: Create FOK Orders (Requirement 1.3, 6.1)
            logger.debug("Creating FOK orders...")
            yes_order = self.order_manager.create_fok_order(
                market_id=market.market_id,
                side="YES",
                price=opportunity.yes_price,
                size=position_size
            )
            
            no_order = self.order_manager.create_fok_order(
                market_id=market.market_id,
                side="NO",
                price=opportunity.no_price,
                size=position_size
            )
            
            logger.info(
                f"Created FOK orders: YES={yes_order.order_id}, NO={no_order.order_id}"
            )
            
            # Step 4: Submit Atomic Order Pair (Requirement 1.4, 6.3)
            logger.debug("Submitting atomic order pair...")
            yes_filled, no_filled = await self.order_manager.submit_atomic_pair(
                yes_order=yes_order,
                no_order=no_order
            )
            
            # Check if both orders filled
            if not (yes_filled and no_filled):
                logger.warning(
                    f"Atomic execution failed: YES={yes_filled}, NO={no_filled}"
                )
                return TradeResult(
                    trade_id=trade_id,
                    opportunity=opportunity,
                    timestamp=timestamp,
                    status="failed",
                    yes_order_id=yes_order.order_id,
                    no_order_id=no_order.order_id,
                    yes_filled=yes_filled,
                    no_filled=no_filled,
                    yes_fill_price=yes_order.fill_price,
                    no_fill_price=no_order.fill_price,
                    actual_cost=Decimal('0'),
                    actual_profit=Decimal('0'),
                    gas_cost=Decimal('0'),
                    net_profit=Decimal('0'),
                    yes_tx_hash=yes_order.tx_hash,
                    no_tx_hash=no_order.tx_hash,
                    error_message="FOK orders failed to fill"
                )
            
            logger.info("Both orders filled successfully")
            
            # Step 5: Calculate Actual Cost
            actual_yes_cost = yes_order.fill_price * position_size
            actual_no_cost = no_order.fill_price * position_size
            
            # Calculate actual fees
            yes_fee_amount = actual_yes_cost * opportunity.yes_fee
            no_fee_amount = actual_no_cost * opportunity.no_fee
            
            actual_cost = actual_yes_cost + actual_no_cost + yes_fee_amount + no_fee_amount
            
            # Step 6: Merge Positions (Requirement 1.5, 1.6)
            logger.debug("Merging positions...")
            merge_receipt = await self.position_merger.merge_positions(
                market_id=market.market_id,
                amount=position_size
            )
            
            logger.info(f"Positions merged: tx={merge_receipt['transactionHash'].hex()}")
            
            # Step 7: Calculate Profit
            redemption_value = position_size  # $1.00 per position pair
            actual_profit = redemption_value - actual_cost
            
            # Estimate gas cost (simplified)
            gas_cost = Decimal('0.05')  # Placeholder, should calculate from receipts
            net_profit = actual_profit - gas_cost
            
            logger.info(
                f"Trade completed: profit=${actual_profit}, gas=${gas_cost}, net=${net_profit}"
            )
            
            return TradeResult(
                trade_id=trade_id,
                opportunity=opportunity,
                timestamp=timestamp,
                status="success",
                yes_order_id=yes_order.order_id,
                no_order_id=no_order.order_id,
                yes_filled=True,
                no_filled=True,
                yes_fill_price=yes_order.fill_price,
                no_fill_price=no_order.fill_price,
                actual_cost=actual_cost,
                actual_profit=actual_profit,
                gas_cost=gas_cost,
                net_profit=net_profit,
                yes_tx_hash=yes_order.tx_hash,
                no_tx_hash=no_order.tx_hash,
                merge_tx_hash=merge_receipt['transactionHash'].hex()
            )
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}", exc_info=True)
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
                error_message=str(e)
            )
    
    def _calculate_fees_and_cost(
        self,
        yes_price: Decimal,
        no_price: Decimal
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Calculate fees and total cost using Rust fee calculator.
        
        Args:
            yes_price: YES position price
            no_price: NO position price
            
        Returns:
            Tuple of (yes_fee, no_fee, total_cost)
        """
        yes_price_float = float(yes_price)
        no_price_float = float(no_price)
        
        yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(
            yes_price_float, no_price_float
        )
        
        return Decimal(str(yes_fee)), Decimal(str(no_fee)), Decimal(str(total_cost))
    
    def _estimate_gas_cost(self) -> int:
        """
        Estimate gas cost for the trade.
        
        Returns:
            Estimated gas units
        """
        # Placeholder: 2 orders + 1 merge = ~300k gas
        return 300000
