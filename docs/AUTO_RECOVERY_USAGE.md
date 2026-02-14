# Auto-Recovery System Usage Guide

## Overview

The `AutoRecoverySystem` provides automatic recovery from common errors with exponential backoff (10s, 30s, 60s). It handles:

- **API errors**: Reconnect to Polymarket API
- **Balance errors**: Refresh balance data
- **WebSocket errors**: Reconnect WebSocket feeds

**Validates Requirement 7.12**: Auto-recover from anomalies (API errors, network issues)

## Features

- ✅ Exponential backoff: 10s → 30s → 60s
- ✅ Independent retry counters per error type
- ✅ Comprehensive logging of all recovery attempts
- ✅ Recovery statistics and monitoring
- ✅ Automatic counter reset on success
- ✅ Max 3 attempts before giving up

## Basic Usage

### 1. Initialize the System

```python
from src.autonomous_risk_manager import AutoRecoverySystem

# Initialize in MainOrchestrator.__init__()
self.auto_recovery = AutoRecoverySystem()
```

### 2. Recover from API Errors

```python
async def fetch_markets_with_recovery(self):
    """Fetch markets with automatic recovery on API errors."""
    try:
        markets = await self._fetch_markets()
        return markets
    except Exception as e:
        logger.warning(f"API error: {e}")
        
        # Attempt recovery
        async def reconnect():
            # Reinitialize API client or reconnect
            await self._reinit_api_client()
        
        success = await self.auto_recovery.recover_from_api_error(
            error=e,
            reconnect_func=reconnect,
            context="market_fetch"
        )
        
        if success:
            # Retry the operation
            return await self._fetch_markets()
        else:
            # Recovery failed, propagate error
            raise
```

### 3. Recover from Balance Errors

```python
async def check_balance_with_recovery(self):
    """Check balance with automatic recovery on errors."""
    try:
        balance = await self.fund_manager.check_balance()
        return balance
    except Exception as e:
        logger.warning(f"Balance error: {e}")
        
        # Attempt recovery
        async def refresh():
            # Refresh balance data
            await self.fund_manager.refresh_balance()
        
        success = await self.auto_recovery.recover_from_balance_error(
            error=e,
            refresh_func=refresh,
            context="balance_check"
        )
        
        if success:
            # Retry the operation
            return await self.fund_manager.check_balance()
        else:
            # Recovery failed, use cached balance or default
            return Decimal('0')
```

### 4. Recover from WebSocket Errors

```python
async def handle_websocket_disconnect(self, error: Exception):
    """Handle WebSocket disconnection with automatic recovery."""
    logger.warning(f"WebSocket disconnected: {error}")
    
    # Attempt recovery
    async def reconnect():
        # Reconnect WebSocket
        await self.price_feed.connect()
        # Resubscribe to tokens
        await self.price_feed.subscribe(self._subscribed_tokens)
    
    success = await self.auto_recovery.recover_from_websocket_error(
        error=error,
        reconnect_func=reconnect,
        context="price_feed"
    )
    
    if not success:
        logger.critical("WebSocket recovery failed - manual intervention required")
```

## Integration Example: Main Orchestrator

```python
async def _scan_and_execute(self) -> None:
    """Scan markets and execute trades with auto-recovery."""
    try:
        # Fetch markets
        markets = await self._fetch_markets()
        
        # Process markets...
        
    except ConnectionError as e:
        # API connection error - attempt recovery
        logger.warning(f"Connection error: {e}")
        
        async def reconnect():
            # Reinitialize CLOB client
            self.clob_client = ClobClient(
                host=self.config.polymarket_api_url,
                key=self.config.private_key,
                chain_id=self.config.chain_id
            )
        
        success = await self.auto_recovery.recover_from_api_error(
            error=e,
            reconnect_func=reconnect,
            context="scan_and_execute"
        )
        
        if success:
            # Retry the scan
            await self._scan_and_execute()
        else:
            logger.error("API recovery failed - skipping this cycle")
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        self.monitoring.record_error(e, {"operation": "scan_and_execute"})
```

## Monitoring Recovery Statistics

```python
# Get recovery statistics
stats = self.auto_recovery.get_recovery_statistics()

logger.info(f"Recovery stats: {stats['total_attempts']} attempts, "
           f"{stats['success_rate']:.1%} success rate")

# Log by error type
for error_type, counts in stats['by_type'].items():
    logger.info(f"{error_type}: {counts['successful']}/{counts['total']} successful")

# Check recent attempts
for attempt in stats['recent_attempts'][-5:]:
    logger.info(f"Recent: {attempt['error_type']} at {attempt['timestamp']} "
               f"- {'✅' if attempt['success'] else '❌'}")
```

