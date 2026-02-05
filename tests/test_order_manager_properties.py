"""
Property-based tests for OrderManager.

Tests universal properties that should hold across all inputs.
Uses Hypothesis for property-based testing with minimum 100 iterations.
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from src.order_manager import OrderManager, Order, AtomicExecutionError, SlippageExceededError
from src.transaction_manager import TransactionManager


# Test strategies
@st.composite
def decimal_price(draw):
    """Generate valid price between 0.01 and 0.99"""
    return Decimal(str(draw(st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False))))


@st.composite
def decimal_size(draw):
    """Generate valid order size between 0.1 and 10.0"""
    return Decimal(str(draw(st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False))))


@st.composite
def order_pair(draw):
    """Generate a pair of YES/NO orders for the same market"""
    market_id = f"market_{draw(st.text(min_size=8, max_size=12, alphabet='0123456789abcdef'))}"
    yes_price = draw(decimal_price())
    no_price = draw(decimal_price())
    size = draw(decimal_size())
    
    return {
        'market_id': market_id,
        'yes_price': yes_price,
        'no_price': no_price,
        'size': size
    }


def create_order_manager():
    """Helper function to create OrderManager instance"""
    mock_clob_client = Mock()
    mock_tx_manager = Mock(spec=TransactionManager)
    mock_tx_manager.get_pending_count = Mock(return_value=0)
    
    return OrderManager(
        clob_client=mock_clob_client,
        tx_manager=mock_tx_manager,
        default_slippage=Decimal('0.001')
    )


class TestAtomicOrderExecution:
    """
    Property 5: Atomic Order Execution
    
    For any arbitrage opportunity, when FOK orders are submitted for both YES and NO positions,
    either both orders fill completely or neither fills, preventing unhedged positions.
    
    Validates: Requirements 1.4, 6.3, 6.1
    """
    
    @given(order_data=order_pair())
    @settings(max_examples=100, deadline=None)
    def test_atomic_execution_both_fill_or_neither(self, order_data):
        """
        Property 5: Atomic Order Execution
        
        For any order pair, when submitted atomically, either both orders fill
        or neither fills. There should never be a case where only one fills.
        """
        # Create order manager
        order_manager = create_order_manager()
        
        # Create YES and NO orders
        yes_order = order_manager.create_fok_order(
            market_id=order_data['market_id'],
            side="YES",
            price=order_data['yes_price'],
            size=order_data['size']
        )
        
        no_order = order_manager.create_fok_order(
            market_id=order_data['market_id'],
            side="NO",
            price=order_data['no_price'],
            size=order_data['size']
        )
        
        # Mock the _submit_order method to simulate various scenarios
        async def mock_submit_both_fill(order):
            """Simulate both orders filling"""
            return {
                'filled': True,
                'fill_price': order.price,
                'tx_hash': f"0x{'a' * 64}"
            }
        
        async def mock_submit_neither_fill(order):
            """Simulate neither order filling"""
            return {
                'filled': False,
                'fill_price': None,
                'tx_hash': None
            }
        
        # Test case 1: Both orders fill
        with patch.object(order_manager, '_submit_order', side_effect=mock_submit_both_fill):
            yes_filled, no_filled = asyncio.run(
                order_manager.submit_atomic_pair(yes_order, no_order)
            )
            
            # Property: Both should fill
            assert yes_filled and no_filled, \
                "When both orders can fill, both should fill"
            assert yes_order.filled and no_order.filled, \
                "Order objects should be marked as filled"
        
        # Reset orders for next test
        yes_order = order_manager.create_fok_order(
            market_id=order_data['market_id'],
            side="YES",
            price=order_data['yes_price'],
            size=order_data['size']
        )
        
        no_order = order_manager.create_fok_order(
            market_id=order_data['market_id'],
            side="NO",
            price=order_data['no_price'],
            size=order_data['size']
        )
        
        # Test case 2: Neither order fills
        with patch.object(order_manager, '_submit_order', side_effect=mock_submit_neither_fill):
            yes_filled, no_filled = asyncio.run(
                order_manager.submit_atomic_pair(yes_order, no_order)
            )
            
            # Property: Neither should fill
            assert not yes_filled and not no_filled, \
                "When orders cannot fill, neither should fill"
            assert not yes_order.filled and not no_order.filled, \
                "Order objects should not be marked as filled"
    
    @given(order_data=order_pair())
    @settings(max_examples=100, deadline=None)
    def test_atomic_execution_prevents_partial_fills(self, order_data):
        """
        Property 5: Atomic Order Execution - Partial Fill Prevention
        
        For any order pair, if one order fills but the other cannot,
        the system should raise an AtomicExecutionError and not leave
        an unhedged position.
        """
        # Create order manager
        order_manager = create_order_manager()
        
        # Create YES and NO orders
        yes_order = order_manager.create_fok_order(
            market_id=order_data['market_id'],
            side="YES",
            price=order_data['yes_price'],
            size=order_data['size']
        )
        
        no_order = order_manager.create_fok_order(
            market_id=order_data['market_id'],
            side="NO",
            price=order_data['no_price'],
            size=order_data['size']
        )
        
        # Mock scenario where YES fills but NO doesn't
        call_count = [0]
        
        async def mock_submit_partial(order):
            """Simulate YES filling but NO not filling"""
            call_count[0] += 1
            if call_count[0] == 1:  # First call (YES order)
                return {
                    'filled': True,
                    'fill_price': order.price,
                    'tx_hash': f"0x{'a' * 64}"
                }
            else:  # Second call (NO order)
                return {
                    'filled': False,
                    'fill_price': None,
                    'tx_hash': None
                }
        
        # Test that partial fill raises error
        with patch.object(order_manager, '_submit_order', side_effect=mock_submit_partial):
            with pytest.raises(AtomicExecutionError) as exc_info:
                asyncio.run(order_manager.submit_atomic_pair(yes_order, no_order))
            
            # Property: Should raise AtomicExecutionError
            assert "Atomic execution failed" in str(exc_info.value), \
                "Partial fill should raise AtomicExecutionError"
    
    @given(order_data=order_pair())
    @settings(max_examples=100, deadline=None)
    def test_fok_order_creation_enforces_constraints(self, order_data):
        """
        Property 5: FOK Order Creation
        
        For any valid order parameters, creating a FOK order should:
        1. Set order_type to "FOK"
        2. Enforce slippage tolerance <= 0.1%
        3. Generate unique order IDs
        """
        # Create order manager
        order_manager = create_order_manager()
        
        # Create order
        order = order_manager.create_fok_order(
            market_id=order_data['market_id'],
            side="YES",
            price=order_data['yes_price'],
            size=order_data['size']
        )
        
        # Property 1: Order type must be FOK
        assert order.order_type == "FOK", \
            "All orders should be FOK type"
        
        # Property 2: Slippage tolerance should not exceed 0.1%
        assert order.slippage_tolerance <= Decimal('0.001'), \
            f"Slippage tolerance {order.slippage_tolerance} exceeds 0.1%"
        
        # Property 3: Order ID should be unique
        order2 = order_manager.create_fok_order(
            market_id=order_data['market_id'],
            side="NO",
            price=order_data['no_price'],
            size=order_data['size']
        )
        
        assert order.order_id != order2.order_id, \
            "Order IDs should be unique"
    
    @given(
        yes_price=decimal_price(),
        no_price=decimal_price(),
        size=decimal_size()
    )
    @settings(max_examples=100, deadline=None)
    def test_atomic_pair_validates_order_sides(self, yes_price, no_price, size):
        """
        Property 5: Order Validation
        
        For any order pair, submit_atomic_pair should validate that:
        1. First order is YES side
        2. Second order is NO side
        3. Both orders are for the same market
        4. Both orders are FOK type
        """
        # Create order manager
        order_manager = create_order_manager()
        
        market_id = "test_market_123"
        
        # Create valid YES and NO orders
        yes_order = order_manager.create_fok_order(
            market_id=market_id,
            side="YES",
            price=yes_price,
            size=size
        )
        
        no_order = order_manager.create_fok_order(
            market_id=market_id,
            side="NO",
            price=no_price,
            size=size
        )
        
        # Test 1: Swapping order sides should raise error
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(order_manager.submit_atomic_pair(no_order, yes_order))
        
        assert "must be YES side" in str(exc_info.value), \
            "Should validate first order is YES"
        
        # Test 2: Different markets should raise error
        no_order_different_market = order_manager.create_fok_order(
            market_id="different_market_456",
            side="NO",
            price=no_price,
            size=size
        )
        
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(order_manager.submit_atomic_pair(yes_order, no_order_different_market))
        
        assert "same market" in str(exc_info.value), \
            "Should validate orders are for same market"



class TestFOKSlippageTolerance:
    """
    Property 17: FOK Order Slippage Tolerance
    
    For any FOK order submitted, the maximum slippage tolerance should be set to 0.1%,
    ensuring fills occur at expected prices.
    
    Validates: Requirements 6.2
    """
    
    @given(
        price=decimal_price(),
        size=decimal_size(),
        slippage=st.decimals(min_value='0.0001', max_value='0.01', places=4)
    )
    @settings(max_examples=100, deadline=None)
    def test_slippage_tolerance_capped_at_0_1_percent(self, price, size, slippage):
        """
        Property 17: Slippage Tolerance Cap
        
        For any requested slippage tolerance, the system should cap it at 0.1% (0.001).
        Even if a higher slippage is requested, the order should use maximum 0.1%.
        """
        # Create order manager
        order_manager = create_order_manager()
        
        # Create order with specified slippage
        order = order_manager.create_fok_order(
            market_id="test_market",
            side="YES",
            price=price,
            size=size,
            slippage_tolerance=slippage
        )
        
        # Property: Slippage should never exceed 0.1%
        max_slippage = Decimal('0.001')
        assert order.slippage_tolerance <= max_slippage, \
            f"Slippage {order.slippage_tolerance} exceeds maximum {max_slippage}"
        
        # If requested slippage was <= 0.1%, it should be preserved
        if slippage <= max_slippage:
            assert order.slippage_tolerance == slippage, \
                f"Slippage should be preserved when <= 0.1%"
        else:
            # If requested slippage was > 0.1%, it should be capped
            assert order.slippage_tolerance == max_slippage, \
                f"Slippage should be capped at 0.1% when requested > 0.1%"
    
    @given(
        price=decimal_price(),
        size=decimal_size()
    )
    @settings(max_examples=100, deadline=None)
    def test_default_slippage_is_0_1_percent(self, price, size):
        """
        Property 17: Default Slippage
        
        For any order created without specifying slippage tolerance,
        the default should be 0.1% (0.001).
        """
        # Create order manager
        order_manager = create_order_manager()
        
        # Create order without specifying slippage
        order = order_manager.create_fok_order(
            market_id="test_market",
            side="YES",
            price=price,
            size=size
            # No slippage_tolerance parameter
        )
        
        # Property: Default slippage should be 0.1%
        expected_default = Decimal('0.001')
        assert order.slippage_tolerance == expected_default, \
            f"Default slippage should be {expected_default}, got {order.slippage_tolerance}"
    
    @given(
        order_price=decimal_price(),
        size=decimal_size(),
        slippage=st.decimals(min_value='0.0001', max_value='0.001', places=4)
    )
    @settings(max_examples=100, deadline=None)
    def test_fill_price_validation_within_tolerance(self, order_price, size, slippage):
        """
        Property 17: Fill Price Validation
        
        For any order with slippage tolerance, a fill price within tolerance
        should be accepted, and a fill price exceeding tolerance should be rejected.
        """
        # Create order manager
        order_manager = create_order_manager()
        
        # Create order
        order = order_manager.create_fok_order(
            market_id="test_market",
            side="YES",
            price=order_price,
            size=size,
            slippage_tolerance=slippage
        )
        
        # Calculate maximum acceptable fill price
        max_fill_price = order_price * (Decimal('1') + slippage)
        
        # Test 1: Fill price exactly at order price should be valid
        assert order_manager._validate_fill_price(order, order_price), \
            "Fill price equal to order price should be valid"
        
        # Test 2: Fill price within tolerance should be valid
        fill_price_within = order_price * (Decimal('1') + slippage / Decimal('2'))
        assert order_manager._validate_fill_price(order, fill_price_within), \
            f"Fill price {fill_price_within} within tolerance should be valid"
        
        # Test 3: Fill price at maximum tolerance should be valid
        assert order_manager._validate_fill_price(order, max_fill_price), \
            f"Fill price {max_fill_price} at maximum tolerance should be valid"
        
        # Test 4: Fill price exceeding tolerance should be invalid
        fill_price_exceeds = order_price * (Decimal('1') + slippage * Decimal('1.1'))
        assert not order_manager._validate_fill_price(order, fill_price_exceeds), \
            f"Fill price {fill_price_exceeds} exceeding tolerance should be invalid"
    
    @given(
        yes_price=decimal_price(),
        no_price=decimal_price(),
        size=decimal_size()
    )
    @settings(max_examples=100, deadline=None)
    def test_slippage_validation_in_atomic_pair(self, yes_price, no_price, size):
        """
        Property 17: Slippage Validation in Atomic Execution
        
        For any atomic order pair, if either order's fill price exceeds
        slippage tolerance, the system should reject the trade.
        """
        # Create order manager
        order_manager = create_order_manager()
        
        # Create orders with tight slippage
        slippage = Decimal('0.001')
        
        yes_order = order_manager.create_fok_order(
            market_id="test_market",
            side="YES",
            price=yes_price,
            size=size,
            slippage_tolerance=slippage
        )
        
        no_order = order_manager.create_fok_order(
            market_id="test_market",
            side="NO",
            price=no_price,
            size=size,
            slippage_tolerance=slippage
        )
        
        # Mock scenario where YES fills with excessive slippage
        async def mock_submit_excessive_slippage(order):
            """Simulate fill with price exceeding slippage tolerance"""
            if order.side == "YES":
                # Fill at price exceeding tolerance
                fill_price = order.price * Decimal('1.002')  # 0.2% slippage
                return {
                    'filled': True,
                    'fill_price': fill_price,
                    'tx_hash': f"0x{'a' * 64}"
                }
            else:
                # NO order fills normally
                return {
                    'filled': True,
                    'fill_price': order.price,
                    'tx_hash': f"0x{'b' * 64}"
                }
        
        # Test that excessive slippage raises error
        with patch.object(order_manager, '_submit_order', side_effect=mock_submit_excessive_slippage):
            with pytest.raises(SlippageExceededError) as exc_info:
                asyncio.run(order_manager.submit_atomic_pair(yes_order, no_order))
            
            # Property: Should raise SlippageExceededError
            assert "exceeds tolerance" in str(exc_info.value), \
                "Excessive slippage should raise SlippageExceededError"



class TestFillPriceValidation:
    """
    Property 18: Fill Price Validation
    
    For any pair of filled orders, the actual fill prices should match the expected prices
    within the configured tolerance, validating execution quality.
    
    Validates: Requirements 6.4
    """
    
    @given(
        yes_price=decimal_price(),
        no_price=decimal_price(),
        size=decimal_size(),
        yes_slippage_pct=st.floats(min_value=-0.05, max_value=0.15, allow_nan=False, allow_infinity=False),
        no_slippage_pct=st.floats(min_value=-0.05, max_value=0.15, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_fill_prices_validated_against_tolerance(
        self, yes_price, no_price, size, yes_slippage_pct, no_slippage_pct
    ):
        """
        Property 18: Fill Price Validation
        
        For any order pair, the system should validate that actual fill prices
        are within the configured slippage tolerance. Orders with fill prices
        exceeding tolerance should be rejected.
        """
        # Create order manager
        order_manager = create_order_manager()
        
        # Create orders with 0.1% slippage tolerance
        tolerance = Decimal('0.001')
        
        yes_order = order_manager.create_fok_order(
            market_id="test_market",
            side="YES",
            price=yes_price,
            size=size,
            slippage_tolerance=tolerance
        )
        
        no_order = order_manager.create_fok_order(
            market_id="test_market",
            side="NO",
            price=no_price,
            size=size,
            slippage_tolerance=tolerance
        )
        
        # Calculate fill prices based on slippage percentages
        yes_fill_price = yes_price * Decimal(str(1 + yes_slippage_pct))
        no_fill_price = no_price * Decimal(str(1 + no_slippage_pct))
        
        # Ensure fill prices are within valid range [0.01, 0.99]
        yes_fill_price = max(Decimal('0.01'), min(Decimal('0.99'), yes_fill_price))
        no_fill_price = max(Decimal('0.01'), min(Decimal('0.99'), no_fill_price))
        
        # Determine if fill prices are within tolerance
        yes_within_tolerance = yes_fill_price <= yes_price * (Decimal('1') + tolerance)
        no_within_tolerance = no_fill_price <= no_price * (Decimal('1') + tolerance)
        
        # Mock order submission with calculated fill prices
        async def mock_submit_with_fill_prices(order):
            if order.side == "YES":
                return {
                    'filled': True,
                    'fill_price': yes_fill_price,
                    'tx_hash': f"0x{'a' * 64}"
                }
            else:
                return {
                    'filled': True,
                    'fill_price': no_fill_price,
                    'tx_hash': f"0x{'b' * 64}"
                }
        
        with patch.object(order_manager, '_submit_order', side_effect=mock_submit_with_fill_prices):
            if yes_within_tolerance and no_within_tolerance:
                # Property: Both within tolerance - should succeed
                yes_filled, no_filled = asyncio.run(
                    order_manager.submit_atomic_pair(yes_order, no_order)
                )
                assert yes_filled and no_filled, \
                    "Orders with fill prices within tolerance should succeed"
                assert yes_order.fill_price == yes_fill_price, \
                    "YES order should record actual fill price"
                assert no_order.fill_price == no_fill_price, \
                    "NO order should record actual fill price"
            else:
                # Property: At least one exceeds tolerance - should fail
                with pytest.raises((SlippageExceededError, AtomicExecutionError)):
                    asyncio.run(order_manager.submit_atomic_pair(yes_order, no_order))
    
    @given(
        order_price=decimal_price(),
        size=decimal_size()
    )
    @settings(max_examples=100, deadline=None)
    def test_fill_price_validation_logic(self, order_price, size):
        """
        Property 18: Fill Price Validation Logic
        
        For any order, the _validate_fill_price method should correctly
        determine if a fill price is within tolerance.
        """
        # Create order manager
        order_manager = create_order_manager()
        
        # Create order with 0.1% tolerance
        tolerance = Decimal('0.001')
        order = order_manager.create_fok_order(
            market_id="test_market",
            side="YES",
            price=order_price,
            size=size,
            slippage_tolerance=tolerance
        )
        
        # Calculate boundary prices
        max_acceptable = order_price * (Decimal('1') + tolerance)
        
        # Test various fill prices
        test_cases = [
            (order_price, True, "exact price"),
            (order_price * Decimal('0.99'), True, "better price"),
            (order_price * (Decimal('1') + tolerance / Decimal('2')), True, "within tolerance"),
            (max_acceptable, True, "at maximum tolerance"),
            (max_acceptable * Decimal('1.001'), False, "exceeds tolerance"),
            (order_price * Decimal('1.002'), False, "exceeds tolerance by 0.1%"),
        ]
        
        for fill_price, expected_valid, description in test_cases:
            # Ensure fill price is in valid range
            fill_price = max(Decimal('0.01'), min(Decimal('0.99'), fill_price))
            
            is_valid = order_manager._validate_fill_price(order, fill_price)
            
            # Property: Validation should match expected result
            if expected_valid:
                assert is_valid, \
                    f"Fill price {fill_price} ({description}) should be valid for order price {order_price}"
            else:
                # Only assert invalid if fill price actually exceeds tolerance
                if fill_price > max_acceptable:
                    assert not is_valid, \
                        f"Fill price {fill_price} ({description}) should be invalid for order price {order_price}"
    
    @given(
        yes_price=decimal_price(),
        no_price=decimal_price(),
        size=decimal_size()
    )
    @settings(max_examples=100, deadline=None)
    def test_both_fill_prices_recorded_on_success(self, yes_price, no_price, size):
        """
        Property 18: Fill Price Recording
        
        For any successful atomic order pair, both orders should record
        their actual fill prices for audit and analysis.
        """
        # Create order manager
        order_manager = create_order_manager()
        
        yes_order = order_manager.create_fok_order(
            market_id="test_market",
            side="YES",
            price=yes_price,
            size=size
        )
        
        no_order = order_manager.create_fok_order(
            market_id="test_market",
            side="NO",
            price=no_price,
            size=size
        )
        
        # Mock successful fills at exact prices
        async def mock_submit_success(order):
            return {
                'filled': True,
                'fill_price': order.price,
                'tx_hash': f"0x{'a' * 64}"
            }
        
        with patch.object(order_manager, '_submit_order', side_effect=mock_submit_success):
            yes_filled, no_filled = asyncio.run(
                order_manager.submit_atomic_pair(yes_order, no_order)
            )
            
            # Property: Both orders should be marked as filled
            assert yes_filled and no_filled, "Both orders should fill"
            assert yes_order.filled and no_order.filled, "Order objects should be marked filled"
            
            # Property: Fill prices should be recorded
            assert yes_order.fill_price is not None, "YES fill price should be recorded"
            assert no_order.fill_price is not None, "NO fill price should be recorded"
            assert yes_order.fill_price == yes_price, "YES fill price should match"
            assert no_order.fill_price == no_price, "NO fill price should match"
            
            # Property: Transaction hashes should be recorded
            assert yes_order.tx_hash is not None, "YES tx hash should be recorded"
            assert no_order.tx_hash is not None, "NO tx hash should be recorded"
    
    @given(
        price=decimal_price(),
        size=decimal_size()
    )
    @settings(max_examples=100, deadline=None)
    def test_fill_price_validation_for_both_sides(self, price, size):
        """
        Property 18: Side-Agnostic Validation
        
        For any order, fill price validation should work correctly for both
        YES and NO sides, as both are buy orders in the arbitrage strategy.
        """
        # Create order manager
        order_manager = create_order_manager()
        
        tolerance = Decimal('0.001')
        
        # Create YES order
        yes_order = order_manager.create_fok_order(
            market_id="test_market",
            side="YES",
            price=price,
            size=size,
            slippage_tolerance=tolerance
        )
        
        # Create NO order
        no_order = order_manager.create_fok_order(
            market_id="test_market",
            side="NO",
            price=price,
            size=size,
            slippage_tolerance=tolerance
        )
        
        # Test fill prices for both sides
        max_acceptable = price * (Decimal('1') + tolerance)
        
        # Property: Valid fill price should be accepted for both sides
        assert order_manager._validate_fill_price(yes_order, price), \
            "YES order should accept fill at order price"
        assert order_manager._validate_fill_price(no_order, price), \
            "NO order should accept fill at order price"
        
        # Property: Fill price at max tolerance should be accepted for both sides
        assert order_manager._validate_fill_price(yes_order, max_acceptable), \
            "YES order should accept fill at max tolerance"
        assert order_manager._validate_fill_price(no_order, max_acceptable), \
            "NO order should accept fill at max tolerance"
        
        # Property: Fill price exceeding tolerance should be rejected for both sides
        exceeds = max_acceptable * Decimal('1.01')
        exceeds = min(exceeds, Decimal('0.99'))  # Keep in valid range
        
        if exceeds > max_acceptable:
            assert not order_manager._validate_fill_price(yes_order, exceeds), \
                "YES order should reject fill exceeding tolerance"
            assert not order_manager._validate_fill_price(no_order, exceeds), \
                "NO order should reject fill exceeding tolerance"
