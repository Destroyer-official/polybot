"""
Unit tests for Memory Monitor.

Validates Task 13.3:
- Track memory usage over 24-hour period
- Check for memory leaks
- Verify deque size limits are working
"""

import pytest
import time
from datetime import datetime, timedelta
from collections import deque
from unittest.mock import Mock, patch, MagicMock

from src.memory_monitor import MemoryMonitor, MemorySnapshot, MemoryLeakReport


@pytest.fixture
def memory_monitor():
    """Create a memory monitor for testing."""
    return MemoryMonitor(
        snapshot_interval_seconds=1,  # 1 second for fast tests
        max_snapshots=100,
        leak_threshold_mb_per_hour=10.0,
        high_memory_threshold_percent=80.0
    )


class TestMemorySnapshot:
    """Test memory snapshot functionality."""
    
    def test_take_snapshot(self, memory_monitor):
        """Test taking a memory snapshot."""
        snapshot = memory_monitor.take_snapshot()
        
        assert isinstance(snapshot, MemorySnapshot)
        assert snapshot.rss_mb > 0
        assert snapshot.vms_mb > 0
        assert 0 <= snapshot.percent <= 100
        assert snapshot.available_mb > 0
        assert len(memory_monitor.snapshots) == 1
    
    def test_snapshot_interval(self, memory_monitor):
        """Test snapshot interval timing."""
        # First snapshot should always be taken
        assert memory_monitor.should_take_snapshot()
        
        memory_monitor.take_snapshot()
        
        # Immediately after, should not take another
        assert not memory_monitor.should_take_snapshot()
        
        # After interval, should take another
        time.sleep(1.1)
        assert memory_monitor.should_take_snapshot()
    
    def test_snapshot_history_limit(self, memory_monitor):
        """Test that snapshot history respects max_snapshots limit."""
        max_snapshots = memory_monitor.max_snapshots
        
        # Take more snapshots than the limit
        for _ in range(max_snapshots + 50):
            memory_monitor.take_snapshot()
            time.sleep(0.01)  # Small delay
        
        # Should not exceed max
        assert len(memory_monitor.snapshots) == max_snapshots


class TestDequeTracking:
    """Test deque size tracking."""
    
    def test_register_deque(self, memory_monitor):
        """Test registering a deque for tracking."""
        test_deque = deque(maxlen=100)
        
        memory_monitor.register_deque("test_deque", test_deque)
        
        assert "test_deque" in memory_monitor.tracked_deques
        assert memory_monitor.tracked_deques["test_deque"] is test_deque
    
    def test_deque_size_in_snapshot(self, memory_monitor):
        """Test that deque sizes are captured in snapshots."""
        test_deque = deque(maxlen=100)
        test_deque.extend([1, 2, 3, 4, 5])
        
        memory_monitor.register_deque("test_deque", test_deque)
        snapshot = memory_monitor.take_snapshot()
        
        assert "test_deque" in snapshot.deque_sizes
        assert snapshot.deque_sizes["test_deque"] == 5
    
    def test_check_deque_limits_ok(self, memory_monitor):
        """Test checking deque limits when all are within limits."""
        test_deque = deque(maxlen=100)
        test_deque.extend(range(50))  # Half full
        
        memory_monitor.register_deque("test_deque", test_deque)
        results = memory_monitor.check_deque_limits()
        
        assert results["test_deque"] is True
    
    def test_check_deque_limits_no_maxlen(self, memory_monitor):
        """Test checking deque without maxlen (should warn)."""
        test_deque = deque()  # No maxlen
        test_deque.extend(range(50))
        
        memory_monitor.register_deque("unlimited_deque", test_deque)
        results = memory_monitor.check_deque_limits()
        
        assert results["unlimited_deque"] is False
    
    def test_get_deque_stats(self, memory_monitor):
        """Test getting deque statistics."""
        test_deque = deque(maxlen=100)
        test_deque.extend(range(75))  # 75% full
        
        memory_monitor.register_deque("test_deque", test_deque)
        stats = memory_monitor.get_deque_stats()
        
        assert "test_deque" in stats
        assert stats["test_deque"]["current_size"] == 75
        assert stats["test_deque"]["max_size"] == 100
        assert stats["test_deque"]["utilization_pct"] == 75.0


