"""
Fast Execution Engine for Sub-1-Second Trades

This module provides caching infrastructure and execution time tracking
to optimize trade execution speed for 15-minute crypto markets.

Requirements validated:
- 5.1: Track execution times
- 5.2: Market data caching with 2-second TTL
- 5.3: LLM decision caching with 60-second TTL
- 13.4: Count API calls with and without caching
- 13.4: Verify 80% reduction from caching
- 13.4: Log cache hit rates
"""

import time
import logging
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with value and timestamp."""
    value: Any
    timestamp: float


@dataclass
class ExecutionMetrics:
    """Execution time tracking metrics."""
    operation: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


class FastExecutionEngine:
    """
    Fast execution engine with caching and performance tracking.
    
    Features:
    - Market data cache with 2-second TTL
    - LLM decision cache with 60-second TTL
    - Execution time tracking for all operations
    - Cache hit rate monitoring
    """
    
    def __init__(
        self,
        market_cache_ttl: float = 2.0,
        decision_cache_ttl: float = 60.0,
        enable_api_tracking: bool = True
    ):
        """
        Initialize the fast execution engine.
        
        Args:
            market_cache_ttl: Time-to-live for market data cache in seconds (default: 2.0)
            decision_cache_ttl: Time-to-live for LLM decision cache in seconds (default: 60.0)
            enable_api_tracking: Enable API call tracking for verification (default: True)
        """
        # Market data cache (2-second TTL)
        self._market_cache: Dict[str, CacheEntry] = {}
        self._market_cache_ttl = market_cache_ttl
        
        # LLM decision cache (60-second TTL)
        self._decision_cache: Dict[str, CacheEntry] = {}
        self._decision_cache_ttl = decision_cache_ttl
        
        # Execution time tracking
        self._execution_metrics: list[ExecutionMetrics] = []
        self._max_metrics_history = 1000  # Keep last 1000 operations
        
        # Cache statistics
        self._market_cache_hits = 0
        self._market_cache_misses = 0
        self._decision_cache_hits = 0
        self._decision_cache_misses = 0
        
        # API call tracking (Task 13.4)
        self._enable_api_tracking = enable_api_tracking
        if enable_api_tracking:
            from src.api_call_tracker import get_global_tracker
            self._api_tracker = get_global_tracker()
            logger.info("📊 API call tracking enabled")
        else:
            self._api_tracker = None
        
        logger.info(
            f"FastExecutionEngine initialized: "
            f"market_ttl={market_cache_ttl}s, decision_ttl={decision_cache_ttl}s"
        )
    
    # ==================== Market Data Cache ====================
    
    def get_market_data(self, market_key: str) -> Optional[Any]:
        """
        Get cached market data if available and not expired.
        
        Args:
            market_key: Unique identifier for the market
            
        Returns:
            Cached market data or None if not found/expired
        """
        current_time = time.time()
        
        if market_key in self._market_cache:
            entry = self._market_cache[market_key]
            age = current_time - entry.timestamp
            
            if age < self._market_cache_ttl:
                self._market_cache_hits += 1
                
                # Track API call (cached)
                if self._api_tracker:
                    self._api_tracker.record_api_call("market_data", was_cached=True)
                
                logger.debug(f"Market cache HIT: {market_key} (age: {age:.2f}s)")
                return entry.value
            else:
                # Expired, remove from cache
                del self._market_cache[market_key]
                logger.debug(f"Market cache EXPIRED: {market_key} (age: {age:.2f}s)")
        
        self._market_cache_misses += 1
        
        # Track API call (not cached - will require actual API call)
        if self._api_tracker:
            self._api_tracker.record_api_call("market_data", was_cached=False)
        
        logger.debug(f"Market cache MISS: {market_key}")
        return None
    
    def set_market_data(self, market_key: str, data: Any) -> None:
        """
        Store market data in cache.
        
        Args:
            market_key: Unique identifier for the market
            data: Market data to cache
        """
        self._market_cache[market_key] = CacheEntry(
            value=data,
            timestamp=time.time()
        )
        logger.debug(f"Market cache SET: {market_key}")
    
    def invalidate_market_cache(self, market_key: Optional[str] = None) -> None:
        """
        Invalidate market cache entries.
        
        Args:
            market_key: Specific market to invalidate, or None to clear all
        """
        if market_key:
            if market_key in self._market_cache:
                del self._market_cache[market_key]
                logger.debug(f"Market cache INVALIDATED: {market_key}")
        else:
            count = len(self._market_cache)
            self._market_cache.clear()
            logger.info(f"Market cache CLEARED: {count} entries removed")
    
    # ==================== LLM Decision Cache ====================
    
    def get_decision(self, decision_key: str) -> Optional[Any]:
        """
        Get cached LLM decision if available and not expired.
        
        Args:
            decision_key: Unique identifier for the decision context
            
        Returns:
            Cached decision or None if not found/expired
        """
        current_time = time.time()
        
        if decision_key in self._decision_cache:
            entry = self._decision_cache[decision_key]
            age = current_time - entry.timestamp
            
            if age < self._decision_cache_ttl:
                self._decision_cache_hits += 1
                
                # Track API call (cached)
                if self._api_tracker:
                    self._api_tracker.record_api_call("llm_decision", was_cached=True)
                
                logger.debug(f"Decision cache HIT: {decision_key} (age: {age:.2f}s)")
                return entry.value
            else:
                # Expired, remove from cache
                del self._decision_cache[decision_key]
                logger.debug(f"Decision cache EXPIRED: {decision_key} (age: {age:.2f}s)")
        
        self._decision_cache_misses += 1
        
        # Track API call (not cached - will require actual LLM call)
        if self._api_tracker:
            self._api_tracker.record_api_call("llm_decision", was_cached=False)
        
        logger.debug(f"Decision cache MISS: {decision_key}")
        return None
    
    def set_decision(self, decision_key: str, decision: Any) -> None:
        """
        Store LLM decision in cache.
        
        Args:
            decision_key: Unique identifier for the decision context
            decision: Decision data to cache
        """
        self._decision_cache[decision_key] = CacheEntry(
            value=decision,
            timestamp=time.time()
        )
        logger.debug(f"Decision cache SET: {decision_key}")
    
    def invalidate_decision_cache(self, decision_key: Optional[str] = None) -> None:
        """
        Invalidate decision cache entries.
        
        Args:
            decision_key: Specific decision to invalidate, or None to clear all
        """
        if decision_key:
            if decision_key in self._decision_cache:
                del self._decision_cache[decision_key]
                logger.debug(f"Decision cache INVALIDATED: {decision_key}")
        else:
            count = len(self._decision_cache)
            self._decision_cache.clear()
            logger.info(f"Decision cache CLEARED: {count} entries removed")
    
    # ==================== Execution Time Tracking ====================
    
    def start_operation(self, operation_name: str) -> float:
        """
        Start tracking execution time for an operation.
        
        Args:
            operation_name: Name of the operation being tracked
            
        Returns:
            Start timestamp for use with end_operation()
        """
        start_time = time.time()
        logger.debug(f"Operation START: {operation_name}")
        return start_time
    
    def end_operation(
        self,
        operation_name: str,
        start_time: float,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExecutionMetrics:
        """
        End tracking and record execution time for an operation.
        
        Args:
            operation_name: Name of the operation
            start_time: Start timestamp from start_operation()
            success: Whether the operation succeeded
            metadata: Optional additional data about the operation
            
        Returns:
            ExecutionMetrics with timing information
        """
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        metrics = ExecutionMetrics(
            operation=operation_name,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            success=success,
            metadata=metadata or {}
        )
        
        # Store metrics (keep last N operations)
        self._execution_metrics.append(metrics)
        if len(self._execution_metrics) > self._max_metrics_history:
            self._execution_metrics.pop(0)
        
        status = "✅" if success else "❌"
        logger.info(
            f"Operation END: {operation_name} {status} "
            f"({duration_ms:.2f}ms)"
        )
        
        return metrics
    
    def get_execution_stats(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get execution statistics for operations.
        
        Args:
            operation_name: Filter by specific operation, or None for all
            
        Returns:
            Dictionary with execution statistics
        """
        # Filter metrics
        if operation_name:
            metrics = [m for m in self._execution_metrics if m.operation == operation_name]
        else:
            metrics = self._execution_metrics
        
        if not metrics:
            return {
                "count": 0,
                "operation": operation_name or "all"
            }
        
        # Calculate statistics
        durations = [m.duration_ms for m in metrics]
        successes = sum(1 for m in metrics if m.success)
        
        durations_sorted = sorted(durations)
        count = len(durations)
        
        return {
            "operation": operation_name or "all",
            "count": count,
            "success_rate": successes / count if count > 0 else 0.0,
            "avg_ms": sum(durations) / count if count > 0 else 0.0,
            "min_ms": min(durations) if durations else 0.0,
            "max_ms": max(durations) if durations else 0.0,
            "p50_ms": durations_sorted[count // 2] if count > 0 else 0.0,
            "p95_ms": durations_sorted[int(count * 0.95)] if count > 0 else 0.0,
            "p99_ms": durations_sorted[int(count * 0.99)] if count > 0 else 0.0,
        }
    
    def get_recent_operations(self, limit: int = 10) -> list[ExecutionMetrics]:
        """
        Get most recent operation metrics.
        
        Args:
            limit: Maximum number of operations to return
            
        Returns:
            List of recent ExecutionMetrics
        """
        return self._execution_metrics[-limit:]
    
    # ==================== Cache Statistics ====================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache hit rate statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        market_total = self._market_cache_hits + self._market_cache_misses
        decision_total = self._decision_cache_hits + self._decision_cache_misses
        
        return {
            "market_cache": {
                "hits": self._market_cache_hits,
                "misses": self._market_cache_misses,
                "hit_rate": self._market_cache_hits / market_total if market_total > 0 else 0.0,
                "size": len(self._market_cache),
                "ttl_seconds": self._market_cache_ttl
            },
            "decision_cache": {
                "hits": self._decision_cache_hits,
                "misses": self._decision_cache_misses,
                "hit_rate": self._decision_cache_hits / decision_total if decision_total > 0 else 0.0,
                "size": len(self._decision_cache),
                "ttl_seconds": self._decision_cache_ttl
            }
        }
    
    def reset_cache_stats(self) -> None:
        """Reset cache hit/miss counters."""
        self._market_cache_hits = 0
        self._market_cache_misses = 0
        self._decision_cache_hits = 0
        self._decision_cache_misses = 0
        logger.info("Cache statistics reset")
    
    # ==================== Utility Methods ====================
    
    def cleanup_expired_entries(self) -> Dict[str, int]:
        """
        Remove expired entries from all caches.
        
        Returns:
            Dictionary with count of removed entries per cache
        """
        current_time = time.time()
        
        # Clean market cache
        market_expired = [
            key for key, entry in self._market_cache.items()
            if current_time - entry.timestamp >= self._market_cache_ttl
        ]
        for key in market_expired:
            del self._market_cache[key]
        
        # Clean decision cache
        decision_expired = [
            key for key, entry in self._decision_cache.items()
            if current_time - entry.timestamp >= self._decision_cache_ttl
        ]
        for key in decision_expired:
            del self._decision_cache[key]
        
        result = {
            "market_cache_expired": len(market_expired),
            "decision_cache_expired": len(decision_expired)
        }
        
        if market_expired or decision_expired:
            logger.info(f"Cleanup: removed {result}")
        
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of engine status.
        
        Returns:
            Dictionary with cache stats, execution stats, and overall health
        """
        summary = {
            "cache_stats": self.get_cache_stats(),
            "execution_stats": self.get_execution_stats(),
            "recent_operations": [
                {
                    "operation": m.operation,
                    "duration_ms": m.duration_ms,
                    "success": m.success,
                    "timestamp": datetime.fromtimestamp(m.end_time).isoformat()
                }
                for m in self.get_recent_operations(5)
            ]
        }
        
        # Add API call tracking stats (Task 13.4)
        if self._api_tracker:
            summary["api_call_stats"] = self._api_tracker.get_stats()
        
        return summary
    
    def get_api_call_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get API call reduction statistics.
        
        Returns:
            Dictionary with API call statistics, or None if tracking disabled
        """
        if self._api_tracker:
            return self._api_tracker.get_stats()
        return None
    
    def log_cache_hit_rates(self) -> None:
        """
        Log detailed cache hit rates for all caches.
        
        This method logs:
        - Market data cache hit rate
        - LLM decision cache hit rate
        - API call reduction statistics
        - Per-endpoint breakdown
        """
        logger.info("=" * 70)
        logger.info("CACHE HIT RATE REPORT")
        logger.info("=" * 70)
        
        cache_stats = self.get_cache_stats()
        
        # Market cache
        market = cache_stats["market_cache"]
        logger.info(
            f"Market Data Cache: {market['hit_rate']*100:.2f}% hit rate "
            f"({market['hits']}/{market['hits']+market['misses']} hits)"
        )
        
        # Decision cache
        decision = cache_stats["decision_cache"]
        logger.info(
            f"LLM Decision Cache: {decision['hit_rate']*100:.2f}% hit rate "
            f"({decision['hits']}/{decision['hits']+decision['misses']} hits)"
        )
        
        # API call tracking
        if self._api_tracker:
            logger.info("")
            self._api_tracker.log_cache_hit_rates()
        
        logger.info("=" * 70)
    
    def verify_cache_reduction(self, target: float = 0.80) -> bool:
        """
        Verify that caching achieves the target API call reduction.
        
        Args:
            target: Target reduction percentage (default: 0.80 = 80%)
            
        Returns:
            True if reduction meets or exceeds target, False otherwise
        """
        if not self._api_tracker:
            logger.warning("API call tracking not enabled, cannot verify reduction")
            return False
        
        stats = self._api_tracker.get_stats()
        overall = stats["overall"]
        
        reduction = overall["reduction_percentage"]
        meets_target = reduction >= target
        
        if meets_target:
            logger.info(
                f"✅ Cache reduction verification PASSED: "
                f"{reduction*100:.2f}% >= {target*100:.0f}%"
            )
        else:
            logger.error(
                f"❌ Cache reduction verification FAILED: "
                f"{reduction*100:.2f}% < {target*100:.0f}%"
            )
        
        return meets_target
    
    def get_api_call_report(self) -> Optional[str]:
        """
        Get detailed API call reduction report.
        
        Returns:
            Formatted report string, or None if tracking disabled
        """
        if self._api_tracker:
            return self._api_tracker.get_detailed_report()
        return None
