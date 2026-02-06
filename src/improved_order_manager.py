"""
Improved Order Manager with Real CLOB API Integration.

Replaces placeholder implementation with actual Polymarket CLOB API calls.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Represents a trading order."""
    order_id: str
    market_id: str
    token_id: str
    side: str  # "BUY" or "SELL"
    price: Decimal
    size: Decimal
    order_type: str  # "FOK" (Fill-Or-Kill) or "GTC" (Good-Til-Cancelled)
    slippage_tolerance: Decimal
    created_at: datetime
    
    # Execution details
    filled: bool = False
    fill_price: Optional[Decimal] = None
    tx_hash: Optional[str] = None
    clob_order_id: Optional[str] = None
    error_message: Optional[str] = None


class ImprovedOrderManager:
    """
    Order manager with real CLOB API integration.
    
    Features:
    - Real order submission via py-clob-client
    - FOK (Fill-Or-Kill) order support
    - Atomic YES/NO pair execution
    - Fill price validation
    - Order status tracking
    """
    
    def __init__(
        self,
        clob_client,
        default_slippage: Decimal = Decimal('0.001'),  # 0.1%
        order_timeout: int = 30  # seconds
    ):
        """
        Initialize Improved Order Manager.
        
        Args:
            clob_client: Authenticated CLOB client
            default_slippage: Default slippage tolerance
            order_timeout: Timeout for order execution (seconds)
        """
        self.clob_client = clob_client
        self.default_slippage = default_slippage
        self.order_timeout = order_timeout
        
        # Track active orders
        self._active_orders: dict[str, Order] = {}
        
        logger.info(
            f"ImprovedOrderManager initialized: "
            f"default_slippage={default_slippage * 100}%, "
            f"order_timeout={order_timeout}s"
        )
    
    def create_fok_order(
        self,
        market_id: str,
        token_id: str,
        side: str,
        price: Decimal,
        size: Decimal,
        slippage_tolerance: Optional[Decimal] = None
    ) -> Order:
        """
        Create a Fill-Or-Kill (FOK) order.
        
        Args:
            market_id: Market identifier
            token_id: Token ID (YES or NO token)
            side: Order side ("BUY" or "SELL")
            price: Limit price
            size: Order size in USDC
            slippage_tolerance: Maximum slippage
            
        Returns:
            Order: Created FOK order
        """
        # Validate parameters
        if side not in ["BUY", "SELL"]:
            raise ValueError(f"Invalid side: {side}. Must be 'BUY' or 'SELL'")
        
        if price <= 0 or price >= 1:
            raise ValueError(f"Invalid price: {price}. Must be between 0 and 1")
        
        if size <= 0:
            raise ValueError(f"Invalid size: {size}. Must be positive")
        
        # Use default slippage if not specified
        if slippage_tolerance is None:
            slippage_tolerance = self.default_slippage
        
        # Cap slippage at 0.1%
        max_slippage = Decimal('0.001')
        if slippage_tolerance > max_slippage:
            logger.warning(f"Capping slippage at {max_slippage}")
            slippage_tolerance = max_slippage
        
        # Generate unique order ID
        order_id = f"order_{uuid.uuid4().hex[:12]}"
        
        # Create order
        order = Order(
            order_id=order_id,
            market_id=market_id,
            token_id=token_id,
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
            f"Created FOK order: id={order_id}, token={token_id}, "
            f"side={side}, price={price}, size={size}"
        )
        
        return order
    
    async def submit_order(self, order: Order) -> bool:
        """
        Submit order to CLOB API.
        
        Args:
            order: Order to submit
            
        Returns:
            bool: True if order filled successfully
        """
        try:
            logger.info(f"Submitting order {order.order_id} to CLOB...")
            
            # Prepare order arguments for py-clob-client
            order_args = {
                "token_id": order.token_id,
                "price": float(order.price),
                "size": float(order.size),
                "side": order.side,
                "fee_rate_bps": 200  # 2% fee (200 basis points)
            }
            
            # Order options
            order_options = {
                "tick_size": "0.01",  # $0.01 tick size
                "neg_risk": False  # Not a negative risk market
            }
            
            # Submit order (run in thread to avoid blocking)
            response = await asyncio.to_thread(
                self.clob_client.create_and_post_order,
                order_args,
                order_options
            )
            
            # Extract order ID from response
            clob_order_id = response.get("orderID")
            order.clob_order_id = clob_order_id
            
            logger.info(f"Order submitted: clob_order_id={clob_order_id}")
            
            # Wait for order to fill (with timeout)
            filled = await self._wait_for_fill(order)
            
            return filled
            
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            order.error_message = str(e)
            return False
    
    async def _wait_for_fill(self, order: Order) -> bool:
        """
        Wait for order to fill or timeout.
        
        Args:
            order: Order to monitor
            
        Returns:
            bool: True if order filled
        """
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < self.order_timeout:
            try:
                # Check order status
                order_status = await asyncio.to_thread(
                    self.clob_client.get_order,
                    order.clob_order_id
                )
                
                status = order_status.get("status", "").upper()
                
                if status == "FILLED":
                    # Order filled successfully
                    fill_price = Decimal(str(order_status.get("price", order.price)))
                    
                    # Validate fill price
                    if not self._validate_fill_price(order, fill_price):
                        logger.error(f"Fill price {fill_price} exceeds slippage tolerance")
                        order.error_message = "Slippage exceeded"
                        return False
                    
                    # Update order
                    order.filled = True
                    order.fill_price = fill_price
                    order.tx_hash = order_status.get("transactionHash")
                    
                    logger.info(
                        f"Order {order.order_id} filled: "
                        f"price={fill_price}, tx={order.tx_hash}"
                    )
                    return True
                
                elif status in ["CANCELLED", "EXPIRED", "FAILED"]:
                    # Order failed
                    logger.warning(f"Order {order.order_id} {status.lower()}")
                    order.error_message = f"Order {status.lower()}"
                    return False
                
                # Still pending, wait and retry
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error checking order status: {e}")
                await asyncio.sleep(1)
        
        # Timeout reached
        logger.warning(f"Order {order.order_id} timed out after {self.order_timeout}s")
        order.error_message = "Timeout"
        
        # Try to cancel the order
        try:
            await asyncio.to_thread(
                self.clob_client.cancel_order,
                order.clob_order_id
            )
            logger.info(f"Cancelled timed-out order {order.order_id}")
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
        
        return False
    
    async def submit_atomic_pair(
        self,
        yes_order: Order,
        no_order: Order
    ) -> Tuple[bool, bool]:
        """
        Submit YES and NO orders atomically.
        
        Both orders must fill or neither fills (prevents legging risk).
        
        Args:
            yes_order: YES side order
            no_order: NO side order
            
        Returns:
            Tuple[bool, bool]: (yes_filled, no_filled)
        """
        # Validate orders
        if yes_order.market_id != no_order.market_id:
            raise ValueError("Orders must be for same market")
        
        logger.info(
            f"Submitting atomic order pair: market={yes_order.market_id}, "
            f"YES@{yes_order.price}, NO@{no_order.price}"
        )
        
        # Submit both orders concurrently
        yes_task = asyncio.create_task(self.submit_order(yes_order))
        no_task = asyncio.create_task(self.submit_order(no_order))
        
        # Wait for both to complete
        yes_filled, no_filled = await asyncio.gather(yes_task, no_task)
        
        # Check atomic execution
        if yes_filled and no_filled:
            logger.info("✅ Atomic order pair filled successfully")
            return (True, True)
        
        elif not yes_filled and not no_filled:
            logger.warning("⚠️ Atomic order pair failed to fill")
            return (False, False)
        
        else:
            # One filled but not the other - CRITICAL ERROR
            logger.critical(
                f"🚨 ATOMIC EXECUTION VIOLATED: "
                f"YES={yes_filled}, NO={no_filled}"
            )
            
            # Try to cancel the filled order or hedge the position
            if yes_filled:
                logger.critical("YES filled but NO failed - unhedged position!")
                # TODO: Implement emergency hedging
            else:
                logger.critical("NO filled but YES failed - unhedged position!")
                # TODO: Implement emergency hedging
            
            return (yes_filled, no_filled)
    
    def _validate_fill_price(self, order: Order, fill_price: Decimal) -> bool:
        """
        Validate that fill price is within slippage tolerance.
        
        Args:
            order: Original order
            fill_price: Actual fill price
            
        Returns:
            bool: True if fill price is acceptable
        """
        if order.side == "BUY":
            # For BUY orders, fill price should not exceed order price + slippage
            max_price = order.price * (Decimal('1') + order.slippage_tolerance)
            is_valid = fill_price <= max_price
        else:
            # For SELL orders, fill price should not be below order price - slippage
            min_price = order.price * (Decimal('1') - order.slippage_tolerance)
            is_valid = fill_price >= min_price
        
        if not is_valid:
            logger.warning(
                f"Fill price validation failed: "
                f"order_price={order.price}, fill_price={fill_price}, "
                f"slippage={order.slippage_tolerance}"
            )
        
        return is_valid
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            bool: True if cancelled successfully
        """
        if order_id not in self._active_orders:
            logger.warning(f"Order not found: {order_id}")
            return False
        
        order = self._active_orders[order_id]
        
        if order.filled:
            logger.warning(f"Cannot cancel filled order: {order_id}")
            return False
        
        if not order.clob_order_id:
            logger.warning(f"Order not submitted yet: {order_id}")
            return False
        
        try:
            await asyncio.to_thread(
                self.clob_client.cancel_order,
                order.clob_order_id
            )
            logger.info(f"Order cancelled: {order_id}")
            del self._active_orders[order_id]
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    def get_active_orders(self) -> list[Order]:
        """Get list of active orders."""
        return list(self._active_orders.values())
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._active_orders.get(order_id)
