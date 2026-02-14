"""
Unit tests for API call tracking and reduction verification.

Tests validate:
- API call counting (cached vs uncached)
- Cache hit rate calculation
- 80% reduction verification
- Per-endpoint breakdown
- Detailed reporting
"""

import pytest
import time
from src.api_call_tracker import APICallTracker, get_global_tracker
from src.fast_execution_engine import FastExecutionEngine


class TestAPICallTracker:
    """Test suite for APICallTracker."""
    
    def test_initialization(self):
        """Test tracker initializes with correct defaults."""
        tracker = APICallTracker()
        
        assert tracker.target_reduction == 0.80
        assert tracker.current_stats.total_calls == 0
        assert tracker.current_stats.cached_calls == 0
        assert tracker.current_stats.uncached_calls == 0
    
    def test_record_uncached_call(self):
        """Test recording an uncached API call."""
        tracker = APICallTracker()
        
        tracker.record_api_call("test_endpoint", was_cached=False)
        
        assert tracker.current_stats.total_calls == 1
        assert tracker.current_stats.uncached_calls == 1
        assert tracker.current_stats.cached_calls == 0
        assert tracker.current_stats.cache_hit_rate == 0.0
    
    def test_record_cached_call(self):
        """Test recording a cached API call."""
        tracker = APICallTracker()
        
        tracker.record_api_call("test_endpoint", was_cached=True)
        
        assert tracker.current_stats.total_calls == 1
        assert tracker.current_stats.cached_calls == 1
        assert tracker.current_stats.uncached_calls == 0
        assert tracker.current_stats.cache_hit_rate == 1.0
    
    def test_mixed_calls(self):
        """Test recording mix of cached and uncached calls."""
        tracker = APICallTracker()
        
        # 1 uncached, 4 cached = 80% hit rate
        tracker.record_api_call("test_endpoint", was_cached=False)
        for _ in range(4):
            tracker.record_api_call("test_endpoint", was_cached=True)
        
        assert tracker.current_stats.total_calls == 5
        assert tracker.current_stats.cached_calls == 4
        assert tracker.current_stats.uncached_calls == 1
        assert tracker.current_stats.cache_hit_rate == 0.80
        assert tracker.current_stats.reduction_percentage == 0.80
    
    def test_per_endpoint_tracking(self):
        """Test per-endpoint call tracking."""
        tracker = APICallTracker()
        
        # Endpoint A: 2 calls (1 cached)
        tracker.record_api_call("endpoint_a", was_cached=False)
        tracker.record_api_call("endpoint_a", was_cached=True)
        
        # Endpoint B: 3 calls (2 cached)
        tracker.record_api_call("endpoint_b", was_cached=False)
        tracker.record_api_call("endpoint_b", was_cached=True)
        tracker.record_api_call("endpoint_b", was_cached=True)
        
        stats = tracker.get_stats()
        
        assert stats["by_endpoint"]["endpoint_a"]["total_calls"] == 2
        assert stats["by_endpoint"]["endpoint_a"]["cached_calls"] == 1
        assert stats["by_endpoint"]["endpoint_a"]["hit_rate"] == 0.5
        
        assert stats["by_endpoint"]["endpoint_b"]["total_calls"] == 3
        assert stats["by_endpoint"]["endpoint_b"]["cached_calls"] == 2
        assert abs(stats["by_endpoint"]["endpoint_b"]["hit_rate"] - 0.6667) < 0.01
    
    def test_verify_reduction_target_pass(self):
        """Test reduction verification passes when target met."""
        tracker = APICallTracker(target_reduction=0.80)
        
        # 80% cached = meets target
        tracker.record_api_call("test", was_cached=False)
        for _ in range(4):
            tracker.record_api_call("test", was_cached=True)
        
        assert tracker.verify_reduction_target() is True
    
    def test_verify_reduction_target_fail(self):
        """Test reduction verification fails when target not met."""
        tracker = APICallTracker(target_reduction=0.80)
        
        # 50% cached = below target
        tracker.record_api_call("test", was_cached=False)
        tracker.record_api_call("test", was_cached=True)
        
        assert tracker.verify_reduction_target() is False
    
    def test_get_stats(self):
        """Test getting comprehensive statistics."""
        tracker = APICallTracker()
        
        # Add some calls
        for _ in range(8):
            tracker.record_api_call("test", was_cached=True)
        for _ in range(2):
            tracker.record_api_call("test", was_cached=False)
        
        stats = tracker.get_stats()
        
        assert "overall" in stats
        assert "by_endpoint" in stats
        assert "performance" in stats
        
        assert stats["overall"]["total_calls"] == 10
        assert stats["overall"]["cached_calls"] == 8
        assert stats["overall"]["uncached_calls"] == 2
        assert stats["overall"]["cache_hit_rate"] == 0.80
        assert stats["overall"]["reduction_percentage"] == 0.80
    
    def test_detailed_report(self):
        """Test generating detailed report."""
        tracker = APICallTracker()
        
        # Add calls to multiple endpoints
        tracker.record_api_call("market_data", was_cached=False)
        for _ in range(9):
            tracker.record_api_call("market_data", was_cached=True)
        
        tracker.record_api_call("llm_decision", was_cached=False)
        for _ in range(4):
            tracker.record_api_call("llm_decision", was_cached=True)
        
        report = tracker.get_detailed_report()
        
        assert "API CALL REDUCTION VERIFICATION REPORT" in report
        assert "OVERALL STATISTICS" in report
        assert "PER-ENDPOINT BREAKDOWN" in report
        assert "market_data" in report
        assert "llm_decision" in report
        assert "90.00%" in report  # market_data hit rate
    
    def test_reset_stats(self):
        """Test resetting statistics."""
        tracker = APICallTracker()
        
        # Add some calls
        tracker.record_api_call("test", was_cached=True)
        tracker.record_api_call("test", was_cached=False)
        
        assert tracker.current_stats.total_calls == 2
        
        # Reset
        tracker.reset_stats()
        
        assert tracker.current_stats.total_calls == 0
        assert tracker.current_stats.cached_calls == 0
        assert tracker.current_stats.uncached_calls == 0
        assert len(tracker.historical_stats) == 1  # Previous stats archived


