"""
API Call Reduction Verification System

This module tracks API calls with and without caching to verify
that caching achieves the target 80% reduction in API calls.

Requirements validated:
- 13.4: Count API calls with and without caching
- 13.4: Verify 80% reduction from caching
- 13.4: Log cache hit rates
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class APICallStats:
    """Statistics for API call tracking."""
    total_calls: int = 0
    cached_calls: int = 0
    uncached_calls: int = 0
    cache_hit_rate: float = 0.0
    reduction_percentage: float = 0.0
    
    # Per-endpoint breakdown
    calls_by_endpoint: Dict[str, int] = field(default_factory=dict)
    cached_by_endpoint: Dict[str, int] = field(default_factory=dict)
    
    # Time tracking
    start_time: float = field(default_factory=time.time)
    last_reset: float = field(default_factory=time.time)


class APICallTracker:
    """
    Tracks API calls and verifies cache effectiveness.
    
    Features:
    - Count total API calls (with and without cache)
    - Calculate cache hit rate
    - Verify 80% reduction target
    - Per-endpoint breakdown
    - Periodic reporting
    """
    
    def __init__(self, target_reduction: float = 0.80):
        """
        Initialize the API call tracker.
        
        Args:
            target_reduction: Target cache reduction percentage (default: 0.80 = 80%)
        """
        self.target_reduction = target_reduction
        
        # Current period stats
        self.current_stats = APICallStats()
        
        # Historical stats (for comparison)
        self.historical_stats: list[APICallStats] = []
        self.max_history = 24  # Keep last 24 periods (e.g., hours)
        
        # Alert thresholds
        self.alert_threshold = 0.70  # Alert if reduction < 70%
        
        logger.info(
            f"APICallTracker initialized: target_reduction={target_reduction*100:.0f}%"
        )
    
    def record_api_call(
        self,
        endpoint: str,
        was_cached: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record an API call.
        
        Args:
            endpoint: API endpoint name (e.g., "gamma_markets", "clob_orderbook")
            was_cached: True if data came from cache, False if actual API call
            metadata: Optional additional information
        """
        # Update total calls
        self.current_stats.total_calls += 1
        
        # Update cached vs uncached
        if was_cached:
            self.current_stats.cached_calls += 1
        else:
            self.current_stats.uncached_calls += 1
        
        # Update per-endpoint stats
        if endpoint not in self.current_stats.calls_by_endpoint:
            self.current_stats.calls_by_endpoint[endpoint] = 0
            self.current_stats.cached_by_endpoint[endpoint] = 0
        
        self.current_stats.calls_by_endpoint[endpoint] += 1
        if was_cached:
            self.current_stats.cached_by_endpoint[endpoint] += 1
        
        # Recalculate rates
        self._update_rates()
        
        # Log if significant milestone
        if self.current_stats.total_calls % 100 == 0:
            self._log_progress()
    
    def _update_rates(self) -> None:
        """Update calculated rates."""
        total = self.current_stats.total_calls
        
        if total > 0:
            # Cache hit rate = cached / total
            self.current_stats.cache_hit_rate = (
                self.current_stats.cached_calls / total
            )
            
            # Reduction percentage = cached / total
            # (cached calls are API calls we DIDN'T make)
            self.current_stats.reduction_percentage = (
                self.current_stats.cached_calls / total
            )
    
    def _log_progress(self) -> None:
        """Log current progress."""
        stats = self.current_stats
        
        logger.info(
            f"📊 API Call Stats: "
            f"total={stats.total_calls}, "
            f"cached={stats.cached_calls}, "
            f"uncached={stats.uncached_calls}, "
            f"hit_rate={stats.cache_hit_rate*100:.1f}%, "
            f"reduction={stats.reduction_percentage*100:.1f}%"
        )
        
        # Check if meeting target
        if stats.reduction_percentage >= self.target_reduction:
            logger.info(
                f"✅ Cache reduction target MET: "
                f"{stats.reduction_percentage*100:.1f}% >= "
                f"{self.target_reduction*100:.0f}%"
            )
        elif stats.reduction_percentage >= self.alert_threshold:
            logger.warning(
                f"⚠️ Cache reduction below target but above alert: "
                f"{stats.reduction_percentage*100:.1f}% "
                f"(target: {self.target_reduction*100:.0f}%)"
            )
        else:
            logger.error(
                f"❌ Cache reduction BELOW alert threshold: "
                f"{stats.reduction_percentage*100:.1f}% < "
                f"{self.alert_threshold*100:.0f}%"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current API call statistics.
        
        Returns:
            Dictionary with comprehensive statistics
        """
        stats = self.current_stats
        
        # Calculate per-endpoint hit rates
        endpoint_stats = {}
        for endpoint, total_calls in stats.calls_by_endpoint.items():
            cached = stats.cached_by_endpoint.get(endpoint, 0)
            endpoint_stats[endpoint] = {
                "total_calls": total_calls,
                "cached_calls": cached,
                "uncached_calls": total_calls - cached,
                "hit_rate": cached / total_calls if total_calls > 0 else 0.0,
                "reduction": cached / total_calls if total_calls > 0 else 0.0
            }
        
        # Calculate time-based metrics
        elapsed_time = time.time() - stats.start_time
        calls_per_minute = (
            stats.total_calls / (elapsed_time / 60)
            if elapsed_time > 0 else 0.0
        )
        
        return {
            "overall": {
                "total_calls": stats.total_calls,
                "cached_calls": stats.cached_calls,
                "uncached_calls": stats.uncached_calls,
                "cache_hit_rate": stats.cache_hit_rate,
                "reduction_percentage": stats.reduction_percentage,
                "meets_target": stats.reduction_percentage >= self.target_reduction,
                "target_reduction": self.target_reduction
            },
            "by_endpoint": endpoint_stats,
            "performance": {
                "elapsed_seconds": elapsed_time,
                "calls_per_minute": calls_per_minute,
                "last_reset": datetime.fromtimestamp(stats.last_reset).isoformat()
            }
        }
    
    def get_detailed_report(self) -> str:
        """
        Generate a detailed human-readable report.
        
        Returns:
            Formatted report string
        """
        stats_dict = self.get_stats()
        overall = stats_dict["overall"]
        by_endpoint = stats_dict["by_endpoint"]
        perf = stats_dict["performance"]
        
        lines = [
            "=" * 70,
            "API CALL REDUCTION VERIFICATION REPORT",
            "=" * 70,
            "",
            "OVERALL STATISTICS:",
            f"  Total API Calls:        {overall['total_calls']:,}",
            f"  Cached (avoided):       {overall['cached_calls']:,}",
            f"  Uncached (actual):      {overall['uncached_calls']:,}",
            f"  Cache Hit Rate:         {overall['cache_hit_rate']*100:.2f}%",
            f"  Reduction Achieved:     {overall['reduction_percentage']*100:.2f}%",
            f"  Target Reduction:       {overall['target_reduction']*100:.0f}%",
            f"  Meets Target:           {'✅ YES' if overall['meets_target'] else '❌ NO'}",
            "",
            "PER-ENDPOINT BREAKDOWN:",
        ]
        
        # Sort endpoints by total calls (descending)
        sorted_endpoints = sorted(
            by_endpoint.items(),
            key=lambda x: x[1]["total_calls"],
            reverse=True
        )
        
        for endpoint, ep_stats in sorted_endpoints:
            lines.extend([
                f"  {endpoint}:",
                f"    Total:      {ep_stats['total_calls']:,}",
                f"    Cached:     {ep_stats['cached_calls']:,}",
                f"    Uncached:   {ep_stats['uncached_calls']:,}",
                f"    Hit Rate:   {ep_stats['hit_rate']*100:.2f}%",
                f"    Reduction:  {ep_stats['reduction']*100:.2f}%",
                ""
            ])
        
        lines.extend([
            "PERFORMANCE METRICS:",
            f"  Elapsed Time:           {perf['elapsed_seconds']:.1f}s",
            f"  Calls Per Minute:       {perf['calls_per_minute']:.1f}",
            f"  Last Reset:             {perf['last_reset']}",
            "",
            "=" * 70
        ])
        
        return "\n".join(lines)
    
    def verify_reduction_target(self) -> bool:
        """
        Verify if cache reduction meets the target.
        
        Returns:
            True if reduction >= target, False otherwise
        """
        meets_target = (
            self.current_stats.reduction_percentage >= self.target_reduction
        )
        
        if meets_target:
            logger.info(
                f"✅ Cache reduction verification PASSED: "
                f"{self.current_stats.reduction_percentage*100:.2f}% >= "
                f"{self.target_reduction*100:.0f}%"
            )
        else:
            logger.error(
                f"❌ Cache reduction verification FAILED: "
                f"{self.current_stats.reduction_percentage*100:.2f}% < "
                f"{self.target_reduction*100:.0f}%"
            )
        
        return meets_target
    
    def reset_stats(self) -> None:
        """
        Reset current statistics and archive to history.
        """
        # Archive current stats
        self.historical_stats.append(self.current_stats)
        if len(self.historical_stats) > self.max_history:
            self.historical_stats.pop(0)
        
        # Reset current stats
        self.current_stats = APICallStats()
        
        logger.info("API call statistics reset")
    
    def get_historical_summary(self) -> Dict[str, Any]:
        """
        Get summary of historical statistics.
        
        Returns:
            Dictionary with historical trends
        """
        if not self.historical_stats:
            return {"message": "No historical data available"}
        
        # Calculate averages
        avg_reduction = sum(
            s.reduction_percentage for s in self.historical_stats
        ) / len(self.historical_stats)
        
        avg_hit_rate = sum(
            s.cache_hit_rate for s in self.historical_stats
        ) / len(self.historical_stats)
        
        total_calls = sum(s.total_calls for s in self.historical_stats)
        total_cached = sum(s.cached_calls for s in self.historical_stats)
        
        return {
            "periods": len(self.historical_stats),
            "average_reduction": avg_reduction,
            "average_hit_rate": avg_hit_rate,
            "total_calls": total_calls,
            "total_cached": total_cached,
            "total_uncached": total_calls - total_cached,
            "overall_reduction": total_cached / total_calls if total_calls > 0 else 0.0
        }
    
    def log_cache_hit_rates(self) -> None:
        """
        Log detailed cache hit rates for all endpoints.
        
        This method provides comprehensive logging of cache performance
        as required by task 13.4.
        """
        logger.info("=" * 70)
        logger.info("CACHE HIT RATE REPORT")
        logger.info("=" * 70)
        
        stats = self.get_stats()
        overall = stats["overall"]
        
        logger.info(
            f"Overall Cache Hit Rate: {overall['cache_hit_rate']*100:.2f}% "
            f"({overall['cached_calls']}/{overall['total_calls']} calls)"
        )
        
        logger.info("Per-Endpoint Cache Hit Rates:")
        for endpoint, ep_stats in stats["by_endpoint"].items():
            logger.info(
                f"  {endpoint}: {ep_stats['hit_rate']*100:.2f}% "
                f"({ep_stats['cached_calls']}/{ep_stats['total_calls']} calls)"
            )
        
        logger.info("=" * 70)


# Global tracker instance
_global_tracker: Optional[APICallTracker] = None


def get_global_tracker() -> APICallTracker:
    """Get or create the global API call tracker."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = APICallTracker()
    return _global_tracker


def record_api_call(endpoint: str, was_cached: bool, metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Convenience function to record an API call using the global tracker.
    
    Args:
        endpoint: API endpoint name
        was_cached: True if data came from cache
        metadata: Optional additional information
    """
    tracker = get_global_tracker()
    tracker.record_api_call(endpoint, was_cached, metadata)
