"""
Unit tests for OrderManager.

Tests specific examples and edge cases for order management functionality.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from src.order_manager import (
    OrderManager, Order, OrderError, OrderNotFilledError,
    SlippageExceededError, AtomicExecutionError
)
from src.transaction_manager import TransactionManager


@pytest.fixture
def mock_clob_client():
    """Create mock CLOB client"""
    return Mock()


@pytest.fixture
def mock_tx_manager():
    """Create mock transaction manager"""
    mock = Mock(spec=TransactionManager)
    mock.get_pending_count = Mock(return_value=0)
    return mock


@pytest.fixture
def order_manager(mock_clob_client, mock_tx_manager):
    """Create OrderManager instance"""
    return OrderManager(
        clob_client=mock_clob_client,
        tx_manager=mock_tx_manager,
        default_slippage=Decimal('0.001')
    )


class TestOrderCreation:
    """Test order creation functionality"""
    
    def test_create_fok_order_success(self, order_manager):
        """Test successful FOK order creation"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        assert order.market_id == "market_123"
        assert order.side == "YES"
        assert order.price == Decimal('0.48')
        assert order.size == Decimal('1.0')
        assert order.order_type == "FOK"
        assert order.slippage_tolerance == Decimal('0.001')
        assert not order.filled
        assert order.order_id.startswith("order_")
    
    def test_create_fok_order_invalid_side(self, order_manager):
        """Test order creation with invalid side"""
        with pytest.raises(ValueError) as exc_info:
            order_manager.create_fok_order(
                market_id="market_123",
                side="INVALID",
                price=Decimal('0.48'),
                size=Decimal('1.0')
            )
        
        assert "Invalid side" in str(exc_info.value)
    
    def test_create_fok_order_invalid_price_too_low(self, order_manager):
        """Test order creation with price <= 0"""
        with pytest.raises(ValueError) as exc_info:
            order_manager.create_fok_order(
                market_id="market_123",
                side="YES",
                price=Decimal('0.0'),
                size=Decimal('1.0')
            )
        
        assert "Invalid price" in str(exc_info.value)
    
    def test_create_fok_order_invalid_price_too_high(self, order_manager):
        """Test order creation with price >= 1"""
        with pytest.raises(ValueError) as exc_info:
            order_manager.create_fok_order(
                market_id="market_123",
                side="YES",
                price=Decimal('1.0'),
                size=Decimal('1.0')
            )
        
        assert "Invalid price" in str(exc_info.value)
    
    def test_create_fok_order_invalid_size(self, order_manager):
        """Test order creation with size <= 0"""
        with pytest.raises(ValueError) as exc_info:
            order_manager.create_fok_order(
                market_id="market_123",
                side="YES",
                price=Decimal('0.48'),
                size=Decimal('0.0')
            )
        
        assert "Invalid size" in str(exc_info.value)
    
    def test_create_fok_order_custom_slippage(self, order_manager):
        """Test order creation with custom slippage tolerance"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0'),
            slippage_tolerance=Decimal('0.0005')
        )
        
        assert order.slippage_tolerance == Decimal('0.0005')
    
    def test_create_fok_order_slippage_capped(self, order_manager):
        """Test that slippage tolerance is capped at 0.1%"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0'),
            slippage_tolerance=Decimal('0.01')  # Request 1%
        )
        
        # Should be capped at 0.1%
        assert order.slippage_tolerance == Decimal('0.001')
    
    def test_order_ids_are_unique(self, order_manager):
        """Test that each order gets a unique ID"""
        order1 = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        order2 = order_manager.create_fok_order(
            market_id="market_123",
            side="NO",
            price=Decimal('0.52'),
            size=Decimal('1.0')
        )
        
        assert order1.order_id != order2.order_id


class TestAtomicOrderPair:
    """Test atomic order pair submission"""
    
    def test_submit_atomic_pair_success(self, order_manager):
        """Test successful atomic order pair submission"""
        yes_order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        no_order = order_manager.create_fok_order(
            market_id="market_123",
            side="NO",
            price=Decimal('0.47'),
            size=Decimal('1.0')
        )
        
        # Mock successful fills
        async def mock_submit(order):
            return {
                'filled': True,
                'fill_price': order.price,
                'tx_hash': f"0x{'a' * 64}"
            }
        
        with patch.object(order_manager, '_submit_order', side_effect=mock_submit):
            yes_filled, no_filled = asyncio.run(
                order_manager.submit_atomic_pair(yes_order, no_order)
            )
        
        assert yes_filled and no_filled
        assert yes_order.filled and no_order.filled
        assert yes_order.fill_price == Decimal('0.48')
        assert no_order.fill_price == Decimal('0.47')
    
    def test_submit_atomic_pair_neither_fills(self, order_manager):
        """Test atomic pair when neither order fills"""
        yes_order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        no_order = order_manager.create_fok_order(
            market_id="market_123",
            side="NO",
            price=Decimal('0.47'),
            size=Decimal('1.0')
        )
        
        # Mock no fills
        async def mock_submit(order):
            return {
                'filled': False,
                'fill_price': None,
                'tx_hash': None
            }
        
        with patch.object(order_manager, '_submit_order', side_effect=mock_submit):
            yes_filled, no_filled = asyncio.run(
                order_manager.submit_atomic_pair(yes_order, no_order)
            )
        
        assert not yes_filled and not no_filled
        assert not yes_order.filled and not no_order.filled
    
    def test_submit_atomic_pair_wrong_order(self, order_manager):
        """Test that orders must be submitted in YES, NO order"""
        yes_order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        no_order = order_manager.create_fok_order(
            market_id="market_123",
            side="NO",
            price=Decimal('0.47'),
            size=Decimal('1.0')
        )
        
        # Submit in wrong order (NO, YES)
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(order_manager.submit_atomic_pair(no_order, yes_order))
        
        assert "must be YES side" in str(exc_info.value)
    
    def test_submit_atomic_pair_different_markets(self, order_manager):
        """Test that orders must be for the same market"""
        yes_order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        no_order = order_manager.create_fok_order(
            market_id="market_456",  # Different market
            side="NO",
            price=Decimal('0.47'),
            size=Decimal('1.0')
        )
        
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(order_manager.submit_atomic_pair(yes_order, no_order))
        
        assert "same market" in str(exc_info.value)


