"""
Property-based tests for error recovery mechanisms.

Tests the correctness properties of retry logic, RPC failover, gas escalation,
and circuit breaker implementations.
"""

import asyncio
import pytest
import time
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from src.error_recovery import (
    retry_with_backoff,
    RPCEndpointManager,
    GasPriceEscalator,
    CircuitBreaker
)


# Property 29: Network Error Exponential Backoff
# **Validates: Requirements 9.2, 16.1**
@given(
    max_attempts=st.integers(min_value=1, max_value=10),
    base_delay=st.floats(min_value=0.1, max_value=5.0),
    failure_count=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100, deadline=None)
def test_property_exponential_backoff_delays(max_attempts, base_delay, failure_count):
    """
    Property 29: Network Error Exponential Backoff
    
    For any network request failure, the system should retry with exponential backoff
    (1s, 2s, 4s, 8s, max 60s) up to 5 attempts before giving up.
    
    This test verifies:
    1. Delays follow exponential pattern: base_delay * 2^(attempt-1)
    2. Delays are capped at max_delay (60s)
    3. Maximum retry attempts are respected
    4. Function eventually raises exception after max attempts
    """
    assume(failure_count <= max_attempts)
    
    call_count = 0
    delays_observed = []
    
    @retry_with_backoff(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=60.0,
        exponential_base=2.0,
        exceptions=(ValueError,)
    )
    def failing_function():
        nonlocal call_count
        call_count += 1
        if call_count <= failure_count:
            raise ValueError(f"Attempt {call_count} failed")
        return "success"
    
    # Patch sleep to capture delays
    with patch('time.sleep') as mock_sleep:
        if failure_count < max_attempts:
            # Should succeed eventually
            result = failing_function()
            assert result == "success"
            assert call_count == failure_count + 1
        else:
            # Should fail after max_attempts
            with pytest.raises(ValueError):
                failing_function()
            assert call_count == max_attempts
        
        # Verify exponential backoff pattern
        if mock_sleep.call_count > 0:
            for i, call in enumerate(mock_sleep.call_args_list):
                delay = call[0][0]
                delays_observed.append(delay)
                
                # Expected delay: base_delay * 2^i, capped at 60s
                expected_delay = min(base_delay * (2 ** i), 60.0)
                
                # Allow small floating point tolerance
                assert abs(delay - expected_delay) < 0.01, \
                    f"Delay {i+1} should be {expected_delay}s, got {delay}s"


@pytest.mark.asyncio
@given(
    max_attempts=st.integers(min_value=1, max_value=10),
    base_delay=st.floats(min_value=0.01, max_value=1.0),
    failure_count=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=50, deadline=None)
async def test_property_exponential_backoff_async(max_attempts, base_delay, failure_count):
    """
    Property 29: Network Error Exponential Backoff (Async version)
    
    Verifies exponential backoff works correctly for async functions.
    """
    assume(failure_count <= max_attempts)
    
    call_count = 0
    
    @retry_with_backoff(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=60.0,
        exceptions=(ValueError,)
    )
    async def failing_async_function():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.001)  # Simulate async work
        if call_count <= failure_count:
            raise ValueError(f"Attempt {call_count} failed")
        return "success"
    
    with patch('asyncio.sleep') as mock_sleep:
        mock_sleep.return_value = asyncio.sleep(0)  # Make sleep instant
        
        if failure_count < max_attempts:
            result = await failing_async_function()
            assert result == "success"
            assert call_count == failure_count + 1
        else:
            with pytest.raises(ValueError):
                await failing_async_function()
            assert call_count == max_attempts


@given(
    max_attempts=st.integers(min_value=2, max_value=10),
    base_delay=st.floats(min_value=0.1, max_value=2.0)
)
@settings(max_examples=100, deadline=None)
def test_property_retry_eventually_fails(max_attempts, base_delay):
    """
    Property: Retry decorator eventually gives up after max_attempts.
    
    Verifies that the retry decorator doesn't retry indefinitely and properly
    raises the exception after exhausting all retry attempts.
    """
    call_count = 0
    
    @retry_with_backoff(
        max_attempts=max_attempts,
        base_delay=base_delay,
        exceptions=(RuntimeError,)
    )
    def always_failing_function():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Always fails")
    
    with patch('time.sleep'):
        with pytest.raises(RuntimeError, match="Always fails"):
            always_failing_function()
        
        # Should have been called exactly max_attempts times
        assert call_count == max_attempts


# Property 43: RPC Endpoint Failover
# **Validates: Requirements 16.2**
@given(
    num_backups=st.integers(min_value=1, max_value=10),
    failures_before_success=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=100, deadline=None)
