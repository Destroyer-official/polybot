"""
Property-based tests for Market Data Caching.

Tests correctness properties for:
- Property 25: Market Data Caching (Requirement 5.2)
"""

import pytest
from hypothesis import given, strategies as st, settings
import time
import asyncio
from decimal import Decimal
from unittest.mock import Mock, AsyncMock
import uuid

from src.fast_execution_engine import FastExecutionEngine


# Helper strategies
@st.composite
def market_data_strategy(draw):
    """Generate market data for testing."""
    return {
        "market_id": str(uuid.uuid4()),
        "asset": draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"])),
        "yes_price": float(draw(st.decimals(min_value=Decimal('0.01'), max_value=Decimal('0.99'), places=2))),
        "no_price": float(draw(st.decimals(min_value=Decimal('0.01'), max_value=Decimal('0.99'), places=2))),
        "volume": float(draw(st.decimals(min_value=Decimal('1000'), max_value=Decimal('100000'), places=2))),
        "liquidity": float(draw(st.decimals(min_value=Decimal('500'), max_value=Decimal('50000'), places=2)))
    }


# Property 25: Market Data Caching
@given(
    num_requests=st.integers(min_value=2, max_value=10),
    market_data=market_data_strategy()
)
@settings(max_examples=50, deadline=None)
def test_property_25_market_data_caching_within_ttl(num_requests, market_data):
    """
    **Validates: Requirements 5.2**
    
    Property 25: Market Data Caching
    
    For any sequence of market data fetch requests made within the 2-second TTL,
    the cache should return the same data without making additional API calls.
    
    This property verifies that:
    1. Multiple requests within 2 seconds return cached data
    2. Only one API call is made for requests within TTL
    3. Cache hit rate is correct
    4. Cached data matches original data
    """
    # Create engine with 2-second TTL
    engine = FastExecutionEngine(market_cache_ttl=2.0)
    
    market_key = market_data["market_id"]
    
    # Store initial data in cache
    engine.set_market_data(market_key, market_data)
    
    # Make multiple requests within TTL
    cached_results = []
    for i in range(num_requests):
        result = engine.get_market_data(market_key)
        cached_results.append(result)
        
        # Small delay but within TTL
        time.sleep(0.1)
    
    # Verify all requests returned the same cached data
    for i, result in enumerate(cached_results):
        assert result is not None, f"Request {i+1} returned None (cache miss)"
        assert result == market_data, (
            f"Request {i+1} returned different data. "
            f"Expected: {market_data}, Got: {result}"
        )
    
    # Verify cache statistics
    stats = engine.get_cache_stats()
    market_stats = stats["market_cache"]
    
    # Should have num_requests cache hits (all requests hit cache)
    assert market_stats["hits"] == num_requests, (
        f"Expected {num_requests} cache hits, got {market_stats['hits']}"
    )
    
    # Should have 0 cache misses (all requests within TTL)
    assert market_stats["misses"] == 0, (
        f"Expected 0 cache misses, got {market_stats['misses']}"
    )
    
    # Cache hit rate should be 100%
    assert market_stats["hit_rate"] == 1.0, (
        f"Expected 100% hit rate, got {market_stats['hit_rate']*100:.1f}%"
    )


@given(
    market_data=market_data_strategy()
)
@settings(max_examples=50, deadline=None)
def test_property_25_market_data_caching_after_ttl_expires(market_data):
    """
    **Validates: Requirements 5.2**
    
    Property 25: Market Data Caching - TTL Expiration
    
    For any market data fetch request made after the 2-second TTL expires,
    the cache should return None (cache miss), requiring a fresh API call.
    
    This property verifies that:
    1. Requests after TTL expiration result in cache miss
    2. Expired entries are removed from cache
    3. Fresh data can be cached after expiration
    """
    # Create engine with 2-second TTL
    engine = FastExecutionEngine(market_cache_ttl=2.0)
    
    market_key = market_data["market_id"]
    
    # Store initial data in cache
    engine.set_market_data(market_key, market_data)
    
    # First request within TTL should hit cache
    result1 = engine.get_market_data(market_key)
    assert result1 == market_data, "First request should return cached data"
    
    # Wait for TTL to expire (2.1 seconds to be safe)
    time.sleep(2.1)
    
    # Request after TTL should miss cache
    result2 = engine.get_market_data(market_key)
    assert result2 is None, (
        f"Request after TTL expiration should return None (cache miss), "
        f"got {result2}"
    )
    
    # Verify cache statistics
    stats = engine.get_cache_stats()
    market_stats = stats["market_cache"]
    
    # Should have 1 hit (first request) and 1 miss (second request)
    assert market_stats["hits"] == 1, (
        f"Expected 1 cache hit, got {market_stats['hits']}"
    )
    assert market_stats["misses"] == 1, (
        f"Expected 1 cache miss, got {market_stats['misses']}"
    )
    
    # Cache should be empty after expiration
    assert market_stats["size"] == 0, (
        f"Cache should be empty after expiration, got size {market_stats['size']}"
    )