class TestFillPriceValidation:
    """Test fill price validation"""
    
    def test_validate_fill_price_at_order_price(self, order_manager):
        """Test fill price validation at exact order price"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        # Fill at exact order price should be valid
        assert order_manager._validate_fill_price(order, Decimal('0.48'))
    
    def test_validate_fill_price_better_than_order(self, order_manager):
        """Test fill price validation when better than order price"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        # Fill at better price should be valid
        assert order_manager._validate_fill_price(order, Decimal('0.47'))
    
    def test_validate_fill_price_within_tolerance(self, order_manager):
        """Test fill price validation within slippage tolerance"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0'),
            slippage_tolerance=Decimal('0.001')
        )
        
        # Fill at 0.48048 (exactly 0.1% slippage) should be valid
        max_price = Decimal('0.48') * Decimal('1.001')
        assert order_manager._validate_fill_price(order, max_price)
    
    def test_validate_fill_price_exceeds_tolerance(self, order_manager):
        """Test fill price validation when exceeding tolerance"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0'),
            slippage_tolerance=Decimal('0.001')
        )
        
        # Fill at 0.485 (1% slippage) should be invalid
        assert not order_manager._validate_fill_price(order, Decimal('0.485'))
    
    def test_validate_fill_price_at_50_percent_odds(self, order_manager):
        """Test fill price validation at 50% odds (highest fees)"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.50'),
            size=Decimal('1.0'),
            slippage_tolerance=Decimal('0.001')
        )
        
        # At 50% odds, 0.1% slippage
        max_price = Decimal('0.50') * Decimal('1.001')
        assert order_manager._validate_fill_price(order, max_price)
        assert not order_manager._validate_fill_price(order, max_price * Decimal('1.01'))
    
    def test_validate_fill_price_at_extreme_odds(self, order_manager):
        """Test fill price validation at extreme odds (lowest fees)"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.01'),
            size=Decimal('1.0'),
            slippage_tolerance=Decimal('0.001')
        )
        
        # At 1% odds, 0.1% slippage
        max_price = Decimal('0.01') * Decimal('1.001')
        assert order_manager._validate_fill_price(order, max_price)


class TestOrderCancellation:
    """Test order cancellation"""
    
    def test_cancel_order_success(self, order_manager):
        """Test successful order cancellation"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        # Order should be in active orders
        assert order.order_id in [o.order_id for o in order_manager.get_active_orders()]
        
        # Cancel order
        result = asyncio.run(order_manager.cancel_order(order.order_id))
        
        assert result is True
        # Order should be removed from active orders
        assert order.order_id not in [o.order_id for o in order_manager.get_active_orders()]
    
    def test_cancel_order_not_found(self, order_manager):
        """Test cancelling non-existent order"""
        with pytest.raises(OrderError) as exc_info:
            asyncio.run(order_manager.cancel_order("nonexistent_order"))
        
        assert "not found" in str(exc_info.value)
    
    def test_cancel_filled_order(self, order_manager):
        """Test that filled orders cannot be cancelled"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        # Mark order as filled
        order.filled = True
        order.fill_price = Decimal('0.48')
        
        # Attempt to cancel
        result = asyncio.run(order_manager.cancel_order(order.order_id))
        
        # Should return False (cannot cancel filled order)
        assert result is False


class TestOrderTracking:
    """Test order tracking functionality"""
    
    def test_get_active_orders(self, order_manager):
        """Test retrieving active orders"""
        # Initially no orders
        assert len(order_manager.get_active_orders()) == 0
        
        # Create orders
        order1 = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        order2 = order_manager.create_fok_order(
            market_id="market_123",
            side="NO",
            price=Decimal('0.47'),
            size=Decimal('1.0')
        )
        
        # Should have 2 active orders
        active = order_manager.get_active_orders()
        assert len(active) == 2
        assert order1 in active
        assert order2 in active
    
    def test_get_order_by_id(self, order_manager):
        """Test retrieving order by ID"""
        order = order_manager.create_fok_order(
            market_id="market_123",
            side="YES",
            price=Decimal('0.48'),
            size=Decimal('1.0')
        )
        
        # Retrieve by ID
        retrieved = order_manager.get_order(order.order_id)
        
        assert retrieved is not None
        assert retrieved.order_id == order.order_id
        assert retrieved.market_id == order.market_id
    
    def test_get_order_not_found(self, order_manager):
        """Test retrieving non-existent order"""
        result = order_manager.get_order("nonexistent_order")
        assert result is None