def test_property_rpc_failover(num_backups, failures_before_success):
    """
    Property 43: RPC Endpoint Failover
    
    For any RPC endpoint that becomes unavailable, the system should automatically
    failover to the next backup RPC endpoint in the configuration.
    
    This test verifies:
    1. System starts with primary endpoint
    2. Failover occurs when endpoint is marked as failed
    3. All backup endpoints are tried in order
    4. Returns None when all endpoints exhausted
    5. Can reset and retry failed endpoints
    """
    assume(failures_before_success <= num_backups + 1)
    
    primary_url = "https://primary-rpc.example.com"
    backup_urls = [f"https://backup-{i}-rpc.example.com" for i in range(num_backups)]
    
    manager = RPCEndpointManager(primary_url, backup_urls)
    
    # Initially should use primary
    assert manager.get_current_endpoint() == primary_url
    assert manager.is_primary_active()
    
    # Simulate failures
    endpoints_tried = [primary_url]
    current_endpoint = primary_url
    
    for i in range(failures_before_success):
        manager.mark_endpoint_failed(current_endpoint)
        current_endpoint = manager.failover_to_next()
        
        if current_endpoint is not None:
            endpoints_tried.append(current_endpoint)
            # Should be one of the backup URLs
            assert current_endpoint in backup_urls
            # Should not be primary anymore
            assert not manager.is_primary_active()
        else:
            # All endpoints exhausted
            assert i == num_backups  # Failed primary + all backups
            break
    
    # Verify failover behavior
    if failures_before_success == 0:
        # No failures, still on primary
        assert current_endpoint == primary_url
        assert manager.is_primary_active()
    elif failures_before_success <= num_backups:
        # Should have found a working endpoint
        assert current_endpoint is not None
        assert current_endpoint == backup_urls[failures_before_success - 1]
    else:
        # All endpoints should be exhausted
        assert current_endpoint is None
    
    # Test reset functionality
    manager.reset_failed_endpoints()
    assert manager.get_current_endpoint() == primary_url
    assert manager.is_primary_active()


@given(
    num_backups=st.integers(min_value=2, max_value=5)
)
@settings(max_examples=50, deadline=None)
def test_property_rpc_failover_skips_failed_endpoints(num_backups):
    """
    Property: RPC failover skips already-failed endpoints.
    
    Verifies that once an endpoint is marked as failed, it won't be used again
    until reset is called.
    """
    primary_url = "https://primary-rpc.example.com"
    backup_urls = [f"https://backup-{i}-rpc.example.com" for i in range(num_backups)]
    
    manager = RPCEndpointManager(primary_url, backup_urls)
    
    # Mark primary as failed
    manager.mark_endpoint_failed(primary_url)
    first_backup = manager.failover_to_next()
    assert first_backup == backup_urls[0]
    
    # Mark first backup as failed
    manager.mark_endpoint_failed(first_backup)
    second_backup = manager.failover_to_next()
    assert second_backup == backup_urls[1]
    
    # Should skip the already-failed endpoints
    assert second_backup != primary_url
    assert second_backup != first_backup


# Property 44: Gas Price Retry Escalation
# **Validates: Requirements 16.3**
@given(
    initial_gas_price=st.integers(min_value=1_000_000_000, max_value=500_000_000_000),  # 1-500 gwei
    escalation_factor=st.floats(min_value=1.05, max_value=1.5),
    num_escalations=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100, deadline=None)
def test_property_gas_price_escalation(initial_gas_price, escalation_factor, num_escalations):
    """
    Property 44: Gas Price Retry Escalation
    
    For any transaction that fails due to insufficient gas, the system should
    increase the gas price by 10% and retry the transaction.
    
    This test verifies:
    1. Gas price increases by the escalation factor on each retry
    2. Escalation is tracked per transaction
    3. Maximum escalations are enforced
    4. Escalated prices are always higher than previous prices
    """
    assume(num_escalations <= 5)  # Max escalations
    
    escalator = GasPriceEscalator(
        escalation_factor=escalation_factor,
        max_escalations=5
    )
    
    tx_hash = "0x1234567890abcdef"
    current_gas_price = initial_gas_price
    previous_prices = [current_gas_price]
    
    # Escalate multiple times
    for i in range(num_escalations):
        new_gas_price = escalator.escalate_gas_price(current_gas_price, tx_hash)
        
        # New price should be higher than current price
        assert new_gas_price > current_gas_price, \
            f"Escalated price {new_gas_price} should be > {current_gas_price}"
        
        # Calculate expected price
        expected_price = int(current_gas_price * escalation_factor)
        
        # Should match expected escalation (within rounding tolerance)
        assert abs(new_gas_price - expected_price) <= 1, \
            f"Expected {expected_price}, got {new_gas_price}"
        
        # Track escalation count
        assert escalator.get_escalation_count(tx_hash) == i + 1
        
        previous_prices.append(new_gas_price)
        current_gas_price = new_gas_price
    
    # Verify monotonic increase
    for i in range(len(previous_prices) - 1):
        assert previous_prices[i + 1] > previous_prices[i], \
            "Gas prices should monotonically increase"


