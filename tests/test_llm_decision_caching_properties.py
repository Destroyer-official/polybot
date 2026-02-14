"""
Property-based tests for LLM Decision Caching.

Property 26: LLM Decision Caching
**Validates: Requirements 5.3**
"""

import pytest
import time
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from typing import Any, Dict

from src.fast_execution_engine import FastExecutionEngine


# ============================================================================
# Property 26: LLM Decision Caching
# ============================================================================
# **Validates: Requirements 5.3**
#
# **Property Statement:**
# For any asset and decision context, when multiple decision requests are made
# within 60 seconds, only the first request should result in a cache miss,
# and all subsequent requests should return the cached decision. After 60 seconds,
# a fresh decision should be made (cache miss).
#
# **Formal Specification:**
# ∀ asset ∈ Assets, ∀ decision_key ∈ DecisionKeys:
#   1. First request at time t₀ → cache MISS
#   2. Requests at time t where (t - t₀) < 60s → cache HIT (same decision)
#   3. Request at time t where (t - t₀) ≥ 60s → cache MISS (fresh decision)
#
# **Test Strategy:**
# 1. Simulate multiple decision requests for the same asset within 60 seconds
# 2. Verify only the first request is a cache miss
# 3. Verify subsequent requests within TTL are cache hits
# 4. Simulate time passing beyond TTL (60 seconds)
# 5. Verify next request after TTL is a cache miss
# ============================================================================


