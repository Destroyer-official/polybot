"""
Memory Usage Monitor for Polymarket Trading Bot.

Tracks memory usage over 24-hour periods, detects memory leaks,
and verifies deque size limits are working correctly.

Validates Requirements: Task 13.3
"""

import logging
import psutil
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import gc

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Single memory usage snapshot."""
    timestamp: datetime
    rss_mb: float  # Resident Set Size in MB
    vms_mb: float  # Virtual Memory Size in MB
    percent: float  # Memory usage percentage
    available_mb: float  # Available system memory in MB
    
    # Deque sizes (if tracked)
    deque_sizes: Dict[str, int] = field(default_factory=dict)


@dataclass
class MemoryLeakReport:
    """Memory leak detection report."""
    leak_detected: bool
    growth_rate_mb_per_hour: float
    total_growth_mb: float
    duration_hours: float
    start_memory_mb: float
    end_memory_mb: float
    confidence: str  # "low", "medium", "high"
    details: str


class MemoryMonitor:
    """
    Monitor memory usage over 24-hour periods.
    
    Features:
    - Track RSS, VMS, and percentage over time
    - Detect memory leaks (sustained growth)
    - Verify deque size limits are working
    - Alert on excessive memory usage
    - Generate 24-hour memory reports
    """
    
    def __init__(
        self,
        snapshot_interval_seconds: int = 300,  # 5 minutes
        max_snapshots: int = 288,  # 24 hours at 5-min intervals
        leak_threshold_mb_per_hour: float = 10.0,  # 10 MB/hour growth = leak
        high_memory_threshold_percent: float = 80.0,  # Alert at 80% usage
    ):
        """
        Initialize memory monitor.
        
        Args:
            snapshot_interval_seconds: How often to take snapshots (default 5 min)
            max_snapshots: Maximum snapshots to keep (default 288 = 24 hours)
            leak_threshold_mb_per_hour: Growth rate indicating leak (MB/hour)
            high_memory_threshold_percent: Alert threshold for memory usage
        """
        self.snapshot_interval = snapshot_interval_seconds
        self.max_snapshots = max_snapshots
        self.leak_threshold = leak_threshold_mb_per_hour
        self.high_memory_threshold = high_memory_threshold_percent
        
        # Memory snapshots (limited to 24 hours)
        self.snapshots: deque = deque(maxlen=max_snapshots)
        
        # Last snapshot time
        self.last_snapshot_time: Optional[datetime] = None
        
        # Process handle
        self.process = psutil.Process()
        
        # Deque tracking (optional)
        self.tracked_deques: Dict[str, deque] = {}
        
        # Alert state
        self.last_high_memory_alert: Optional[datetime] = None
        self.alert_cooldown_minutes = 30  # Don't spam alerts
        
        logger.info(f"📊 Memory Monitor initialized:")
        logger.info(f"   Snapshot interval: {snapshot_interval_seconds}s")
        logger.info(f"   Max snapshots: {max_snapshots} ({max_snapshots * snapshot_interval_seconds / 3600:.1f} hours)")
        logger.info(f"   Leak threshold: {leak_threshold_mb_per_hour} MB/hour")
        logger.info(f"   High memory alert: {high_memory_threshold_percent}%")
    
    def take_snapshot(self) -> MemorySnapshot:
        """
        Take a memory usage snapshot.
        
        Returns:
            MemorySnapshot with current memory stats
        """
        # Get memory info
        mem_info = self.process.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)  # Convert to MB
        vms_mb = mem_info.vms / (1024 * 1024)
        
        # Get system memory
        sys_mem = psutil.virtual_memory()
        percent = sys_mem.percent
        available_mb = sys_mem.available / (1024 * 1024)
        
        # Track deque sizes
        deque_sizes = {}
        for name, dq in self.tracked_deques.items():
            deque_sizes[name] = len(dq)
        
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            rss_mb=rss_mb,
            vms_mb=vms_mb,
            percent=percent,
            available_mb=available_mb,
            deque_sizes=deque_sizes
        )
        
        # Add to history
        self.snapshots.append(snapshot)
        self.last_snapshot_time = snapshot.timestamp
        
        # Check for high memory usage
        if percent >= self.high_memory_threshold:
            self._check_high_memory_alert(snapshot)
        
        return snapshot
    
    def should_take_snapshot(self) -> bool:
        """
        Check if it's time to take a snapshot.
        
        Returns:
            bool: True if snapshot should be taken
        """
        if self.last_snapshot_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_snapshot_time).total_seconds()
        return elapsed >= self.snapshot_interval
    
    def register_deque(self, name: str, dq: deque) -> None:
        """
        Register a deque for size tracking.
        
        Args:
            name: Descriptive name for the deque
            dq: The deque object to track
        """
        self.tracked_deques[name] = dq
        logger.info(f"📊 Registered deque for tracking: {name} (maxlen={dq.maxlen})")
    
    def check_deque_limits(self) -> Dict[str, bool]:
        """
        Verify all tracked deques respect their maxlen limits.
        
        Returns:
            Dict mapping deque name to whether limit is respected
        """
        results = {}
        
        for name, dq in self.tracked_deques.items():
            if dq.maxlen is None:
                logger.warning(f"⚠️ Deque '{name}' has no maxlen limit!")
                results[name] = False
            else:
                current_size = len(dq)
                limit_ok = current_size <= dq.maxlen
                results[name] = limit_ok
                
                if not limit_ok:
                    logger.error(
                        f"❌ Deque '{name}' exceeded limit! "
                        f"Size: {current_size}, Limit: {dq.maxlen}"
                    )
        
        return results
    
    def detect_memory_leak(
        self,
        min_duration_hours: float = 2.0,
        min_samples: int = 24
    ) -> MemoryLeakReport:
        """
        Detect memory leaks by analyzing growth rate.
        
        A memory leak is detected if:
        1. Memory grows consistently over time
        2. Growth rate exceeds threshold
        3. Sufficient data points exist
        
        Args:
            min_duration_hours: Minimum duration to analyze (default 2 hours)
            min_samples: Minimum number of samples needed
            
        Returns:
            MemoryLeakReport with leak detection results
        """
        if len(self.snapshots) < min_samples:
            return MemoryLeakReport(
                leak_detected=False,
                growth_rate_mb_per_hour=0.0,
                total_growth_mb=0.0,
                duration_hours=0.0,
                start_memory_mb=0.0,
                end_memory_mb=0.0,
                confidence="low",
                details=f"Insufficient data: {len(self.snapshots)} samples (need {min_samples})"
            )
        
        # Get time range
        first_snapshot = self.snapshots[0]
        last_snapshot = self.snapshots[-1]
        duration = (last_snapshot.timestamp - first_snapshot.timestamp).total_seconds() / 3600
        
        if duration < min_duration_hours:
            return MemoryLeakReport(
                leak_detected=False,
                growth_rate_mb_per_hour=0.0,
                total_growth_mb=0.0,
                duration_hours=duration,
                start_memory_mb=first_snapshot.rss_mb,
                end_memory_mb=last_snapshot.rss_mb,
                confidence="low",
                details=f"Insufficient duration: {duration:.1f}h (need {min_duration_hours}h)"
            )
        
        # Calculate growth rate
        start_memory = first_snapshot.rss_mb
        end_memory = last_snapshot.rss_mb
        total_growth = end_memory - start_memory
        growth_rate = total_growth / duration
        
        # Determine confidence based on consistency
        # Check if memory is consistently growing (not just fluctuating)
        growth_samples = 0
        for i in range(1, len(self.snapshots)):
            if self.snapshots[i].rss_mb > self.snapshots[i-1].rss_mb:
                growth_samples += 1
        
        growth_ratio = growth_samples / (len(self.snapshots) - 1)
        
        if growth_ratio > 0.8:
            confidence = "high"
        elif growth_ratio > 0.6:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Detect leak
        leak_detected = (
            growth_rate >= self.leak_threshold and
            confidence in ["medium", "high"]
        )
        
        details = (
            f"Growth rate: {growth_rate:.2f} MB/hour "
            f"({growth_ratio*100:.1f}% of samples growing). "
            f"Threshold: {self.leak_threshold} MB/hour"
        )
        
        if leak_detected:
            logger.warning(
                f"⚠️ Memory leak detected! "
                f"Growth: {growth_rate:.2f} MB/hour "
                f"(confidence: {confidence})"
            )
        
        return MemoryLeakReport(
            leak_detected=leak_detected,
            growth_rate_mb_per_hour=growth_rate,
            total_growth_mb=total_growth,
            duration_hours=duration,
            start_memory_mb=start_memory,
            end_memory_mb=end_memory,
            confidence=confidence,
            details=details
        )
    
    def get_current_memory_mb(self) -> float:
        """
        Get current memory usage in MB.
        
        Returns:
            float: Current RSS memory in MB
        """
        mem_info = self.process.memory_info()
        return mem_info.rss / (1024 * 1024)
    
    def get_memory_stats(self) -> Dict[str, float]:
        """
        Get memory statistics from recent snapshots.
        
        Returns:
            Dict with min, max, avg, current memory usage
        """
        if not self.snapshots:
            return {
                "current_mb": self.get_current_memory_mb(),
                "min_mb": 0.0,
                "max_mb": 0.0,
                "avg_mb": 0.0,
                "samples": 0
            }
        
        rss_values = [s.rss_mb for s in self.snapshots]
        
        return {
            "current_mb": self.snapshots[-1].rss_mb,
            "min_mb": min(rss_values),
            "max_mb": max(rss_values),
            "avg_mb": sum(rss_values) / len(rss_values),
            "samples": len(self.snapshots)
        }
    
    def get_deque_stats(self) -> Dict[str, Dict[str, int]]:
        """
        Get statistics for all tracked deques.
        
        Returns:
            Dict mapping deque name to stats (current_size, max_size, utilization_pct)
        """
        stats = {}
        
        for name, dq in self.tracked_deques.items():
            current_size = len(dq)
            max_size = dq.maxlen if dq.maxlen else 0
            utilization = (current_size / max_size * 100) if max_size > 0 else 0
            
            stats[name] = {
                "current_size": current_size,
                "max_size": max_size,
                "utilization_pct": utilization
            }
        
        return stats
    
    def generate_24h_report(self) -> str:
        """
        Generate a 24-hour memory usage report.
        
        Returns:
            str: Formatted report
        """
        if not self.snapshots:
            return "No memory data available"
        
        # Memory stats
        mem_stats = self.get_memory_stats()
        
        # Leak detection
        leak_report = self.detect_memory_leak()
        
        # Deque stats
        deque_stats = self.get_deque_stats()
        deque_limits_ok = self.check_deque_limits()
        
        # Build report
        report = []
        report.append("=" * 80)
        report.append("24-HOUR MEMORY USAGE REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Memory usage
        report.append("MEMORY USAGE:")
        report.append(f"  Current: {mem_stats['current_mb']:.1f} MB")
        report.append(f"  Average: {mem_stats['avg_mb']:.1f} MB")
        report.append(f"  Min: {mem_stats['min_mb']:.1f} MB")
        report.append(f"  Max: {mem_stats['max_mb']:.1f} MB")
        report.append(f"  Samples: {mem_stats['samples']}")
        report.append("")
        
        # Leak detection
        report.append("MEMORY LEAK DETECTION:")
        if leak_report.leak_detected:
            report.append(f"  ⚠️ LEAK DETECTED (confidence: {leak_report.confidence})")
            report.append(f"  Growth rate: {leak_report.growth_rate_mb_per_hour:.2f} MB/hour")
            report.append(f"  Total growth: {leak_report.total_growth_mb:.1f} MB over {leak_report.duration_hours:.1f}h")
        else:
            report.append(f"  ✅ No leak detected")
            report.append(f"  Growth rate: {leak_report.growth_rate_mb_per_hour:.2f} MB/hour (threshold: {self.leak_threshold})")
        report.append(f"  Details: {leak_report.details}")
        report.append("")
        
        # Deque limits
        report.append("DEQUE SIZE LIMITS:")
        if not deque_stats:
            report.append("  No deques tracked")
        else:
            all_ok = all(deque_limits_ok.values())
            if all_ok:
                report.append("  ✅ All deques within limits")
            else:
                report.append("  ⚠️ Some deques exceeded limits!")
            
            for name, stats in deque_stats.items():
                limit_ok = deque_limits_ok.get(name, False)
                status = "✅" if limit_ok else "❌"
                report.append(
                    f"  {status} {name}: {stats['current_size']}/{stats['max_size']} "
                    f"({stats['utilization_pct']:.1f}% full)"
                )
        report.append("")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def force_garbage_collection(self) -> Tuple[int, float]:
        """
        Force garbage collection and measure memory freed.
        
        Returns:
            Tuple of (objects_collected, memory_freed_mb)
        """
        before_mb = self.get_current_memory_mb()
        
        # Force GC
        collected = gc.collect()
        
        after_mb = self.get_current_memory_mb()
        freed_mb = before_mb - after_mb
        
        logger.info(f"🗑️ Garbage collection: {collected} objects, {freed_mb:.2f} MB freed")
        
        return collected, freed_mb
    
    def _check_high_memory_alert(self, snapshot: MemorySnapshot) -> None:
        """
        Check if high memory alert should be sent.
        
        Args:
            snapshot: Current memory snapshot
        """
        # Check cooldown
        if self.last_high_memory_alert:
            elapsed = (datetime.now() - self.last_high_memory_alert).total_seconds() / 60
            if elapsed < self.alert_cooldown_minutes:
                return  # Still in cooldown
        
        # Send alert
        logger.warning(
            f"⚠️ HIGH MEMORY USAGE: {snapshot.percent:.1f}% "
            f"(RSS: {snapshot.rss_mb:.1f} MB, Available: {snapshot.available_mb:.1f} MB)"
        )
        
        self.last_high_memory_alert = datetime.now()
    
    def get_snapshot_history(
        self,
        hours: Optional[float] = None
    ) -> List[MemorySnapshot]:
        """
        Get snapshot history for a time period.
        
        Args:
            hours: Number of hours to look back (None = all)
            
        Returns:
            List of MemorySnapshot objects
        """
        if hours is None:
            return list(self.snapshots)
        
        cutoff = datetime.now() - timedelta(hours=hours)
        return [s for s in self.snapshots if s.timestamp >= cutoff]