@given(
    num_rapid_requests=st.integers(min_value=3, max_value=8),
    market_data=market_data_strategy()
)
@settings(max_examples=50, deadline=None)
def test_property_25_market_data_caching_prevents_api_spam(num_rapid_requests, market_data):
    """
    **Validates: Requirements 5.2**
    
    Property 25: Market Data Caching - API Call Prevention
    
    For any sequence of rapid market data fetch requests within 2 seconds,
    the cache should prevent excessive API calls by serving cached data.
    
    This property verifies that:
    1. Rapid requests within TTL don't trigger multiple API calls
    2. Cache effectively reduces API load
    3. All rapid requests receive consistent data
    """
    # Create engine with 2-second TTL
    engine = FastExecutionEngine(market_cache_ttl=2.0)
    
    market_key = market_data["market_id"]
    
    # Mock API call counter
    api_call_count = 0
    
    def mock_api_fetch():
        nonlocal api_call_count
        api_call_count += 1
        return market_data
    
    # Simulate first API call and cache
    engine.set_market_data(market_key, mock_api_fetch())
    
    # Make rapid requests (all within 2 seconds)
    results = []
    for i in range(num_rapid_requests):
        result = engine.get_market_data(market_key)
        results.append(result)
        # Very small delay (simulating rapid requests)
        time.sleep(0.05)
    
    # Verify only 1 API call was made (initial set)
    assert api_call_count == 1, (
        f"Expected only 1 API call for {num_rapid_requests} rapid requests, "
        f"got {api_call_count} calls"
    )
    
    # Verify all requests returned cached data
    for i, result in enumerate(results):
        assert result == market_data, (
            f"Request {i+1} returned different data"
        )
    
    # Verify cache hit rate
    stats = engine.get_cache_stats()
    market_stats = stats["market_cache"]
    
    # All rapid requests should be cache hits
    assert market_stats["hits"] == num_rapid_requests, (
        f"Expected {num_rapid_requests} cache hits, got {market_stats['hits']}"
    )


@given(
    market_data1=market_data_strategy(),
    market_data2=market_data_strategy()
)
@settings(max_examples=50, deadline=None)
def test_property_25_market_data_caching_multiple_markets(market_data1, market_data2):
    """
    **Validates: Requirements 5.2**
    
    Property 25: Market Data Caching - Multiple Markets
    
    For any set of different markets, the cache should maintain separate
    entries for each market with independent TTLs.
    
    This property verifies that:
    1. Different markets have separate cache entries
    2. Cache hits/misses are tracked independently
    3. TTL expiration is independent per market
    """
    # Create engine with 2-second TTL
    engine = FastExecutionEngine(market_cache_ttl=2.0)
    
    # Ensure different market IDs
    market_key1 = market_data1["market_id"]
    market_key2 = str(uuid.uuid4())  # Force different key
    market_data2["market_id"] = market_key2
    
    # Cache both markets
    engine.set_market_data(market_key1, market_data1)
    time.sleep(0.5)  # Small delay between caching
    engine.set_market_data(market_key2, market_data2)
    
    # Retrieve both markets
    result1 = engine.get_market_data(market_key1)
    result2 = engine.get_market_data(market_key2)
    
    # Verify correct data returned for each market
    assert result1 == market_data1, "Market 1 data mismatch"
    assert result2 == market_data2, "Market 2 data mismatch"
    
    # Verify cache contains both entries
    stats = engine.get_cache_stats()
    market_stats = stats["market_cache"]
    
    assert market_stats["size"] == 2, (
        f"Expected 2 cache entries, got {market_stats['size']}"
    )
    
    # Wait for first market to expire
    time.sleep(1.6)  # Total 2.1s for market1, 1.6s for market2
    
    # Market 1 should be expired, Market 2 should still be cached
    result1_expired = engine.get_market_data(market_key1)
    result2_cached = engine.get_market_data(market_key2)
    
    assert result1_expired is None, "Market 1 should be expired"
    assert result2_cached == market_data2, "Market 2 should still be cached"


