# Memory Monitoring System

## Overview

The Memory Monitoring system tracks memory usage over 24-hour periods, detects memory leaks, and verifies that deque size limits are working correctly. This ensures the bot runs reliably without memory issues during long-term autonomous operation.

## Features

### 1. Memory Usage Tracking
- Takes snapshots every 5 minutes (configurable)
- Tracks RSS (Resident Set Size) and VMS (Virtual Memory Size)
- Monitors system memory percentage and available memory
- Maintains 24-hour history (288 snapshots at 5-minute intervals)

### 2. Memory Leak Detection
- Analyzes memory growth rate over time
- Detects sustained memory growth (> 10 MB/hour by default)
- Calculates confidence level (low/medium/high) based on consistency
- Requires minimum 2 hours of data and 24 samples for reliable detection

### 3. Deque Size Limit Verification
- Tracks all registered deques (56 total in the bot)
- Verifies each deque has a maxlen limit set
- Monitors current size vs. maximum size
- Alerts if any deque exceeds its limit

### 4. Automatic Garbage Collection
- Forces garbage collection when memory exceeds 500 MB
- Logs objects collected and memory freed
- Helps prevent memory buildup during long runs

## Integration with Main Orchestrator

The memory monitor is integrated into the main orchestrator at several points:

### Initialization
```python
self.memory_monitor = MemoryMonitor(
    snapshot_interval_seconds=300,  # 5 minutes
    max_snapshots=288,  # 24 hours
    leak_threshold_mb_per_hour=10.0,
    high_memory_threshold_percent=80.0
)
```

### Deque Registration
All deques from the trading strategy are registered for monitoring:
- Binance price history (4 assets × 1 = 4 deques)
- Binance volume history (4 assets × 1 = 4 deques)
- Multi-timeframe price history (4 assets × 3 timeframes = 12 deques)
- Multi-timeframe volume history (4 assets × 3 timeframes = 12 deques)
- **Total: 32 deques tracked**

### Heartbeat Check
Memory snapshots are taken during heartbeat checks (every 60 seconds):
```python
if self.memory_monitor.should_take_snapshot():
    snapshot = self.memory_monitor.take_snapshot()
```

### 24-Hour Report
A comprehensive memory report is generated every 24 hours:
- Memory usage statistics (current, min, max, average)
- Memory leak detection results
- Deque size limit verification
- Alerts sent for any issues detected

## Memory Report Example

```
================================================================================
24-HOUR MEMORY USAGE REPORT
================================================================================

MEMORY USAGE:
  Current: 245.3 MB
  Average: 238.7 MB
  Min: 220.1 MB
  Max: 251.4 MB
  Samples: 288

MEMORY LEAK DETECTION:
  ✅ No leak detected
  Growth rate: 2.15 MB/hour (threshold: 10.0)
  Details: Growth rate: 2.15 MB/hour (65.3% of samples growing). Threshold: 10.0 MB/hour

DEQUE SIZE LIMITS:
  ✅ All deques within limits
  ✅ binance_price_history_BTC: 8234/10000 (82.3% full)
  ✅ binance_volume_history_BTC: 3456/5000 (69.1% full)
  ✅ mtf_price_BTC_1m: 60/60 (100.0% full)
  ✅ mtf_price_BTC_5m: 58/60 (96.7% full)
  ... (32 deques total)

================================================================================
```

## Alerts

The system sends alerts for:

1. **Memory Leak Detected** (Warning)
   - Triggered when growth rate exceeds threshold
   - Includes growth rate, total growth, and confidence level

2. **Deque Limits Exceeded** (Error)
   - Triggered when any deque exceeds its maxlen
   - Lists all failed deques

3. **High Memory Usage** (Warning)
   - Triggered when memory usage exceeds 80%
   - Includes RSS, system percentage, and available memory
   - Respects 30-minute cooldown to avoid spam

## Configuration

Key configuration parameters:

- `snapshot_interval_seconds`: How often to take snapshots (default: 300 = 5 minutes)
- `max_snapshots`: Maximum snapshots to keep (default: 288 = 24 hours)
- `leak_threshold_mb_per_hour`: Growth rate indicating leak (default: 10.0 MB/hour)
- `high_memory_threshold_percent`: Alert threshold (default: 80%)

## Testing

The memory monitor includes comprehensive tests:

### Unit Tests (`test_memory_monitor.py`)
- Memory snapshot functionality
- Deque tracking and limit checking
- Memory leak detection algorithms
- Statistics and reporting
- Garbage collection
- High memory alerting

### Integration Tests (`test_memory_monitor_integration.py`)
- Integration with orchestrator patterns
- Deque registration patterns
- Heartbeat snapshot patterns
- 24-hour report generation
- Memory leak detection workflows

All tests pass successfully, validating the implementation.

## Performance Impact

The memory monitor has minimal performance impact:
- Snapshots taken every 5 minutes (not every cycle)
- Deque size checks are O(1) operations
- Memory leak detection only runs during report generation
- No impact on trading logic or execution speed

## Benefits

1. **Early Warning**: Detect memory issues before they cause crashes
2. **Root Cause Analysis**: Identify which deques are growing unexpectedly
3. **Autonomous Operation**: Bot can run for weeks without manual monitoring
4. **Data-Driven Optimization**: Historical data helps optimize deque sizes
5. **Production Readiness**: Essential for 24/7 autonomous trading

## Future Enhancements

Potential improvements:
- Export memory data to Prometheus for visualization
- Add memory usage predictions based on historical trends
- Implement automatic deque size adjustments
- Add per-component memory tracking
- Create memory usage dashboards