class TestMemoryLeakDetection:
    """Test memory leak detection."""
    
    def test_insufficient_data(self, memory_monitor):
        """Test leak detection with insufficient data."""
        # Take only a few snapshots
        for _ in range(5):
            memory_monitor.take_snapshot()
        
        report = memory_monitor.detect_memory_leak(min_samples=24)
        
        assert not report.leak_detected
        assert report.confidence == "low"
        assert "Insufficient data" in report.details
    
    def test_insufficient_duration(self, memory_monitor):
        """Test leak detection with insufficient duration."""
        # Take many snapshots quickly
        for _ in range(50):
            memory_monitor.take_snapshot()
            time.sleep(0.01)
        
        report = memory_monitor.detect_memory_leak(min_duration_hours=2.0)
        
        assert not report.leak_detected
        assert report.confidence == "low"
        assert "Insufficient duration" in report.details
    
    @patch('src.memory_monitor.MemoryMonitor.take_snapshot')
    def test_detect_memory_leak(self, mock_snapshot, memory_monitor):
        """Test detecting a memory leak with simulated growth."""
        # Simulate memory growing over time
        base_time = datetime.now()
        base_memory = 100.0
        
        # Create 50 snapshots over 3 hours with steady growth
        for i in range(50):
            snapshot = MemorySnapshot(
                timestamp=base_time + timedelta(hours=i * 0.06),  # 3.6 min intervals
                rss_mb=base_memory + (i * 1.0),  # 1 MB growth per snapshot = ~17 MB/hour
                vms_mb=200.0,
                percent=50.0,
                available_mb=1000.0,
                deque_sizes={}
            )
            memory_monitor.snapshots.append(snapshot)
        
        report = memory_monitor.detect_memory_leak(
            min_duration_hours=2.0,
            min_samples=24
        )
        
        # Should detect leak (17 MB/hour > 10 MB/hour threshold)
        assert report.leak_detected
        assert report.growth_rate_mb_per_hour > 10.0
        assert report.confidence in ["medium", "high"]
    
    @patch('src.memory_monitor.MemoryMonitor.take_snapshot')
    def test_no_leak_stable_memory(self, mock_snapshot, memory_monitor):
        """Test no leak detection with stable memory."""
        # Simulate stable memory over time
        base_time = datetime.now()
        base_memory = 100.0
        
        # Create 50 snapshots over 3 hours with minimal fluctuation
        for i in range(50):
            snapshot = MemorySnapshot(
                timestamp=base_time + timedelta(hours=i * 0.06),
                rss_mb=base_memory + (i % 2) * 0.5,  # Small fluctuation
                vms_mb=200.0,
                percent=50.0,
                available_mb=1000.0,
                deque_sizes={}
            )
            memory_monitor.snapshots.append(snapshot)
        
        report = memory_monitor.detect_memory_leak(
            min_duration_hours=2.0,
            min_samples=24
        )
        
        # Should not detect leak
        assert not report.leak_detected
        assert abs(report.growth_rate_mb_per_hour) < 10.0


