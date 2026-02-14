"""
Simple integration test for concurrent market processing (Task 5.4).

Tests the concurrent processing methods directly without complex mocking.
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from src.fifteen_min_crypto_strategy import CryptoMarket


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
async def test_process_markets_concurrently_batching():
    """Test that markets are processed in batches with correct concurrency limit."""
    # Create a mock strategy object with just the methods we need
    strategy = MagicMock()
    strategy.positions = {}
    strategy.max_positions = 10
    
    # Track concurrent execution
    active_tasks = []
    max_concurrent = 0
    
    async def mock_process(market):
        """Mock processing that tracks concurrency."""
        nonlocal max_concurrent
        active_tasks.append(market.asset)
        max_concurrent = max(max_concurrent, len(active_tasks))
        await asyncio.sleep(0.01)  # Simulate work
        active_tasks.remove(market.asset)
    
    # Import the actual methods
    from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
    
    # Bind methods to our mock
    strategy._process_single_market = mock_process
    strategy._process_markets_concurrently = FifteenMinuteCryptoStrategy._process_markets_concurrently.__get__(strategy)
    
    # Create 25 markets (should be processed in 3 batches: 10, 10, 5)
    markets = [create_test_market(f"ASSET{i}", f"market{i}") for i in range(25)]
    
    # Process with max_concurrent=10
    await strategy._process_markets_concurrently(markets, max_concurrent=10)
    
    # Verify max concurrent tasks never exceeded 10
    assert max_concurrent <= 10, f"Max concurrent tasks was {max_concurrent}, expected <= 10"
    print(f"✅ Max concurrent tasks: {max_concurrent} (limit: 10)")


@pytest.mark.asyncio
async def test_process_markets_concurrently_exception_handling():
    """Test that exceptions in one market don't stop processing of others."""
    strategy = MagicMock()
    strategy.positions = {}
    strategy.max_positions = 10
    
    processed = []
    errors = []
    
    async def mock_process(market):
        """Mock processing that raises exception for specific market."""
        if market.asset == "ASSET5":
            errors.append(market.asset)
            raise ValueError(f"Test error for {market.asset}")
        processed.append(market.asset)
        await asyncio.sleep(0.001)
    
    # Import and bind methods
    from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
    strategy._process_single_market = mock_process
    strategy._process_markets_concurrently = FifteenMinuteCryptoStrategy._process_markets_concurrently.__get__(strategy)
    
    # Create 10 markets
    markets = [create_test_market(f"ASSET{i}", f"market{i}") for i in range(10)]
    
    # Process (should not raise exception)
    await strategy._process_markets_concurrently(markets, max_concurrent=5)
    
    # Verify all markets were attempted (9 succeeded, 1 failed)
    assert len(processed) == 9, f"Expected 9 processed, got {len(processed)}"
    assert len(errors) == 1, f"Expected 1 error, got {len(errors)}"
    assert "ASSET5" in errors
    print(f"✅ Processed {len(processed)} markets, {len(errors)} errors (gracefully handled)")


@pytest.mark.asyncio
async def test_concurrent_vs_sequential_performance():
    """Test that concurrent processing is faster than sequential."""
    strategy = MagicMock()
    
    async def slow_process(market):
        """Simulate slow processing."""
        await asyncio.sleep(0.05)  # 50ms per market
    
    # Import and bind methods
    from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
    strategy._process_single_market = slow_process
    strategy._process_markets_concurrently = FifteenMinuteCryptoStrategy._process_markets_concurrently.__get__(strategy)
    
    # Create 20 markets
    markets = [create_test_market(f"ASSET{i}", f"market{i}") for i in range(20)]
    
    # Measure concurrent processing (max_concurrent=10)
    start = asyncio.get_event_loop().time()
    await strategy._process_markets_concurrently(markets, max_concurrent=10)
    concurrent_time = asyncio.get_event_loop().time() - start
    
    # With 20 markets, 50ms each, max_concurrent=10:
    # - Batch 1: 10 markets in parallel = ~50ms
    # - Batch 2: 10 markets in parallel = ~50ms
    # Total: ~100ms (plus overhead)
    
    # Sequential would take: 20 * 50ms = 1000ms
    # Concurrent should be significantly faster
    assert concurrent_time < 0.5, f"Concurrent took {concurrent_time:.3f}s, expected < 0.5s"
    
    # Calculate speedup
    sequential_estimate = 20 * 0.05  # 1.0 second
    speedup = sequential_estimate / concurrent_time
    print(f"✅ Concurrent processing speedup: {speedup:.1f}x faster")
    print(f"   Concurrent: {concurrent_time:.3f}s, Sequential estimate: {sequential_estimate:.3f}s")


@pytest.mark.asyncio
async def test_empty_market_list():
    """Test that empty market list is handled gracefully."""
    strategy = MagicMock()
    
    from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
    strategy._process_markets_concurrently = FifteenMinuteCryptoStrategy._process_markets_concurrently.__get__(strategy)
    
    # Should complete without error
    await strategy._process_markets_concurrently([])
    print("✅ Empty market list handled gracefully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
