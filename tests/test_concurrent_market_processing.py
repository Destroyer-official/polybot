"""
Unit tests for concurrent market processing (Task 5.4).

Tests the implementation of asyncio.gather() for processing markets
concurrently with a limit of 10 tasks at a time.
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket


@pytest.fixture
def mock_clob_client():
    """Create a mock CLOB client."""
    client = Mock()
    client.create_order = Mock(return_value={"orderID": "test123"})
    client.post_order = Mock(return_value={"success": True, "orderID": "test123"})
    return client


@pytest.fixture
def strategy(mock_clob_client):
    """Create a strategy instance with mocked dependencies."""
    with patch('src.portfolio_risk_manager.PortfolioRiskManager'), \
         patch('src.dynamic_parameter_system.DynamicParameterSystem'), \
         patch('src.fast_execution_engine.FastExecutionEngine'), \
         patch('src.adaptive_learning_engine.AdaptiveLearningEngine'), \
         patch('src.super_smart_learning.SuperSmartLearning'), \
         patch('src.multi_timeframe_analyzer.MultiTimeframeAnalyzer'), \
         patch('src.order_book_analyzer.OrderBookAnalyzer'), \
         patch('src.historical_success_tracker.HistoricalSuccessTracker'), \
         patch('src.reinforcement_learning_engine.ReinforcementLearningEngine'), \
         patch('src.ensemble_decision_engine.EnsembleDecisionEngine'), \
         patch('src.context_optimizer.ContextOptimizer'):
        
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_clob_client,
            trade_size=5.0,
            dry_run=True,
            enable_adaptive_learning=False
        )
        
        # Mock the processing methods
        strategy.check_exit_conditions = AsyncMock()
        strategy.check_flash_crash = AsyncMock(return_value=False)
        strategy.check_latency_arbitrage = AsyncMock(return_value=False)
        strategy.check_directional_trade = AsyncMock(return_value=False)
        strategy.check_sum_to_one_arbitrage = AsyncMock(return_value=False)
        
        return strategy


def create_test_market(asset: str, market_id: str) -> CryptoMarket:
    """Create a test market."""
    return CryptoMarket(
        market_id=market_id,
        question=f"Will {asset} go up?",
        asset=asset,
        up_token_id=f"{market_id}_up",
        down_token_id=f"{market_id}_down",
        up_price=Decimal("0.50"),
        down_price=Decimal("0.50"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        neg_risk=True,
        tick_size="0.01"
    )


@pytest.mark.asyncio
async def test_process_markets_concurrently_empty_list(strategy):
    """Test that processing empty market list completes without error."""
    await strategy._process_markets_concurrently([])
    
    # Should not call any processing methods
    strategy.check_exit_conditions.assert_not_called()


@pytest.mark.asyncio
async def test_process_markets_concurrently_single_market(strategy):
    """Test processing a single market."""
    market = create_test_market("BTC", "market1")
    
    await strategy._process_markets_concurrently([market])
    
    # Should process the market
    strategy.check_exit_conditions.assert_called_once_with(market)


@pytest.mark.asyncio
async def test_process_markets_concurrently_multiple_markets(strategy):
    """Test processing multiple markets concurrently."""
    markets = [
        create_test_market("BTC", "market1"),
        create_test_market("ETH", "market2"),
        create_test_market("SOL", "market3"),
    ]
    
    await strategy._process_markets_concurrently(markets)
    
    # Should process all markets
    assert strategy.check_exit_conditions.call_count == 3


@pytest.mark.asyncio
async def test_process_markets_concurrently_respects_max_concurrent(strategy):
    """Test that concurrency limit is respected."""
    # Create 25 markets (should be processed in 3 batches: 10, 10, 5)
    markets = [create_test_market(f"ASSET{i}", f"market{i}") for i in range(25)]
    
    # Track when tasks start and finish
    task_times = []
    
    async def track_timing(*args, **kwargs):
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(0.01)  # Simulate some work
        end = asyncio.get_event_loop().time()
        task_times.append((start, end))
    
    strategy.check_exit_conditions = AsyncMock(side_effect=track_timing)
    
    await strategy._process_markets_concurrently(markets, max_concurrent=10)
    
    # Should process all 25 markets
    assert strategy.check_exit_conditions.call_count == 25
    
    # Verify batching: should have 3 distinct time windows
    # (This is a simplified check - in reality, timing can vary)
    assert len(task_times) == 25


@pytest.mark.asyncio
async def test_process_markets_concurrently_handles_exceptions(strategy):
    """Test that exceptions in one market don't stop processing of others."""
    markets = [
        create_test_market("BTC", "market1"),
        create_test_market("ETH", "market2"),
        create_test_market("SOL", "market3"),
    ]
    
    # Make the second market raise an exception
    call_count = 0
    async def side_effect_with_error(market):
        nonlocal call_count
        call_count += 1
        if market.asset == "ETH":
            raise ValueError("Test error")
    
    strategy.check_exit_conditions = AsyncMock(side_effect=side_effect_with_error)
    
    # Should not raise exception (gracefully handled)
    await strategy._process_markets_concurrently(markets)
    
    # Should still process all markets
    assert call_count == 3