@given(
    initial_gas_price=st.integers(min_value=1_000_000_000, max_value=100_000_000_000)
)
@settings(max_examples=50, deadline=None)
def test_property_gas_escalation_max_limit(initial_gas_price):
    """
    Property: Gas escalation respects maximum escalation limit.
    
    Verifies that the escalator raises an error when maximum escalations
    are reached for a transaction.
    """
    escalator = GasPriceEscalator(escalation_factor=1.1, max_escalations=5)
    
    tx_hash = "0xabcdef1234567890"
    current_gas_price = initial_gas_price
    
    # Escalate to the maximum
    for i in range(5):
        current_gas_price = escalator.escalate_gas_price(current_gas_price, tx_hash)
    
    # Next escalation should fail
    with pytest.raises(ValueError, match="Maximum gas escalations"):
        escalator.escalate_gas_price(current_gas_price, tx_hash)


# Property 46: Circuit Breaker Activation
# **Validates: Requirements 16.6**
@given(
    failure_threshold=st.integers(min_value=1, max_value=20),
    num_failures=st.integers(min_value=0, max_value=25)
)
@settings(max_examples=100, deadline=None)
def test_property_circuit_breaker_activation(failure_threshold, num_failures):
    """
    Property 46: Circuit Breaker Activation
    
    For any sequence of 10 consecutive failed trades, the system should activate
    the circuit breaker, halt all trading, and require manual reset.
    
    This test verifies:
    1. Circuit remains closed below threshold
    2. Circuit opens at exactly the threshold
    3. Circuit stays open after threshold
    4. Manual reset is required to close circuit
    5. Success resets failure counter when circuit is closed
    """
    breaker = CircuitBreaker(failure_threshold=failure_threshold)
    
    # Initially circuit should be closed
    assert not breaker.is_open
    assert breaker.consecutive_failures == 0
    
    # Record failures
    for i in range(num_failures):
        breaker.record_failure(f"Failure {i + 1}")
        
        if i + 1 < failure_threshold:
            # Circuit should still be closed
            assert not breaker.is_open
            assert breaker.consecutive_failures == i + 1
        else:
            # Circuit should be open
            assert breaker.is_open
            assert breaker.consecutive_failures >= failure_threshold
    
    # Verify final state
    if num_failures >= failure_threshold:
        assert breaker.is_open
        
        # check_circuit should raise exception
        with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
            breaker.check_circuit()
        
        # Manual reset required
        breaker.close_circuit()
        assert not breaker.is_open
        assert breaker.consecutive_failures == 0
    else:
        assert not breaker.is_open
        breaker.check_circuit()  # Should not raise


@given(
    failure_threshold=st.integers(min_value=5, max_value=15),
    failures_before_success=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=100, deadline=None)
def test_property_circuit_breaker_reset_on_success(failure_threshold, failures_before_success):
    """
    Property: Circuit breaker resets failure counter on success.
    
    Verifies that a successful operation resets the consecutive failure counter,
    preventing circuit from opening due to non-consecutive failures.
    """
    assume(failures_before_success < failure_threshold)
    
    breaker = CircuitBreaker(failure_threshold=failure_threshold)
    
    # Record some failures (but not enough to open circuit)
    for i in range(failures_before_success):
        breaker.record_failure(f"Failure {i + 1}")
    
    assert breaker.consecutive_failures == failures_before_success
    assert not breaker.is_open
    
    # Record success - should reset counter
    breaker.record_success()
    
    assert breaker.consecutive_failures == 0
    assert not breaker.is_open
    
    # Can now fail again without opening circuit
    for i in range(failures_before_success):
        breaker.record_failure(f"Failure after reset {i + 1}")
    
    assert breaker.consecutive_failures == failures_before_success
    assert not breaker.is_open


@given(
    failure_threshold=st.integers(min_value=3, max_value=10)
)
@settings(max_examples=50, deadline=None)
def test_property_circuit_breaker_tracks_failure_reasons(failure_threshold):
    """
    Property: Circuit breaker tracks recent failure reasons.
    
    Verifies that the circuit breaker maintains a history of recent failure
    reasons for debugging purposes.
    """
    breaker = CircuitBreaker(failure_threshold=failure_threshold)
    
    reasons = [f"Reason {i}" for i in range(failure_threshold)]
    
    for reason in reasons:
        breaker.record_failure(reason)
    
    status = breaker.get_status()
    
    assert status["is_open"] == True
    assert status["consecutive_failures"] == failure_threshold
    assert len(status["recent_failures"]) > 0
    
    # Should contain at least some of the recent reasons
    for reason in reasons[-5:]:  # Last 5 reasons
        assert reason in status["recent_failures"]