class TestLLMDecisionCaching:
    """Property 26: LLM Decision Caching"""

    @given(
        asset=st.sampled_from(["BTC", "ETH", "SOL", "XRP"]),
        num_requests=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=50)
    def test_property_26_multiple_requests_within_ttl(self, asset, num_requests):
        """
        **Validates: Requirements 5.3**
        
        Property 26: LLM Decision Caching
        
        For any asset, when multiple decision requests are made within 60 seconds,
        only the first request should be a cache miss, and all subsequent requests
        should return the same cached decision.
        """
        # Initialize engine with 60-second decision cache TTL
        engine = FastExecutionEngine(decision_cache_ttl=60.0)
        
        # Create a decision key for the asset
        decision_key = f"llm_decision_{asset}"
        
        # Create a mock decision
        mock_decision = {
            "action": "buy_yes",
            "confidence": 75.5,
            "reasoning": f"Strong momentum for {asset}"
        }
        
        # PROPERTY 1: First request should be a cache miss
        initial_stats = engine.get_cache_stats()
        initial_misses = initial_stats["decision_cache"]["misses"]
        
        cached_decision = engine.get_decision(decision_key)
        assert cached_decision is None, "First request should return None (cache miss)"
        
        # Verify cache miss was recorded
        stats_after_first = engine.get_cache_stats()
        assert stats_after_first["decision_cache"]["misses"] == initial_misses + 1, \
            "First request should increment cache misses"
        
        # Store the decision in cache
        engine.set_decision(decision_key, mock_decision)
        
        # PROPERTY 2: All subsequent requests within TTL should be cache hits
        initial_hits = stats_after_first["decision_cache"]["hits"]
        
        for i in range(num_requests - 1):
            cached_decision = engine.get_decision(decision_key)
            
            # Verify we got the cached decision
            assert cached_decision is not None, \
                f"Request {i+2} should return cached decision"
            assert cached_decision == mock_decision, \
                f"Request {i+2} should return the same decision"
        
        # Verify all requests were cache hits
        final_stats = engine.get_cache_stats()
        expected_hits = initial_hits + (num_requests - 1)
        assert final_stats["decision_cache"]["hits"] == expected_hits, \
            f"Expected {num_requests - 1} cache hits, got {final_stats['decision_cache']['hits'] - initial_hits}"
        
        # PROPERTY 3: Cache hit rate should be high (>= 50% to handle edge case of 2 requests)
        hit_rate = final_stats["decision_cache"]["hit_rate"]
        assert hit_rate >= 0.5, \
            f"Cache hit rate should be >= 50%, got {hit_rate:.2%}"

    @given(
        asset=st.sampled_from(["BTC", "ETH", "SOL", "XRP"]),
        ttl_seconds=st.floats(min_value=0.1, max_value=2.0)
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_26_cache_expires_after_ttl(self, asset, ttl_seconds):
        """
        **Validates: Requirements 5.3**
        
        Property 26: LLM Decision Caching - TTL Expiration
        
        For any asset, after the TTL expires (60 seconds in production, shorter in test),
        the next request should be a cache miss and allow for a fresh decision.
        """
        # Initialize engine with custom TTL for testing
        engine = FastExecutionEngine(decision_cache_ttl=ttl_seconds)
        
        # Create a decision key for the asset
        decision_key = f"llm_decision_{asset}"
        
        # Create mock decisions
        first_decision = {
            "action": "buy_yes",
            "confidence": 75.5,
            "reasoning": f"First decision for {asset}"
        }
        second_decision = {
            "action": "buy_no",
            "confidence": 82.3,
            "reasoning": f"Second decision for {asset}"
        }
        
        # PROPERTY 1: First request is a cache miss
        cached = engine.get_decision(decision_key)
        assert cached is None, "First request should be a cache miss"
        
        # Store first decision
        engine.set_decision(decision_key, first_decision)
        
        # PROPERTY 2: Immediate request should be a cache hit
        cached = engine.get_decision(decision_key)
        assert cached == first_decision, "Immediate request should return cached decision"
        
        # PROPERTY 3: Wait for TTL to expire
        time.sleep(ttl_seconds + 0.1)  # Add small buffer
        
        # PROPERTY 4: Request after TTL should be a cache miss
        initial_misses = engine.get_cache_stats()["decision_cache"]["misses"]
        
        cached = engine.get_decision(decision_key)
        assert cached is None, "Request after TTL should be a cache miss"
        
        # Verify cache miss was recorded
        final_misses = engine.get_cache_stats()["decision_cache"]["misses"]
        assert final_misses == initial_misses + 1, \
            "Expired cache access should increment misses"
        
        # PROPERTY 5: Can store new decision after expiration
        engine.set_decision(decision_key, second_decision)
        cached = engine.get_decision(decision_key)
        assert cached == second_decision, \
            "Should be able to cache new decision after expiration"

    @given(
        assets=st.lists(
            st.sampled_from(["BTC", "ETH", "SOL", "XRP"]),
            min_size=2,
            max_size=4,
            unique=True
        )
    )
    @settings(max_examples=30)
    def test_property_26_independent_cache_per_asset(self, assets):
        """
        **Validates: Requirements 5.3**
        
        Property 26: LLM Decision Caching - Asset Independence
        
        For any set of assets, each asset should have an independent cache entry.
        Caching a decision for one asset should not affect other assets.
        """
        # Initialize engine
        engine = FastExecutionEngine(decision_cache_ttl=60.0)
        
        # Create decisions for each asset
        decisions = {}
        for asset in assets:
            decision_key = f"llm_decision_{asset}"
            decision = {
                "action": "buy_yes" if hash(asset) % 2 == 0 else "buy_no",
                "confidence": 70.0 + (hash(asset) % 30),
                "reasoning": f"Decision for {asset}"
            }
            decisions[asset] = decision
            engine.set_decision(decision_key, decision)
        
        # PROPERTY 1: Each asset should have its own cached decision
        for asset in assets:
            decision_key = f"llm_decision_{asset}"
            cached = engine.get_decision(decision_key)
            
            assert cached is not None, f"Asset {asset} should have cached decision"
            assert cached == decisions[asset], \
                f"Asset {asset} should return its own decision, not another asset's"
        
        # PROPERTY 2: Cache size should equal number of assets
        cache_stats = engine.get_cache_stats()
        assert cache_stats["decision_cache"]["size"] == len(assets), \
            f"Cache should contain {len(assets)} entries, got {cache_stats['decision_cache']['size']}"
        
        # PROPERTY 3: Invalidating one asset should not affect others
        first_asset = assets[0]
        first_key = f"llm_decision_{first_asset}"
        engine.invalidate_decision_cache(first_key)
        
        # First asset should be gone
        cached = engine.get_decision(first_key)
        assert cached is None, f"Invalidated asset {first_asset} should not be cached"
        
        # Other assets should still be cached
        for asset in assets[1:]:
            decision_key = f"llm_decision_{asset}"
            cached = engine.get_decision(decision_key)
            assert cached == decisions[asset], \
                f"Asset {asset} should still be cached after invalidating {first_asset}"

    @given(
        asset=st.sampled_from(["BTC", "ETH", "SOL", "XRP"]),
        num_cycles=st.integers(min_value=3, max_value=8)
    )
    @settings(max_examples=30)
    def test_property_26_cache_prevents_redundant_llm_calls(self, asset, num_cycles):
        """
        **Validates: Requirements 5.3**
        
        Property 26: LLM Decision Caching - Redundancy Prevention
        
        For any asset, the cache should prevent redundant LLM calls within the TTL period.
        This simulates the real-world scenario where the bot checks the same asset
        multiple times per minute.
        """
        # Initialize engine
        engine = FastExecutionEngine(decision_cache_ttl=60.0)
        
        decision_key = f"llm_decision_{asset}"
        
        # Simulate LLM call counter (in real code, this would be actual LLM API calls)
        llm_call_count = 0
        
        # Simulate multiple trading cycles
        for cycle in range(num_cycles):
            # Check cache first (simulating what the bot does)
            cached_decision = engine.get_decision(decision_key)
            
            if cached_decision is None:
                # Cache miss - would make LLM call
                llm_call_count += 1
                
                # Simulate LLM decision
                new_decision = {
                    "action": "buy_yes",
                    "confidence": 75.0,
                    "reasoning": f"LLM call #{llm_call_count} for {asset}",
                    "call_number": llm_call_count
                }
                
                # Store in cache
                engine.set_decision(decision_key, new_decision)
            else:
                # Cache hit - no LLM call needed
                pass
        
        # PROPERTY 1: Should only make ONE LLM call for all cycles within TTL
        assert llm_call_count == 1, \
            f"Expected 1 LLM call for {num_cycles} cycles, got {llm_call_count}"
        
        # PROPERTY 2: Cache hit rate should be very high
        cache_stats = engine.get_cache_stats()
        hit_rate = cache_stats["decision_cache"]["hit_rate"]
        expected_hit_rate = (num_cycles - 1) / num_cycles
        
        assert hit_rate >= expected_hit_rate - 0.01, \
            f"Expected hit rate ~{expected_hit_rate:.2%}, got {hit_rate:.2%}"
        
        # PROPERTY 3: All cache hits should return the same decision
        for _ in range(5):
            cached = engine.get_decision(decision_key)
            assert cached is not None, "Should still be cached"
            assert cached["call_number"] == 1, \
                "All hits should return the first (and only) LLM decision"

    def test_property_26_production_ttl_is_60_seconds(self):
        """
        **Validates: Requirements 5.3**
        
        Property 26: LLM Decision Caching - Production TTL
        
        Verify that the default TTL for LLM decision caching is 60 seconds
        as specified in the requirements.
        """
        # Initialize engine with default parameters
        engine = FastExecutionEngine()
        
        # PROPERTY: Default decision cache TTL should be 60 seconds
        cache_stats = engine.get_cache_stats()
        assert cache_stats["decision_cache"]["ttl_seconds"] == 60.0, \
            f"Production TTL should be 60 seconds, got {cache_stats['decision_cache']['ttl_seconds']}"
        
        # Verify it's different from market cache TTL
        assert cache_stats["market_cache"]["ttl_seconds"] != cache_stats["decision_cache"]["ttl_seconds"], \
            "Decision cache TTL should be different from market cache TTL"
        
        # Verify market cache has shorter TTL (2 seconds)
        assert cache_stats["market_cache"]["ttl_seconds"] == 2.0, \
            f"Market cache TTL should be 2 seconds, got {cache_stats['market_cache']['ttl_seconds']}"
