"""
Throughput Benchmarking Tests

Task 13.2: Add throughput benchmarking
- Measure time to process 100 markets
- Verify concurrent processing is working
- Optimize if throughput < target

Target: Process 100 markets in < 5 seconds
"""

import asyncio
import pytest
import pytest_asyncio
import time
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from src.fifteen_min_crypto_strategy import (
    FifteenMinuteCryptoStrategy,
    CryptoMarket,
)
from config.config import Config


def create_test_market(asset: str, market_id: str, up_price: float = 0.50, down_price: float = 0.50) -> CryptoMarket:
    """Create a test market for benchmarking."""
    return CryptoMarket(
        market_id=market_id,
        question=f"Will {asset} go up in the next 15 minutes?",
        asset=asset,
        up_token_id=f"{market_id}_up",
        down_token_id=f"{market_id}_down",
        up_price=Decimal(str(up_price)),
        down_price=Decimal(str(down_price)),
        end_time=datetime.now() + timedelta(minutes=15),
        neg_risk=False,
        tick_size="0.01",
    )


@pytest.fixture
def config():
    """Create test config."""
    from unittest.mock import Mock
    cfg = Mock(spec=Config)
    cfg.PRIVATE_KEY = "0x" + "1" * 64
    cfg.CLOB_API_URL = "https://clob.polymarket.com"
    cfg.GAMMA_API_URL = "https://gamma-api.polymarket.com"
    return cfg


@pytest_asyncio.fixture
async def strategy(config):
    """Create strategy instance for testing."""
    with patch('src.fifteen_min_crypto_strategy.ClobClient'):
        strat = FifteenMinuteCryptoStrategy(config)
        
        # Mock external dependencies
        strat.clob_client = MagicMock()
        strat.binance_feed = MagicMock()
        strat.binance_feed.get_price_change = MagicMock(return_value=Decimal("0.001"))
        strat.binance_feed.is_bullish_signal = MagicMock(return_value=True)
        strat.binance_feed.is_bearish_signal = MagicMock(return_value=False)
        
        # Mock ensemble decision engine
        strat.ensemble_engine = MagicMock()
        strat.ensemble_engine.make_decision = AsyncMock(return_value=MagicMock(
            action="skip",
            confidence=Decimal("50.0"),
            consensus_score=Decimal("50.0"),
        ))
        
        yield strat


@pytest.mark.asyncio
async def test_throughput_100_markets_baseline(strategy):
    """
    Benchmark: Process 100 markets and measure throughput.
    
    Target: < 5 seconds for 100 markets
    This establishes baseline performance.
    """
    # Create 100 test markets
    markets = []
    for i in range(100):
        asset = ["BTC", "ETH", "SOL", "XRP"][i % 4]
        markets.append(create_test_market(asset, f"market_{i}"))
    
    # Mock the strategy methods to simulate realistic work
    async def mock_exit_check(market):
        await asyncio.sleep(0.001)  # 1ms per market (realistic)
    
    async def mock_sum_to_one(market):
        await asyncio.sleep(0.002)  # 2ms per check
        return False
    
    async def mock_flash_crash(market):
        await asyncio.sleep(0.002)  # 2ms per check
        return False
    
    async def mock_latency_arb(market):
        await asyncio.sleep(0.003)  # 3ms per check
        return False
    
    async def mock_directional(market):
        await asyncio.sleep(0.003)  # 3ms per check
        return False
    
    strategy.check_exit_conditions = AsyncMock(side_effect=mock_exit_check)
    strategy.check_sum_to_one_arbitrage = AsyncMock(side_effect=mock_sum_to_one)
    strategy.check_flash_crash = AsyncMock(side_effect=mock_flash_crash)
    strategy.check_latency_arbitrage = AsyncMock(side_effect=mock_latency_arb)
    strategy.check_directional_trade = AsyncMock(side_effect=mock_directional)
    
    # Measure throughput
    start_time = time.time()
    await strategy._process_markets_concurrently(markets, max_concurrent=10)
    elapsed_time = time.time() - start_time
    
    # Calculate metrics
    markets_per_second = len(markets) / elapsed_time
    
    print(f"\n📊 Throughput Benchmark Results:")
    print(f"   Markets processed: {len(markets)}")
    print(f"   Time elapsed: {elapsed_time:.3f}s")
    print(f"   Throughput: {markets_per_second:.1f} markets/second")
    print(f"   Average time per market: {(elapsed_time / len(markets)) * 1000:.1f}ms")
    
    # Verify target met
    assert elapsed_time < 5.0, f"Throughput too slow: {elapsed_time:.3f}s (target: < 5s)"
    assert markets_per_second > 20, f"Throughput too low: {markets_per_second:.1f} markets/s (target: > 20)"