class TestMemoryStats:
    """Test memory statistics."""
    
    def test_get_current_memory(self, memory_monitor):
        """Test getting current memory usage."""
        current_mb = memory_monitor.get_current_memory_mb()
        
        assert current_mb > 0
        assert isinstance(current_mb, float)
    
    def test_get_memory_stats_empty(self, memory_monitor):
        """Test getting stats with no snapshots."""
        stats = memory_monitor.get_memory_stats()
        
        assert stats["current_mb"] > 0
        assert stats["min_mb"] == 0.0
        assert stats["max_mb"] == 0.0
        assert stats["avg_mb"] == 0.0
        assert stats["samples"] == 0
    
    def test_get_memory_stats_with_data(self, memory_monitor):
        """Test getting stats with snapshots."""
        # Take several snapshots
        for _ in range(10):
            memory_monitor.take_snapshot()
            time.sleep(0.01)
        
        stats = memory_monitor.get_memory_stats()
        
        assert stats["samples"] == 10
        assert stats["min_mb"] > 0
        assert stats["max_mb"] >= stats["min_mb"]
        assert stats["avg_mb"] >= stats["min_mb"]
        assert stats["avg_mb"] <= stats["max_mb"]
    
    def test_get_snapshot_history_all(self, memory_monitor):
        """Test getting all snapshot history."""
        for _ in range(10):
            memory_monitor.take_snapshot()
            time.sleep(0.01)
        
        history = memory_monitor.get_snapshot_history()
        
        assert len(history) == 10
    
    def test_get_snapshot_history_filtered(self, memory_monitor):
        """Test getting filtered snapshot history."""
        # Create snapshots with different timestamps
        base_time = datetime.now()
        for i in range(10):
            snapshot = MemorySnapshot(
                timestamp=base_time - timedelta(hours=i),
                rss_mb=100.0,
                vms_mb=200.0,
                percent=50.0,
                available_mb=1000.0,
                deque_sizes={}
            )
            memory_monitor.snapshots.append(snapshot)
        
        # Get last 5 hours
        history = memory_monitor.get_snapshot_history(hours=5.0)
        
        # Should have snapshots from 0-4 hours ago (5 snapshots)
        assert len(history) == 5


class TestReport:
    """Test report generation."""
    
    def test_generate_report_no_data(self, memory_monitor):
        """Test generating report with no data."""
        report = memory_monitor.generate_24h_report()
        
        assert "No memory data available" in report
    
    def test_generate_report_with_data(self, memory_monitor):
        """Test generating report with data."""
        # Add some test data
        test_deque = deque(maxlen=100)
        test_deque.extend(range(50))
        memory_monitor.register_deque("test_deque", test_deque)
        
        # Take snapshots
        for _ in range(10):
            memory_monitor.take_snapshot()
            time.sleep(0.01)
        
        report = memory_monitor.generate_24h_report()
        
        assert "24-HOUR MEMORY USAGE REPORT" in report
        assert "MEMORY USAGE:" in report
        assert "MEMORY LEAK DETECTION:" in report
        assert "DEQUE SIZE LIMITS:" in report
        assert "test_deque" in report


class TestGarbageCollection:
    """Test garbage collection."""
    
    def test_force_garbage_collection(self, memory_monitor):
        """Test forcing garbage collection."""
        # Create some garbage
        garbage = [list(range(1000)) for _ in range(100)]
        del garbage
        
        # Force GC
        collected, freed_mb = memory_monitor.force_garbage_collection()
        
        assert isinstance(collected, int)
        assert isinstance(freed_mb, float)
        # Note: freed_mb might be negative if memory increased


class TestHighMemoryAlert:
    """Test high memory alerting."""
    
    @patch('src.memory_monitor.psutil.virtual_memory')
    def test_high_memory_alert(self, mock_vm, memory_monitor):
        """Test high memory alert is triggered."""
        # Mock high memory usage
        mock_vm.return_value = Mock(
            percent=85.0,  # Above 80% threshold
            available=1024 * 1024 * 100  # 100 MB available
        )
        
        # Take snapshot (should trigger alert)
        snapshot = memory_monitor.take_snapshot()
        
        # Alert should be recorded
        assert memory_monitor.last_high_memory_alert is not None
    
    @patch('src.memory_monitor.psutil.virtual_memory')
    def test_high_memory_alert_cooldown(self, mock_vm, memory_monitor):
        """Test high memory alert respects cooldown."""
        # Mock high memory usage
        mock_vm.return_value = Mock(
            percent=85.0,
            available=1024 * 1024 * 100
        )
        
        # First alert
        memory_monitor.take_snapshot()
        first_alert_time = memory_monitor.last_high_memory_alert
        
        # Immediate second snapshot (should not alert due to cooldown)
        time.sleep(0.1)
        memory_monitor.take_snapshot()
        
        # Alert time should not change
        assert memory_monitor.last_high_memory_alert == first_alert_time


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