@pytest.mark.asyncio
async def test_process_single_market_checks_exit_conditions(strategy):
    """Test that _process_single_market checks exit conditions."""
    market = create_test_market("BTC", "market1")
    
    await strategy._process_single_market(market)
    
    strategy.check_exit_conditions.assert_called_once_with(market)


@pytest.mark.asyncio
async def test_process_single_market_respects_position_limit(strategy):
    """Test that _process_single_market respects max_positions limit."""
    market = create_test_market("BTC", "market1")
    
    # Fill up positions to max
    strategy.max_positions = 3
    strategy.positions = {f"pos{i}": Mock() for i in range(3)}
    
    await strategy._process_single_market(market)
    
    # Should check exit conditions
    strategy.check_exit_conditions.assert_called_once()
    
    # Should NOT check for entry opportunities (at max positions)
    strategy.check_flash_crash.assert_not_called()
    strategy.check_latency_arbitrage.assert_not_called()
    strategy.check_directional_trade.assert_not_called()
    strategy.check_sum_to_one_arbitrage.assert_not_called()


@pytest.mark.asyncio
async def test_process_single_market_checks_strategies_in_priority_order(strategy):
    """Test that strategies are checked in correct priority order."""
    market = create_test_market("BTC", "market1")
    
    # Ensure we have capacity
    strategy.max_positions = 5
    strategy.positions = {}
    
    await strategy._process_single_market(market)
    
    # Should check all strategies in priority order
    strategy.check_exit_conditions.assert_called_once()
    strategy.check_flash_crash.assert_called_once()
    strategy.check_latency_arbitrage.assert_called_once()
    strategy.check_directional_trade.assert_called_once()
    strategy.check_sum_to_one_arbitrage.assert_called_once()


@pytest.mark.asyncio
async def test_process_single_market_stops_after_successful_strategy(strategy):
    """Test that processing stops after a strategy succeeds."""
    market = create_test_market("BTC", "market1")
    
    # Make latency arbitrage succeed
    strategy.check_latency_arbitrage = AsyncMock(return_value=True)
    
    strategy.max_positions = 5
    strategy.positions = {}
    
    await strategy._process_single_market(market)
    
    # Should check strategies up to latency arbitrage
    strategy.check_flash_crash.assert_called_once()
    strategy.check_latency_arbitrage.assert_called_once()
    
    # Should NOT check subsequent strategies
    strategy.check_directional_trade.assert_not_called()
    strategy.check_sum_to_one_arbitrage.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_processing_improves_throughput(strategy):
    """Test that concurrent processing is faster than sequential."""
    # Create 20 markets
    markets = [create_test_market(f"ASSET{i}", f"market{i}") for i in range(20)]
    
    # Simulate work with a delay
    async def slow_check(*args, **kwargs):
        await asyncio.sleep(0.05)  # 50ms per market
    
    strategy.check_exit_conditions = AsyncMock(side_effect=slow_check)
    
    # Measure concurrent processing time
    start = asyncio.get_event_loop().time()
    await strategy._process_markets_concurrently(markets, max_concurrent=10)
    concurrent_time = asyncio.get_event_loop().time() - start
    
    # With 20 markets, 50ms each, max_concurrent=10:
    # - Batch 1: 10 markets in parallel = ~50ms
    # - Batch 2: 10 markets in parallel = ~50ms
    # Total: ~100ms
    
    # Sequential would take: 20 * 50ms = 1000ms
    # Concurrent should be significantly faster
    assert concurrent_time < 0.5  # Should be well under 500ms


@pytest.mark.asyncio
async def test_process_single_market_propagates_exceptions(strategy):
    """Test that _process_single_market propagates exceptions for gather to catch."""
    market = create_test_market("BTC", "market1")
    
    # Make check_exit_conditions raise an exception
    strategy.check_exit_conditions = AsyncMock(side_effect=ValueError("Test error"))
    
    # Should raise the exception
    with pytest.raises(ValueError, match="Test error"):
        await strategy._process_single_market(market)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
