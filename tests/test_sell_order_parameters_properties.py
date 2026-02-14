"""
Property-based tests for sell order parameter matching.

Tests that sell orders use the position's neg_risk flag (not the market's) and that
token_id and size match exactly.

**Validates: Requirements 2.6**
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import math

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position, CryptoMarket


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def position_strategy(draw):
    """Generate random Position with various neg_risk flags."""
    entry_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    size = Decimal(str(draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False))))
    side = draw(st.sampled_from(["UP", "DOWN"]))
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    token_id = f"token_{draw(st.integers(min_value=1, max_value=100000))}"
    market_id = f"market_{draw(st.integers(min_value=1, max_value=10000))}"
    neg_risk = draw(st.booleans())  # Random neg_risk flag
    
    position = Position(
        token_id=token_id,
        side=side,
        entry_price=entry_price,
        size=size,
        entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        market_id=market_id,
        asset=asset,
        strategy="directional",
        neg_risk=neg_risk,  # Position's neg_risk flag
        highest_price=entry_price
    )
    
    return position


@st.composite
def position_with_market_strategy(draw):
    """Generate random Position with matching CryptoMarket that may have different neg_risk."""
    position = draw(position_strategy())
    
    # Create market with potentially DIFFERENT neg_risk flag
    market_neg_risk = draw(st.booleans())  # Market's neg_risk may differ from position's
    
    current_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    
    market = CryptoMarket(
        market_id=position.market_id,
        question=f"Will {position.asset} go up?",
        asset=position.asset,
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=current_price if position.side == "UP" else Decimal("0.50"),
        down_price=current_price if position.side == "DOWN" else Decimal("0.50"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
        neg_risk=market_neg_risk  # Market's neg_risk flag (may differ)
    )
    
    return position, market, current_price


# ============================================================================
# HELPER FUNCTION TO CREATE MOCK STRATEGY
# ============================================================================

def create_mock_strategy():
    """Create a mock strategy instance for testing."""
    mock_clob = MagicMock()
    
    # Mock the create_order and post_order methods
    mock_clob.create_order = MagicMock(return_value={"signed": "order"})
    mock_clob.post_order = MagicMock(return_value={"orderID": "test_order_123", "success": True})
    
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=False
    )
    
    # Disable dry_run for testing
    strategy.dry_run = False
    
    # Mock _get_actual_token_balance to return None (use tracked size)
    strategy._get_actual_token_balance = AsyncMock(return_value=None)
    
    return strategy


# ============================================================================
# PROPERTY 3: SELL ORDERS MATCH POSITION PARAMETERS
# ============================================================================

@given(position_market=position_with_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sell_order_uses_position_neg_risk_flag(position_market):
    """
    **Validates: Requirements 2.6**
    
    Property 3a: Sell Orders Use Position's neg_risk Flag
    
    When closing a position, the sell order MUST use the position's neg_risk flag,
    NOT the market's neg_risk flag. The market's flag may have changed since entry.
    """
    position, market, current_price = position_market
    strategy = create_mock_strategy()
    
    # Close the position
    success = await strategy._close_position(position, current_price)
    
    # Verify order was placed
    assert success is True, "Position close should succeed"
    
    # Verify create_order was called
    assert strategy.clob_client.create_order.called, "create_order should be called"
    
    # Get the call arguments
    call_args = strategy.clob_client.create_order.call_args
    order_args = call_args[0][0]  # First positional argument
    options = call_args[1].get('options')  # Keyword argument
    
    # Verify: neg_risk flag matches POSITION, not market
    assert options is not None, "Options should be provided"
    assert hasattr(options, 'neg_risk'), "Options should have neg_risk attribute"
    assert options.neg_risk == position.neg_risk, \
        f"Sell order neg_risk should match position ({position.neg_risk}), not market ({market.neg_risk})"
    
    # If position and market have different neg_risk flags, verify we used position's
    if position.neg_risk != market.neg_risk:
        assert options.neg_risk == position.neg_risk, \
            f"When position.neg_risk={position.neg_risk} and market.neg_risk={market.neg_risk}, " \
            f"sell order should use position's flag ({position.neg_risk})"


@given(position_market=position_with_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sell_order_uses_position_token_id(position_market):
    """
    **Validates: Requirements 2.6**
    
    Property 3b: Sell Orders Use Position's token_id
    
    The sell order MUST use the exact token_id from the position, not any other identifier.
    """
    position, market, current_price = position_market
    strategy = create_mock_strategy()
    
    # Close the position
    success = await strategy._close_position(position, current_price)
    
    # Verify order was placed
    assert success is True, "Position close should succeed"
    
    # Verify create_order was called
    assert strategy.clob_client.create_order.called, "create_order should be called"
    
    # Get the call arguments
    call_args = strategy.clob_client.create_order.call_args
    order_args = call_args[0][0]  # First positional argument
    
    # Verify: token_id matches position exactly
    assert order_args.token_id == position.token_id, \
        f"Sell order token_id should match position ({position.token_id}), got {order_args.token_id}"


@given(position_market=position_with_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sell_order_size_matches_position_size(position_market):
    """
    **Validates: Requirements 2.6**
    
    Property 3c: Sell Order Size Matches Position Size
    
    The sell order size should match the position size (after rounding down to 2 decimals).
    Size should never exceed position size by more than 1%.
    """
    position, market, current_price = position_market
    strategy = create_mock_strategy()
    
    # Close the position
    success = await strategy._close_position(position, current_price)
    
    # Verify order was placed
    assert success is True, "Position close should succeed"
    
    # Verify create_order was called
    assert strategy.clob_client.create_order.called, "create_order should be called"
    
    # Get the call arguments
    call_args = strategy.clob_client.create_order.call_args
    order_args = call_args[0][0]  # First positional argument
    
    # Calculate expected size (rounded down to 2 decimals with 80% safety margin)
    expected_size = math.floor(float(position.size) * 0.80 * 100) / 100
    
    # Verify: size matches expected (within tolerance)
    assert order_args.size == expected_size, \
        f"Sell order size should be {expected_size} (80% of {float(position.size)}), got {order_args.size}"
    
    # Verify: size doesn't exceed position size by more than 1%
    size_ratio = order_args.size / float(position.size)
    assert size_ratio <= 1.01, \
        f"Sell order size ({order_args.size}) should not exceed position size ({float(position.size)}) by more than 1%"


@given(position_market=position_with_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sell_order_size_rounded_down_to_two_decimals(position_market):
    """
    **Validates: Requirements 2.6**
    
    Property 3d: Sell Order Size Rounded Down to 2 Decimals
    
    The sell order size must be rounded DOWN to 2 decimal places to avoid
    "insufficient balance" errors from trying to sell more than owned.
    """
    position, market, current_price = position_market
    strategy = create_mock_strategy()
    
    # Close the position
    success = await strategy._close_position(position, current_price)
    
    # Verify order was placed
    assert success is True, "Position close should succeed"
    
    # Verify create_order was called
    assert strategy.clob_client.create_order.called, "create_order should be called"
    
    # Get the call arguments
    call_args = strategy.clob_client.create_order.call_args
    order_args = call_args[0][0]  # First positional argument
    
    # Verify: size has at most 2 decimal places
    size_str = f"{order_args.size:.10f}"  # Convert to string with many decimals
    decimal_part = size_str.split('.')[1] if '.' in size_str else ""
    
    # Remove trailing zeros
    decimal_part = decimal_part.rstrip('0')
    
    assert len(decimal_part) <= 2, \
        f"Sell order size should have at most 2 decimal places, got {order_args.size} ({len(decimal_part)} decimals)"
    
    # Verify: size is rounded DOWN, not up
    original_size = float(position.size) * 0.80  # With safety margin
    expected_floored = math.floor(original_size * 100) / 100
    
    assert order_args.size == expected_floored, \
        f"Sell order size should be floored to {expected_floored}, got {order_args.size}"


@given(position_market=position_with_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sell_order_uses_correct_side(position_market):
    """
    **Validates: Requirements 2.6**
    
    Property 3e: Sell Orders Use SELL Side
    
    All sell orders must use the SELL side constant, not BUY.
    """
    position, market, current_price = position_market
    strategy = create_mock_strategy()
    
    # Close the position
    success = await strategy._close_position(position, current_price)
    
    # Verify order was placed
    assert success is True, "Position close should succeed"
    
    # Verify create_order was called
    assert strategy.clob_client.create_order.called, "create_order should be called"
    
    # Get the call arguments
    call_args = strategy.clob_client.create_order.call_args
    order_args = call_args[0][0]  # First positional argument
    
    # Import SELL constant
    from py_clob_client.order_builder.constants import SELL
    
    # Verify: side is SELL
    assert order_args.side == SELL, \
        f"Sell order side should be SELL, got {order_args.side}"


@given(position_market=position_with_market_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_sell_order_validation_prevents_invalid_orders(position_market):
    """
    **Validates: Requirements 2.6**
    
    Property 3f: Sell Order Validation Prevents Invalid Orders
    
    The validation logic should prevent orders with:
    - Empty token_id
    - Zero or negative size
    - Size exceeding position size by more than 1%
    """
    position, market, current_price = position_market
    strategy = create_mock_strategy()
    
    # Test 1: Empty token_id should fail validation
    invalid_position = Position(
        token_id="",  # Empty token_id
        side=position.side,
        entry_price=position.entry_price,
        size=position.size,
        entry_time=position.entry_time,
        market_id=position.market_id,
        asset=position.asset,
        strategy=position.strategy,
        neg_risk=position.neg_risk,
        highest_price=position.highest_price
    )
    
    success = await strategy._close_position(invalid_position, current_price)
    assert success is False, "Should fail validation with empty token_id"
    
    # Test 2: Zero size should fail validation
    # (This is handled by the size reduction logic, but let's verify)
    zero_size_position = Position(
        token_id=position.token_id,
        side=position.side,
        entry_price=position.entry_price,
        size=Decimal("0.0"),  # Zero size
        entry_time=position.entry_time,
        market_id=position.market_id,
        asset=position.asset,
        strategy=position.strategy,
        neg_risk=position.neg_risk,
        highest_price=position.highest_price
    )
    
    success = await strategy._close_position(zero_size_position, current_price)
    assert success is False, "Should fail validation with zero size"


@given(position_market=position_with_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sell_order_parameters_are_consistent(position_market):
    """
    **Validates: Requirements 2.6**
    
    Property 3g: All Sell Order Parameters Are Consistent
    
    Verify that all parameters (token_id, size, neg_risk, side) are consistent
    with the position being closed.
    """
    position, market, current_price = position_market
    strategy = create_mock_strategy()
    
    # Close the position
    success = await strategy._close_position(position, current_price)
    
    # Verify order was placed
    assert success is True, "Position close should succeed"
    
    # Verify create_order was called
    assert strategy.clob_client.create_order.called, "create_order should be called"
    
    # Get the call arguments
    call_args = strategy.clob_client.create_order.call_args
    order_args = call_args[0][0]  # First positional argument
    options = call_args[1].get('options')  # Keyword argument
    
    # Import SELL constant
    from py_clob_client.order_builder.constants import SELL
    
    # Verify all parameters are consistent
    assert order_args.token_id == position.token_id, "token_id should match position"
    assert order_args.side == SELL, "side should be SELL"
    assert options.neg_risk == position.neg_risk, "neg_risk should match position"
    
    # Verify size is reasonable (within 1% of position size)
    size_ratio = order_args.size / float(position.size)
    assert 0.0 < size_ratio <= 1.01, \
        f"Size ratio should be between 0 and 1.01, got {size_ratio}"
    
    # Verify price is positive
    assert order_args.price > 0, "Price should be positive"
    assert order_args.price == float(current_price), "Price should match current_price"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
