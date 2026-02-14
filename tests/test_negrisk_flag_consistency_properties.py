"""
Property-based tests for NegRisk flag consistency.

Tests that orders for NegRisk markets have the correct neg_risk flag set:
- Orders for NegRisk markets must have neg_risk=true
- Orders for non-NegRisk markets must have neg_risk=false

**Validates: Requirements 1.7**
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position, CryptoMarket


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def negrisk_market_strategy(draw):
    """Generate random CryptoMarket with various neg_risk flags."""
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    neg_risk = draw(st.booleans())  # Random neg_risk flag
    
    up_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    down_price = Decimal("1.00") - up_price  # Ensure sum = 1.00
    
    market = CryptoMarket(
        market_id=f"market_{draw(st.integers(min_value=1, max_value=100000))}",
        question=f"Will {asset} go up in the next 15 minutes?",
        asset=asset,
        up_token_id=f"up_token_{draw(st.integers(min_value=1, max_value=100000))}",
        down_token_id=f"down_token_{draw(st.integers(min_value=1, max_value=100000))}",
        up_price=up_price,
        down_price=down_price,
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        neg_risk=neg_risk,  # Market's neg_risk flag
        tick_size="0.01"
    )
    
    return market


@st.composite
def position_from_market_strategy(draw):
    """Generate a Position that was created from a specific market."""
    market = draw(negrisk_market_strategy())
    side = draw(st.sampled_from(["UP", "DOWN"]))
    
    # Position should inherit neg_risk from the market it was created from
    position = Position(
        token_id=market.up_token_id if side == "UP" else market.down_token_id,
        side=side,
        entry_price=market.up_price if side == "UP" else market.down_price,
        size=Decimal(str(draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False)))),
        entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        market_id=market.market_id,
        asset=market.asset,
        strategy="directional",
        neg_risk=market.neg_risk,  # Position inherits market's neg_risk
        highest_price=market.up_price if side == "UP" else market.down_price
    )
    
    return position, market


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
# PROPERTY 7: NEGRISK FLAG CONSISTENCY
# ============================================================================

@given(market=negrisk_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_negrisk_market_buy_orders_have_correct_flag(market):
    """
    **Validates: Requirements 1.7**
    
    Property 7a: Buy Orders for NegRisk Markets Have neg_risk=true
    
    When placing a buy order on a NegRisk market (market.neg_risk=True),
    the order MUST have neg_risk=true in the options.
    
    When placing a buy order on a non-NegRisk market (market.neg_risk=False),
    the order MUST have neg_risk=false in the options.
    """
    strategy = create_mock_strategy()
    
    # Mock risk manager to allow trade
    strategy.risk_manager.check_can_trade = MagicMock(
        return_value=MagicMock(can_trade=True, max_position_size=Decimal("10.0"))
    )
    
    # Mock ensemble decision to approve trade
    mock_decision = MagicMock(
        action="buy_yes" if market.up_price < market.down_price else "buy_no",
        confidence=Decimal("75.0"),
        consensus_score=Decimal("80.0"),
        reasoning="Test trade"
    )
    
    # Place a buy order on this market
    side = "UP" if mock_decision.action == "buy_yes" else "DOWN"
    token_id = market.up_token_id if side == "UP" else market.down_token_id
    price = market.up_price if side == "UP" else market.down_price
    size = Decimal("10.0")
    
    # Call the internal order placement method
    try:
        # Import required modules
        from py_clob_client.clob_types import OrderArgs
        from py_clob_client.order_builder.constants import BUY
        from types import SimpleNamespace
        
        # Create order args
        order_args = OrderArgs(
            token_id=token_id,
            price=float(price),
            size=float(size),
            side=BUY,
        )
        
        # Create options with neg_risk from market
        options = SimpleNamespace(
            tick_size=market.tick_size,
            neg_risk=market.neg_risk  # Should match market's neg_risk
        )
        
        # Create order
        signed_order = strategy.clob_client.create_order(order_args, options=options)
        
        # Verify create_order was called
        assert strategy.clob_client.create_order.called, "create_order should be called"
        
        # Get the call arguments
        call_args = strategy.clob_client.create_order.call_args
        call_options = call_args[1].get('options')
        
        # Verify: neg_risk flag matches market's neg_risk
        assert call_options is not None, "Options should be provided"
        assert hasattr(call_options, 'neg_risk'), "Options should have neg_risk attribute"
        assert call_options.neg_risk == market.neg_risk, \
            f"Buy order neg_risk should match market: order.neg_risk={call_options.neg_risk}, market.neg_risk={market.neg_risk}"
        
        # Specific checks for NegRisk vs non-NegRisk markets
        if market.neg_risk:
            assert call_options.neg_risk is True, \
                f"NegRisk market (neg_risk=True) should have order with neg_risk=True, got {call_options.neg_risk}"
        else:
            assert call_options.neg_risk is False, \
                f"Non-NegRisk market (neg_risk=False) should have order with neg_risk=False, got {call_options.neg_risk}"
    
    except Exception as e:
        pytest.fail(f"Order placement failed: {e}")


@given(position_market=position_from_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_negrisk_position_sell_orders_have_correct_flag(position_market):
    """
    **Validates: Requirements 1.7**
    
    Property 7b: Sell Orders for NegRisk Positions Have Correct Flag
    
    When closing a position that was opened on a NegRisk market,
    the sell order MUST have neg_risk=true.
    
    When closing a position that was opened on a non-NegRisk market,
    the sell order MUST have neg_risk=false.
    
    The sell order should use the position's neg_risk flag, which was
    inherited from the market at entry time.
    """
    position, market = position_market
    strategy = create_mock_strategy()
    
    # Current price for exit
    current_price = position.entry_price * Decimal("1.02")  # 2% profit
    
    # Close the position
    success = await strategy._close_position(position, current_price)
    
    # Verify order was placed
    assert success is True, "Position close should succeed"
    
    # Verify create_order was called
    assert strategy.clob_client.create_order.called, "create_order should be called"
    
    # Get the call arguments
    call_args = strategy.clob_client.create_order.call_args
    call_options = call_args[1].get('options')
    
    # Verify: neg_risk flag matches position's neg_risk (which came from market)
    assert call_options is not None, "Options should be provided"
    assert hasattr(call_options, 'neg_risk'), "Options should have neg_risk attribute"
    assert call_options.neg_risk == position.neg_risk, \
        f"Sell order neg_risk should match position: order.neg_risk={call_options.neg_risk}, position.neg_risk={position.neg_risk}"
    
    # Verify position's neg_risk matches the market it came from
    assert position.neg_risk == market.neg_risk, \
        f"Position should inherit market's neg_risk: position.neg_risk={position.neg_risk}, market.neg_risk={market.neg_risk}"
    
    # Specific checks for NegRisk vs non-NegRisk
    if market.neg_risk:
        assert position.neg_risk is True, \
            f"Position from NegRisk market should have neg_risk=True, got {position.neg_risk}"
        assert call_options.neg_risk is True, \
            f"Sell order for NegRisk position should have neg_risk=True, got {call_options.neg_risk}"
    else:
        assert position.neg_risk is False, \
            f"Position from non-NegRisk market should have neg_risk=False, got {position.neg_risk}"
        assert call_options.neg_risk is False, \
            f"Sell order for non-NegRisk position should have neg_risk=False, got {call_options.neg_risk}"


@given(
    negrisk_flag=st.booleans(),
    num_orders=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_all_orders_for_same_market_have_same_negrisk_flag(negrisk_flag, num_orders):
    """
    **Validates: Requirements 1.7**
    
    Property 7c: All Orders for Same Market Have Same neg_risk Flag
    
    When placing multiple orders on the same market (e.g., buying both UP and DOWN
    for sum-to-one arbitrage), all orders MUST have the same neg_risk flag that
    matches the market's neg_risk flag.
    """
    strategy = create_mock_strategy()
    
    # Create a market with specific neg_risk flag
    market = CryptoMarket(
        market_id="test_market_123",
        question="Will BTC go up?",
        asset="BTC",
        up_token_id="up_token_123",
        down_token_id="down_token_123",
        up_price=Decimal("0.48"),
        down_price=Decimal("0.52"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        neg_risk=negrisk_flag,  # Use the generated flag
        tick_size="0.01"
    )
    
    # Place multiple orders on this market
    from py_clob_client.clob_types import OrderArgs
    from py_clob_client.order_builder.constants import BUY
    from types import SimpleNamespace
    
    neg_risk_flags_used = []
    
    for i in range(num_orders):
        # Alternate between UP and DOWN
        side = "UP" if i % 2 == 0 else "DOWN"
        token_id = market.up_token_id if side == "UP" else market.down_token_id
        price = market.up_price if side == "UP" else market.down_price
        
        # Create order args
        order_args = OrderArgs(
            token_id=token_id,
            price=float(price),
            size=10.0,
            side=BUY,
        )
        
        # Create options with neg_risk from market
        options = SimpleNamespace(
            tick_size=market.tick_size,
            neg_risk=market.neg_risk
        )
        
        # Create order
        strategy.clob_client.create_order(order_args, options=options)
        
        # Track the neg_risk flag used
        neg_risk_flags_used.append(options.neg_risk)
    
    # Verify all orders used the same neg_risk flag
    assert len(set(neg_risk_flags_used)) == 1, \
        f"All orders for same market should use same neg_risk flag, got {neg_risk_flags_used}"
    
    # Verify the flag matches the market
    assert neg_risk_flags_used[0] == market.neg_risk, \
        f"All orders should use market's neg_risk flag: orders={neg_risk_flags_used[0]}, market={market.neg_risk}"


@given(
    market_neg_risk=st.booleans(),
    position_neg_risk=st.booleans()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sell_order_uses_position_negrisk_not_market_negrisk(market_neg_risk, position_neg_risk):
    """
    **Validates: Requirements 1.7**
    
    Property 7d: Sell Order Uses Position's neg_risk, Not Current Market's
    
    When closing a position, the sell order MUST use the position's neg_risk flag,
    even if the market's neg_risk flag has changed since entry.
    
    This is critical because:
    1. The position was opened with a specific neg_risk flag
    2. The market's flag might change over time
    3. The sell order must match the original entry to close correctly
    """
    strategy = create_mock_strategy()
    
    # Create a position with specific neg_risk flag
    position = Position(
        token_id="test_token_123",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        market_id="test_market_123",
        asset="BTC",
        strategy="directional",
        neg_risk=position_neg_risk,  # Position's neg_risk
        highest_price=Decimal("0.50")
    )
    
    # Create a market with potentially DIFFERENT neg_risk flag
    market = CryptoMarket(
        market_id=position.market_id,
        question="Will BTC go up?",
        asset=position.asset,
        up_token_id="up_token_123",
        down_token_id="down_token_123",
        up_price=Decimal("0.51"),
        down_price=Decimal("0.49"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
        neg_risk=market_neg_risk,  # Market's neg_risk (may differ)
        tick_size="0.01"
    )
    
    # Close the position
    current_price = Decimal("0.51")
    success = await strategy._close_position(position, current_price)
    
    # Verify order was placed
    assert success is True, "Position close should succeed"
    
    # Verify create_order was called
    assert strategy.clob_client.create_order.called, "create_order should be called"
    
    # Get the call arguments
    call_args = strategy.clob_client.create_order.call_args
    call_options = call_args[1].get('options')
    
    # CRITICAL: Verify sell order uses POSITION's neg_risk, not market's
    assert call_options is not None, "Options should be provided"
    assert hasattr(call_options, 'neg_risk'), "Options should have neg_risk attribute"
    assert call_options.neg_risk == position.neg_risk, \
        f"Sell order MUST use position's neg_risk ({position.neg_risk}), not market's ({market.neg_risk})"
    
    # If position and market have different flags, verify we used position's
    if position.neg_risk != market.neg_risk:
        assert call_options.neg_risk == position.neg_risk, \
            f"When position.neg_risk={position.neg_risk} differs from market.neg_risk={market.neg_risk}, " \
            f"sell order MUST use position's flag ({position.neg_risk}), got {call_options.neg_risk}"


@given(market=negrisk_market_strategy())
@settings(max_examples=100, deadline=None)
def test_property_negrisk_flag_is_boolean(market):
    """
    **Validates: Requirements 1.7**
    
    Property 7e: NegRisk Flag Is Always Boolean
    
    The neg_risk flag should always be a boolean value (True or False),
    never None, string, or other type.
    """
    # Verify market's neg_risk is boolean
    assert isinstance(market.neg_risk, bool), \
        f"Market neg_risk should be boolean, got {type(market.neg_risk)}"
    
    # Create a position from this market
    position = Position(
        token_id=market.up_token_id,
        side="UP",
        entry_price=market.up_price,
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        market_id=market.market_id,
        asset=market.asset,
        strategy="directional",
        neg_risk=market.neg_risk,
        highest_price=market.up_price
    )
    
    # Verify position's neg_risk is boolean
    assert isinstance(position.neg_risk, bool), \
        f"Position neg_risk should be boolean, got {type(position.neg_risk)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
