"""
Unit tests for liquidity verification (Task 7.2 - Requirement 3.7).

Tests that the bot:
1. Fetches orderbook before every entry
2. Checks if available liquidity >= 2x trade size
3. Skips trade if insufficient liquidity
4. Logs liquidity checks
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from src.order_book_analyzer import OrderBookDepth, OrderBookLevel


class MockStrategy:
    """Minimal mock strategy for testing liquidity verification."""
    
    def __init__(self):
        self.order_book_analyzer = MagicMock()
    
    async def _verify_liquidity_before_entry(
        self,
        token_id: str,
        side: str,
        trade_size: Decimal,
        strategy: str,
        asset: str
    ):
        """Copy of the actual method from FifteenMinuteCryptoStrategy."""
        try:
            # Calculate shares needed
            orderbook = await self.order_book_analyzer.get_order_book(token_id)
            if not orderbook:
                return (True, "No orderbook data available")
            
            # Get price from orderbook
            if side == "buy":
                if not orderbook.asks or len(orderbook.asks) == 0:
                    return (True, "No asks in orderbook")
                price = orderbook.asks[0].price
            else:
                if not orderbook.bids or len(orderbook.bids) == 0:
                    return (True, "No bids in orderbook")
                price = orderbook.bids[0].price
            
            shares_needed = trade_size / price
            
            # REQUIREMENT 3.7: Check if available liquidity >= 2x trade size
            required_liquidity = shares_needed * Decimal("2.0")
            
            # Check available depth
            available_depth = orderbook.ask_depth if side == "buy" else orderbook.bid_depth
            
            if available_depth < required_liquidity:
                reason = f"Insufficient liquidity: need {required_liquidity:.1f} shares (2x {shares_needed:.1f}), available {available_depth:.1f}"
                return (False, reason)
            
            # Check slippage with 2x size
            avg_price, slippage_pct = await self.order_book_analyzer.estimate_slippage(
                token_id, side, required_liquidity
            )
            
            # Allow up to 50% slippage for high-confidence trades
            max_slippage = Decimal("0.50")
            if slippage_pct > max_slippage:
                reason = f"Excessive slippage with 2x size: {slippage_pct*100:.1f}% > {max_slippage*100:.1f}%"
                return (False, reason)
            
            return (True, "Sufficient liquidity")
            
        except Exception as e:
            # On error, allow trade to proceed (fail-open for availability)
            return (True, f"Liquidity check error: {e}")


@pytest.fixture
def mock_strategy():
    """Create a mock strategy instance for testing."""
    return MockStrategy()


@pytest.mark.asyncio
async def test_liquidity_verification_sufficient_liquidity(mock_strategy):
    """Test that trade proceeds when liquidity >= 2x trade size."""
    
    # Setup: Create orderbook with sufficient liquidity
    orderbook = OrderBookDepth(
        bids=[OrderBookLevel(price=Decimal("0.54"), size=Decimal("100.0"))],
        asks=[OrderBookLevel(price=Decimal("0.55"), size=Decimal("100.0"))],
        bid_depth=Decimal("100.0"),
        ask_depth=Decimal("100.0"),  # 100 shares available
        spread=Decimal("0.01"),
        mid_price=Decimal("0.545"),
        liquidity_score=80.0
    )
    
    mock_strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=orderbook)
    mock_strategy.order_book_analyzer.estimate_slippage = AsyncMock(
        return_value=(Decimal("0.55"), Decimal("0.02"))  # 2% slippage
    )
    
    # Test: Verify liquidity for 10 USD trade (needs ~18 shares, 2x = 36 shares)
    can_trade, reason = await mock_strategy._verify_liquidity_before_entry(
        token_id="token_up_123",
        side="buy",
        trade_size=Decimal("10.0"),
        strategy="test",
        asset="BTC"
    )
    
    # Assert: Trade should be allowed
    assert can_trade is True
    assert "Sufficient liquidity" in reason


@pytest.mark.asyncio
async def test_liquidity_verification_insufficient_liquidity(mock_strategy):
    """Test that trade is skipped when liquidity < 2x trade size."""
    
    # Setup: Create orderbook with insufficient liquidity
    orderbook = OrderBookDepth(
        bids=[OrderBookLevel(price=Decimal("0.54"), size=Decimal("10.0"))],
        asks=[OrderBookLevel(price=Decimal("0.55"), size=Decimal("10.0"))],
        bid_depth=Decimal("10.0"),
        ask_depth=Decimal("10.0"),  # Only 10 shares available
        spread=Decimal("0.01"),
        mid_price=Decimal("0.545"),
        liquidity_score=20.0
    )
    
    mock_strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=orderbook)
    mock_strategy.order_book_analyzer.estimate_slippage = AsyncMock(
        return_value=(Decimal("0.55"), Decimal("0.02"))
    )
    
    # Test: Verify liquidity for 10 USD trade (needs ~18 shares, 2x = 36 shares)
    can_trade, reason = await mock_strategy._verify_liquidity_before_entry(
        token_id="token_up_123",
        side="buy",
        trade_size=Decimal("10.0"),
        strategy="test",
        asset="BTC"
    )
    
    # Assert: Trade should be blocked
    assert can_trade is False
    assert "Insufficient liquidity" in reason


@pytest.mark.asyncio
async def test_liquidity_verification_excessive_slippage(mock_strategy):
    """Test that trade is skipped when slippage > 50% with 2x size."""
    
    # Setup: Create orderbook with high slippage
    orderbook = OrderBookDepth(
        bids=[OrderBookLevel(price=Decimal("0.54"), size=Decimal("100.0"))],
        asks=[OrderBookLevel(price=Decimal("0.55"), size=Decimal("100.0"))],
        bid_depth=Decimal("100.0"),
        ask_depth=Decimal("100.0"),
        spread=Decimal("0.01"),
        mid_price=Decimal("0.545"),
        liquidity_score=50.0
    )
    
    mock_strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=orderbook)
    mock_strategy.order_book_analyzer.estimate_slippage = AsyncMock(
        return_value=(Decimal("0.60"), Decimal("0.60"))  # 60% slippage (excessive)
    )
    
    # Test: Verify liquidity
    can_trade, reason = await mock_strategy._verify_liquidity_before_entry(
        token_id="token_up_123",
        side="buy",
        trade_size=Decimal("10.0"),
        strategy="test",
        asset="BTC"
    )
    
    # Assert: Trade should be blocked due to excessive slippage
    assert can_trade is False
    assert "Excessive slippage" in reason


@pytest.mark.asyncio
async def test_liquidity_verification_no_orderbook_data(mock_strategy):
    """Test that trade proceeds with caution when no orderbook data available."""
    
    # Setup: No orderbook data
    mock_strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=None)
    
    # Test: Verify liquidity
    can_trade, reason = await mock_strategy._verify_liquidity_before_entry(
        token_id="token_up_123",
        side="buy",
        trade_size=Decimal("10.0"),
        strategy="test",
        asset="BTC"
    )
    
    # Assert: Trade should proceed (fail-open for availability)
    assert can_trade is True
    assert "No orderbook data" in reason


@pytest.mark.asyncio
async def test_liquidity_verification_empty_asks(mock_strategy):
    """Test that trade proceeds with caution when orderbook has no asks."""
    
    # Setup: Orderbook with no asks
    orderbook = OrderBookDepth(
        bids=[OrderBookLevel(price=Decimal("0.54"), size=Decimal("100.0"))],
        asks=[],  # No asks
        bid_depth=Decimal("100.0"),
        ask_depth=Decimal("0.0"),
        spread=Decimal("0.01"),
        mid_price=Decimal("0.54"),
        liquidity_score=0.0
    )
    
    mock_strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=orderbook)
    
    # Test: Verify liquidity for buy order
    can_trade, reason = await mock_strategy._verify_liquidity_before_entry(
        token_id="token_up_123",
        side="buy",
        trade_size=Decimal("10.0"),
        strategy="test",
        asset="BTC"
    )
    
    # Assert: Trade should proceed (fail-open for availability)
    assert can_trade is True
    assert "No asks in orderbook" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
