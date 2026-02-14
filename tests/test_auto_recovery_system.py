"""
Unit tests for AutoRecoverySystem.

Tests the automatic recovery system for handling API errors, balance errors,
and WebSocket errors with exponential backoff.

Validates Requirement 7.12: Auto-recover from anomalies (API errors, network issues)
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.autonomous_risk_manager import AutoRecoverySystem, RecoveryAttempt


@pytest.fixture
def recovery_system():
    """Create a fresh AutoRecoverySystem for each test."""
    return AutoRecoverySystem()


@pytest.mark.asyncio
async def test_api_error_recovery_success(recovery_system):
    """Test successful API error recovery on first attempt."""
    # Mock reconnect function that succeeds
    reconnect_func = AsyncMock()
    
    # Attempt recovery
    success = await recovery_system.recover_from_api_error(
        Exception("Connection timeout"),
        reconnect_func,
        context="market_fetch"
    )
    
    # Verify success
    assert success is True
    assert reconnect_func.called
    assert recovery_system._api_attempt_count == 0  # Reset on success
    
    # Check statistics
    stats = recovery_system.get_recovery_statistics()
    assert stats["total_attempts"] == 1
    assert stats["successful_attempts"] == 1
    assert stats["failed_attempts"] == 0
    assert stats["by_type"]["API_ERROR"]["successful"] == 1


@pytest.mark.asyncio
async def test_api_error_recovery_with_backoff(recovery_system):
    """Test API error recovery uses exponential backoff."""
    reconnect_func = AsyncMock()
    
    # First attempt (10s backoff)
    start_time = asyncio.get_event_loop().time()
    await recovery_system.recover_from_api_error(
        Exception("Connection timeout"),
        reconnect_func,
        context="market_fetch"
    )
    elapsed = asyncio.get_event_loop().time() - start_time
    
    # Verify backoff delay was applied (approximately 10s)
    assert elapsed >= 10.0
    assert elapsed < 11.0  # Allow small margin


@pytest.mark.asyncio
async def test_api_error_recovery_multiple_attempts(recovery_system):
    """Test API error recovery with multiple failed attempts."""
    # Mock reconnect function that fails twice then succeeds
    reconnect_func = AsyncMock(side_effect=[
        Exception("Still failing"),
        Exception("Still failing"),
        None  # Success on third attempt
    ])
    
    # First attempt (10s backoff) - fails
    success1 = await recovery_system.recover_from_api_error(
        Exception("Connection timeout"),
        reconnect_func,
        context="market_fetch"
    )
    assert success1 is False
    assert recovery_system._api_attempt_count == 1
    
    # Second attempt (30s backoff) - fails
    success2 = await recovery_system.recover_from_api_error(
        Exception("Connection timeout"),
        reconnect_func,
        context="market_fetch"
    )
    assert success2 is False
    assert recovery_system._api_attempt_count == 2
    
    # Third attempt (60s backoff) - succeeds
    success3 = await recovery_system.recover_from_api_error(
        Exception("Connection timeout"),
        reconnect_func,
        context="market_fetch"
    )
    assert success3 is True
    assert recovery_system._api_attempt_count == 0  # Reset on success
    
    # Check statistics
    stats = recovery_system.get_recovery_statistics()
    assert stats["total_attempts"] == 3
    assert stats["successful_attempts"] == 1
    assert stats["failed_attempts"] == 2


@pytest.mark.asyncio
async def test_api_error_recovery_max_attempts(recovery_system):
    """Test API error recovery stops after max attempts."""
    # Mock reconnect function that always fails
    reconnect_func = AsyncMock(side_effect=Exception("Always fails"))
    
    # Attempt recovery 3 times (max attempts)
    for i in range(3):
        success = await recovery_system.recover_from_api_error(
            Exception("Connection timeout"),
            reconnect_func,
            context="market_fetch"
        )
        assert success is False
    
    # Verify counter was reset after max attempts
    assert recovery_system._api_attempt_count == 0
    
    # Check statistics
    stats = recovery_system.get_recovery_statistics()
    assert stats["total_attempts"] == 3
    assert stats["successful_attempts"] == 0
    assert stats["failed_attempts"] == 3


@pytest.mark.asyncio
async def test_balance_error_recovery_success(recovery_system):
    """Test successful balance error recovery."""
    # Mock refresh function that succeeds
    refresh_func = AsyncMock()
    
    # Attempt recovery
    success = await recovery_system.recover_from_balance_error(
        Exception("Insufficient balance"),
        refresh_func,
        context="order_placement"
    )
    
    # Verify success
    assert success is True
    assert refresh_func.called
    assert recovery_system._balance_attempt_count == 0  # Reset on success
    
    # Check statistics
    stats = recovery_system.get_recovery_statistics()
    assert stats["total_attempts"] == 1
    assert stats["successful_attempts"] == 1
    assert stats["by_type"]["BALANCE_ERROR"]["successful"] == 1


@pytest.mark.asyncio
async def test_websocket_error_recovery_success(recovery_system):
    """Test successful WebSocket error recovery."""
    # Mock reconnect function that succeeds
    reconnect_func = AsyncMock()
    
    # Attempt recovery
    success = await recovery_system.recover_from_websocket_error(
        Exception("WebSocket disconnected"),
        reconnect_func,
        context="price_feed"
    )
    
    # Verify success
    assert success is True
    assert reconnect_func.called
    assert recovery_system._websocket_attempt_count == 0  # Reset on success
    
    # Check statistics
    stats = recovery_system.get_recovery_statistics()
    assert stats["total_attempts"] == 1
    assert stats["successful_attempts"] == 1
    assert stats["by_type"]["WEBSOCKET_ERROR"]["successful"] == 1


@pytest.mark.asyncio
async def test_mixed_error_types(recovery_system):
    """Test recovery from multiple error types."""
    api_reconnect = AsyncMock()
    balance_refresh = AsyncMock()
    ws_reconnect = AsyncMock()
    
    # Recover from different error types
    await recovery_system.recover_from_api_error(
        Exception("API error"),
        api_reconnect
    )
    await recovery_system.recover_from_balance_error(
        Exception("Balance error"),
        balance_refresh
    )
    await recovery_system.recover_from_websocket_error(
        Exception("WebSocket error"),
        ws_reconnect
    )
    
    # Check statistics
    stats = recovery_system.get_recovery_statistics()
    assert stats["total_attempts"] == 3
    assert stats["successful_attempts"] == 3
    assert len(stats["by_type"]) == 3
    assert "API_ERROR" in stats["by_type"]
    assert "BALANCE_ERROR" in stats["by_type"]
    assert "WEBSOCKET_ERROR" in stats["by_type"]


@pytest.mark.asyncio
async def test_recovery_statistics_recent_attempts(recovery_system):
    """Test that recovery statistics include recent attempts."""
    reconnect_func = AsyncMock()
    
    # Make several recovery attempts
    for i in range(5):
        await recovery_system.recover_from_api_error(
            Exception(f"Error {i}"),
            reconnect_func,
            context=f"attempt_{i}"
        )
    
    # Check statistics
    stats = recovery_system.get_recovery_statistics()
    assert len(stats["recent_attempts"]) == 5
    
    # Verify recent attempts have correct structure
    for attempt in stats["recent_attempts"]:
        assert "timestamp" in attempt
        assert "error_type" in attempt
        assert "error_message" in attempt
        assert "attempt_number" in attempt
        assert "backoff_delay" in attempt
        assert "success" in attempt


def test_reset_attempt_counters(recovery_system):
    """Test resetting attempt counters."""
    # Set some counters
    recovery_system._api_attempt_count = 2
    recovery_system._balance_attempt_count = 1
    recovery_system._websocket_attempt_count = 3
    
    # Reset
    recovery_system.reset_attempt_counters()
    
    # Verify all counters are zero
    assert recovery_system._api_attempt_count == 0
    assert recovery_system._balance_attempt_count == 0
    assert recovery_system._websocket_attempt_count == 0


@pytest.mark.asyncio
async def test_clear_history(recovery_system):
    """Test clearing recovery history."""
    reconnect_func = AsyncMock()
    
    # Make some recovery attempts
    await recovery_system.recover_from_api_error(
        Exception("Error 1"),
        reconnect_func
    )
    await recovery_system.recover_from_api_error(
        Exception("Error 2"),
        reconnect_func
    )
    
    # Verify history exists
    stats = recovery_system.get_recovery_statistics()
    assert stats["total_attempts"] == 2
    
    # Clear history
    recovery_system.clear_history()
    
    # Verify history is empty
    stats = recovery_system.get_recovery_statistics()
    assert stats["total_attempts"] == 0
    assert len(stats["recent_attempts"]) == 0


@pytest.mark.asyncio
async def test_exponential_backoff_delays(recovery_system):
    """Test that exponential backoff uses correct delays: 10s, 30s, 60s."""
    reconnect_func = AsyncMock(side_effect=Exception("Always fails"))
    
    # Track delays
    delays = []
    
    for i in range(3):
        start_time = asyncio.get_event_loop().time()
        await recovery_system.recover_from_api_error(
            Exception("Connection timeout"),
            reconnect_func
        )
        elapsed = asyncio.get_event_loop().time() - start_time
        delays.append(elapsed)
    
    # Verify delays match expected pattern (10s, 30s, 60s)
    assert 10.0 <= delays[0] < 11.0
    assert 30.0 <= delays[1] < 31.0
    assert 60.0 <= delays[2] < 61.0


@pytest.mark.asyncio
async def test_recovery_attempt_dataclass(recovery_system):
    """Test RecoveryAttempt dataclass structure."""
    reconnect_func = AsyncMock()
    
    # Make a recovery attempt
    await recovery_system.recover_from_api_error(
        Exception("Test error"),
        reconnect_func,
        context="test_context"
    )
    
    # Get the recorded attempt
    attempt = recovery_system._recovery_history[0]
    
    # Verify structure
    assert isinstance(attempt, RecoveryAttempt)
    assert isinstance(attempt.timestamp, datetime)
    assert attempt.error_type == "API_ERROR"
    assert attempt.error_message == "Test error"
    assert attempt.attempt_number == 1
    assert attempt.backoff_delay == 10.0
    assert attempt.success is True


@pytest.mark.asyncio
async def test_success_rate_calculation(recovery_system):
    """Test success rate calculation in statistics."""
    # Mock functions with mixed success/failure
    success_func = AsyncMock()
    fail_func = AsyncMock(side_effect=Exception("Fails"))
    
    # 2 successes
    await recovery_system.recover_from_api_error(Exception("E1"), success_func)
    await recovery_system.recover_from_balance_error(Exception("E2"), success_func)
    
    # 1 failure
    await recovery_system.recover_from_websocket_error(Exception("E3"), fail_func)
    
    # Check success rate
    stats = recovery_system.get_recovery_statistics()
    assert stats["total_attempts"] == 3
    assert stats["successful_attempts"] == 2
    assert stats["failed_attempts"] == 1
    assert abs(stats["success_rate"] - 0.6667) < 0.01  # 2/3 ≈ 0.6667


@pytest.mark.asyncio
async def test_independent_attempt_counters(recovery_system):
    """Test that different error types have independent attempt counters."""
    fail_func = AsyncMock(side_effect=Exception("Fails"))
    
    # Fail API recovery twice
    await recovery_system.recover_from_api_error(Exception("API1"), fail_func)
    await recovery_system.recover_from_api_error(Exception("API2"), fail_func)
    
    # Fail balance recovery once
    await recovery_system.recover_from_balance_error(Exception("BAL1"), fail_func)
    
    # Verify independent counters
    assert recovery_system._api_attempt_count == 2
    assert recovery_system._balance_attempt_count == 1
    assert recovery_system._websocket_attempt_count == 0
    
    # Check statistics
    stats = recovery_system.get_recovery_statistics()
    assert stats["current_api_attempts"] == 2
    assert stats["current_balance_attempts"] == 1
    assert stats["current_websocket_attempts"] == 0