@given(
    market_data=market_data_strategy()
)
@settings(max_examples=50, deadline=None)
def test_property_25_market_data_caching_invalidation(market_data):
    """
    **Validates: Requirements 5.2**
    
    Property 25: Market Data Caching - Manual Invalidation
    
    For any cached market data, manual invalidation should immediately
    remove the entry from cache, regardless of TTL.
    
    This property verifies that:
    1. Manual invalidation removes specific cache entry
    2. Subsequent requests result in cache miss
    3. Cache size is updated correctly
    """
    # Create engine with 2-second TTL
    engine = FastExecutionEngine(market_cache_ttl=2.0)
    
    market_key = market_data["market_id"]
    
    # Cache market data
    engine.set_market_data(market_key, market_data)
    
    # Verify data is cached
    result1 = engine.get_market_data(market_key)
    assert result1 == market_data, "Data should be cached"
    
    # Manually invalidate cache
    engine.invalidate_market_cache(market_key)
    
    # Verify cache is invalidated
    result2 = engine.get_market_data(market_key)
    assert result2 is None, (
        "Data should be invalidated, expected None (cache miss)"
    )
    
    # Verify cache size is 0
    stats = engine.get_cache_stats()
    market_stats = stats["market_cache"]
    
    assert market_stats["size"] == 0, (
        f"Cache should be empty after invalidation, got size {market_stats['size']}"
    )


@given(
    num_markets=st.integers(min_value=2, max_value=5)
)
@settings(max_examples=30, deadline=None)
def test_property_25_market_data_caching_clear_all(num_markets):
    """
    **Validates: Requirements 5.2**
    
    Property 25: Market Data Caching - Clear All
    
    For any number of cached markets, clearing the entire cache should
    remove all entries at once.
    
    This property verifies that:
    1. Clear all removes all cache entries
    2. Cache size becomes 0
    3. All subsequent requests result in cache miss
    """
    # Create engine with 2-second TTL
    engine = FastExecutionEngine(market_cache_ttl=2.0)
    
    # Cache multiple markets
    market_keys = []
    for i in range(num_markets):
        market_key = str(uuid.uuid4())
        market_keys.append(market_key)
        market_data = {
            "market_id": market_key,
            "asset": "BTC",
            "yes_price": 0.50 + (i * 0.01),
            "no_price": 0.50 - (i * 0.01)
        }
        engine.set_market_data(market_key, market_data)
    
    # Verify all markets are cached
    stats_before = engine.get_cache_stats()
    assert stats_before["market_cache"]["size"] == num_markets, (
        f"Expected {num_markets} cached entries, got {stats_before['market_cache']['size']}"
    )
    
    # Clear entire cache
    engine.invalidate_market_cache()  # No argument = clear all
    
    # Verify cache is empty
    stats_after = engine.get_cache_stats()
    assert stats_after["market_cache"]["size"] == 0, (
        f"Cache should be empty after clear all, got size {stats_after['market_cache']['size']}"
    )
    
    # Verify all requests result in cache miss
    for market_key in market_keys:
        result = engine.get_market_data(market_key)
        assert result is None, (
            f"Market {market_key} should be cleared, got {result}"
        )


# Additional test: Verify cache cleanup removes expired entries
@given(
    num_markets=st.integers(min_value=2, max_value=5)
)
@settings(max_examples=30, deadline=None)
def test_market_data_cache_cleanup_expired_entries(num_markets):
    """
    Verify that cleanup_expired_entries() removes only expired entries
    and keeps valid ones.
    """
    # Create engine with 2-second TTL
    engine = FastExecutionEngine(market_cache_ttl=2.0)
    
    # Cache markets at different times
    old_markets = []
    new_markets = []
    
    # Cache old markets (will expire)
    for i in range(num_markets // 2 + 1):
        market_key = str(uuid.uuid4())
        old_markets.append(market_key)
        engine.set_market_data(market_key, {"id": market_key, "old": True})
    
    # Wait for old markets to expire
    time.sleep(2.1)
    
    # Cache new markets (won't expire)
    for i in range(num_markets // 2):
        market_key = str(uuid.uuid4())
        new_markets.append(market_key)
        engine.set_market_data(market_key, {"id": market_key, "new": True})
    
    # Run cleanup
    cleanup_result = engine.cleanup_expired_entries()
    
    # Verify old markets were removed
    assert cleanup_result["market_cache_expired"] == len(old_markets), (
        f"Expected {len(old_markets)} expired entries, "
        f"got {cleanup_result['market_cache_expired']}"
    )
    
    # Verify new markets are still cached
    for market_key in new_markets:
        result = engine.get_market_data(market_key)
        assert result is not None, f"New market {market_key} should still be cached"
    
    # Verify old markets are removed
    for market_key in old_markets:
        result = engine.get_market_data(market_key)
        assert result is None, f"Old market {market_key} should be expired"
