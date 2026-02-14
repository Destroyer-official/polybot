"""
Property-Based Tests for Automatic Circuit Breaker System.

Tests the circuit breaker functionality in AutonomousRiskManager:
- Activation when consecutive losses reach threshold
- Cooldown period calculation based on severity
- Automatic reset after cooldown expires
- Logging of activation and reset events

Validates Requirements: 7.3, 7.9
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import logging

from src.autonomous_risk_manager import AutonomousRiskManager, CircuitBreakerState


class TestCircuitBreakerActivation:
    """
    Property 31: Automatic Circuit Breaker Activation
    
    **Validates: Requirements 7.3, 7.9**
    
    The circuit breaker should:
    1. Activate when consecutive losses reach the threshold
    2. Calculate cooldown based on severity (1h for 3-4 losses, 3h for 5-6, 6h for 7+)
    3. Block new positions when active
    4. Log activation events
    """
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('10000'), max_value=Decimal('100000'), places=2),  # Large balance to avoid drawdown
        consecutive_losses=st.integers(min_value=0, max_value=10),
        loss_amount=st.decimals(min_value=Decimal('1'), max_value=Decimal('10'), places=2)  # Small losses to avoid drawdown
    )
    @settings(max_examples=100, deadline=None)
    def test_circuit_breaker_activates_at_threshold(
        self,
        starting_balance,
        consecutive_losses,
        loss_amount
    ):
        """
        Property: Circuit breaker activates when consecutive losses reach threshold.
        
        For any sequence of losses:
        - If consecutive_losses < threshold: circuit breaker remains inactive
        - If consecutive_losses >= threshold: circuit breaker activates
        - Cooldown period is calculated based on severity AT THE TIME OF ACTIVATION
        """
        # Create risk manager
        risk_manager = AutonomousRiskManager(
            starting_balance=starting_balance,
            current_balance=starting_balance
        )
        
        # Get the current threshold (default is 5)
        threshold = risk_manager.thresholds.consecutive_loss_limit
        
        # Record consecutive losses
        for i in range(consecutive_losses):
            risk_manager.record_trade_outcome(-loss_amount, "BTC")
        
        # Verify circuit breaker state
        if consecutive_losses >= threshold:
            # Should be active
            assert risk_manager.circuit_breaker.is_active, \
                f"Circuit breaker should be active after {consecutive_losses} losses (threshold={threshold})"
            
            # Verify activation reason mentions consecutive losses (not drawdown)
            assert "consecutive losses" in risk_manager.circuit_breaker.activation_reason.lower(), \
                f"Activation should be due to consecutive losses, got: {risk_manager.circuit_breaker.activation_reason}"
            
            # Verify cooldown period is set correctly based on severity AT ACTIVATION
            # The circuit breaker activates when consecutive_losses == threshold
            # So the cooldown is based on the threshold value, not the final count
            expected_cooldown = 1  # Default
            if threshold >= 7:
                expected_cooldown = 6
            elif threshold >= 5:
                expected_cooldown = 3
            else:
                expected_cooldown = 1
            
            assert risk_manager.circuit_breaker.cooldown_hours == expected_cooldown, \
                f"Expected cooldown {expected_cooldown}h for threshold {threshold}, got {risk_manager.circuit_breaker.cooldown_hours}h"
            
            # Verify activation count incremented
            assert risk_manager.circuit_breaker.activation_count > 0, \
                "Activation count should be incremented"
        else:
            # Should remain inactive
            assert not risk_manager.circuit_breaker.is_active, \
                f"Circuit breaker should not be active after {consecutive_losses} losses (threshold={threshold})"


class TestCircuitBreakerCooldown:
    """
    Property 32: Circuit Breaker Cooldown Calculation
    
    **Validates: Requirements 7.3, 7.9**
    
    The cooldown period should be calculated based on severity:
    - 3-4 consecutive losses: 1 hour cooldown
    - 5-6 consecutive losses: 3 hour cooldown
    - 7+ consecutive losses: 6 hour cooldown
    """
    
    @given(
        consecutive_losses=st.integers(min_value=3, max_value=15)
    )
    @settings(max_examples=50, deadline=None)
    def test_cooldown_period_based_on_severity(self, consecutive_losses):
        """
        Property: Cooldown period increases with severity of losses.
        
        For any number of consecutive losses >= threshold:
        - Circuit breaker activates when threshold is reached
        - Cooldown is based on the number of losses AT ACTIVATION
        - 3-4 losses: 1 hour cooldown
        - 5-6 losses: 3 hour cooldown
        - 7+ losses: 6 hour cooldown
        """
        # Create risk manager with large balance to avoid drawdown trigger
        risk_manager = AutonomousRiskManager(
            starting_balance=Decimal('100000'),
            current_balance=Decimal('100000')
        )
        
        # Set threshold to match consecutive_losses so it activates on the last loss
        risk_manager.thresholds.consecutive_loss_limit = consecutive_losses
        
        # Disable threshold adaptation by patching the method
        original_adapt = risk_manager.adapt_thresholds
        risk_manager.adapt_thresholds = lambda: None
        
        # Record consecutive losses (small amounts to avoid drawdown)
        for i in range(consecutive_losses):
            risk_manager.record_trade_outcome(Decimal('-1'), "BTC")
        
        # Restore original method
        risk_manager.adapt_thresholds = original_adapt
        
        # Verify circuit breaker activated
        assert risk_manager.circuit_breaker.is_active, \
            f"Circuit breaker should be active after {consecutive_losses} losses"
        
        # Verify it was activated by consecutive losses, not drawdown
        assert "consecutive losses" in risk_manager.circuit_breaker.activation_reason.lower(), \
            f"Should be activated by consecutive losses, got: {risk_manager.circuit_breaker.activation_reason}"
        
        # Verify cooldown period based on the number of losses at activation
        expected_cooldown = 1
        if consecutive_losses >= 7:
            expected_cooldown = 6
        elif consecutive_losses >= 5:
            expected_cooldown = 3
        else:
            expected_cooldown = 1
        
        assert risk_manager.circuit_breaker.cooldown_hours == expected_cooldown, \
            f"Expected {expected_cooldown}h cooldown for {consecutive_losses} losses, got {risk_manager.circuit_breaker.cooldown_hours}h"


class TestCircuitBreakerAutoReset:
    """
    Property 33: Automatic Circuit Breaker Reset
    
    **Validates: Requirements 7.3, 7.9**
    
    The circuit breaker should automatically reset after the cooldown period expires.
    """
    
    @given(
        cooldown_hours=st.integers(min_value=1, max_value=6)
    )
    @settings(max_examples=20, deadline=None)
    def test_auto_reset_after_cooldown(self, cooldown_hours):
        """
        Property: Circuit breaker auto-resets after cooldown expires.
        
        For any cooldown period:
        - Before cooldown expires: circuit breaker remains active
        - After cooldown expires: circuit breaker auto-resets
        - Reset is logged
        """
        # Create circuit breaker state
        cb = CircuitBreakerState()
        
        # Activate with specific cooldown
        cb.activate("Test activation", cooldown_hours)
        
        # Verify it's active
        assert cb.is_active
        assert cb.cooldown_hours == cooldown_hours
        
        # Check reset before cooldown expires (should remain active)
        cb.cooldown_until = datetime.now() + timedelta(hours=1)  # Still 1 hour left
        reset = cb.check_and_reset()
        assert not reset, "Should not reset before cooldown expires"
        assert cb.is_active, "Should remain active before cooldown"
        
        # Check reset after cooldown expires (should reset)
        cb.cooldown_until = datetime.now() - timedelta(seconds=1)  # Expired 1 second ago
        reset = cb.check_and_reset()
        assert reset, "Should reset after cooldown expires"
        assert not cb.is_active, "Should be inactive after reset"
        assert cb.activation_time is None, "Activation time should be cleared"
        assert cb.cooldown_until is None, "Cooldown until should be cleared"
        assert cb.activation_reason == "", "Activation reason should be cleared"
        assert cb.cooldown_hours == 0, "Cooldown hours should be cleared"


class TestCircuitBreakerComprehensive:
    """
    Property 31: Automatic Circuit Breaker (Comprehensive)
    
    **Validates: Requirements 7.3, 7.9**
    
    Comprehensive test that validates the complete circuit breaker lifecycle:
    1. Generate random loss sequences
    2. Verify circuit breaker activates at threshold
    3. Verify cooldown period calculated correctly based on severity
    4. Verify auto-reset after cooldown expires
    """
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('10000'), max_value=Decimal('100000'), places=2),
        num_losses=st.integers(min_value=3, max_value=10),
        loss_amount=st.decimals(min_value=Decimal('1'), max_value=Decimal('10'), places=2)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_31_circuit_breaker_comprehensive(
        self,
        starting_balance,
        num_losses,
        loss_amount
    ):
        """
        Property 31: Automatic Circuit Breaker (Comprehensive)
        
        **Validates: Requirements 7.3, 7.9**
        
        For any sequence of losses:
        1. Circuit breaker activates when consecutive losses reach threshold
        2. Cooldown period is calculated based on severity:
           - 3-4 losses: 1 hour
           - 5-6 losses: 3 hours
           - 7+ losses: 6 hours
        3. Circuit breaker auto-resets after cooldown expires
        4. Trading can resume after reset
        """
        # Create risk manager with large balance to avoid drawdown trigger
        risk_manager = AutonomousRiskManager(
            starting_balance=starting_balance,
            current_balance=starting_balance
        )
        
        # Get the threshold (default is 5)
        threshold = risk_manager.thresholds.consecutive_loss_limit
        
        # Phase 1: Generate random loss sequence
        for i in range(num_losses):
            risk_manager.record_trade_outcome(-loss_amount, "BTC")
        
        # Phase 2: Verify circuit breaker activation at threshold
        if num_losses >= threshold:
            # Should be active
            assert risk_manager.circuit_breaker.is_active, \
                f"Circuit breaker should be active after {num_losses} losses (threshold={threshold})"
            
            # Verify activation reason
            assert "consecutive losses" in risk_manager.circuit_breaker.activation_reason.lower(), \
                f"Activation should be due to consecutive losses, got: {risk_manager.circuit_breaker.activation_reason}"
            
            # Phase 3: Verify cooldown period calculated correctly based on severity
            # The cooldown is based on the number of losses at activation (which is the threshold)
            expected_cooldown = 1  # Default
            if threshold >= 7:
                expected_cooldown = 6
            elif threshold >= 5:
                expected_cooldown = 3
            else:
                expected_cooldown = 1
            
            assert risk_manager.circuit_breaker.cooldown_hours == expected_cooldown, \
                f"Expected cooldown {expected_cooldown}h for threshold {threshold}, got {risk_manager.circuit_breaker.cooldown_hours}h"
            
            # Verify cooldown_until is set correctly
            assert risk_manager.circuit_breaker.cooldown_until is not None, \
                "Cooldown until should be set"
            
            # Verify activation count incremented
            assert risk_manager.circuit_breaker.activation_count > 0, \
                "Activation count should be incremented"
            
            # Verify new positions are blocked
            can_add, reason = risk_manager.can_add_position("BTC")
            assert not can_add, \
                "Should not be able to add positions when circuit breaker active"
            assert "circuit breaker" in reason.lower(), \
                f"Reason should mention circuit breaker: {reason}"
            
            # Phase 4: Verify auto-reset after cooldown expires
            # Simulate cooldown expiry
            risk_manager.circuit_breaker.cooldown_until = datetime.now() - timedelta(seconds=1)
            
            # Check and reset
            reset = risk_manager.circuit_breaker.check_and_reset()
            assert reset, "Circuit breaker should reset after cooldown expires"
            assert not risk_manager.circuit_breaker.is_active, \
                "Circuit breaker should be inactive after reset"
            
            # Verify state is cleared
            assert risk_manager.circuit_breaker.activation_time is None, \
                "Activation time should be cleared"
            assert risk_manager.circuit_breaker.cooldown_until is None, \
                "Cooldown until should be cleared"
            assert risk_manager.circuit_breaker.activation_reason == "", \
                "Activation reason should be cleared"
            assert risk_manager.circuit_breaker.cooldown_hours == 0, \
                "Cooldown hours should be cleared"
            
            # Verify trading can resume
            can_add, _ = risk_manager.can_add_position("BTC")
            assert can_add, \
                "Should be able to add positions after circuit breaker reset"
        else:
            # Should remain inactive
            assert not risk_manager.circuit_breaker.is_active, \
                f"Circuit breaker should not be active after {num_losses} losses (threshold={threshold})"


class TestCircuitBreakerBlocksPositions:
    """
    Property 34: Circuit Breaker Blocks New Positions
    
    **Validates: Requirements 7.3, 7.9**
    
    When the circuit breaker is active, no new positions should be allowed.
    """
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('100'), max_value=Decimal('10000'), places=2),
        asset=st.sampled_from(["BTC", "ETH", "SOL", "XRP"])
    )
    @settings(max_examples=50, deadline=None)
    def test_circuit_breaker_blocks_new_positions(self, starting_balance, asset):
        """
        Property: Circuit breaker blocks new positions when active.
        
        For any asset:
        - When circuit breaker is inactive: can add positions
        - When circuit breaker is active: cannot add positions
        - Reason includes circuit breaker status
        """
        # Create risk manager
        risk_manager = AutonomousRiskManager(
            starting_balance=starting_balance,
            current_balance=starting_balance
        )
        
        # Initially should be able to add positions
        can_add, reason = risk_manager.can_add_position(asset)
        assert can_add, f"Should be able to add position initially: {reason}"
        
        # Activate circuit breaker manually
        risk_manager.circuit_breaker.activate("Test activation", 1)
        
        # Now should NOT be able to add positions
        can_add, reason = risk_manager.can_add_position(asset)
        assert not can_add, "Should not be able to add position when circuit breaker active"
        assert "circuit breaker" in reason.lower(), \
            f"Reason should mention circuit breaker: {reason}"


class TestCircuitBreakerDailyDrawdown:
    """
    Property 35: Circuit Breaker Activates on Daily Drawdown
    
    **Validates: Requirements 7.3, 7.9**
    
    The circuit breaker should also activate when daily drawdown exceeds the limit.
    """
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('100'), max_value=Decimal('10000'), places=2),
        drawdown_pct=st.decimals(min_value=Decimal('0.05'), max_value=Decimal('0.30'), places=2)
    )
    @settings(max_examples=50, deadline=None)
    def test_circuit_breaker_activates_on_drawdown(self, starting_balance, drawdown_pct):
        """
        Property: Circuit breaker activates when daily drawdown exceeds limit.
        
        For any drawdown percentage:
        - If drawdown < limit: circuit breaker remains inactive
        - If drawdown >= limit: circuit breaker activates
        - Cooldown is 4 hours for drawdown activation
        """
        # Create risk manager
        risk_manager = AutonomousRiskManager(
            starting_balance=starting_balance,
            current_balance=starting_balance
        )
        
        # Get the drawdown limit (default is 15%)
        drawdown_limit = risk_manager.thresholds.daily_drawdown_limit
        
        # Calculate loss amount to achieve desired drawdown
        loss_amount = starting_balance * drawdown_pct
        
        # Record a single large loss
        risk_manager.record_trade_outcome(-loss_amount, "BTC")
        
        # Verify circuit breaker state
        if drawdown_pct >= drawdown_limit:
            # Should be active
            assert risk_manager.circuit_breaker.is_active, \
                f"Circuit breaker should be active after {drawdown_pct:.1%} drawdown (limit={drawdown_limit:.1%})"
            
            # Verify cooldown is 4 hours for drawdown
            assert risk_manager.circuit_breaker.cooldown_hours == 4, \
                f"Expected 4h cooldown for drawdown, got {risk_manager.circuit_breaker.cooldown_hours}h"
            
            # Verify activation reason mentions drawdown
            assert "drawdown" in risk_manager.circuit_breaker.activation_reason.lower(), \
                f"Activation reason should mention drawdown: {risk_manager.circuit_breaker.activation_reason}"
        else:
            # Should remain inactive (unless consecutive losses triggered it)
            # Only check if we had just 1 loss
            if risk_manager.performance.consecutive_losses < risk_manager.thresholds.consecutive_loss_limit:
                assert not risk_manager.circuit_breaker.is_active, \
                    f"Circuit breaker should not be active after {drawdown_pct:.1%} drawdown (limit={drawdown_limit:.1%})"


class TestCircuitBreakerLogging:
    """
    Property 36: Circuit Breaker Logging
    
    **Validates: Requirements 7.3, 7.9**
    
    All circuit breaker events should be logged:
    - Activation events (with reason and cooldown)
    - Reset events (with previous reason)
    """
    
    def test_circuit_breaker_logs_activation(self):
        """
        Property: Circuit breaker logs activation events.
        
        When circuit breaker activates:
        - Log level is WARNING
        - Log includes reason
        - Log includes cooldown period
        - Log includes cooldown expiry time
        """
        with patch('src.autonomous_risk_manager.logger') as mock_logger:
            # Create risk manager
            risk_manager = AutonomousRiskManager(
                starting_balance=Decimal('1000'),
                current_balance=Decimal('1000')
            )
            
            # Set low threshold
            risk_manager.thresholds.consecutive_loss_limit = 3
            
            # Record losses to trigger circuit breaker
            for i in range(3):
                risk_manager.record_trade_outcome(Decimal('-10'), "BTC")
            
            # Verify activation was logged
            activation_logged = False
            for call in mock_logger.warning.call_args_list:
                args = call[0]
                if len(args) > 0 and "Circuit breaker ACTIVATED" in str(args[0]):
                    activation_logged = True
                    log_message = str(args[0])
                    # Verify log contains key information
                    assert "consecutive losses" in log_message.lower(), \
                        "Log should mention consecutive losses"
                    assert "cooldown" in log_message.lower(), \
                        "Log should mention cooldown"
                    break
            
            assert activation_logged, "Circuit breaker activation should be logged"
    
    def test_circuit_breaker_logs_reset(self):
        """
        Property: Circuit breaker logs reset events.
        
        When circuit breaker resets:
        - Log level is INFO
        - Log includes previous reason
        - Log includes cooldown duration
        """
        with patch('src.autonomous_risk_manager.logger') as mock_logger:
            # Create circuit breaker
            cb = CircuitBreakerState()
            
            # Activate
            cb.activate("Test reason", 1)
            
            # Expire cooldown
            cb.cooldown_until = datetime.now() - timedelta(seconds=1)
            
            # Reset
            cb.check_and_reset()
            
            # Verify reset was logged
            reset_logged = False
            for call in mock_logger.info.call_args_list:
                args = call[0]
                if len(args) > 0 and "Circuit breaker AUTO-RESET" in str(args[0]):
                    reset_logged = True
                    log_message = str(args[0])
                    # Verify log contains key information
                    assert "reason was" in log_message.lower(), \
                        "Log should mention previous reason"
                    assert "cooldown" in log_message.lower(), \
                        "Log should mention cooldown"
                    break
            
            assert reset_logged, "Circuit breaker reset should be logged"


class TestCircuitBreakerIntegration:
    """
    Integration test: Full circuit breaker lifecycle
    
    **Validates: Requirements 7.3, 7.9**
    
    Test the complete circuit breaker lifecycle:
    1. Normal operation (no circuit breaker)
    2. Losses accumulate
    3. Circuit breaker activates
    4. New positions blocked
    5. Cooldown expires
    6. Circuit breaker resets
    7. Normal operation resumes
    """
    
    def test_full_circuit_breaker_lifecycle(self):
        """
        Integration test: Complete circuit breaker lifecycle.
        """
        # Create risk manager
        risk_manager = AutonomousRiskManager(
            starting_balance=Decimal('1000'),
            current_balance=Decimal('1000')
        )
        
        # Set low threshold for testing
        risk_manager.thresholds.consecutive_loss_limit = 3
        
        # Phase 1: Normal operation
        can_add, _ = risk_manager.can_add_position("BTC")
        assert can_add, "Should be able to add positions initially"
        assert not risk_manager.circuit_breaker.is_active, "Circuit breaker should be inactive"
        
        # Phase 2: Record losses
        risk_manager.record_trade_outcome(Decimal('-10'), "BTC")
        assert not risk_manager.circuit_breaker.is_active, "Circuit breaker should still be inactive after 1 loss"
        
        risk_manager.record_trade_outcome(Decimal('-10'), "BTC")
        assert not risk_manager.circuit_breaker.is_active, "Circuit breaker should still be inactive after 2 losses"
        
        # Phase 3: Circuit breaker activates
        risk_manager.record_trade_outcome(Decimal('-10'), "BTC")
        assert risk_manager.circuit_breaker.is_active, "Circuit breaker should activate after 3 losses"
        assert risk_manager.circuit_breaker.cooldown_hours == 1, "Should have 1 hour cooldown"
        
        # Phase 4: New positions blocked
        can_add, reason = risk_manager.can_add_position("BTC")
        assert not can_add, "Should not be able to add positions when circuit breaker active"
        assert "circuit breaker" in reason.lower(), "Reason should mention circuit breaker"
        
        # Phase 5: Cooldown expires
        risk_manager.circuit_breaker.cooldown_until = datetime.now() - timedelta(seconds=1)
        reset = risk_manager.circuit_breaker.check_and_reset()
        assert reset, "Circuit breaker should reset after cooldown"
        assert not risk_manager.circuit_breaker.is_active, "Circuit breaker should be inactive after reset"
        
        # Phase 6: Normal operation resumes
        can_add, _ = risk_manager.can_add_position("BTC")
        assert can_add, "Should be able to add positions after reset"
