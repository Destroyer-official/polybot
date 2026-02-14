"""
Property-based tests for liquidity verification before entry.

Tests that the bot correctly verifies orderbook liquidity before entering trades
and skips trades when insufficient liquidity is available.

**Validates: Requirements 3.7**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from typing import List

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
from src.order_book_analyzer import OrderBookDepth, OrderBookLevel


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def orderbook_strategy(draw):
    """Generate random orderbook states with various liquidity levels."""
    # Generate bid levels (buy orders)
    num_bid_levels = draw(st.integers(min_value=1, max_value=10))
    bids = []
    for i in range(num_bid_levels):
        price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
        size = Decimal(str(draw(st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False))))
        bids.append(OrderBookLevel(price=price, size=size))
    
    # Sort bids descending (highest price first)
    bids.sort(key=lambda x: x.price, reverse=True)
    
    # Generate ask levels (sell orders)
    num_ask_levels = draw(st.integers(min_value=1, max_value=10))
    asks = []
    for i in range(num_ask_levels):
        price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
        size = Decimal(str(draw(st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False))))
        asks.append(OrderBookLevel(price=price, size=size))
    
    # Sort asks ascending (lowest price first)
    asks.sort(key=lambda x: x.price)
    
    # Ensure asks are higher than bids (valid orderbook)
    if asks and bids:
        if asks[0].price <= bids[0].price:
            # Adjust ask prices to be above bid prices
            price_gap = bids[0].price - asks[0].price + Decimal("0.01")
            asks = [OrderBookLevel(price=level.price + price_gap, size=level.size) for level in asks]
    
    # Calculate metrics
    bid_depth = sum(level.size for level in bids)
    ask_depth = sum(level.size for level in asks)
    
    best_bid = bids[0].price if bids else Decimal("0.40")
    best_ask = asks[0].price if asks else Decimal("0.60")
    spread = best_ask - best_bid
    mid_price = (best_bid + best_ask) / Decimal("2")
    
    # Calculate liquidity score
    min_depth = min(bid_depth, ask_depth)
    liquidity_score = min(100.0, float(min_depth) * 10)
    
    spread_pct = spread / mid_price if mid_price > 0 else Decimal("1.0")
    if spread_pct > Decimal("0.05"):
        liquidity_score *= 0.5
    
    return OrderBookDepth(
        bids=bids,
        asks=asks,
        bid_depth=bid_depth,
        ask_depth=ask_depth,
        spread=spread,
        mid_price=mid_price,
        liquidity_score=liquidity_score
    )


@st.composite
def trade_parameters_strategy(draw):
    """Generate random trade parameters."""
    token_id = f"token_{draw(st.integers(min_value=1, max_value=100000))}"
    side = draw(st.sampled_from(["buy", "sell"]))
    trade_size = Decimal(str(draw(st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False))))
    strategy = draw(st.sampled_from(["sum_to_one", "latency", "directional", "flash_crash"]))
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    
    return {
        "token_id": token_id,
        "side": side,
        "trade_size": trade_size,
        "strategy": strategy,
        "asset": asset
    }


# ============================================================================
# HELPER FUNCTION TO CREATE MOCK STRATEGY
# ============================================================================

def create_mock_strategy_with_orderbook(orderbook: OrderBookDepth):
    """Create a mock strategy instance with a specific orderbook."""
    mock_clob = MagicMock()
    
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=False
    )
    
    # Mock the order book analyzer
    strategy.order_book_analyzer = MagicMock()
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=orderbook)
    strategy.order_book_analyzer.estimate_slippage = AsyncMock(return_value=(orderbook.mid_price, Decimal("0.01")))
    
    return strategy


# ============================================================================
# PROPERTY 15: LIQUIDITY VERIFICATION BEFORE ENTRY
# ============================================================================

@given(orderbook=orderbook_strategy(), trade_params=trade_parameters_strategy())
@settings(max_examples=200, deadline=None)
@pytest.mark.asyncio
async def test_property_liquidity_verification_skips_insufficient_liquidity(orderbook, trade_params):
    """
    **Validates: Requirements 3.7**
    
    Property 15a: Trade Skipped When Liquidity < 2x Trade Size
    
    For any orderbook state and trade parameters, if the available liquidity
    is less than 2x the trade size, the trade should be skipped.
    """
    strategy = create_mock_strategy_with_orderbook(orderbook)
    
    # Extract trade parameters
    token_id = trade_params["token_id"]
    side = trade_params["side"]
    trade_size = trade_params["trade_size"]
    strategy_name = trade_params["strategy"]
    asset = trade_params["asset"]
    
    # Get the price from orderbook
    if side == "buy":
        if not orderbook.asks or len(orderbook.asks) == 0:
            # Skip this test case - no asks available
            assume(False)
        price = orderbook.asks[0].price
        available_depth = orderbook.ask_depth
    else:
        if not orderbook.bids or len(orderbook.bids) == 0:
            # Skip this test case - no bids available
            assume(False)
        price = orderbook.bids[0].price
        available_depth = orderbook.bid_depth
    
    # Calculate required liquidity (2x trade size in shares)
    shares_needed = trade_size / price
    required_liquidity = shares_needed * Decimal("2.0")
    
    # Execute liquidity verification
    can_trade, reason = await strategy._verify_liquidity_before_entry(
        token_id, side, trade_size, strategy_name, asset
    )
    
    # PROPERTY: If available liquidity < required liquidity, trade should be skipped
    if available_depth < required_liquidity:
        assert can_trade == False, (
            f"Trade should be skipped when liquidity insufficient: "
            f"available={available_depth:.1f}, required={required_liquidity:.1f}"
        )
        assert "Insufficient liquidity" in reason, (
            f"Reason should mention insufficient liquidity, got: {reason}"
        )


@given(orderbook=orderbook_strategy(), trade_params=trade_parameters_strategy())
@settings(max_examples=200, deadline=None)
@pytest.mark.asyncio
async def test_property_liquidity_verification_proceeds_with_sufficient_liquidity(orderbook, trade_params):
    """
    **Validates: Requirements 3.7**
    
    Property 15b: Trade Proceeds When Liquidity >= 2x Trade Size
    
    For any orderbook state and trade parameters, if the available liquidity
    is >= 2x the trade size AND slippage is acceptable, the trade should proceed.
    """
    strategy = create_mock_strategy_with_orderbook(orderbook)
    
    # Extract trade parameters
    token_id = trade_params["token_id"]
    side = trade_params["side"]
    trade_size = trade_params["trade_size"]
    strategy_name = trade_params["strategy"]
    asset = trade_params["asset"]
    
    # Get the price from orderbook
    if side == "buy":
        if not orderbook.asks or len(orderbook.asks) == 0:
            assume(False)
        price = orderbook.asks[0].price
        available_depth = orderbook.ask_depth
    else:
        if not orderbook.bids or len(orderbook.bids) == 0:
            assume(False)
        price = orderbook.bids[0].price
        available_depth = orderbook.bid_depth
    
    # Calculate required liquidity (2x trade size in shares)
    shares_needed = trade_size / price
    required_liquidity = shares_needed * Decimal("2.0")
    
    # Mock slippage to be acceptable (< 50%)
    acceptable_slippage = Decimal("0.10")  # 10% slippage
    strategy.order_book_analyzer.estimate_slippage = AsyncMock(
        return_value=(orderbook.mid_price, acceptable_slippage)
    )
    
    # Execute liquidity verification
    can_trade, reason = await strategy._verify_liquidity_before_entry(
        token_id, side, trade_size, strategy_name, asset
    )
    
    # PROPERTY: If available liquidity >= required liquidity AND slippage acceptable, trade should proceed
    if available_depth >= required_liquidity:
        assert can_trade == True, (
            f"Trade should proceed when liquidity sufficient: "
            f"available={available_depth:.1f}, required={required_liquidity:.1f}, "
            f"reason={reason}"
        )
        assert "Sufficient liquidity" in reason or "liquidity OK" in reason, (
            f"Reason should indicate sufficient liquidity, got: {reason}"
        )


@given(orderbook=orderbook_strategy(), trade_params=trade_parameters_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_liquidity_verification_skips_excessive_slippage(orderbook, trade_params):
    """
    **Validates: Requirements 3.7**
    
    Property 15c: Trade Skipped When Slippage > 50% (Even With Sufficient Depth)
    
    For any orderbook state, if the estimated slippage with 2x trade size
    exceeds 50%, the trade should be skipped even if depth is sufficient.
    """
    strategy = create_mock_strategy_with_orderbook(orderbook)
    
    # Extract trade parameters
    token_id = trade_params["token_id"]
    side = trade_params["side"]
    trade_size = trade_params["trade_size"]
    strategy_name = trade_params["strategy"]
    asset = trade_params["asset"]
    
    # Get the price from orderbook
    if side == "buy":
        if not orderbook.asks or len(orderbook.asks) == 0:
            assume(False)
        price = orderbook.asks[0].price
        available_depth = orderbook.ask_depth
    else:
        if not orderbook.bids or len(orderbook.bids) == 0:
            assume(False)
        price = orderbook.bids[0].price
        available_depth = orderbook.bid_depth
    
    # Calculate required liquidity
    shares_needed = trade_size / price
    required_liquidity = shares_needed * Decimal("2.0")
    
    # Only test cases where depth is sufficient
    assume(available_depth >= required_liquidity)
    
    # Mock excessive slippage (> 50%)
    excessive_slippage = Decimal("0.60")  # 60% slippage
    strategy.order_book_analyzer.estimate_slippage = AsyncMock(
        return_value=(orderbook.mid_price, excessive_slippage)
    )
    
    # Execute liquidity verification
    can_trade, reason = await strategy._verify_liquidity_before_entry(
        token_id, side, trade_size, strategy_name, asset
    )
    
    # PROPERTY: If slippage > 50%, trade should be skipped
    assert can_trade == False, (
        f"Trade should be skipped when slippage excessive: "
        f"slippage={excessive_slippage*100:.1f}%, max=50%, "
        f"reason={reason}"
    )
    assert "slippage" in reason.lower(), (
        f"Reason should mention slippage, got: {reason}"
    )


@given(trade_params=trade_parameters_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_liquidity_verification_handles_missing_orderbook(trade_params):
    """
    **Validates: Requirements 3.7**
    
    Property 15d: Graceful Handling of Missing Orderbook Data
    
    For any trade parameters, if orderbook data is unavailable, the system
    should handle it gracefully (fail-open with warning).
    """
    # Create strategy with no orderbook data
    mock_clob = MagicMock()
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=False
    )
    
    # Mock orderbook analyzer to return None
    strategy.order_book_analyzer = MagicMock()
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=None)
    
    # Extract trade parameters
    token_id = trade_params["token_id"]
    side = trade_params["side"]
    trade_size = trade_params["trade_size"]
    strategy_name = trade_params["strategy"]
    asset = trade_params["asset"]
    
    # Execute liquidity verification
    can_trade, reason = await strategy._verify_liquidity_before_entry(
        token_id, side, trade_size, strategy_name, asset
    )
    
    # PROPERTY: Missing orderbook should fail-open (allow trade with warning)
    assert can_trade == True, (
        f"Trade should proceed with caution when orderbook unavailable, got: {reason}"
    )
    assert "orderbook" in reason.lower() or "no orderbook" in reason.lower(), (
        f"Reason should mention missing orderbook, got: {reason}"
    )


@given(trade_params=trade_parameters_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_liquidity_verification_handles_empty_orderbook_side(trade_params):
    """
    **Validates: Requirements 3.7**
    
    Property 15e: Graceful Handling of Empty Orderbook Side
    
    For any trade parameters, if the relevant orderbook side (bids/asks) is empty,
    the system should handle it gracefully (fail-open with warning).
    """
    # Extract trade parameters
    token_id = trade_params["token_id"]
    side = trade_params["side"]
    trade_size = trade_params["trade_size"]
    strategy_name = trade_params["strategy"]
    asset = trade_params["asset"]
    
    # Create orderbook with empty side
    if side == "buy":
        # Empty asks (no sellers)
        orderbook = OrderBookDepth(
            bids=[OrderBookLevel(price=Decimal("0.50"), size=Decimal("100.0"))],
            asks=[],  # Empty asks
            bid_depth=Decimal("100.0"),
            ask_depth=Decimal("0.0"),
            spread=Decimal("0.10"),
            mid_price=Decimal("0.50"),
            liquidity_score=50.0
        )
    else:
        # Empty bids (no buyers)
        orderbook = OrderBookDepth(
            bids=[],  # Empty bids
            asks=[OrderBookLevel(price=Decimal("0.60"), size=Decimal("100.0"))],
            bid_depth=Decimal("0.0"),
            ask_depth=Decimal("100.0"),
            spread=Decimal("0.10"),
            mid_price=Decimal("0.60"),
            liquidity_score=50.0
        )
    
    strategy = create_mock_strategy_with_orderbook(orderbook)
    
    # Execute liquidity verification
    can_trade, reason = await strategy._verify_liquidity_before_entry(
        token_id, side, trade_size, strategy_name, asset
    )
    
    # PROPERTY: Empty orderbook side should fail-open (allow trade with warning)
    assert can_trade == True, (
        f"Trade should proceed with caution when orderbook side empty, got: {reason}"
    )
    expected_term = "asks" if side == "buy" else "bids"
    assert expected_term in reason.lower() or "orderbook" in reason.lower(), (
        f"Reason should mention empty {expected_term}, got: {reason}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
