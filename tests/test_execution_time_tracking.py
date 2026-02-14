"""
Test execution time tracking functionality.

Task 5.7: Add execution time tracking
- Track time from signal detection to order placement
- Log execution times for each trade
- Alert if execution time > 1 second
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket


@pytest.fixture
def mock_clob_client():
    """Create a mock CLOB client."""
    client = Mock()
    client.get_balance_allowance = Mock(return_value={
        'balance': '10000000',  # $10 USDC (6 decimals)
        'allowance': '10000000'
    })
    client.create_order = Mock(return_value={'order': 'signed'})
    client.post_order = Mock(return_value={
        'orderID': 'test-order-123',
        'status': 'live',
        'success': True
    })
    return client


@pytest.fixture
def strategy(mock_clob_client):
    """Create a strategy instance for testing."""
    return FifteenMinuteCryptoStrategy(
        clob_client=mock_clob_client,
        trade_size=5.0,
        dry_run=False,
        enable_adaptive_learning=False
    )


@pytest.fixture
def test_market():
    """Create a test market."""
    from datetime import datetime, timezone
    return CryptoMarket(
        market_id="test-market-123",
        question="Will BTC be above $50,000 at 3:15 PM?",
        asset="BTC",
        up_token_id="token-up-123",
        down_token_id="token-down-123",
        up_price=Decimal("0.55"),
        down_price=Decimal("0.45"),
        end_time=datetime(2024, 1, 1, 15, 15, 0, tzinfo=timezone.utc),
        neg_risk=True
    )


def test_execution_time_stats_initialized(strategy):
    """Test that execution time stats are initialized."""
    assert "total_execution_time_ms" in strategy.stats
    assert "slow_executions" in strategy.stats
    assert "avg_execution_time_ms" in strategy.stats
    assert strategy.stats["total_execution_time_ms"] == 0
    assert strategy.stats["slow_executions"] == 0
    assert strategy.stats["avg_execution_time_ms"] == 0


def test_track_execution_time_fast(strategy):
    """Test tracking a fast execution (< 1 second)."""
    # Track a fast execution (500ms)
    strategy._track_execution_time(500.0, "sum_to_one", "BTC")
    
    # Verify stats updated
    assert strategy.stats["total_execution_time_ms"] == 500.0
    assert strategy.stats["slow_executions"] == 0
    assert strategy.stats["avg_execution_time_ms"] == 500.0


def test_track_execution_time_slow(strategy):
    """Test tracking a slow execution (> 1 second)."""
    # Track a slow execution (1500ms)
    strategy._track_execution_time(1500.0, "latency", "ETH")
    
    # Verify stats updated
    assert strategy.stats["total_execution_time_ms"] == 1500.0
    assert strategy.stats["slow_executions"] == 1
    assert strategy.stats["avg_execution_time_ms"] == 1500.0


def test_track_execution_time_average(strategy):
    """Test that average execution time is calculated correctly."""
    # Simulate placing a trade first (to increment trades_placed)
    strategy.stats["trades_placed"] = 1
    
    # Track first execution (500ms)
    strategy._track_execution_time(500.0, "sum_to_one", "BTC")
    assert strategy.stats["avg_execution_time_ms"] == 500.0
    
    # Simulate second trade
    strategy.stats["trades_placed"] = 2
    
    # Track second execution (1500ms)
    strategy._track_execution_time(1500.0, "directional", "ETH")
    
    # Verify average is correct: (500 + 1500) / 2 = 1000
    assert strategy.stats["total_execution_time_ms"] == 2000.0
    assert strategy.stats["avg_execution_time_ms"] == 1000.0


def test_track_execution_time_multiple_slow(strategy):
    """Test tracking multiple slow executions."""
    # Simulate trades
    strategy.stats["trades_placed"] = 3
    
    # Track three slow executions
    strategy._track_execution_time(1200.0, "sum_to_one", "BTC")
    strategy._track_execution_time(1500.0, "latency", "ETH")
    strategy._track_execution_time(800.0, "directional", "SOL")  # Fast one
    
    # Verify slow execution count
    assert strategy.stats["slow_executions"] == 2  # Only first two are > 1000ms
    assert strategy.stats["total_execution_time_ms"] == 3500.0
    assert strategy.stats["avg_execution_time_ms"] == pytest.approx(1166.67, rel=0.01)


@pytest.mark.asyncio
async def test_sum_to_one_tracks_execution_time(strategy, test_market):
    """Test that sum-to-one arbitrage tracks execution time."""
    # Mock orderbook to trigger arbitrage
    with patch.object(strategy.order_book_analyzer, 'get_order_book') as mock_orderbook:
        mock_orderbook.return_value = Mock(
            asks=[Mock(price=Decimal("0.48"), size=100)]
        )
        
        # Mock other dependencies
        with patch.object(strategy, '_has_min_time_to_close', return_value=True), \
             patch.object(strategy, '_should_take_trade', return_value=(True, 90.0, "approved")), \
             patch.object(strategy, '_check_daily_limit', return_value=True), \
             patch.object(strategy, '_check_asset_exposure', return_value=True), \
             patch.object(strategy, '_calculate_position_size', return_value=Decimal("5.0")), \
             patch.object(strategy, '_verify_liquidity_before_entry', new_callable=AsyncMock, return_value=(True, "ok")), \
             patch.object(strategy, '_place_order', new_callable=AsyncMock, return_value=True):
            
            # Execute sum-to-one check
            result = await strategy.check_sum_to_one_arbitrage(test_market)
            
            # Verify execution time was tracked
            assert result is True
            assert strategy.stats["total_execution_time_ms"] > 0
            assert strategy.stats["avg_execution_time_ms"] > 0


@pytest.mark.asyncio
async def test_latency_arbitrage_tracks_execution_time(strategy, test_market):
    """Test that latency arbitrage tracks execution time."""
    # Mock multi-timeframe signal
    with patch.object(strategy.multi_tf_analyzer, 'get_multi_timeframe_signal', return_value=("bullish", 50.0, {})), \
         patch.object(strategy.success_tracker, 'should_trade', return_value=(True, 80.0, "approved")), \
         patch.object(strategy, '_has_min_time_to_close', return_value=True), \
         patch.object(strategy, '_should_take_trade', return_value=(True, 90.0, "approved")), \
         patch.object(strategy, '_check_daily_limit', return_value=True), \
         patch.object(strategy, '_check_asset_exposure', return_value=True), \
         patch.object(strategy, '_calculate_position_size', return_value=Decimal("5.0")), \
         patch.object(strategy, '_verify_liquidity_before_entry', new_callable=AsyncMock, return_value=(True, "ok")), \
         patch.object(strategy, '_place_order', new_callable=AsyncMock, return_value=True):
        
        # Execute latency check
        result = await strategy.check_latency_arbitrage(test_market)
        
        # Verify execution time was tracked
        assert result is True
        assert strategy.stats["total_execution_time_ms"] > 0
        assert strategy.stats["avg_execution_time_ms"] > 0


@pytest.mark.asyncio
async def test_directional_trade_tracks_execution_time(strategy, test_market):
    """Test that directional trading tracks execution time."""
    # Mock LLM decision engine
    strategy.llm_decision_engine = Mock()
    
    # Mock ensemble decision
    mock_decision = Mock(
        action="buy_yes",
        confidence=75.0,
        reasoning="Test reasoning"
    )
    
    with patch.object(strategy.ensemble_engine, 'make_decision', new_callable=AsyncMock, return_value=mock_decision), \
         patch.object(strategy, '_has_min_time_to_close', return_value=True), \
         patch.object(strategy.binance_feed, 'get_price_change', return_value=Decimal("0.002")), \
         patch.object(strategy, '_check_circuit_breaker', return_value=True), \
         patch.object(strategy, '_check_daily_loss_limit', return_value=True), \
         patch.object(strategy, '_check_daily_limit', return_value=True), \
         patch.object(strategy, '_check_asset_exposure', return_value=True), \
         patch.object(strategy, '_calculate_position_size', return_value=Decimal("5.0")), \
         patch.object(strategy, '_verify_liquidity_before_entry', new_callable=AsyncMock, return_value=(True, "ok")), \
         patch.object(strategy, '_place_order', new_callable=AsyncMock, return_value=True):
        
        # Execute directional check
        result = await strategy.check_directional_trade(test_market)
        
        # Verify execution time was tracked
        assert result is True
        assert strategy.stats["total_execution_time_ms"] > 0
        assert strategy.stats["avg_execution_time_ms"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
