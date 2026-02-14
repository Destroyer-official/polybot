"""
Property-based tests for Concurrent Market Processing.

Tests correctness properties for:
- Property 27: Concurrent Market Processing (Requirement 5.4)

**Validates: Requirements 5.4**
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket


# ============================================================================
# Helper Strategies
# ============================================================================

@st.composite
def crypto_market_strategy(draw):
    """Generate a CryptoMarket for testing."""
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    market_id = str(uuid.uuid4())
    
    return CryptoMarket(
        market_id=market_id,
        question=f"Will {asset} go up in 15 minutes?",
        asset=asset,
        up_token_id=f"{market_id}_up",
        down_token_id=f"{market_id}_down",
        up_price=draw(st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=2)),
        down_price=draw(st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.99"), places=2)),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        neg_risk=draw(st.booleans()),
        tick_size="0.01"
    )


# ============================================================================
# PROPERTY 27: CONCURRENT MARKET PROCESSING
# ============================================================================

class TestConcurrentMarketProcessing:
    """
    Property 27: Concurrent Market Processing
    
    **Validates: Requirements 5.4**
    
    For any batch of markets, the system should:
    1. Use asyncio.gather() for concurrent processing (not sequential loops)
    2. Process all markets in the batch
    3. Respect the concurrency limit (max 10 concurrent tasks)
    4. Handle exceptions gracefully (one failure doesn't stop others)
    """
    
    @given(
        num_markets=st.integers(min_value=1, max_value=50),
        max_concurrent=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50, deadline=5000)
    @pytest.mark.asyncio
    async def test_property_27_all_markets_processed(self, num_markets, max_concurrent):
        """
        **Validates: Requirements 5.4**
        
        Property 27: Concurrent Market Processing - All Markets Processed
        
        For any batch of N markets with concurrency limit M, all N markets
        should be processed exactly once, regardless of the batch size or
        concurrency limit.
        
        This property verifies that:
        1. Every market in the batch is processed
        2. No market is processed more than once
        3. Processing completes successfully
        """
        # Create mock strategy
        strategy = MagicMock()
        strategy.positions = {}
        strategy.max_positions = 10
        
        # Track which markets were processed
        processed_markets = []
        
        async def mock_process(market):
            """Mock processing that tracks which markets are processed."""
            processed_markets.append(market.market_id)
            await asyncio.sleep(0.001)  # Simulate minimal work
        
        # Bind the actual concurrent processing method
        strategy._process_single_market = mock_process
        strategy._process_markets_concurrently = (
            FifteenMinuteCryptoStrategy._process_markets_concurrently.__get__(strategy)
        )
        
        # Generate test markets
        markets = []
        for i in range(num_markets):
            market = CryptoMarket(
                market_id=f"market_{i}",
                question=f"Test market {i}",
                asset="BTC",
                up_token_id=f"up_{i}",
                down_token_id=f"down_{i}",
                up_price=Decimal("0.50"),
                down_price=Decimal("0.50"),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
                neg_risk=True,
                tick_size="0.01"
            )
            markets.append(market)
        
        # Process markets concurrently
        await strategy._process_markets_concurrently(markets, max_concurrent=max_concurrent)
        
        # PROPERTY: All markets should be processed exactly once
        assert len(processed_markets) == num_markets, (
            f"Expected {num_markets} markets to be processed, "
            f"but {len(processed_markets)} were processed"
        )
        
        # PROPERTY: No duplicates (each market processed exactly once)
        assert len(set(processed_markets)) == num_markets, (
            f"Some markets were processed multiple times: "
            f"{len(processed_markets)} total, {len(set(processed_markets))} unique"
        )
        
        # PROPERTY: All original market IDs are present
        expected_ids = {m.market_id for m in markets}
        actual_ids = set(processed_markets)
        assert expected_ids == actual_ids, (
            f"Market IDs mismatch. Missing: {expected_ids - actual_ids}, "
            f"Extra: {actual_ids - expected_ids}"
        )
    
    @given(
        num_markets=st.integers(min_value=5, max_value=30),
        max_concurrent=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=30, deadline=5000)
    @pytest.mark.asyncio
    async def test_property_27_concurrency_limit_respected(self, num_markets, max_concurrent):
        """
        **Validates: Requirements 5.4**
        
        Property 27: Concurrent Market Processing - Concurrency Limit
        
        For any batch of markets with concurrency limit M, the number of
        simultaneously executing tasks should never exceed M.
        
        This property verifies that:
        1. asyncio.gather() is used (enables concurrent execution)
        2. Concurrency limit is enforced
        3. Tasks are batched appropriately
        """
        # Skip if max_concurrent >= num_markets (no batching needed)
        assume(num_markets > max_concurrent)
        
        strategy = MagicMock()
        strategy.positions = {}
        
        # Track concurrent execution
        active_tasks = []
        max_concurrent_observed = 0
        lock = asyncio.Lock()
        
        async def mock_process(market):
            """Mock processing that tracks concurrency."""
            nonlocal max_concurrent_observed
            
            async with lock:
                active_tasks.append(market.market_id)
                current_concurrent = len(active_tasks)
                max_concurrent_observed = max(max_concurrent_observed, current_concurrent)
            
            # Simulate work
            await asyncio.sleep(0.01)
            
            async with lock:
                active_tasks.remove(market.market_id)
        
        # Bind methods
        strategy._process_single_market = mock_process
        strategy._process_markets_concurrently = (
            FifteenMinuteCryptoStrategy._process_markets_concurrently.__get__(strategy)
        )
        
        # Generate test markets
        markets = []
        for i in range(num_markets):
            market = CryptoMarket(
                market_id=f"market_{i}",
                question=f"Test market {i}",
                asset="BTC",
                up_token_id=f"up_{i}",
                down_token_id=f"down_{i}",
                up_price=Decimal("0.50"),
                down_price=Decimal("0.50"),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
                neg_risk=True,
                tick_size="0.01"
            )
            markets.append(market)
        
        # Process markets concurrently
        await strategy._process_markets_concurrently(markets, max_concurrent=max_concurrent)
        
        # PROPERTY: Concurrency limit should never be exceeded
        assert max_concurrent_observed <= max_concurrent, (
            f"Concurrency limit violated: observed {max_concurrent_observed} "
            f"concurrent tasks, limit was {max_concurrent}"
        )
        
        # PROPERTY: Should actually use concurrency (not sequential)
        # If we have more markets than the limit, we should see concurrent execution
        assert max_concurrent_observed > 1, (
            f"Expected concurrent execution, but only {max_concurrent_observed} "
            f"task(s) ran concurrently (sequential execution detected)"
        )
    
    @given(
        num_markets=st.integers(min_value=5, max_value=20),
        num_failures=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=30, deadline=5000)
    @pytest.mark.asyncio
    async def test_property_27_exception_handling(self, num_markets, num_failures):
        """
        **Validates: Requirements 5.4**
        
        Property 27: Concurrent Market Processing - Exception Handling
        
        For any batch of markets where some processing fails, the system
        should continue processing remaining markets and not propagate
        exceptions to the caller.
        
        This property verifies that:
        1. Exceptions in one market don't stop processing of others
        2. All markets are attempted (including those after failures)
        3. The method completes successfully despite exceptions
        """
        # Ensure we have more markets than failures
        assume(num_failures < num_markets)
        
        strategy = MagicMock()
        strategy.positions = {}
        
        # Track processing
        processed_successfully = []
        failed_markets = []
        failure_indices = set(range(0, num_failures))  # First N markets will fail
        
        async def mock_process(market):
            """Mock processing that fails for specific markets."""
            market_index = int(market.market_id.split("_")[1])
            
            if market_index in failure_indices:
                failed_markets.append(market.market_id)
                raise ValueError(f"Simulated failure for {market.market_id}")
            
            processed_successfully.append(market.market_id)
            await asyncio.sleep(0.001)
        
        # Bind methods
        strategy._process_single_market = mock_process
        strategy._process_markets_concurrently = (
            FifteenMinuteCryptoStrategy._process_markets_concurrently.__get__(strategy)
        )
        
        # Generate test markets
        markets = []
        for i in range(num_markets):
            market = CryptoMarket(
                market_id=f"market_{i}",
                question=f"Test market {i}",
                asset="BTC",
                up_token_id=f"up_{i}",
                down_token_id=f"down_{i}",
                up_price=Decimal("0.50"),
                down_price=Decimal("0.50"),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
                neg_risk=True,
                tick_size="0.01"
            )
            markets.append(market)
        
        # Process markets concurrently (should NOT raise exception)
        await strategy._process_markets_concurrently(markets, max_concurrent=10)
        
        # PROPERTY: All markets should be attempted
        total_attempted = len(processed_successfully) + len(failed_markets)
        assert total_attempted == num_markets, (
            f"Expected {num_markets} markets to be attempted, "
            f"but only {total_attempted} were attempted"
        )
        
        # PROPERTY: Correct number of failures
        assert len(failed_markets) == num_failures, (
            f"Expected {num_failures} failures, but got {len(failed_markets)}"
        )
        
        # PROPERTY: Correct number of successes
        expected_successes = num_markets - num_failures
        assert len(processed_successfully) == expected_successes, (
            f"Expected {expected_successes} successful processes, "
            f"but got {len(processed_successfully)}"
        )
    
    @given(
        num_markets=st.integers(min_value=0, max_value=5)
    )
    @settings(max_examples=10, deadline=2000)
    @pytest.mark.asyncio
    async def test_property_27_empty_and_small_batches(self, num_markets):
        """
        **Validates: Requirements 5.4**
        
        Property 27: Concurrent Market Processing - Edge Cases
        
        For edge cases (empty list, single market, small batches), the
        system should handle them gracefully without errors.
        
        This property verifies that:
        1. Empty market list completes without error
        2. Single market is processed correctly
        3. Small batches work as expected
        """
        strategy = MagicMock()
        strategy.positions = {}
        
        processed_count = 0
        
        async def mock_process(market):
            """Mock processing that counts invocations."""
            nonlocal processed_count
            processed_count += 1
            await asyncio.sleep(0.001)
        
        # Bind methods
        strategy._process_single_market = mock_process
        strategy._process_markets_concurrently = (
            FifteenMinuteCryptoStrategy._process_markets_concurrently.__get__(strategy)
        )
        
        # Generate test markets
        markets = []
        for i in range(num_markets):
            market = CryptoMarket(
                market_id=f"market_{i}",
                question=f"Test market {i}",
                asset="BTC",
                up_token_id=f"up_{i}",
                down_token_id=f"down_{i}",
                up_price=Decimal("0.50"),
                down_price=Decimal("0.50"),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
                neg_risk=True,
                tick_size="0.01"
            )
            markets.append(market)
        
        # Process markets concurrently (should complete without error)
        await strategy._process_markets_concurrently(markets, max_concurrent=10)
        
        # PROPERTY: Correct number of markets processed
        assert processed_count == num_markets, (
            f"Expected {num_markets} markets to be processed, "
            f"but {processed_count} were processed"
        )
    
    @given(
        num_markets=st.integers(min_value=15, max_value=30)
    )
    @settings(max_examples=15, deadline=5000)
    @pytest.mark.asyncio
    async def test_property_27_uses_asyncio_gather(self, num_markets):
        """
        **Validates: Requirements 5.4**
        
        Property 27: Concurrent Market Processing - Uses asyncio.gather()
        
        The implementation should use asyncio.gather() for concurrent
        execution, not sequential loops. This is verified by measuring
        execution time: concurrent execution should be significantly
        faster than sequential.
        
        This property verifies that:
        1. asyncio.gather() is used (not sequential for loops)
        2. Concurrent execution provides speedup
        3. All markets are still processed correctly
        """
        strategy = MagicMock()
        strategy.positions = {}
        
        processed_count = 0
        processing_delay = 0.02  # 20ms per market
        
        async def mock_process(market):
            """Mock processing with fixed delay."""
            nonlocal processed_count
            processed_count += 1
            await asyncio.sleep(processing_delay)
        
        # Bind methods
        strategy._process_single_market = mock_process
        strategy._process_markets_concurrently = (
            FifteenMinuteCryptoStrategy._process_markets_concurrently.__get__(strategy)
        )
        
        # Generate test markets
        markets = []
        for i in range(num_markets):
            market = CryptoMarket(
                market_id=f"market_{i}",
                question=f"Test market {i}",
                asset="BTC",
                up_token_id=f"up_{i}",
                down_token_id=f"down_{i}",
                up_price=Decimal("0.50"),
                down_price=Decimal("0.50"),
                end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
                neg_risk=True,
                tick_size="0.01"
            )
            markets.append(market)
        
        # Measure execution time
        start_time = asyncio.get_event_loop().time()
        await strategy._process_markets_concurrently(markets, max_concurrent=10)
        elapsed_time = asyncio.get_event_loop().time() - start_time
        
        # PROPERTY: All markets processed
        assert processed_count == num_markets, (
            f"Expected {num_markets} markets processed, got {processed_count}"
        )
        
        # PROPERTY: Concurrent execution is faster than sequential
        # Sequential time would be: num_markets * processing_delay
        # Concurrent time should be: ceil(num_markets / 10) * processing_delay
        sequential_time = num_markets * processing_delay
        expected_concurrent_time = ((num_markets + 9) // 10) * processing_delay
        
        # Allow generous overhead (100% margin) to account for system variability
        max_allowed_time = expected_concurrent_time * 2.0
        
        # Main property: Should be significantly faster than sequential
        # Use 70% threshold to be more lenient with system overhead
        assert elapsed_time < sequential_time * 0.7, (
            f"Execution time {elapsed_time:.3f}s suggests sequential execution. "
            f"Expected < {sequential_time * 0.7:.3f}s (70% of sequential time {sequential_time:.3f}s)"
        )
        
        # Secondary check: Should be within reasonable concurrent time bounds
        # This is more lenient to avoid flakiness from system overhead
        assert elapsed_time < max_allowed_time, (
            f"Execution time {elapsed_time:.3f}s exceeds expected concurrent time "
            f"{expected_concurrent_time:.3f}s (with 100% overhead margin)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