class TestFastExecutionEngineAPITracking:
    """Test suite for FastExecutionEngine API tracking integration."""
    
    def setup_method(self):
        """Reset global tracker before each test."""
        from src.api_call_tracker import _global_tracker
        import src.api_call_tracker as tracker_module
        tracker_module._global_tracker = None
    
    def test_engine_with_tracking_enabled(self):
        """Test engine initializes with API tracking enabled."""
        engine = FastExecutionEngine(enable_api_tracking=True)
        
        assert engine._enable_api_tracking is True
        assert engine._api_tracker is not None
    
    def test_engine_with_tracking_disabled(self):
        """Test engine initializes with API tracking disabled."""
        engine = FastExecutionEngine(enable_api_tracking=False)
        
        assert engine._enable_api_tracking is False
        assert engine._api_tracker is None
    
    def test_market_cache_tracks_api_calls(self):
        """Test market cache operations are tracked."""
        engine = FastExecutionEngine(enable_api_tracking=True)
        
        # First call - cache miss (uncached)
        result1 = engine.get_market_data("test_market")
        assert result1 is None
        
        # Set data
        engine.set_market_data("test_market", {"price": 0.5})
        
        # Second call - cache hit (cached)
        result2 = engine.get_market_data("test_market")
        assert result2 is not None
        
        # Check API tracker
        stats = engine.get_api_call_stats()
        assert stats is not None
        assert stats["overall"]["total_calls"] == 2
        assert stats["overall"]["cached_calls"] == 1
        assert stats["overall"]["uncached_calls"] == 1
    
    def test_decision_cache_tracks_api_calls(self):
        """Test decision cache operations are tracked."""
        engine = FastExecutionEngine(enable_api_tracking=True)
        
        # First call - cache miss (uncached)
        result1 = engine.get_decision("test_decision")
        assert result1 is None
        
        # Set decision
        engine.set_decision("test_decision", {"action": "buy"})
        
        # Second call - cache hit (cached)
        result2 = engine.get_decision("test_decision")
        assert result2 is not None
        
        # Check API tracker
        stats = engine.get_api_call_stats()
        assert stats is not None
        assert stats["overall"]["total_calls"] == 2
        assert stats["overall"]["cached_calls"] == 1
        assert stats["overall"]["uncached_calls"] == 1
    
    def test_verify_cache_reduction(self):
        """Test cache reduction verification."""
        engine = FastExecutionEngine(enable_api_tracking=True)
        
        # Simulate 80% cache hit rate
        # 1 miss, 4 hits
        engine.get_market_data("market1")  # miss
        engine.set_market_data("market1", {"price": 0.5})
        
        for _ in range(4):
            engine.get_market_data("market1")  # hits
        
        # Verify reduction
        assert engine.verify_cache_reduction(target=0.80) is True
    
    def test_log_cache_hit_rates(self):
        """Test logging cache hit rates."""
        engine = FastExecutionEngine(enable_api_tracking=True)
        
        # Add some cache activity
        engine.get_market_data("market1")
        engine.set_market_data("market1", {"price": 0.5})
        engine.get_market_data("market1")
        
        # Should not raise exception
        engine.log_cache_hit_rates()
    
    def test_get_api_call_report(self):
        """Test getting detailed API call report."""
        engine = FastExecutionEngine(enable_api_tracking=True)
        
        # Add some activity
        for i in range(10):
            engine.get_market_data(f"market{i}")
            engine.set_market_data(f"market{i}", {"price": 0.5})
            engine.get_market_data(f"market{i}")  # Cache hit
        
        report = engine.get_api_call_report()
        
        assert report is not None
        assert "API CALL REDUCTION VERIFICATION REPORT" in report
        assert "market_data" in report
    
    def test_summary_includes_api_stats(self):
        """Test summary includes API call statistics."""
        engine = FastExecutionEngine(enable_api_tracking=True)
        
        # Add some activity
        engine.get_market_data("test")
        engine.set_market_data("test", {"price": 0.5})
        engine.get_market_data("test")
        
        summary = engine.get_summary()
        
        assert "api_call_stats" in summary
        assert "overall" in summary["api_call_stats"]
        assert "by_endpoint" in summary["api_call_stats"]