## Advanced Usage

### Manual Counter Reset

```python
# Reset all attempt counters (useful after manual intervention)
self.auto_recovery.reset_attempt_counters()
```

### Clear History

```python
# Clear recovery history (useful for testing or cleanup)
self.auto_recovery.clear_history()
```

### Custom Backoff Delays

The system uses fixed backoff delays: 10s, 30s, 60s. To customize, modify the class constants:

```python
class AutoRecoverySystem:
    BACKOFF_DELAYS = [10, 30, 60]  # Customize here
    MAX_ATTEMPTS = 3  # Customize max attempts
```

## Best Practices

1. **Always provide context**: Include operation context in recovery calls for better logging
2. **Implement proper reconnect functions**: Ensure reconnect functions fully reinitialize the connection
3. **Monitor statistics**: Regularly check recovery statistics to identify recurring issues
4. **Handle max attempts**: Always handle the case where recovery fails after max attempts
5. **Log appropriately**: Use appropriate log levels (warning for attempts, critical for failures)

## Error Handling Flow

```
┌─────────────────┐
│  Operation      │
│  Fails          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Detect Error   │
│  Type           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Attempt 1      │
│  (10s backoff)  │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Success?│
    └────┬────┘
         │
    No   │   Yes
    ▼    │    ▼
┌─────────────────┐  ┌─────────────────┐
│  Attempt 2      │  │  Reset Counter  │
│  (30s backoff)  │  │  Return Success │
└────────┬────────┘  └─────────────────┘
         │
    ┌────┴────┐
    │ Success?│
    └────┬────┘
         │
    No   │   Yes
    ▼    │    ▼
┌─────────────────┐  ┌─────────────────┐
│  Attempt 3      │  │  Reset Counter  │
│  (60s backoff)  │  │  Return Success │
└────────┬────────┘  └─────────────────┘
         │
    ┌────┴────┐
    │ Success?│
    └────┬────┘
         │
    No   │   Yes
    ▼    │    ▼
┌─────────────────┐  ┌─────────────────┐
│  Max Attempts   │  │  Reset Counter  │
│  Reached        │  │  Return Success │
│  Reset Counter  │  └─────────────────┘
│  Return Failure │
└─────────────────┘
```

## Testing

The auto-recovery system includes comprehensive unit tests:

```bash
# Run all tests
python -m pytest tests/test_auto_recovery_system.py -v

# Run specific test
python -m pytest tests/test_auto_recovery_system.py::test_api_error_recovery_success -v
```

## Logging Output Examples

### Successful Recovery
```
WARNING - API error detected (attempt 1/3): Connection timeout [market_fetch] - attempting recovery in 10s
INFO - ✅ API recovery successful after 10s backoff
```

### Failed Recovery
```
WARNING - API error detected (attempt 1/3): Connection timeout [market_fetch] - attempting recovery in 10s
ERROR - ❌ API recovery failed: Still failing
WARNING - API error detected (attempt 2/3): Connection timeout [market_fetch] - attempting recovery in 30s
ERROR - ❌ API recovery failed: Still failing
WARNING - API error detected (attempt 3/3): Connection timeout [market_fetch] - attempting recovery in 60s
ERROR - ❌ API recovery failed: Still failing
CRITICAL - API recovery failed after 3 attempts - manual intervention required
```

## Integration with Monitoring

```python
# Add recovery statistics to heartbeat check
async def heartbeat_check(self) -> HealthStatus:
    # ... existing checks ...
    
    # Check recovery statistics
    recovery_stats = self.auto_recovery.get_recovery_statistics()
    
    if recovery_stats['failed_attempts'] > 10:
        issues.append(f"High recovery failure rate: {recovery_stats['failed_attempts']} failures")
    
    # Log recovery stats
    logger.info(f"Recovery: {recovery_stats['total_attempts']} attempts, "
               f"{recovery_stats['success_rate']:.1%} success rate")
    
    return HealthStatus(is_healthy=len(issues) == 0, issues=issues)
```

## Conclusion

The AutoRecoverySystem provides robust, automatic error recovery with minimal code changes. It handles common failure scenarios autonomously, reducing manual intervention and improving system reliability.

For questions or issues, check the test file `tests/test_auto_recovery_system.py` for comprehensive usage examples.
