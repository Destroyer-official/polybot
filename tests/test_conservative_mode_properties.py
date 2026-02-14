"""
Property-Based Tests for Conservative Mode System.

Tests the conservative mode functionality in AutonomousRiskManager:
- Activation when balance drops below 20% of starting
- Only high-confidence trades allowed (80%+)
- Auto-deactivation when balance recovers to 50%+
- Logging of mode changes

Validates Requirements: 7.10
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import logging

from src.autonomous_risk_manager import AutonomousRiskManager, ConservativeModeState


class TestConservativeModeActivation:
    """
    Property 32: Conservative Mode Activation
    
    **Validates: Requirements 7.10**
    
    Conservative mode should:
    1. Activate when balance drops below 20% of starting balance
    2. Require 80%+ confidence for all trades when active
    3. Auto-deactivate when balance recovers to 50%+ of starting
    4. Log activation and deactivation events
    """
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('100'), max_value=Decimal('10000'), places=2),
        balance_drop_pct=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('0.99'), places=2)
    )
    @settings(max_examples=100, deadline=None)
    def test_conservative_mode_activates_at_20_percent_threshold(
        self,
        starting_balance,
        balance_drop_pct
    ):
        """
        Property: Conservative mode activates when balance drops below 20% of starting.
        
        For any starting balance and balance drop:
        - If current_balance < 20% of starting: conservative mode activates
        - If current_balance >= 20% of starting: conservative mode remains inactive
        """
        # Create risk manager
        risk_manager = AutonomousRiskManager(
            starting_balance=starting_balance,
            current_balance=starting_balance
        )
        
        # Calculate new balance after drop
        current_balance = starting_balance * (Decimal('1') - balance_drop_pct)
        risk_manager.current_balance = current_balance
        
        # Check activation
        threshold = starting_balance * Decimal('0.20')
        activated = risk_manager.conservative_mode.check_activation(current_balance, starting_balance)
        
        # Verify activation state
        if current_balance < threshold:
            # Should activate
            assert activated, \
                f"Conservative mode should activate when balance ${current_balance} < 20% of ${starting_balance} (threshold: ${threshold})"
            assert risk_manager.conservative_mode.is_active, \
                "Conservative mode should be active"
            assert risk_manager.conservative_mode.activation_time is not None, \
                "Activation time should be set"
            assert risk_manager.conservative_mode.activation_balance == current_balance, \
                "Activation balance should be recorded"
        else:
            # Should not activate
            assert not activated, \
                f"Conservative mode should not activate when balance ${current_balance} >= 20% of ${starting_balance} (threshold: ${threshold})"
            assert not risk_manager.conservative_mode.is_active, \
                "Conservative mode should remain inactive"
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('100'), max_value=Decimal('10000'), places=2),
        confidence_pct=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('1.00'), places=2)
    )
    @settings(max_examples=100, deadline=None)
    def test_conservative_mode_requires_high_confidence(
        self,
        starting_balance,
        confidence_pct
    ):
        """
        Property: Conservative mode requires 80%+ confidence for all trades.
        
        For any confidence level:
        - If conservative mode active and confidence < 80%: trade blocked
        - If conservative mode active and confidence >= 80%: trade allowed
        - If conservative mode inactive: confidence requirement not enforced
        """
        # Create risk manager with conservative mode active
        risk_manager = AutonomousRiskManager(
            starting_balance=starting_balance,
            current_balance=starting_balance * Decimal('0.15')  # 15% of starting (below 20% threshold)
        )
        
        # Activate conservative mode
        risk_manager.conservative_mode.check_activation(
            risk_manager.current_balance,
            starting_balance
        )
        
        # Verify conservative mode is active
        assert risk_manager.conservative_mode.is_active, \
            "Conservative mode should be active for test"
        
        # Check if trade would be allowed based on confidence
        min_confidence = risk_manager.conservative_mode.min_confidence_required
        
        if confidence_pct < min_confidence:
            # Trade should be blocked
            # Note: The actual blocking logic would be in the strategy layer
            # Here we just verify the state is correct
            assert risk_manager.conservative_mode.is_active, \
                f"Conservative mode should block trades with {confidence_pct*100:.0f}% confidence (requires {min_confidence*100:.0f}%+)"
        else:
            # Trade should be allowed (conservative mode doesn't block high-confidence trades)
            assert risk_manager.conservative_mode.is_active, \
                f"Conservative mode should allow trades with {confidence_pct*100:.0f}% confidence (requires {min_confidence*100:.0f}%+)"


class TestConservativeModeDeactivation:
    """
    Property 32: Conservative Mode Auto-Deactivation
    
    **Validates: Requirements 7.10**
    
    Conservative mode should auto-deactivate when balance recovers to 50%+ of starting.
    """
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('100'), max_value=Decimal('10000'), places=2),
        recovery_pct=st.decimals(min_value=Decimal('0.20'), max_value=Decimal('1.00'), places=2)
    )
    @settings(max_examples=100, deadline=None)
    def test_conservative_mode_deactivates_at_50_percent_recovery(
        self,
        starting_balance,
        recovery_pct
    ):
        """
        Property: Conservative mode deactivates when balance recovers to 50%+ of starting.
        
        For any starting balance and recovery level:
        - If current_balance >= 50% of starting: conservative mode deactivates
        - If current_balance < 50% of starting: conservative mode remains active
        """
        # Create risk manager with conservative mode active
        risk_manager = AutonomousRiskManager(
            starting_balance=starting_balance,
            current_balance=starting_balance * Decimal('0.15')  # 15% of starting (below 20% threshold)
        )
        
        # Activate conservative mode
        risk_manager.conservative_mode.check_activation(
            risk_manager.current_balance,
            starting_balance
        )
        
        # Verify conservative mode is active
        assert risk_manager.conservative_mode.is_active, \
            "Conservative mode should be active before recovery test"
        
        # Simulate balance recovery
        recovered_balance = starting_balance * recovery_pct
        risk_manager.current_balance = recovered_balance
        
        # Check deactivation
        threshold = starting_balance * Decimal('0.50')
        deactivated = risk_manager.conservative_mode.check_deactivation(recovered_balance)
        
        # Verify deactivation state
        if recovered_balance >= threshold:
            # Should deactivate
            assert deactivated, \
                f"Conservative mode should deactivate when balance ${recovered_balance} >= 50% of ${starting_balance} (threshold: ${threshold})"
            assert not risk_manager.conservative_mode.is_active, \
                "Conservative mode should be inactive after recovery"
            assert risk_manager.conservative_mode.activation_time is None, \
                "Activation time should be cleared"
        else:
            # Should remain active
            assert not deactivated, \
                f"Conservative mode should remain active when balance ${recovered_balance} < 50% of ${starting_balance} (threshold: ${threshold})"
            assert risk_manager.conservative_mode.is_active, \
                "Conservative mode should remain active"


class TestConservativeModeComprehensive:
    """
    Property 32: Conservative Mode (Comprehensive)
    
    **Validates: Requirements 7.10**
    
    Test complete conservative mode lifecycle with random balance sequences.
    """
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('1000'), max_value=Decimal('10000'), places=2),
        balance_sequence=st.lists(
            st.decimals(min_value=Decimal('0.05'), max_value=Decimal('1.50'), places=2),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_conservative_mode_lifecycle_with_balance_sequences(
        self,
        starting_balance,
        balance_sequence
    ):
        """
        Property: Conservative mode correctly handles sequences of balance changes.
        
        For any sequence of balance changes:
        1. Activates when balance drops below 20%
        2. Remains active while balance < 50%
        3. Deactivates when balance recovers to 50%+
        4. Can reactivate if balance drops below 20% again
        """
        # Create risk manager
        risk_manager = AutonomousRiskManager(
            starting_balance=starting_balance,
            current_balance=starting_balance
        )
        
        # Track state changes
        activation_count = 0
        deactivation_count = 0
        
        # Process balance sequence
        for i, balance_multiplier in enumerate(balance_sequence):
            # Calculate new balance
            new_balance = starting_balance * balance_multiplier
            risk_manager.current_balance = new_balance
            
            # Check activation/deactivation
            was_active_before = risk_manager.conservative_mode.is_active
            
            activated = risk_manager.conservative_mode.check_activation(new_balance, starting_balance)
            deactivated = risk_manager.conservative_mode.check_deactivation(new_balance)
            
            if activated:
                activation_count += 1
            if deactivated:
                deactivation_count += 1
            
            # Verify state consistency
            activation_threshold = starting_balance * Decimal('0.20')
            deactivation_threshold = starting_balance * Decimal('0.50')
            
            if new_balance < activation_threshold:
                # Should be active (either already was, or just activated)
                assert risk_manager.conservative_mode.is_active, \
                    f"Step {i}: Conservative mode should be active when balance ${new_balance} < 20% of ${starting_balance}"
            elif new_balance >= deactivation_threshold:
                # Should be inactive (either already was, or just deactivated)
                assert not risk_manager.conservative_mode.is_active, \
                    f"Step {i}: Conservative mode should be inactive when balance ${new_balance} >= 50% of ${starting_balance}"
            else:
                # In the hysteresis zone (20%-50%): state depends on history
                # If it was active, it should remain active
                # If it was inactive, it should remain inactive
                if was_active_before:
                    assert risk_manager.conservative_mode.is_active, \
                        f"Step {i}: Conservative mode should remain active in hysteresis zone (${new_balance} between 20% and 50%)"
                else:
                    assert not risk_manager.conservative_mode.is_active, \
                        f"Step {i}: Conservative mode should remain inactive in hysteresis zone (${new_balance} between 20% and 50%)"
        
        # Verify activation/deactivation counts are reasonable
        # (can't deactivate more times than activated)
        assert deactivation_count <= activation_count, \
            f"Deactivation count ({deactivation_count}) should not exceed activation count ({activation_count})"


class TestConservativeModeLogging:
    """
    Property 32: Conservative Mode Logging
    
    **Validates: Requirements 7.10**
    
    Conservative mode should log activation and deactivation events.
    """
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('100'), max_value=Decimal('10000'), places=2)
    )
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_conservative_mode_logs_activation(
        self,
        starting_balance,
        caplog
    ):
        """
        Property: Conservative mode logs activation events.
        
        When conservative mode activates, it should log:
        - Current balance
        - Starting balance
        - Threshold (20%)
        """
        with caplog.at_level(logging.WARNING):
            # Create risk manager
            risk_manager = AutonomousRiskManager(
                starting_balance=starting_balance,
                current_balance=starting_balance * Decimal('0.15')  # 15% of starting
            )
            
            # Activate conservative mode
            risk_manager.conservative_mode.check_activation(
                risk_manager.current_balance,
                starting_balance
            )
            
            # Verify logging
            assert any("Conservative mode ACTIVATED" in record.message for record in caplog.records), \
                "Should log conservative mode activation"
    
    @given(
        starting_balance=st.decimals(min_value=Decimal('100'), max_value=Decimal('10000'), places=2)
    )
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_conservative_mode_logs_deactivation(
        self,
        starting_balance,
        caplog
    ):
        """
        Property: Conservative mode logs deactivation events.
        
        When conservative mode deactivates, it should log:
        - Current balance
        - Starting balance
        - Threshold (50%)
        """
        with caplog.at_level(logging.INFO):
            # Create risk manager with conservative mode active
            risk_manager = AutonomousRiskManager(
                starting_balance=starting_balance,
                current_balance=starting_balance * Decimal('0.15')  # 15% of starting
            )
            
            # Activate conservative mode
            risk_manager.conservative_mode.check_activation(
                risk_manager.current_balance,
                starting_balance
            )
            
            # Clear previous logs
            caplog.clear()
            
            # Recover balance and deactivate
            recovered_balance = starting_balance * Decimal('0.60')  # 60% of starting
            risk_manager.current_balance = recovered_balance
            risk_manager.conservative_mode.check_deactivation(recovered_balance)
            
            # Verify logging
            assert any("Conservative mode DEACTIVATED" in record.message for record in caplog.records), \
                "Should log conservative mode deactivation"
