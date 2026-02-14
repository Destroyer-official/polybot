"""
Test Task 2.2: Orderbook fallback logic and tracking.

Verifies:
1. Fallback to mid prices when orderbook unavailable
2. Logging when using fallback vs actual orderbook prices
3. Tracking success rate of orderbook-based vs fallback trades
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position


@pytest.fixture
def strategy():
    """Create a test strategy instance."""
    with patch('src.fifteen_min_crypto_strategy.ClobClient'):
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=Mock(),
            trade_size=Decimal("5.0"),
            take_profit_pct=Decimal("0.02"),
            stop_loss_pct=Decimal("0.02"),
            max_positions=5,
            dry_run=True
        )
        return strategy


@pytest.mark.asyncio
async def test_orderbook_fallback_to_mid_price(strategy):
    """Test that strategy falls back to mid prices when orderbook unavailable."""
    # Create a mock market with prices that trigger arbitrage
    market = Mock()
    market.asset = "BTC"
    market.up_token_id = "test_up_token"
    market.down_token_id = "test_down_token"
    market.up_price = Decimal("0.45")  # Lower prices to trigger arbitrage
    market.down_price = Decimal("0.50")  # 0.45 + 0.50 = 0.95 < 1.02
    market.question = "Will BTC go up?"
    market.end_time = datetime.now(timezone.utc)
    market.market_id = "test_market"
    
    # Mock orderbook analyzer to return None (orderbook unavailable)
    strategy.order_book_analyzer = Mock()
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=None)
    
    # Mock other dependencies
    strategy._has_min_time_to_close = Mock(return_value=True)
    strategy._check_daily_limit = Mock(return_value=True)
    strategy._check_asset_exposure = Mock(return_value=True)
    strategy._should_take_trade = Mock(return_value=(True, 80.0, "Test approved"))
    strategy.order_book_analyzer.check_liquidity = AsyncMock(return_value=(True, "OK"))
    strategy._place_order = AsyncMock(return_value=True)
    
    # Set sum-to-one threshold to trigger arbitrage
    strategy.sum_to_one_threshold = Decimal("1.02")
    
    # Execute sum-to-one check
    result = await strategy.check_sum_to_one_arbitrage(market)
    
    # Verify fallback was used
    assert result == True, "Should execute trade with fallback prices"
    
    # Verify _place_order was called with used_orderbook=False
    assert strategy._place_order.call_count == 2  # UP and DOWN
    for call in strategy._place_order.call_args_list:
        assert call.kwargs['used_orderbook'] == False, "Should indicate fallback was used"


@pytest.mark.asyncio
async def test_orderbook_used_when_available(strategy):
    """Test that strategy uses orderbook prices when available."""
    # Create a mock market
    market = Mock()
    market.asset = "BTC"
    market.up_token_id = "test_up_token"
    market.down_token_id = "test_down_token"
    market.up_price = Decimal("0.48")
    market.down_price = Decimal("0.52")
    market.question = "Will BTC go up?"
    market.end_time = datetime.now(timezone.utc)
    market.market_id = "test_market"
    
    # Mock orderbook analyzer to return orderbook data
    mock_orderbook = Mock()
    mock_ask = Mock()
    mock_ask.price = Decimal("0.47")  # Better price than mid
    mock_orderbook.asks = [mock_ask]
    
    strategy.order_book_analyzer = Mock()
    strategy.order_book_analyzer.get_order_book = AsyncMock(return_value=mock_orderbook)
    
    # Mock other dependencies
    strategy._has_min_time_to_close = Mock(return_value=True)
    strategy._check_daily_limit = Mock(return_value=True)
    strategy._check_asset_exposure = Mock(return_value=True)
    strategy._should_take_trade = Mock(return_value=(True, 80.0, "Test approved"))
    strategy.order_book_analyzer.check_liquidity = AsyncMock(return_value=(True, "OK"))
    strategy._place_order = AsyncMock(return_value=True)
    
    # Set sum-to-one threshold to trigger arbitrage
    strategy.sum_to_one_threshold = Decimal("1.02")
    
    # Execute sum-to-one check
    result = await strategy.check_sum_to_one_arbitrage(market)
    
    # Verify orderbook was used
    assert result == True, "Should execute trade with orderbook prices"
    
    # Verify _place_order was called with used_orderbook=True
    assert strategy._place_order.call_count == 2  # UP and DOWN
    for call in strategy._place_order.call_args_list:
        assert call.kwargs['used_orderbook'] == True, "Should indicate orderbook was used"


def test_track_exit_outcome_orderbook_win(strategy):
    """Test tracking of orderbook-based winning trade."""
    position = Position(
        token_id="test_token",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market",
        asset="BTC",
        strategy="sum_to_one",
        used_orderbook_entry=True
    )
    
    # Track a winning exit using orderbook
    strategy._track_exit_outcome(position, used_orderbook_exit=True, is_win=True)
    
    # Verify stats
    assert strategy.stats["orderbook_exits"] == 1
    assert strategy.stats["orderbook_wins"] == 1
    assert strategy.stats["orderbook_losses"] == 0
    assert strategy.stats["fallback_exits"] == 0


def test_track_exit_outcome_fallback_loss(strategy):
    """Test tracking of fallback-based losing trade."""
    position = Position(
        token_id="test_token",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market",
        asset="BTC",
        strategy="sum_to_one",
        used_orderbook_entry=False
    )
    
    # Track a losing exit using fallback
    strategy._track_exit_outcome(position, used_orderbook_exit=False, is_win=False)
    
    # Verify stats
    assert strategy.stats["fallback_exits"] == 1
    assert strategy.stats["fallback_wins"] == 0
    assert strategy.stats["fallback_losses"] == 1
    assert strategy.stats["orderbook_exits"] == 0


def test_track_exit_outcome_mixed_methods(strategy):
    """Test tracking of trade with mixed entry/exit methods."""
    position = Position(
        token_id="test_token",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market",
        asset="BTC",
        strategy="sum_to_one",
        used_orderbook_entry=True  # Entry used orderbook
    )
    
    # Track a winning exit using fallback (mixed methods)
    strategy._track_exit_outcome(position, used_orderbook_exit=False, is_win=True)
    
    # Verify stats - mixed methods count as fallback
    assert strategy.stats["fallback_exits"] == 1
    assert strategy.stats["fallback_wins"] == 1
    assert strategy.stats["orderbook_exits"] == 0


def test_log_orderbook_stats(strategy):
    """Test that orderbook stats are logged correctly."""
    import logging
    
    # Set up some test data
    strategy.stats["orderbook_entries"] = 10
    strategy.stats["fallback_entries"] = 5
    strategy.stats["orderbook_exits"] = 8
    strategy.stats["fallback_exits"] = 7
    strategy.stats["orderbook_wins"] = 6
    strategy.stats["orderbook_losses"] = 2
    strategy.stats["fallback_wins"] = 3
    strategy.stats["fallback_losses"] = 4
    
    # Capture logs manually
    with patch('src.fifteen_min_crypto_strategy.logger') as mock_logger:
        # Log stats
        strategy.log_orderbook_stats()
        
        # Verify logging occurred
        assert mock_logger.info.called, "Logger should be called"
        
        # Check that key messages were logged
        log_messages = [call.args[0] for call in mock_logger.info.call_args_list]
        log_text = " ".join(log_messages)
        
        assert "ORDERBOOK VS FALLBACK STATISTICS" in log_text
        assert "ENTRY METHOD:" in log_text
        assert "EXIT METHOD:" in log_text
        assert "WIN RATE COMPARISON:" in log_text


def test_stats_initialization(strategy):
    """Test that orderbook tracking stats are initialized."""
    assert "orderbook_entries" in strategy.stats
    assert "fallback_entries" in strategy.stats
    assert "orderbook_exits" in strategy.stats
    assert "fallback_exits" in strategy.stats
    assert "orderbook_wins" in strategy.stats
    assert "orderbook_losses" in strategy.stats
    assert "fallback_wins" in strategy.stats
    assert "fallback_losses" in strategy.stats
    
    # Verify all initialized to 0
    assert strategy.stats["orderbook_entries"] == 0
    assert strategy.stats["fallback_entries"] == 0
    assert strategy.stats["orderbook_exits"] == 0
    assert strategy.stats["fallback_exits"] == 0
    assert strategy.stats["orderbook_wins"] == 0
    assert strategy.stats["orderbook_losses"] == 0
    assert strategy.stats["fallback_wins"] == 0
    assert strategy.stats["fallback_losses"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
