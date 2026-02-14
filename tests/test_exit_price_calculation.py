"""
Unit tests for exit price calculation with orderbook and mid-price fallback.

Tests the _get_exit_price method to ensure:
1. Uses orderbook best bid when available (realistic exit price)
2. Falls back to mid price when orderbook unavailable
3. Returns None when neither orderbook nor market data available
4. Handles errors gracefully with fallback

Validates Requirement 2.5: Exit prices use orderbook best bid with mid-price fallback
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position, CryptoMarket


@pytest.fixture
def strategy():
    """Create a strategy instance with mocked dependencies."""
    mock_clob_client = MagicMock()
    strategy = FifteenMinuteCryptoStrategy(clob_client=mock_clob_client)
    strategy.order_book_analyzer = AsyncMock()
    return strategy


@pytest.fixture
def test_position():
    """Create a test position."""
    return Position(
        token_id="test_token_123",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market",
        asset="BTC",
        strategy="latency",
        neg_risk=True,
        highest_price=Decimal("0.50")
    )


@pytest.fixture
def test_market():
    """Create a test market with mid prices."""
    return CryptoMarket(
        market_id="test_market",
        question="Will BTC go up?",
        asset="BTC",
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=Decimal("0.52"),  # Mid price for UP
        down_price=Decimal("0.48"),  # Mid price for DOWN
        end_time=datetime.now(timezone.utc),
        neg_risk=True
    )


@pytest.mark.asyncio
async def test_exit_price_uses_orderbook_best_bid(strategy, test_position, test_market):
    """Test that exit price uses orderbook best bid when available."""
    # Mock orderbook with best bid
    mock_orderbook = Mock()
    mock_bid = Mock()
    mock_bid.price = Decimal("0.51")  # Best bid price (realistic exit)
    mock_orderbook.bids = [mock_bid]
    
    strategy.order_book_analyzer.get_order_book.return_value = mock_orderbook
    
    # Get exit price
    exit_price = await strategy._get_exit_price(test_position, test_market)
    
    # Should use orderbook best bid, not mid price
    assert exit_price == Decimal("0.51")
    assert exit_price != test_market.up_price  # Not using mid price
    
    # Verify orderbook was fetched with force_refresh
    strategy.order_book_analyzer.get_order_book.assert_called_once_with(
        test_position.token_id,
        force_refresh=True
    )


@pytest.mark.asyncio
async def test_exit_price_falls_back_to_mid_price_when_no_orderbook(strategy, test_position, test_market):
    """Test that exit price falls back to mid price when orderbook unavailable."""
    # Mock orderbook as unavailable (None)
    strategy.order_book_analyzer.get_order_book.return_value = None
    
    # Get exit price
    exit_price = await strategy._get_exit_price(test_position, test_market)
    
    # Should fall back to mid price for UP side
    assert exit_price == test_market.up_price
    assert exit_price == Decimal("0.52")


@pytest.mark.asyncio
async def test_exit_price_falls_back_to_mid_price_for_down_side(strategy, test_market):
    """Test that exit price uses correct mid price for DOWN side."""
    # Create DOWN position
    down_position = Position(
        token_id="test_token_456",
        side="DOWN",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market",
        asset="BTC",
        strategy="latency",
        neg_risk=True,
        highest_price=Decimal("0.50")
    )
    
    # Mock orderbook as unavailable
    strategy.order_book_analyzer.get_order_book.return_value = None
    
    # Get exit price
    exit_price = await strategy._get_exit_price(down_position, test_market)
    
    # Should fall back to mid price for DOWN side
    assert exit_price == test_market.down_price
    assert exit_price == Decimal("0.48")


@pytest.mark.asyncio
async def test_exit_price_returns_none_when_no_data_available(strategy, test_position):
    """Test that exit price returns None when neither orderbook nor market data available."""
    # Mock orderbook as unavailable
    strategy.order_book_analyzer.get_order_book.return_value = None
    
    # Get exit price without market data
    exit_price = await strategy._get_exit_price(test_position, market=None)
    
    # Should return None
    assert exit_price is None


@pytest.mark.asyncio
async def test_exit_price_falls_back_on_orderbook_error(strategy, test_position, test_market):
    """Test that exit price falls back to mid price when orderbook fetch raises error."""
    # Mock orderbook fetch to raise exception
    strategy.order_book_analyzer.get_order_book.side_effect = Exception("API error")
    
    # Get exit price
    exit_price = await strategy._get_exit_price(test_position, test_market)
    
    # Should fall back to mid price despite error
    assert exit_price == test_market.up_price
    assert exit_price == Decimal("0.52")


@pytest.mark.asyncio
async def test_exit_price_returns_none_on_error_without_market(strategy, test_position):
    """Test that exit price returns None on error when no market data for fallback."""
    # Mock orderbook fetch to raise exception
    strategy.order_book_analyzer.get_order_book.side_effect = Exception("API error")
    
    # Get exit price without market data
    exit_price = await strategy._get_exit_price(test_position, market=None)
    
    # Should return None
    assert exit_price is None


@pytest.mark.asyncio
async def test_exit_price_with_empty_orderbook_bids(strategy, test_position, test_market):
    """Test that exit price falls back when orderbook has no bids."""
    # Mock orderbook with empty bids
    mock_orderbook = Mock()
    mock_orderbook.bids = []  # No bids available
    
    strategy.order_book_analyzer.get_order_book.return_value = mock_orderbook
    
    # Get exit price
    exit_price = await strategy._get_exit_price(test_position, test_market)
    
    # Should fall back to mid price
    assert exit_price == test_market.up_price
    assert exit_price == Decimal("0.52")


@pytest.mark.asyncio
async def test_pnl_calculation_uses_realistic_exit_price(strategy, test_position, test_market):
    """Test that P&L calculations use realistic exit prices from orderbook."""
    # Mock orderbook with best bid lower than mid price (realistic scenario)
    mock_orderbook = Mock()
    mock_bid = Mock()
    mock_bid.price = Decimal("0.51")  # Best bid (what we can actually sell for)
    mock_orderbook.bids = [mock_bid]
    
    strategy.order_book_analyzer.get_order_book.return_value = mock_orderbook
    
    # Get exit price
    exit_price = await strategy._get_exit_price(test_position, test_market)
    
    # Calculate P&L
    pnl_pct = (exit_price - test_position.entry_price) / test_position.entry_price
    
    # P&L should be based on realistic exit price (0.51), not mid price (0.52)
    assert exit_price == Decimal("0.51")
    assert pnl_pct == Decimal("0.02")  # 2% profit
    
    # If we used mid price, P&L would be higher (incorrect)
    mid_price_pnl = (test_market.up_price - test_position.entry_price) / test_position.entry_price
    assert mid_price_pnl == Decimal("0.04")  # 4% profit (unrealistic)
    
    # Verify we're using the more conservative (realistic) estimate
    assert pnl_pct < mid_price_pnl


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