class TestAPICallReductionScenarios:
    """Test realistic API call reduction scenarios."""
    
    def test_high_cache_hit_scenario(self):
        """Test scenario with high cache hit rate (90%)."""
        tracker = APICallTracker()
        
        # Simulate 10 unique markets, each fetched 10 times
        for market_id in range(10):
            # First fetch - uncached
            tracker.record_api_call("market_data", was_cached=False)
            
            # Next 9 fetches - cached
            for _ in range(9):
                tracker.record_api_call("market_data", was_cached=True)
        
        stats = tracker.get_stats()
        
        assert stats["overall"]["total_calls"] == 100
        assert stats["overall"]["cached_calls"] == 90
        assert stats["overall"]["uncached_calls"] == 10
        assert stats["overall"]["reduction_percentage"] == 0.90
        assert tracker.verify_reduction_target() is True
    
    def test_low_cache_hit_scenario(self):
        """Test scenario with low cache hit rate (30%)."""
        tracker = APICallTracker()
        
        # Simulate poor caching (many unique requests)
        for _ in range(70):
            tracker.record_api_call("market_data", was_cached=False)
        
        for _ in range(30):
            tracker.record_api_call("market_data", was_cached=True)
        
        stats = tracker.get_stats()
        
        assert stats["overall"]["total_calls"] == 100
        assert stats["overall"]["cached_calls"] == 30
        assert stats["overall"]["reduction_percentage"] == 0.30
        assert tracker.verify_reduction_target() is False
    
    def test_mixed_endpoint_scenario(self):
        """Test scenario with multiple endpoints having different hit rates."""
        tracker = APICallTracker()
        
        # Market data: 90% hit rate (good caching)
        tracker.record_api_call("market_data", was_cached=False)
        for _ in range(9):
            tracker.record_api_call("market_data", was_cached=True)
        
        # LLM decisions: 50% hit rate (moderate caching)
        for _ in range(5):
            tracker.record_api_call("llm_decision", was_cached=False)
        for _ in range(5):
            tracker.record_api_call("llm_decision", was_cached=True)
        
        # Orderbook: 70% hit rate
        for _ in range(3):
            tracker.record_api_call("orderbook", was_cached=False)
        for _ in range(7):
            tracker.record_api_call("orderbook", was_cached=True)
        
        stats = tracker.get_stats()
        
        # Overall: (9+5+7) / (10+10+10) = 21/30 = 70%
        assert stats["overall"]["total_calls"] == 30
        assert stats["overall"]["cached_calls"] == 21
        assert abs(stats["overall"]["reduction_percentage"] - 0.70) < 0.01
        
        # Per-endpoint verification
        assert stats["by_endpoint"]["market_data"]["hit_rate"] == 0.90
        assert stats["by_endpoint"]["llm_decision"]["hit_rate"] == 0.50
        assert stats["by_endpoint"]["orderbook"]["hit_rate"] == 0.70


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