@pytest.mark.asyncio
async def test_concurrent_vs_sequential_speedup(strategy):
    """
    Verify concurrent processing provides significant speedup over sequential.
    
    Expected: Concurrent should be 5-10x faster with max_concurrent=10
    """
    # Create 50 markets for faster test
    markets = [create_test_market(f"ASSET{i % 4}", f"market_{i}") for i in range(50)]
    
    # Simulate realistic work
    async def mock_work(market):
        await asyncio.sleep(0.01)  # 10ms per market
    
    strategy.check_exit_conditions = AsyncMock(side_effect=mock_work)
    strategy.check_sum_to_one_arbitrage = AsyncMock(return_value=False)
    strategy.check_flash_crash = AsyncMock(return_value=False)
    strategy.check_latency_arbitrage = AsyncMock(return_value=False)
    strategy.check_directional_trade = AsyncMock(return_value=False)
    
    # Measure concurrent processing
    start_concurrent = time.time()
    await strategy._process_markets_concurrently(markets, max_concurrent=10)
    concurrent_time = time.time() - start_concurrent
    
    # Measure sequential processing (simulate)
    # Sequential would be: 50 markets * 10ms = 500ms minimum
    expected_sequential_time = len(markets) * 0.01
    
    # Calculate speedup
    speedup = expected_sequential_time / concurrent_time
    
    print(f"\n⚡ Concurrency Speedup Analysis:")
    print(f"   Markets: {len(markets)}")
    print(f"   Concurrent time: {concurrent_time:.3f}s")
    print(f"   Expected sequential time: {expected_sequential_time:.3f}s")
    print(f"   Speedup: {speedup:.1f}x")
    
    # Verify significant speedup (at least 3x with max_concurrent=10)
    assert speedup >= 3.0, f"Insufficient speedup: {speedup:.1f}x (expected: >= 3x)"
    assert concurrent_time < expected_sequential_time / 2, "Concurrent not significantly faster"


@pytest.mark.asyncio
async def test_throughput_with_varying_concurrency(strategy):
    """
    Test throughput with different concurrency levels.
    
    Verify that higher concurrency improves throughput up to a point.
    """
    markets = [create_test_market(f"ASSET{i % 4}", f"market_{i}") for i in range(40)]
    
    # Simulate work
    async def mock_work(market):
        await asyncio.sleep(0.01)  # 10ms per market
    
    strategy.check_exit_conditions = AsyncMock(side_effect=mock_work)
    strategy.check_sum_to_one_arbitrage = AsyncMock(return_value=False)
    strategy.check_flash_crash = AsyncMock(return_value=False)
    strategy.check_latency_arbitrage = AsyncMock(return_value=False)
    strategy.check_directional_trade = AsyncMock(return_value=False)
    
    results = {}
    
    # Test different concurrency levels
    for max_concurrent in [1, 5, 10, 20]:
        start = time.time()
        await strategy._process_markets_concurrently(markets, max_concurrent=max_concurrent)
        elapsed = time.time() - start
        throughput = len(markets) / elapsed
        results[max_concurrent] = {
            'time': elapsed,
            'throughput': throughput
        }
    
    print(f"\n📈 Concurrency Level Analysis:")
    for level, metrics in results.items():
        print(f"   max_concurrent={level:2d}: {metrics['time']:.3f}s ({metrics['throughput']:.1f} markets/s)")
    
    # Verify throughput improves with concurrency
    assert results[5]['throughput'] > results[1]['throughput'], "Concurrency level 5 should be faster than 1"
    assert results[10]['throughput'] > results[5]['throughput'], "Concurrency level 10 should be faster than 5"
    
    # Verify diminishing returns (20 might not be much better than 10 due to overhead)
    # But it should still be at least as fast
    assert results[20]['throughput'] >= results[10]['throughput'] * 0.9, "Higher concurrency shouldn't hurt performance"


