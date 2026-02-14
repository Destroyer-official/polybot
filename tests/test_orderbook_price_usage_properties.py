"""
Property-based tests for orderbook price usage in exit calculations.

Tests that exit prices use orderbook best bid when available, with proper fallback to mid prices.

**Validates: Requirements 2.5**
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position, CryptoMarket
from src.order_book_analyzer import OrderBookDepth, OrderBookLevel


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def orderbook_state_strategy(draw):
    """Generate random orderbook states with various bid/ask configurations."""
    # Generate bid prices (what buyers are willing to pay)
    num_bids = draw(st.integers(min_value=0, max_value=10))
    bids = []
    
    if num_bids > 0:
        # Start with best bid (highest price)
        best_bid_price = Decimal(str(draw(st.floats(min_value=0.40, max_value=0.95, allow_nan=False, allow_infinity=False))))
        
        for i in range(num_bids):
            # Each subsequent bid is lower
            price = best_bid_price - Decimal(str(i * 0.01))
            if price <= Decimal("0.01"):
                break
            size = Decimal(str(draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False))))
            bids.append(OrderBookLevel(price=price, size=size))
    
    # Generate ask prices (what sellers are asking)
    num_asks = draw(st.integers(min_value=0, max_value=10))
    asks = []
    
    if num_asks > 0:
        # Start with best ask (lowest price)
        best_ask_price = Decimal(str(draw(st.floats(min_value=0.05, max_value=0.60, allow_nan=False, allow_infinity=False))))
        
        for i in range(num_asks):
            # Each subsequent ask is higher
            price = best_ask_price + Decimal(str(i * 0.01))
            if price >= Decimal("0.99"):
                break
            size = Decimal(str(draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False))))
            asks.append(OrderBookLevel(price=price, size=size))
    
    # Calculate derived values
    bid_depth = sum(level.size for level in bids)
    ask_depth = sum(level.size for level in asks)
    
    if bids and asks:
        spread = asks[0].price - bids[0].price
        mid_price = (bids[0].price + asks[0].price) / Decimal("2")
    elif bids:
        spread = Decimal("0")
        mid_price = bids[0].price
    elif asks:
        spread = Decimal("0")
        mid_price = asks[0].price
    else:
        spread = Decimal("0")
        mid_price = Decimal("0.50")
    
    liquidity_score = min(100.0, float(bid_depth + ask_depth))
    
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
def position_with_market_strategy(draw):
    """Generate random Position with matching CryptoMarket."""
    entry_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    size = Decimal(str(draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False))))
    side = draw(st.sampled_from(["UP", "DOWN"]))
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    token_id = f"token_{draw(st.integers(min_value=1, max_value=100000))}"
    market_id = f"market_{draw(st.integers(min_value=1, max_value=10000))}"
    
    position = Position(
        token_id=token_id,
        side=side,
        entry_price=entry_price,
        size=size,
        entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        market_id=market_id,
        asset=asset,
        strategy="directional",
        neg_risk=False,
        highest_price=entry_price
    )
    
    # Create matching market with mid prices
    mid_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    
    market = CryptoMarket(
        market_id=market_id,
        question=f"Will {asset} go up?",
        asset=asset,
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=mid_price if side == "UP" else Decimal("0.50"),
        down_price=mid_price if side == "DOWN" else Decimal("0.50"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
        neg_risk=False
    )
    
    return position, market


# ============================================================================
# HELPER FUNCTION TO CREATE MOCK STRATEGY
# ============================================================================

def create_mock_strategy():
    """Create a mock strategy instance for testing."""
    mock_clob = MagicMock()
    
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=False
    )
    
    return strategy


# ============================================================================
# PROPERTY 2: EXIT PRICES USE ORDERBOOK BEST BID
# ============================================================================

@given(
    position_market=position_with_market_strategy(),
    orderbook=orderbook_state_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_exit_price_uses_orderbook_best_bid_when_available(position_market, orderbook):
    """
    **Validates: Requirements 2.5**
    
    Property 2a: Exit Price Uses Orderbook Best Bid
    
    When orderbook data is available with bids, the exit price should use the best bid price
    (highest price buyers are willing to pay), not the mid price.
    """
    position, market = position_market
    strategy = create_mock_strategy()
    
    # Skip if orderbook has no bids (will test fallback separately)
    if not orderbook.bids:
        return
    
    # Mock the order_book_analyzer to return our test orderbook
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=orderbook)
    
    # Get exit price
    exit_price, used_orderbook = await strategy._get_exit_price(position, market)
    
    # Verify: Should use orderbook best bid
    assert exit_price is not None, "Exit price should not be None when orderbook available"
    assert used_orderbook is True, "Should indicate orderbook was used"
    assert exit_price == orderbook.bids[0].price, f"Exit price should be best bid {orderbook.bids[0].price}, got {exit_price}"
    
    # Verify: Should NOT use mid price
    market_mid_price = market.up_price if position.side == "UP" else market.down_price
    if orderbook.bids[0].price != market_mid_price:
        assert exit_price != market_mid_price, "Should not use mid price when orderbook available"


@given(position_market=position_with_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_exit_price_falls_back_to_mid_when_orderbook_unavailable(position_market):
    """
    **Validates: Requirements 2.5**
    
    Property 2b: Exit Price Falls Back to Mid Price
    
    When orderbook data is unavailable (None or empty bids), the exit price should fall back
    to the mid price from market data.
    """
    position, market = position_market
    strategy = create_mock_strategy()
    
    # Mock the order_book_analyzer to return None (orderbook unavailable)
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=None)
    
    # Get exit price
    exit_price, used_orderbook = await strategy._get_exit_price(position, market)
    
    # Verify: Should fall back to mid price
    assert exit_price is not None, "Exit price should not be None when market data available"
    assert used_orderbook is False, "Should indicate orderbook was NOT used"
    
    expected_mid_price = market.up_price if position.side == "UP" else market.down_price
    assert exit_price == expected_mid_price, f"Exit price should be mid price {expected_mid_price}, got {exit_price}"


@given(position_market=position_with_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_exit_price_falls_back_when_orderbook_has_no_bids(position_market):
    """
    **Validates: Requirements 2.5**
    
    Property 2c: Exit Price Falls Back When No Bids
    
    When orderbook exists but has no bids (empty list), should fall back to mid price.
    """
    position, market = position_market
    strategy = create_mock_strategy()
    
    # Create orderbook with no bids
    empty_orderbook = OrderBookDepth(
        bids=[],  # Empty bids
        asks=[OrderBookLevel(price=Decimal("0.55"), size=Decimal("10.0"))],
        bid_depth=Decimal("0"),
        ask_depth=Decimal("10.0"),
        spread=Decimal("0"),
        mid_price=Decimal("0.55"),
        liquidity_score=10.0
    )
    
    # Mock the order_book_analyzer to return empty orderbook
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=empty_orderbook)
    
    # Get exit price
    exit_price, used_orderbook = await strategy._get_exit_price(position, market)
    
    # Verify: Should fall back to mid price
    assert exit_price is not None, "Exit price should not be None when market data available"
    assert used_orderbook is False, "Should indicate orderbook was NOT used (no bids)"
    
    expected_mid_price = market.up_price if position.side == "UP" else market.down_price
    assert exit_price == expected_mid_price, f"Exit price should be mid price {expected_mid_price}, got {exit_price}"


@given(position_market=position_with_market_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_exit_price_returns_none_when_no_data_available(position_market):
    """
    **Validates: Requirements 2.5**
    
    Property 2d: Exit Price Returns None When No Data
    
    When both orderbook and market data are unavailable, should return None.
    """
    position, _ = position_market  # Don't use market
    strategy = create_mock_strategy()
    
    # Mock the order_book_analyzer to return None
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=None)
    
    # Get exit price WITHOUT market data
    exit_price, used_orderbook = await strategy._get_exit_price(position, market=None)
    
    # Verify: Should return None
    assert exit_price is None, "Exit price should be None when no data available"
    assert used_orderbook is False, "Should indicate orderbook was NOT used"


@given(
    position_market=position_with_market_strategy(),
    orderbook=orderbook_state_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_exit_price_handles_orderbook_errors_gracefully(position_market, orderbook):
    """
    **Validates: Requirements 2.5**
    
    Property 2e: Exit Price Handles Errors Gracefully
    
    When orderbook fetch raises an exception, should fall back to mid price without crashing.
    """
    position, market = position_market
    strategy = create_mock_strategy()
    
    # Mock the order_book_analyzer to raise an exception
    strategy.order_book_analyzer.get_order_book = AsyncMock(side_effect=Exception("API error"))
    
    # Get exit price (should not raise exception)
    exit_price, used_orderbook = await strategy._get_exit_price(position, market)
    
    # Verify: Should fall back to mid price
    assert exit_price is not None, "Exit price should not be None after error (should use fallback)"
    assert used_orderbook is False, "Should indicate orderbook was NOT used (error occurred)"
    
    expected_mid_price = market.up_price if position.side == "UP" else market.down_price
    assert exit_price == expected_mid_price, f"Exit price should be mid price {expected_mid_price} after error, got {exit_price}"


@given(
    position_market=position_with_market_strategy(),
    orderbook=orderbook_state_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_orderbook_best_bid_is_realistic_exit_price(position_market, orderbook):
    """
    **Validates: Requirements 2.5**
    
    Property 2f: Orderbook Best Bid Represents Realistic Exit Price
    
    The best bid price (what we can actually sell for) should be used for P&L calculations,
    not the mid price (which is theoretical). This ensures realistic profit/loss tracking.
    """
    position, market = position_market
    strategy = create_mock_strategy()
    
    # Skip if orderbook has no bids
    if not orderbook.bids:
        return
    
    # Mock the order_book_analyzer to return our test orderbook
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=orderbook)
    
    # Get exit price
    exit_price, used_orderbook = await strategy._get_exit_price(position, market)
    
    # Verify: Exit price should be the best bid (most realistic)
    assert exit_price == orderbook.bids[0].price, "Exit price should be best bid for realistic P&L"
    
    # Calculate P&L with orderbook price vs mid price
    orderbook_pnl = (exit_price - position.entry_price) * position.size
    
    market_mid_price = market.up_price if position.side == "UP" else market.down_price
    mid_price_pnl = (market_mid_price - position.entry_price) * position.size
    
    # The difference can be significant (affects profitability assessment)
    # This property ensures we use the realistic price for decision-making
    if orderbook.bids[0].price != market_mid_price:
        assert orderbook_pnl != mid_price_pnl, "P&L should differ when using orderbook vs mid price"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
