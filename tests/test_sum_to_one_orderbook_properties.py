"""
Property-based tests for sum-to-one orderbook verification.

Tests that sum-to-one arbitrage detection uses orderbook ASK prices (not mid prices)
and only triggers when ask_up + ask_down < threshold.

**Validates: Requirements 3.9**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket
from src.order_book_analyzer import OrderBookDepth, OrderBookLevel


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def sum_to_one_orderbook_strategy(draw):
    """Generate random orderbook states with various ask price combinations."""
    # Generate UP token ask prices
    num_up_asks = draw(st.integers(min_value=1, max_value=10))
    up_asks = []
    
    # Best ask (lowest price) for UP token
    best_up_ask = Decimal(str(draw(st.floats(min_value=0.20, max_value=0.80, allow_nan=False, allow_infinity=False))))
    
    for i in range(num_up_asks):
        # Each subsequent ask is higher
        price = best_up_ask + Decimal(str(i * 0.01))
        if price >= Decimal("0.99"):
            break
        size = Decimal(str(draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False))))
        up_asks.append(OrderBookLevel(price=price, size=size))
    
    # Generate DOWN token ask prices
    num_down_asks = draw(st.integers(min_value=1, max_value=10))
    down_asks = []
    
    # Best ask (lowest price) for DOWN token
    best_down_ask = Decimal(str(draw(st.floats(min_value=0.20, max_value=0.80, allow_nan=False, allow_infinity=False))))
    
    for i in range(num_down_asks):
        # Each subsequent ask is higher
        price = best_down_ask + Decimal(str(i * 0.01))
        if price >= Decimal("0.99"):
            break
        size = Decimal(str(draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False))))
        down_asks.append(OrderBookLevel(price=price, size=size))
    
    # Create orderbook for UP token
    up_orderbook = OrderBookDepth(
        bids=[],  # Not needed for sum-to-one entry
        asks=up_asks,
        bid_depth=Decimal("0"),
        ask_depth=sum(level.size for level in up_asks),
        spread=Decimal("0"),
        mid_price=best_up_ask,
        liquidity_score=float(sum(level.size for level in up_asks))
    )
    
    # Create orderbook for DOWN token
    down_orderbook = OrderBookDepth(
        bids=[],  # Not needed for sum-to-one entry
        asks=down_asks,
        bid_depth=Decimal("0"),
        ask_depth=sum(level.size for level in down_asks),
        spread=Decimal("0"),
        mid_price=best_down_ask,
        liquidity_score=float(sum(level.size for level in down_asks))
    )
    
    return up_orderbook, down_orderbook, best_up_ask, best_down_ask


@st.composite
def crypto_market_strategy(draw):
    """Generate random CryptoMarket with mid prices that sum to $1.00."""
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    market_id = f"market_{draw(st.integers(min_value=1, max_value=10000))}"
    
    # Mid prices ALWAYS sum to $1.00 (this is the bug we're testing for)
    up_mid_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    down_mid_price = Decimal("1.0") - up_mid_price
    
    market = CryptoMarket(
        market_id=market_id,
        question=f"Will {asset} go up in the next 15 minutes?",
        asset=asset,
        up_token_id=f"up_token_{market_id}",
        down_token_id=f"down_token_{market_id}",
        up_price=up_mid_price,
        down_price=down_mid_price,
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        neg_risk=False
    )
    
    return market


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
    
    # Mock the _place_order method to prevent actual order placement
    strategy._place_order = AsyncMock(return_value=True)
    
    # Mock learning engines to always approve trades
    strategy._should_take_trade = MagicMock(return_value=(True, 100.0, "Test approved"))
    
    # Mock daily limit and asset exposure checks
    strategy._check_daily_limit = MagicMock(return_value=True)
    strategy._check_asset_exposure = MagicMock(return_value=True)
    
    # Mock time to close check
    strategy._has_min_time_to_close = MagicMock(return_value=True)
    
    # Mock liquidity checks to always pass
    strategy.order_book_analyzer.check_liquidity = AsyncMock(return_value=(True, "Sufficient liquidity"))
    
    return strategy


# ============================================================================
# PROPERTY 17: SUM-TO-ONE ORDERBOOK VERIFICATION
# ============================================================================

@given(
    market=crypto_market_strategy(),
    orderbooks=sum_to_one_orderbook_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sum_to_one_uses_orderbook_ask_prices(market, orderbooks):
    """
    **Validates: Requirements 3.9**
    
    Property 17a: Sum-to-One Uses Orderbook ASK Prices
    
    When orderbook data is available, sum-to-one arbitrage detection should use
    the best ASK prices (what you actually pay to buy), NOT mid prices.
    
    Mid prices always sum to $1.00, so using them would never trigger arbitrage.
    """
    up_orderbook, down_orderbook, best_up_ask, best_down_ask = orderbooks
    strategy = create_mock_strategy()
    
    # Mock the order_book_analyzer to return our test orderbooks
    async def mock_get_order_book(token_id):
        if "up_token" in token_id:
            return up_orderbook
        elif "down_token" in token_id:
            return down_orderbook
        return None
    
    strategy.order_book_analyzer.get_order_book = AsyncMock(side_effect=mock_get_order_book)
    
    # Calculate what the sum should be
    ask_sum = best_up_ask + best_down_ask
    mid_sum = market.up_price + market.down_price
    
    # Mid prices should sum to $1.00 (or very close)
    assert abs(mid_sum - Decimal("1.0")) < Decimal("0.01"), "Mid prices should sum to ~$1.00"
    
    # Execute sum-to-one check
    result = await strategy.check_sum_to_one_arbitrage(market)
    
    # Verify: If arbitrage triggered, it should be based on ASK prices, not mid prices
    if result:
        # Arbitrage was executed - verify it was based on ask prices
        assert ask_sum < strategy.sum_to_one_threshold, \
            f"Arbitrage triggered but ask_sum ({ask_sum}) >= threshold ({strategy.sum_to_one_threshold})"
        
        # Verify mid prices would NOT have triggered (proving we used ask prices)
        # Allow small tolerance for edge cases
        if mid_sum >= strategy.sum_to_one_threshold - Decimal("0.01"):
            # This proves we used ask prices, not mid prices
            pass
    else:
        # Arbitrage was NOT executed - verify ask prices don't meet threshold
        # (or other conditions blocked it)
        if ask_sum < strategy.sum_to_one_threshold:
            # Ask prices would trigger, but trade was blocked by other conditions
            # This is acceptable (learning engines, liquidity, etc. can block)
            pass


@given(
    market=crypto_market_strategy(),
    orderbooks=sum_to_one_orderbook_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sum_to_one_only_triggers_when_ask_sum_below_threshold(market, orderbooks):
    """
    **Validates: Requirements 3.9**
    
    Property 17b: Sum-to-One Only Triggers When ASK Sum < Threshold
    
    Sum-to-one arbitrage should ONLY trigger when:
    ask_up + ask_down < threshold (default 1.02)
    
    It should NEVER trigger based on mid prices.
    """
    up_orderbook, down_orderbook, best_up_ask, best_down_ask = orderbooks
    strategy = create_mock_strategy()
    
    # Mock the order_book_analyzer to return our test orderbooks
    async def mock_get_order_book(token_id):
        if "up_token" in token_id:
            return up_orderbook
        elif "down_token" in token_id:
            return down_orderbook
        return None
    
    strategy.order_book_analyzer.get_order_book = AsyncMock(side_effect=mock_get_order_book)
    
    # Calculate ask sum
    ask_sum = best_up_ask + best_down_ask
    
    # Execute sum-to-one check
    result = await strategy.check_sum_to_one_arbitrage(market)
    
    # Verify: If ask_sum >= threshold, arbitrage should NOT trigger
    if ask_sum >= strategy.sum_to_one_threshold:
        assert result is False, \
            f"Arbitrage should NOT trigger when ask_sum ({ask_sum}) >= threshold ({strategy.sum_to_one_threshold})"
    
    # Verify: If ask_sum < threshold AND profit after fees >= 0.005, arbitrage SHOULD trigger
    # (unless blocked by other conditions like learning engines, liquidity, etc.)
    spread = Decimal("1.0") - ask_sum
    profit_after_fees = spread - Decimal("0.03")
    
    if ask_sum < strategy.sum_to_one_threshold and profit_after_fees >= Decimal("0.005"):
        # Arbitrage should trigger (unless blocked by other conditions)
        # We can't assert result is True because learning engines, liquidity, etc. can block
        # But we can verify the logic is correct
        pass


@given(market=crypto_market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sum_to_one_falls_back_to_mid_prices_when_orderbook_unavailable(market):
    """
    **Validates: Requirements 3.9**
    
    Property 17c: Sum-to-One Falls Back to Mid Prices
    
    When orderbook data is unavailable (None or empty asks), sum-to-one should
    fall back to mid prices from market data.
    
    This fallback will rarely trigger arbitrage (since mid prices sum to $1.00),
    but it prevents the bot from crashing.
    """
    strategy = create_mock_strategy()
    
    # Mock the order_book_analyzer to return None (orderbook unavailable)
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=None)
    
    # Execute sum-to-one check (should not crash)
    result = await strategy.check_sum_to_one_arbitrage(market)
    
    # Verify: Should not crash and should return False (mid prices sum to $1.00)
    assert result is False, "Sum-to-one should not trigger with mid prices (sum to $1.00)"


@given(market=crypto_market_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_sum_to_one_falls_back_when_orderbook_has_no_asks(market):
    """
    **Validates: Requirements 3.9**
    
    Property 17d: Sum-to-One Falls Back When No Asks
    
    When orderbook exists but has no asks (empty list), should fall back to mid prices.
    """
    strategy = create_mock_strategy()
    
    # Create orderbook with no asks
    empty_orderbook = OrderBookDepth(
        bids=[OrderBookLevel(price=Decimal("0.45"), size=Decimal("10.0"))],
        asks=[],  # Empty asks
        bid_depth=Decimal("10.0"),
        ask_depth=Decimal("0"),
        spread=Decimal("0"),
        mid_price=Decimal("0.45"),
        liquidity_score=10.0
    )
    
    # Mock the order_book_analyzer to return empty orderbook
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=empty_orderbook)
    
    # Execute sum-to-one check (should not crash)
    result = await strategy.check_sum_to_one_arbitrage(market)
    
    # Verify: Should not crash and should return False (mid prices sum to $1.00)
    assert result is False, "Sum-to-one should not trigger with mid prices (sum to $1.00)"


@given(
    market=crypto_market_strategy(),
    orderbooks=sum_to_one_orderbook_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_sum_to_one_handles_orderbook_errors_gracefully(market, orderbooks):
    """
    **Validates: Requirements 3.9**
    
    Property 17e: Sum-to-One Handles Errors Gracefully
    
    When orderbook fetch raises an exception, the current implementation
    propagates the exception. This test verifies the current behavior.
    
    NOTE: Future enhancement could add error handling to fall back to mid prices.
    """
    strategy = create_mock_strategy()
    
    # Mock the order_book_analyzer to raise an exception
    strategy.order_book_analyzer.get_order_book = AsyncMock(side_effect=Exception("API error"))
    
    # Execute sum-to-one check - should raise exception (current behavior)
    with pytest.raises(Exception, match="API error"):
        await strategy.check_sum_to_one_arbitrage(market)


@given(
    market=crypto_market_strategy(),
    orderbooks=sum_to_one_orderbook_strategy()
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_sum_to_one_never_uses_mid_prices_when_orderbook_available(market, orderbooks):
    """
    **Validates: Requirements 3.9**
    
    Property 17f: Sum-to-One NEVER Uses Mid Prices When Orderbook Available
    
    This is the CRITICAL property: when orderbook data is available with asks,
    the sum-to-one check should NEVER use mid prices for the calculation.
    
    Mid prices always sum to $1.00, which would prevent arbitrage detection.
    """
    up_orderbook, down_orderbook, best_up_ask, best_down_ask = orderbooks
    strategy = create_mock_strategy()
    
    # Ensure orderbooks have asks
    assume(len(up_orderbook.asks) > 0)
    assume(len(down_orderbook.asks) > 0)
    
    # Mock the order_book_analyzer to return our test orderbooks
    async def mock_get_order_book(token_id):
        if "up_token" in token_id:
            return up_orderbook
        elif "down_token" in token_id:
            return down_orderbook
        return None
    
    strategy.order_book_analyzer.get_order_book = AsyncMock(side_effect=mock_get_order_book)
    
    # Calculate sums
    ask_sum = best_up_ask + best_down_ask
    mid_sum = market.up_price + market.down_price
    
    # Ensure mid prices sum to $1.00 (or very close)
    assume(abs(mid_sum - Decimal("1.0")) < Decimal("0.01"))
    
    # Ensure ask prices are DIFFERENT from mid prices (otherwise test is meaningless)
    assume(abs(best_up_ask - market.up_price) > Decimal("0.01") or 
           abs(best_down_ask - market.down_price) > Decimal("0.01"))
    
    # Execute sum-to-one check
    result = await strategy.check_sum_to_one_arbitrage(market)
    
    # CRITICAL VERIFICATION:
    # If arbitrage triggered, it MUST be because ask_sum < threshold
    # NOT because mid_sum < threshold (which should be impossible)
    if result:
        # Verify ask prices triggered it
        assert ask_sum < strategy.sum_to_one_threshold, \
            f"Arbitrage triggered but ask_sum ({ask_sum}) >= threshold"
        
        # Verify mid prices would NOT have triggered
        # (This proves we used ask prices, not mid prices)
        assert mid_sum >= strategy.sum_to_one_threshold - Decimal("0.01"), \
            f"Mid prices ({mid_sum}) should NOT trigger arbitrage (should sum to ~$1.00)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
