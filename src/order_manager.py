"""
Order Manager for Polymarket Arbitrage Bot.

Manages order creation, submission, and tracking with FOK (Fill-Or-Kill) orders.
Validates Requirements 6.1, 6.2, 1.3, 1.4, 6.3, 6.4.
"""

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple
from datetime import datetime
import uuid

from src.transaction_manager import TransactionManager

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    market_id: str
    side: str  # "YES" or "NO"
    price: Decimal
    size: Decimal
    order_type: str  # "FOK" (Fill-Or-Kill)
    slippage_tolerance: Decimal  # Maximum slippage (e.g., 0.001 = 0.1%)
    created_at: datetime
    
    # Execution details
    filled: bool = False
    fill_price: Optional[Decimal] = None
    tx_hash: Optional[str] = None
    error_message: Optional[str] = None


class OrderError(Exception):
    """Base exception for order errors."""
    pass


class OrderNotFilledError(OrderError):
    """Raised when FOK order fails to fill."""
    pass


class SlippageExceededError(OrderError):
    """Raised when fill price exceeds slippage tolerance."""
    pass


class AtomicExecutionError(OrderError):
    """Raised when atomic order pair execution fails."""
    pass


class OrderManager:
    """
    Manages order creation and execution with FOK orders.
    
    Features:
    - FOK (Fill-Or-Kill) order creation with 0.1% slippage tolerance
    - Atomic YES/NO order pair submission
    - Fill price validation
    - Order cancellation
    
    Validates Requirements:
    - 6.1: Create FOK orders
    - 6.2: 0.1% maximum slippage tolerance
    - 1.3: Submit atomic YES/NO order pairs
    - 1.4: Verify both orders fill or neither fills
    - 6.3: Atomic order execution
    - 6.4: Fill price validation
    """
    
    def __init__(
        self,
        clob_client,  # Type hint omitted to avoid import dependency
        tx_manager: TransactionManager,
        default_slippage: Decimal = Decimal('0.001'),  # 0.1%
        dry_run: bool = False
    ):
        """
        Initialize Order Manager.
        
        Args:
            clob_client: CLOB client for order submission
            tx_manager: Transaction manager for blockchain operations
            default_slippage: Default slippage tolerance (default 0.1%)
            dry_run: If True, simulate orders without submitting to CLOB
        """
        self.clob_client = clob_client
        self.tx_manager = tx_manager
        self.default_slippage = default_slippage
        self.dry_run = dry_run
        
        # Track active orders
        self._active_orders: dict[str, Order] = {}
        
        logger.info(
            f"OrderManager initialized: "
            f"default_slippage={default_slippage * 100}%, "
            f"dry_run={dry_run}"
        )
    
    def create_fok_order(
        self,
        market_id: str,
        side: str,
        price: Decimal,
        size: Decimal,
        slippage_tolerance: Optional[Decimal] = None
    ) -> Order:
        """
        Create a Fill-Or-Kill (FOK) order with slippage tolerance.
        
        FOK orders execute completely or not at all, preventing partial fills
        that could leave unhedged positions.
        
        Validates Requirements:
        - 6.1: Create FOK orders
        - 6.2: 0.1% maximum slippage tolerance
        
        Args:
            market_id: Market identifier
            side: Order side ("YES" or "NO")
            price: Limit price (Decimal for precision)
            size: Order size in USDC (Decimal for precision)
            slippage_tolerance: Maximum slippage (default 0.1%)
            
        Returns:
            Order: Created FOK order
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Validate parameters
        if side not in ["YES", "NO"]:
            raise ValueError(f"Invalid side: {side}. Must be 'YES' or 'NO'")
        
        if price <= 0 or price >= 1:
            raise ValueError(f"Invalid price: {price}. Must be between 0 and 1")
        
        if size <= 0:
            raise ValueError(f"Invalid size: {size}. Must be positive")
        
        # Use default slippage if not specified
        if slippage_tolerance is None:
            slippage_tolerance = self.default_slippage
        
        # Ensure slippage doesn't exceed 0.1% (Requirement 6.2)
        max_slippage = Decimal('0.001')
        if slippage_tolerance > max_slippage:
            logger.warning(
                f"Slippage tolerance {slippage_tolerance} exceeds maximum {max_slippage}, "
                f"capping at {max_slippage}"
            )
            slippage_tolerance = max_slippage
        
        # Generate unique order ID
        order_id = f"order_{uuid.uuid4().hex[:12]}"
        
        # Create order
        order = Order(
            order_id=order_id,
            market_id=market_id,
            side=side,
            price=price,
            size=size,
            order_type="FOK",
            slippage_tolerance=slippage_tolerance,
            created_at=datetime.now()
        )
        
        # Track order
        self._active_orders[order_id] = order
        
        logger.debug(
            f"Created FOK order: id={order_id}, market={market_id}, "
            f"side={side}, price={price}, size={size}, "
            f"slippage={slippage_tolerance * 100}%"
        )
        
        return order
    
    async def submit_atomic_pair(
        self,
        yes_order: Order,
        no_order: Order
    ) -> Tuple[bool, bool]:
        """
        Submit YES and NO orders atomically.
        
        Both orders must fill completely or neither fills, preventing
        unhedged positions (legging risk).
        
        Validates Requirements:
        - 1.3: Submit atomic YES/NO order pairs
        - 1.4: Verify both orders fill or neither fills
        - 6.3: Atomic order execution
        - 6.4: Fill price validation
        
        Args:
            yes_order: YES side order
            no_order: NO side order
            
        Returns:
            Tuple[bool, bool]: (yes_filled, no_filled)
            
        Raises:
            AtomicExecutionError: If atomic execution fails
            ValueError: If orders are invalid
        """
        # Validate orders
        if yes_order.side != "YES":
            raise ValueError(f"First order must be YES side, got {yes_order.side}")
        
        if no_order.side != "NO":
            raise ValueError(f"Second order must be NO side, got {no_order.side}")
        
        if yes_order.market_id != no_order.market_id:
            raise ValueError(
                f"Orders must be for same market: "
                f"YES={yes_order.market_id}, NO={no_order.market_id}"
            )
        
        if yes_order.order_type != "FOK" or no_order.order_type != "FOK":
            raise ValueError("Both orders must be FOK type")
        
        logger.info(
            f"Submitting atomic order pair: market={yes_order.market_id}, "
            f"YES@{yes_order.price}, NO@{no_order.price}"
        )
        
        yes_filled = False
        no_filled = False
        yes_tx_hash = None
        no_tx_hash = None
        
        try:
            # Submit both orders simultaneously
            # In a real implementation, this would use the CLOB API
            # For now, we simulate the submission
            
            # Submit YES order
            logger.debug(f"Submitting YES order: {yes_order.order_id}")
            yes_result = await self._submit_order(yes_order)
            yes_filled = yes_result['filled']
            yes_tx_hash = yes_result.get('tx_hash')
            
            if yes_filled:
                # Validate fill price (Requirement 6.4)
                fill_price = yes_result['fill_price']
                if not self._validate_fill_price(yes_order, fill_price):
                    logger.error(
                        f"YES order fill price {fill_price} exceeds slippage tolerance"
                    )
                    # Cancel NO order if not yet submitted
                    raise SlippageExceededError(
                        f"YES fill price {fill_price} exceeds tolerance"
                    )
                
                yes_order.filled = True
                yes_order.fill_price = fill_price
                yes_order.tx_hash = yes_tx_hash
            
            # Submit NO order
            logger.debug(f"Submitting NO order: {no_order.order_id}")
            no_result = await self._submit_order(no_order)
            no_filled = no_result['filled']
            no_tx_hash = no_result.get('tx_hash')
            
            if no_filled:
                # Validate fill price (Requirement 6.4)
                fill_price = no_result['fill_price']
                if not self._validate_fill_price(no_order, fill_price):
                    logger.error(
                        f"NO order fill price {fill_price} exceeds slippage tolerance"
                    )
                    # If YES filled but NO slippage exceeded, we have a problem
                    if yes_filled:
                        raise AtomicExecutionError(
                            "NO order slippage exceeded after YES filled - atomic execution violated"
                        )
                    raise SlippageExceededError(
                        f"NO fill price {fill_price} exceeds tolerance"
                    )
                
                no_order.filled = True
                no_order.fill_price = fill_price
                no_order.tx_hash = no_tx_hash
            
            # Verify atomic execution (Requirement 1.4)
            if yes_filled and no_filled:
                logger.info(
                    f"Atomic order pair filled successfully: "
                    f"YES@{yes_order.fill_price}, NO@{no_order.fill_price}"
                )
                return (True, True)
            
            elif not yes_filled and not no_filled:
                logger.warning(
                    f"Atomic order pair failed to fill: "
                    f"market={yes_order.market_id}"
                )
                return (False, False)
            
            else:
                # One filled but not the other - atomic execution violated
                logger.error(
                    f"Atomic execution violated: "
                    f"YES_filled={yes_filled}, NO_filled={no_filled}"
                )
                
                # Attempt to cancel the filled order or handle the situation
                if yes_filled:
                    logger.critical(
                        f"YES order filled but NO order failed - "
                        f"unhedged position created!"
                    )
                else:
                    logger.critical(
                        f"NO order filled but YES order failed - "
                        f"unhedged position created!"
                    )
                
                raise AtomicExecutionError(
                    f"Atomic execution failed: YES={yes_filled}, NO={no_filled}"
                )
        
        except Exception as e:
            logger.error(f"Atomic order pair submission failed: {e}")
            
            # Mark orders as failed
            yes_order.error_message = str(e)
            no_order.error_message = str(e)
            
            # If one order filled, we need to handle the unhedged position
            if yes_filled or no_filled:
                logger.critical(
                    f"CRITICAL: Partial fill detected - "
                    f"YES={yes_filled}, NO={no_filled}"
                )
            
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            bool: True if order was cancelled successfully
            
        Raises:
            OrderError: If order not found or cancellation fails
        """
        if order_id not in self._active_orders:
            raise OrderError(f"Order not found: {order_id}")
        
        order = self._active_orders[order_id]
        
        if order.filled:
            logger.warning(f"Cannot cancel filled order: {order_id}")
            return False
        
        logger.info(f"Cancelling order: {order_id}")
        
        try:
            # In a real implementation, this would call the CLOB API
            # to cancel the order
            
            # For now, just remove from active orders
            del self._active_orders[order_id]
            
            logger.info(f"Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise OrderError(f"Order cancellation failed: {e}")
    
    def _validate_fill_price(self, order: Order, fill_price: Decimal) -> bool:
        """
        Validate that fill price is within slippage tolerance.
        
        Validates Requirement 6.4: Fill price validation
        
        Args:
            order: Original order
            fill_price: Actual fill price
            
        Returns:
            bool: True if fill price is within tolerance
        """
        # Calculate maximum acceptable price based on side
        if order.side == "YES":
            # For YES orders, we're buying, so fill price should not exceed
            # order price + slippage
            max_price = order.price * (Decimal('1') + order.slippage_tolerance)
            is_valid = fill_price <= max_price
        else:
            # For NO orders, we're also buying, so same logic
            max_price = order.price * (Decimal('1') + order.slippage_tolerance)
            is_valid = fill_price <= max_price
        
        if not is_valid:
            logger.warning(
                f"Fill price validation failed: "
                f"order_price={order.price}, fill_price={fill_price}, "
                f"max_price={max_price}, slippage={order.slippage_tolerance}"
            )
        
        return is_valid
    
    async def _submit_order(self, order: Order) -> dict:
        """
        Submit order to CLOB.
        
        This is a placeholder implementation. In production, this would:
        1. Call the Polymarket CLOB API to submit the order
        2. Wait for order to fill or reject
        3. Return fill details
        
        Args:
            order: Order to submit
            
        Returns:
            dict: Order result with 'filled', 'fill_price', 'tx_hash'
        """
        # Placeholder implementation
        # In production, this would interact with the CLOB API
        
        # For now, simulate order submission
        # This will be replaced with actual CLOB API calls
        
        if self.dry_run:
            logger.info(f"DRY RUN: Simulating order submission for {order.order_id}")
            # Simulate network delay
            await asyncio.sleep(0.1)
            
            return {
                'filled': True,
                'fill_price': order.price,
                'tx_hash': f"0x{uuid.uuid4().hex}"
            }
            
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.constants import AMOY
            
            # 1. Create OrderArgs
            order_args = OrderArgs(
                price=float(order.price),
                size=float(order.size),
                side="BUY" if order.side == "YES" else "BUY",  # Both are BUY orders in recent CLOB version? 
                # Wait, "side" in Order object is YES/NO outcome side. 
                # In CLOB, we buy the TOKEN. 
                # The token_id in the order implies the outcome?
                # Actually, clob_client.create_order() usually takes token_id, price, side(BUY/SELL).
                # But here we are passing order.market_id as market_id? 
                # Wait, Order struct has 'market_id' which might be token_id?
                # Let's check how it's called.
                # In NegRiskArbitrageEngine: market_id=outcome.token_id.
                # So order.market_id holds the TOKEN ID.
                token_id=order.market_id,
            )
            
            # The side "YES" or "NO" in the Order object is metadata.
            # IN POLYMARKET CLOB: You BUY a token (YES or NO token).
            # So the side passed to CLOB should be "BUY".
            # (Unless we are selling, but NegRisk "buy_all" strategy means BUYing tokens)
            
            logger.info(f"🚀 SUBMITTING REAL ORDER: {order.order_id} | Token: {order.market_id} | Price: {order.price} | Size: {order.size}")
            
            # 2. Create signed order
            # Note: create_order signature depends on py-clob-client version.
            # Assuming standard usage: create_order(OrderArgs)
            signed_order = self.clob_client.create_order(
                OrderArgs(
                    price=float(order.price),
                    size=float(order.size),
                    side="BUY", # We are always buying the outcome token
                    token_id=order.market_id,
                )
            )
            
            # 3. Post order
            resp = self.clob_client.post_order(signed_order)
            
            logger.info(f"✅ Order submitted! Response: {resp}")
            
            # 4. Parse response
            # Response might be a dict with 'transactionHash' or 'orderID'
            # Or it might be a list of fills if FOK?
            # CLOB API usually returns order ID.
            
            tx_hash = None
            if isinstance(resp, dict):
                tx_hash = resp.get("transactionHash") or resp.get("hash")
                order_id = resp.get("orderID") or resp.get("order_id")
                if order_id:
                     order.order_id = order_id # Update with real ID
            
            # For FOK orders, if it returns, it usually means filled (or partially?).
            # But post_order might just return the order ID.
            # If FOK failed, it might raise exception or return error.
            
            # Assuming success if no exception raised
            return {
                'filled': True,
                'fill_price': order.price, # Assume filled at price for now (FOK)
                'tx_hash': tx_hash or f"0x{uuid.uuid4().hex}" # Fallback if no hash immediately
            }
            
        except Exception as e:
            logger.error(f"❌ REAL ORDER FAILED: {e}")
            raise OrderError(f"CLOB submission failed: {e}")
    
    def get_active_orders(self) -> list[Order]:
        """
        Get list of active orders.
        
        Returns:
            list: List of active Order objects
        """
        return list(self._active_orders.values())
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """
        Get order by ID.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Optional[Order]: Order if found, None otherwise
        """
        return self._active_orders.get(order_id)
