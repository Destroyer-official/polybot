"""
Property-based tests for dynamic threshold adaptation.

Uses Hypothesis to test dynamic threshold adjustments based on performance.
Validates Requirement 4.11.

**Validates: Requirements 4.11**
"""

import pytest
from decimal import Decimal
from hypothesis import given, strategies as st, settings, assume
from src.dynamic_parameter_system import DynamicParameterSystem, TradeResult
from datetime import datetime


class TestDynamicThresholdAdaptationProperties:
    """Property-based tests for dynamic threshold adaptation."""
    
    def setup_method(self):
        """Create a DynamicParameterSystem instance for testing."""
        self.system = DynamicParameterSystem(
            min_fractional_kelly=0.25,
            max_fractional_kelly=0.50,
            transaction_cost_pct=Decimal('0.02'),
            min_edge_threshold=Decimal('0.025')
        )
    
    @given(
        win_rate=st.floats(min_value=0.0, max_value=1.0),
        num_trades=st.integers(min_value=10, max_value=50)
    )
    @settings(max_examples=100)
    def test_property_daily_trade_limit_adjusts_with_win_rate(self, win_rate, num_trades):
        """
        Property 22: Dynamic Threshold Adaptation - Daily Trade Limit
        
        **Validates: Requirements 4.11**
        
        Daily trade limit adjusts based on win rate:
        - Win rate >= 80%: 200 trades
        - Win rate >= 60%: 150 trades
        - Win rate >= 40%: 100 trades
        - Win rate < 40%: 50 trades
        """
        # Generate performance sequence with specified win rate
        num_wins = int(num_trades * win_rate)
        num_losses = num_trades - num_wins
        
        # Record winning trades
        for i in range(num_wins):
            self.system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('0.50'),  # Positive profit
                was_successful=True,
                edge=Decimal('0.05'),
                odds=Decimal('1.0')
            )
        
        # Record losing trades
        for i in range(num_losses):
            self.system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('-0.30'),  # Negative profit
                was_successful=False,
                edge=Decimal('0.05'),
                odds=Decimal('1.0')
            )
        
        # Update dynamic parameters
        self.system.update_dynamic_parameters()
        
        # Calculate actual win rate from recorded trades
        metrics = self.system.get_performance_metrics()
        actual_win_rate = metrics.win_rate
        
        # Verify daily trade limit adjusts correctly based on actual win rate
        if actual_win_rate >= 0.80:
            assert self.system.daily_trade_limit == 200, \
                f"Win rate {actual_win_rate*100:.1f}% should set daily limit to 200 (got {self.system.daily_trade_limit})"
        elif actual_win_rate >= 0.60:
            assert self.system.daily_trade_limit == 150, \
                f"Win rate {actual_win_rate*100:.1f}% should set daily limit to 150 (got {self.system.daily_trade_limit})"
        elif actual_win_rate >= 0.40:
            assert self.system.daily_trade_limit == 100, \
                f"Win rate {actual_win_rate*100:.1f}% should set daily limit to 100 (got {self.system.daily_trade_limit})"
        else:
            assert self.system.daily_trade_limit == 50, \
                f"Win rate {actual_win_rate*100:.1f}% should set daily limit to 50 (got {self.system.daily_trade_limit})"
        
        # Verify limit is within valid range (50-200)
        assert 50 <= self.system.daily_trade_limit <= 200, \
            f"Daily trade limit {self.system.daily_trade_limit} outside valid range [50, 200]"
    
    @given(
        avg_edge=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('0.20'), places=4),
        num_trades=st.integers(min_value=10, max_value=50)
    )
    @settings(max_examples=100)
    def test_property_circuit_breaker_adjusts_with_confidence(self, avg_edge, num_trades):
        """
        Property 22: Dynamic Threshold Adaptation - Circuit Breaker Threshold
        
        **Validates: Requirements 4.11**
        
        Circuit breaker threshold adjusts based on confidence (normalized edge):
        - Confidence >= 80%: 7 losses
        - Confidence >= 60%: 5 losses
        - Confidence >= 40%: 4 losses
        - Confidence < 40%: 3 losses
        """
        # Generate performance sequence with specified average edge
        for i in range(num_trades):
            # Alternate wins and losses to ensure we have enough trades
            is_win = (i % 2 == 0)
            self.system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('0.50') if is_win else Decimal('-0.30'),
                was_successful=is_win,
                edge=avg_edge,  # Use specified edge
                odds=Decimal('1.0')
            )
        
        # Update dynamic parameters
        self.system.update_dynamic_parameters()
        
        # Get actual average edge from metrics
        metrics = self.system.get_performance_metrics()
        actual_avg_edge = metrics.avg_edge
        
        # Calculate confidence (normalized edge: edge / 0.10)
        confidence = actual_avg_edge / Decimal('0.10')
        
        # Verify circuit breaker threshold adjusts correctly based on confidence
        if confidence >= Decimal('0.80'):
            assert self.system.circuit_breaker_threshold == 7, \
                f"Confidence {confidence*100:.1f}% (edge={actual_avg_edge}) should set circuit breaker to 7 (got {self.system.circuit_breaker_threshold})"
        elif confidence >= Decimal('0.60'):
            assert self.system.circuit_breaker_threshold == 5, \
                f"Confidence {confidence*100:.1f}% (edge={actual_avg_edge}) should set circuit breaker to 5 (got {self.system.circuit_breaker_threshold})"
        elif confidence >= Decimal('0.40'):
            assert self.system.circuit_breaker_threshold == 4, \
                f"Confidence {confidence*100:.1f}% (edge={actual_avg_edge}) should set circuit breaker to 4 (got {self.system.circuit_breaker_threshold})"
        else:
            assert self.system.circuit_breaker_threshold == 3, \
                f"Confidence {confidence*100:.1f}% (edge={actual_avg_edge}) should set circuit breaker to 3 (got {self.system.circuit_breaker_threshold})"
        
        # Verify threshold is within valid range (3-7)
        assert 3 <= self.system.circuit_breaker_threshold <= 7, \
            f"Circuit breaker threshold {self.system.circuit_breaker_threshold} outside valid range [3, 7]"
    
    @given(
        win_rate=st.floats(min_value=0.0, max_value=1.0),
        avg_edge=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('0.20'), places=4),
        num_trades=st.integers(min_value=10, max_value=50)
    )
    @settings(max_examples=200)
    def test_property_thresholds_adapt_together(self, win_rate, avg_edge, num_trades):
        """
        Property 22: Dynamic Threshold Adaptation - Combined Adaptation
        
        **Validates: Requirements 4.11**
        
        Both daily trade limit and circuit breaker threshold adapt based on performance.
        """
        # Generate performance sequence
        num_wins = int(num_trades * win_rate)
        num_losses = num_trades - num_wins
        
        # Record winning trades with specified edge
        for i in range(num_wins):
            self.system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=avg_edge,
                odds=Decimal('1.0')
            )
        
        # Record losing trades with specified edge
        for i in range(num_losses):
            self.system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('-0.30'),
                was_successful=False,
                edge=avg_edge,
                odds=Decimal('1.0')
            )
        
        # Update dynamic parameters
        self.system.update_dynamic_parameters()
        
        # Verify both thresholds are within valid ranges
        assert 50 <= self.system.daily_trade_limit <= 200, \
            f"Daily trade limit {self.system.daily_trade_limit} outside valid range"
        assert 3 <= self.system.circuit_breaker_threshold <= 7, \
            f"Circuit breaker threshold {self.system.circuit_breaker_threshold} outside valid range"
        
        # Verify thresholds can be retrieved
        thresholds = self.system.get_dynamic_thresholds()
        assert 'daily_trade_limit' in thresholds
        assert 'circuit_breaker_threshold' in thresholds
        assert thresholds['daily_trade_limit'] == self.system.daily_trade_limit
        assert thresholds['circuit_breaker_threshold'] == self.system.circuit_breaker_threshold
    
    @given(
        num_trades=st.integers(min_value=1, max_value=9)
    )
    @settings(max_examples=50)
    def test_property_no_adaptation_with_insufficient_data(self, num_trades):
        """
        Property 22: Dynamic Threshold Adaptation - Insufficient Data
        
        **Validates: Requirements 4.11**
        
        Thresholds should not adapt when there are fewer than 10 trades.
        """
        # Create a fresh system for this test
        system = DynamicParameterSystem()
        
        # Record fewer than 10 trades
        for i in range(num_trades):
            system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.05'),
                odds=Decimal('1.0')
            )
        
        # Store initial values (base values from initialization)
        initial_daily_limit = 100  # Base value
        initial_circuit_breaker = 5  # Base value
        
        # Update dynamic parameters
        system.update_dynamic_parameters()
        
        # Verify thresholds remain at base values (no adaptation)
        assert system.daily_trade_limit == initial_daily_limit, \
            f"Daily trade limit should not change with {num_trades} trades (expected {initial_daily_limit}, got {system.daily_trade_limit})"
        assert system.circuit_breaker_threshold == initial_circuit_breaker, \
            f"Circuit breaker threshold should not change with {num_trades} trades (expected {initial_circuit_breaker}, got {system.circuit_breaker_threshold})"
    
    @given(
        performance_sequence=st.lists(
            st.tuples(
                st.booleans(),  # was_successful
                st.decimals(min_value=Decimal('0.01'), max_value=Decimal('0.20'), places=4)  # edge
            ),
            min_size=10,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_property_adaptation_is_deterministic(self, performance_sequence):
        """
        Property 22: Dynamic Threshold Adaptation - Determinism
        
        **Validates: Requirements 4.11**
        
        Same performance sequence should always produce same threshold values.
        """
        # Create two systems with identical configuration
        system1 = DynamicParameterSystem()
        system2 = DynamicParameterSystem()
        
        # Apply same performance sequence to both systems
        for was_successful, edge in performance_sequence:
            profit = Decimal('0.50') if was_successful else Decimal('-0.30')
            
            system1.record_trade(
                position_size=Decimal('10.0'),
                profit=profit,
                was_successful=was_successful,
                edge=edge,
                odds=Decimal('1.0')
            )
            
            system2.record_trade(
                position_size=Decimal('10.0'),
                profit=profit,
                was_successful=was_successful,
                edge=edge,
                odds=Decimal('1.0')
            )
        
        # Update both systems
        system1.update_dynamic_parameters()
        system2.update_dynamic_parameters()
        
        # Verify both systems have identical thresholds
        assert system1.daily_trade_limit == system2.daily_trade_limit, \
            "Same performance should produce same daily trade limit"
        assert system1.circuit_breaker_threshold == system2.circuit_breaker_threshold, \
            "Same performance should produce same circuit breaker threshold"
    
    @given(
        win_rate=st.floats(min_value=0.0, max_value=1.0),
        num_trades=st.integers(min_value=10, max_value=50)
    )
    @settings(max_examples=100)
    def test_property_higher_win_rate_increases_daily_limit(self, win_rate, num_trades):
        """
        Property 22: Dynamic Threshold Adaptation - Monotonicity
        
        **Validates: Requirements 4.11**
        
        Higher win rate should never decrease daily trade limit.
        """
        # Skip edge cases
        assume(0.35 < win_rate < 0.95)
        
        # Generate performance sequence
        num_wins = int(num_trades * win_rate)
        num_losses = num_trades - num_wins
        
        for i in range(num_wins):
            self.system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.05'),
                odds=Decimal('1.0')
            )
        
        for i in range(num_losses):
            self.system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('-0.30'),
                was_successful=False,
                edge=Decimal('0.05'),
                odds=Decimal('1.0')
            )
        
        # Update and get first limit
        self.system.update_dynamic_parameters()
        first_limit = self.system.daily_trade_limit
        
        # Add more winning trades to increase win rate
        for i in range(5):
            self.system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.05'),
                odds=Decimal('1.0')
            )
        
        # Update again
        self.system.update_dynamic_parameters()
        second_limit = self.system.daily_trade_limit
        
        # Verify limit increased or stayed the same (never decreased)
        assert second_limit >= first_limit, \
            f"Adding wins should not decrease daily limit (was {first_limit}, now {second_limit})"
    
    @given(
        avg_edge=st.decimals(min_value=Decimal('0.03'), max_value=Decimal('0.12'), places=4),
        num_trades=st.integers(min_value=10, max_value=30)
    )
    @settings(max_examples=100)
    def test_property_higher_confidence_increases_circuit_breaker(self, avg_edge, num_trades):
        """
        Property 22: Dynamic Threshold Adaptation - Confidence Monotonicity
        
        **Validates: Requirements 4.11**
        
        Higher confidence (edge) should never decrease circuit breaker threshold.
        """
        # Create a fresh system for this test
        system = DynamicParameterSystem()
        
        # Generate performance sequence with specified edge
        for i in range(num_trades):
            is_win = (i % 2 == 0)
            system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('0.50') if is_win else Decimal('-0.30'),
                was_successful=is_win,
                edge=avg_edge,
                odds=Decimal('1.0')
            )
        
        # Update and get first threshold
        system.update_dynamic_parameters()
        first_threshold = system.circuit_breaker_threshold
        
        # Add more trades with higher edge to increase confidence
        higher_edge = min(avg_edge * Decimal('1.5'), Decimal('0.20'))
        for i in range(5):
            is_win = (i % 2 == 0)
            system.record_trade(
                position_size=Decimal('10.0'),
                profit=Decimal('0.50') if is_win else Decimal('-0.30'),
                was_successful=is_win,
                edge=higher_edge,
                odds=Decimal('1.0')
            )
        
        # Update again
        system.update_dynamic_parameters()
        second_threshold = system.circuit_breaker_threshold
        
        # Verify threshold increased or stayed the same (never decreased)
        assert second_threshold >= first_threshold, \
            f"Higher confidence should not decrease circuit breaker (was {first_threshold}, now {second_threshold})"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