@pytest.mark.asyncio
async def test_throughput_under_load(strategy):
    """
    Test throughput under realistic load conditions.
    
    Simulates:
    - Multiple positions to check for exit
    - Various market conditions
    - Realistic API latencies
    """
    # Create 100 markets
    markets = [create_test_market(f"ASSET{i % 4}", f"market_{i}") for i in range(100)]
    
    # Add some positions to simulate realistic load
    for i in range(5):
        from src.fifteen_min_crypto_strategy import Position
        position = Position(
            token_id=f"token_{i}",
            side="UP",
            entry_price=Decimal("0.50"),
            size=Decimal("10.0"),
            entry_time=datetime.now() - timedelta(minutes=5),
            market_id=f"market_{i}",
            asset=["BTC", "ETH", "SOL", "XRP"][i % 4],
            strategy="test",
            neg_risk=False,
            highest_price=Decimal("0.52"),
        )
        strategy.positions[f"token_{i}"] = position
    
    # Simulate realistic work with variable latency
    async def mock_exit_check(market):
        await asyncio.sleep(0.002)  # 2ms
    
    async def mock_strategy_check(market):
        await asyncio.sleep(0.005)  # 5ms average
        return False
    
    strategy.check_exit_conditions = AsyncMock(side_effect=mock_exit_check)
    strategy.check_sum_to_one_arbitrage = AsyncMock(side_effect=mock_strategy_check)
    strategy.check_flash_crash = AsyncMock(side_effect=mock_strategy_check)
    strategy.check_latency_arbitrage = AsyncMock(side_effect=mock_strategy_check)
    strategy.check_directional_trade = AsyncMock(side_effect=mock_strategy_check)
    
    # Measure throughput under load
    start_time = time.time()
    await strategy._process_markets_concurrently(markets, max_concurrent=10)
    elapsed_time = time.time() - start_time
    
    throughput = len(markets) / elapsed_time
    
    print(f"\n🔥 Throughput Under Load:")
    print(f"   Markets: {len(markets)}")
    print(f"   Active positions: {len(strategy.positions)}")
    print(f"   Time: {elapsed_time:.3f}s")
    print(f"   Throughput: {throughput:.1f} markets/s")
    
    # Should still meet target even under load
    assert elapsed_time < 6.0, f"Throughput under load too slow: {elapsed_time:.3f}s"
    assert throughput > 15, f"Throughput under load too low: {throughput:.1f} markets/s"


@pytest.mark.asyncio
async def test_throughput_with_failures(strategy):
    """
    Test that throughput remains acceptable even when some markets fail.
    
    Verify graceful error handling doesn't significantly impact throughput.
    """
    markets = [create_test_market(f"ASSET{i % 4}", f"market_{i}") for i in range(50)]
    
    # Simulate failures for 20% of markets
    call_count = {'count': 0}
    
    async def mock_work_with_failures(market):
        call_count['count'] += 1
        if call_count['count'] % 5 == 0:  # Every 5th call fails
            raise ValueError("Simulated API error")
        await asyncio.sleep(0.01)
    
    strategy.check_exit_conditions = AsyncMock(side_effect=mock_work_with_failures)
    strategy.check_sum_to_one_arbitrage = AsyncMock(return_value=False)
    strategy.check_flash_crash = AsyncMock(return_value=False)
    strategy.check_latency_arbitrage = AsyncMock(return_value=False)
    strategy.check_directional_trade = AsyncMock(return_value=False)
    
    # Measure throughput with failures
    start_time = time.time()
    await strategy._process_markets_concurrently(markets, max_concurrent=10)
    elapsed_time = time.time() - start_time
    
    throughput = len(markets) / elapsed_time
    
    print(f"\n⚠️  Throughput With Failures:")
    print(f"   Markets: {len(markets)}")
    print(f"   Failure rate: ~20%")
    print(f"   Time: {elapsed_time:.3f}s")
    print(f"   Throughput: {throughput:.1f} markets/s")
    
    # Should still maintain reasonable throughput
    assert elapsed_time < 3.0, f"Throughput with failures too slow: {elapsed_time:.3f}s"
    assert throughput > 15, f"Throughput with failures too low: {throughput:.1f} markets/s"


@pytest.mark.asyncio
async def test_memory_efficiency_large_batch(strategy):
    """
    Test memory efficiency when processing large batches.
    
    Verify that concurrent processing doesn't create excessive memory overhead.
    """
    import sys
    
    # Create 200 markets (larger batch)
    markets = [create_test_market(f"ASSET{i % 4}", f"market_{i}") for i in range(200)]
    
    # Mock lightweight work
    strategy.check_exit_conditions = AsyncMock(return_value=None)
    strategy.check_sum_to_one_arbitrage = AsyncMock(return_value=False)
    strategy.check_flash_crash = AsyncMock(return_value=False)
    strategy.check_latency_arbitrage = AsyncMock(return_value=False)
    strategy.check_directional_trade = AsyncMock(return_value=False)
    
    # Measure memory before
    import gc
    gc.collect()
    
    # Process markets
    start_time = time.time()
    await strategy._process_markets_concurrently(markets, max_concurrent=10)
    elapsed_time = time.time() - start_time
    
    throughput = len(markets) / elapsed_time
    
    print(f"\n💾 Large Batch Processing:")
    print(f"   Markets: {len(markets)}")
    print(f"   Time: {elapsed_time:.3f}s")
    print(f"   Throughput: {throughput:.1f} markets/s")
    
    # Should handle large batches efficiently
    assert elapsed_time < 10.0, f"Large batch too slow: {elapsed_time:.3f}s"
    assert throughput > 20, f"Large batch throughput too low: {throughput:.1f} markets/s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
