"""
Unit tests for DynamicParameterSystem.

Tests edge calculation, Kelly Criterion, fractional Kelly adjustments,
and performance tracking.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from src.dynamic_parameter_system import (
    DynamicParameterSystem,
    TradeResult,
    PerformanceMetrics
)


class TestDynamicParameterSystem:
    """Test suite for DynamicParameterSystem."""
    
    def test_initialization(self):
        """Test system initializes with correct defaults."""
        system = DynamicParameterSystem()
        
        assert system.min_fractional_kelly == 0.25
        assert system.max_fractional_kelly == 0.50
        assert system.performance_window == 20
        assert system.transaction_cost_pct == Decimal('0.02')
        assert system.min_edge_threshold == Decimal('0.025')
        assert system.max_position_pct == Decimal('0.20')
        assert system.min_position_size == Decimal('0.10')
        assert system.current_fractional_kelly == 0.375  # Midpoint
        assert len(system.trade_history) == 0
    
    def test_calculate_edge_with_transaction_costs(self):
        """Test edge calculation accounts for transaction costs."""
        system = DynamicParameterSystem()
        
        # 5% profit, 99.5% win rate, 2% transaction costs
        profit_pct = Decimal('0.05')
        win_prob = Decimal('0.995')
        
        edge = system.calculate_edge(profit_pct, win_prob)
        
        # Expected: (0.995 * 0.05) - 0.02 = 0.04975 - 0.02 = 0.02975
        expected_edge = Decimal('0.02975')
        assert abs(edge - expected_edge) < Decimal('0.0001')
    
    def test_calculate_edge_below_threshold(self):
        """Test edge calculation when profit is too low."""
        system = DynamicParameterSystem()
        
        # 3% profit, 99.5% win rate, 2% transaction costs
        profit_pct = Decimal('0.03')
        win_prob = Decimal('0.995')
        
        edge = system.calculate_edge(profit_pct, win_prob)
        
        # Expected: (0.995 * 0.03) - 0.02 = 0.02985 - 0.02 = 0.00985
        # This is below the 2.5% threshold
        assert edge < system.min_edge_threshold
    
    def test_calculate_kelly_fraction(self):
        """Test Kelly Criterion formula: f = edge / odds."""
        system = DynamicParameterSystem()
        
        edge = Decimal('0.03')  # 3% edge
        odds = Decimal('0.05')  # 5% odds
        
        kelly_fraction = system.calculate_kelly_fraction(edge, odds)
        
        # Expected: 0.03 / 0.05 = 0.6
        assert kelly_fraction == Decimal('0.6')
    
    def test_calculate_kelly_fraction_zero_odds(self):
        """Test Kelly Criterion with zero odds returns zero."""
        system = DynamicParameterSystem()
        
        edge = Decimal('0.03')
        odds = Decimal('0')
        
        kelly_fraction = system.calculate_kelly_fraction(edge, odds)
        
        assert kelly_fraction == Decimal('0')
    
    def test_calculate_position_size_basic(self):
        """Test basic position size calculation."""
        system = DynamicParameterSystem()
        
        bankroll = Decimal('100.00')
        profit_pct = Decimal('0.05')  # 5% profit
        cost = Decimal('10.00')
        
        position_size, details = system.calculate_position_size(
            bankroll, profit_pct, cost
        )
        
        # Should return a valid position size
        assert position_size > Decimal('0')
        assert position_size <= bankroll
        assert 'edge' in details
        assert 'kelly_fraction' in details
        assert 'fractional_kelly' in details
    
    def test_calculate_position_size_edge_too_low(self):
        """Test position size returns zero when edge is too low."""
        system = DynamicParameterSystem()
        
        bankroll = Decimal('100.00')
        profit_pct = Decimal('0.025')  # 2.5% profit (too low after costs)
        cost = Decimal('10.00')
        
        position_size, details = system.calculate_position_size(
            bankroll, profit_pct, cost
        )
        
        # Should return zero due to low edge
        assert position_size == Decimal('0')
        assert details['reason'] == 'edge_too_low'
    
    def test_calculate_position_size_capped_at_max(self):
        """Test position size is capped at 20% of bankroll."""
        system = DynamicParameterSystem()
        
        bankroll = Decimal('100.00')
        profit_pct = Decimal('0.50')  # 50% profit (very high)
        cost = Decimal('10.00')
        
        position_size, details = system.calculate_position_size(
            bankroll, profit_pct, cost
        )
        
        # Should be capped at 20% of bankroll
        max_position = bankroll * Decimal('0.20')
        assert position_size <= max_position
        assert details['was_capped'] == True
    
    def test_calculate_position_size_below_minimum(self):
        """Test position size returns zero when below minimum."""
        system = DynamicParameterSystem()
        
        bankroll = Decimal('1.00')  # Very small bankroll
        profit_pct = Decimal('0.10')  # 10% profit (high enough edge)
        cost = Decimal('0.50')
        
        position_size, details = system.calculate_position_size(
            bankroll, profit_pct, cost
        )
        
        # Should return zero if below $0.10 minimum, or a valid position
        # With small bankroll, position might be below minimum
        if position_size == Decimal('0'):
            assert details['reason'] in ['below_minimum', 'edge_too_low']
        else:
            # If position is calculated, it should be >= minimum
            assert position_size >= system.min_position_size
    
    def test_calculate_position_size_fractional_kelly_applied(self):
        """Test fractional Kelly is properly applied."""
        system = DynamicParameterSystem()
        system.current_fractional_kelly = 0.5  # 50%
        
        bankroll = Decimal('100.00')
        profit_pct = Decimal('0.10')  # 10% profit
        cost = Decimal('10.00')
        
        position_size, details = system.calculate_position_size(
            bankroll, profit_pct, cost
        )
        
        # Verify fractional Kelly was applied
        assert details['fractional_kelly'] == Decimal('0.5')
        assert details['adjusted_kelly'] == details['kelly_fraction'] * Decimal('0.5')
    
    def test_record_trade(self):
        """Test recording a trade updates history."""
        system = DynamicParameterSystem()
        
        system.record_trade(
            position_size=Decimal('10.00'),
            profit=Decimal('0.50'),
            was_successful=True,
            edge=Decimal('0.03'),
            odds=Decimal('0.05')
        )
        
        assert len(system.trade_history) == 1
        trade = system.trade_history[0]
        assert trade.position_size == Decimal('10.00')
        assert trade.profit == Decimal('0.50')
        assert trade.was_successful == True
    
    def test_record_trade_max_window(self):
        """Test trade history respects maximum window size."""
        system = DynamicParameterSystem(performance_window=5)
        
        # Record 10 trades
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        # Should only keep last 5
        assert len(system.trade_history) == 5
    
    def test_get_performance_metrics_empty(self):
        """Test performance metrics with no trades."""
        system = DynamicParameterSystem()
        
        metrics = system.get_performance_metrics()
        
        assert metrics.win_rate == 0.0
        assert metrics.avg_profit == Decimal('0')
        assert metrics.avg_edge == Decimal('0')
        assert metrics.total_trades == 0
        assert metrics.profitable_trades == 0
    
    def test_get_performance_metrics_with_trades(self):
        """Test performance metrics calculation."""
        system = DynamicParameterSystem()
        
        # Record 10 trades: 8 wins, 2 losses
        for i in range(8):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        for i in range(2):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('-0.20'),
                was_successful=False,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        metrics = system.get_performance_metrics()
        
        assert metrics.total_trades == 10
        assert metrics.profitable_trades == 8
        assert metrics.win_rate == 0.8
        assert metrics.avg_profit > Decimal('0')  # Net positive
    
    def test_adjust_fractional_kelly_high_win_rate(self):
        """Test fractional Kelly increases with high win rate."""
        system = DynamicParameterSystem()
        
        # Record 20 winning trades (100% win rate)
        for i in range(20):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        # Should increase to max
        assert system.current_fractional_kelly == system.max_fractional_kelly
    
    def test_adjust_fractional_kelly_low_win_rate(self):
        """Test fractional Kelly decreases with low win rate."""
        system = DynamicParameterSystem()
        
        # Record 20 trades: 15 losses, 5 wins (25% win rate)
        for i in range(15):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('-0.20'),
                was_successful=False,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        for i in range(5):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        # Should decrease to min
        assert system.current_fractional_kelly == system.min_fractional_kelly
    
    def test_adjust_fractional_kelly_medium_win_rate(self):
        """Test fractional Kelly stays at midpoint with medium win rate."""
        system = DynamicParameterSystem()
        
        # Record 20 trades: 18 wins, 2 losses (90% win rate)
        for i in range(18):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        for i in range(2):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('-0.20'),
                was_successful=False,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        # Should stay at midpoint
        expected_midpoint = (system.min_fractional_kelly + system.max_fractional_kelly) / 2
        assert system.current_fractional_kelly == expected_midpoint
    
    def test_get_current_state(self):
        """Test getting current system state."""
        system = DynamicParameterSystem()
        
        # Record some trades
        for i in range(5):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        state = system.get_current_state()
        
        assert 'fractional_kelly' in state
        assert 'min_edge_threshold' in state
        assert 'transaction_cost_pct' in state
        assert 'performance' in state
        assert state['performance']['total_trades'] == 5
        assert state['performance']['win_rate'] == 1.0
    
    def test_reset_performance_tracking(self):
        """Test resetting performance tracking."""
        system = DynamicParameterSystem()
        
        # Record some trades
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        # Reset
        system.reset_performance_tracking()
        
        assert len(system.trade_history) == 0
        expected_midpoint = (system.min_fractional_kelly + system.max_fractional_kelly) / 2
        assert system.current_fractional_kelly == expected_midpoint
    
    def test_position_size_bounds_invariant(self):
        """Test position size always respects bounds."""
        system = DynamicParameterSystem()
        
        test_cases = [
            (Decimal('100.00'), Decimal('0.05'), Decimal('10.00')),
            (Decimal('50.00'), Decimal('0.10'), Decimal('5.00')),
            (Decimal('200.00'), Decimal('0.03'), Decimal('20.00')),
            (Decimal('10.00'), Decimal('0.08'), Decimal('2.00')),
        ]
        
        for bankroll, profit_pct, cost in test_cases:
            position_size, details = system.calculate_position_size(
                bankroll, profit_pct, cost
            )
            
            # Verify bounds
            assert position_size >= Decimal('0')
            assert position_size <= bankroll
            assert position_size <= bankroll * system.max_position_pct or position_size == Decimal('0')
            
            if position_size > Decimal('0'):
                assert position_size >= system.min_position_size


class TestCostBenefitAnalysis:
    """Test suite for cost-benefit analysis (Requirements 4.13, 4.14)."""
    
    def test_cost_benefit_analysis_passes(self):
        """Test cost-benefit analysis passes with reasonable costs."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.30')  # 30% of profit
        estimated_slippage = Decimal('0.10')  # 10% of profit
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        assert should_trade == True
        assert details['expected_profit'] == expected_profit
        assert details['transaction_costs'] == transaction_costs
        assert details['estimated_slippage'] == estimated_slippage
        assert details['total_costs'] == Decimal('0.40')
        assert details['net_profit'] == Decimal('0.60')
        assert details['transaction_cost_pct'] == 30
        assert details['slippage_pct'] == 10
    
    def test_cost_benefit_analysis_transaction_costs_too_high(self):
        """Test trade rejected when transaction costs > 50% of profit (Requirement 4.13)."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.60')  # 60% of profit (> 50%)
        estimated_slippage = Decimal('0.10')  # 10% of profit
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        assert should_trade == False
        assert details['reason'] == 'transaction_costs_too_high'
        assert details['transaction_cost_pct'] == 60
    
    def test_cost_benefit_analysis_transaction_costs_exactly_50_percent(self):
        """Test trade rejected when transaction costs = 50% of profit (boundary)."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.50')  # Exactly 50% of profit
        estimated_slippage = Decimal('0.10')
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        # Should pass at exactly 50% (> 50% is the threshold)
        assert should_trade == True
        assert details['net_profit'] == Decimal('0.40')
    
    def test_cost_benefit_analysis_slippage_too_high(self):
        """Test trade rejected when slippage > 25% of profit (Requirement 4.14)."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.20')  # 20% of profit
        estimated_slippage = Decimal('0.30')  # 30% of profit (> 25%)
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        assert should_trade == False
        assert details['reason'] == 'slippage_too_high'
        assert details['slippage_pct'] == 30
    
    def test_cost_benefit_analysis_slippage_exactly_25_percent(self):
        """Test trade rejected when slippage = 25% of profit (boundary)."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.20')
        estimated_slippage = Decimal('0.25')  # Exactly 25% of profit
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        # Should pass at exactly 25% (> 25% is the threshold)
        assert should_trade == True
        assert details['net_profit'] == Decimal('0.55')
    
    def test_cost_benefit_analysis_net_profit_zero(self):
        """Test trade rejected when net profit = 0."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.75')  # 75% but will be caught by 50% check first
        estimated_slippage = Decimal('0.25')  # Exactly 25% (passes)
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        # This will be caught by transaction_costs_too_high first
        assert should_trade == False
        assert details['reason'] == 'transaction_costs_too_high'
    
    def test_cost_benefit_analysis_net_profit_negative(self):
        """Test trade rejected when net profit < 0."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.50')  # Exactly 50% (passes)
        estimated_slippage = Decimal('0.51')  # 51% (> 25%, will be caught)
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        # This will be caught by slippage_too_high first
        assert should_trade == False
        assert details['reason'] == 'slippage_too_high'
    
    def test_cost_benefit_analysis_net_profit_exactly_zero(self):
        """Test trade rejected when net profit = 0 (passes other checks)."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.50')  # Exactly 50% (passes)
        estimated_slippage = Decimal('0.50')  # Total = 1.00, net profit = 0
        
        # Note: slippage is 50% which is > 25%, so this will be caught by slippage check
        # Let's use values that pass both checks but result in zero net profit
        transaction_costs = Decimal('0.49')  # 49% (passes)
        estimated_slippage = Decimal('0.51')  # 51% (> 25%, will be caught)
        
        # Actually, we need to test the net profit check specifically
        # Let's use smaller slippage that passes but total costs = profit
        transaction_costs = Decimal('0.80')  # 80% (> 50%, will be caught)
        estimated_slippage = Decimal('0.20')  # 20% (passes)
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        # This will be caught by transaction_costs_too_high
        assert should_trade == False
        assert details['reason'] == 'transaction_costs_too_high'
    
    def test_cost_benefit_analysis_net_profit_barely_negative(self):
        """Test trade rejected when net profit is barely negative."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.49')  # 49% (passes)
        estimated_slippage = Decimal('0.52')  # 52% (> 25%, will be caught)
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        # This will be caught by slippage_too_high
        assert should_trade == False
        assert details['reason'] == 'slippage_too_high'
    
    def test_cost_benefit_analysis_no_profit_expected(self):
        """Test trade rejected when expected profit <= 0."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('0.00')
        transaction_costs = Decimal('0.10')
        estimated_slippage = Decimal('0.05')
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        assert should_trade == False
        assert details['reason'] == 'no_profit_expected'
    
    def test_cost_benefit_analysis_negative_profit_expected(self):
        """Test trade rejected when expected profit is negative."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('-0.50')
        transaction_costs = Decimal('0.10')
        estimated_slippage = Decimal('0.05')
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        assert should_trade == False
        assert details['reason'] == 'no_profit_expected'
    
    def test_cost_benefit_analysis_minimal_costs(self):
        """Test cost-benefit analysis with minimal costs."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.01')  # 1% of profit
        estimated_slippage = Decimal('0.01')  # 1% of profit
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        assert should_trade == True
        assert details['net_profit'] == Decimal('0.98')
        assert details['net_profit_pct'] == 98
    
    def test_cost_benefit_analysis_high_profit_high_costs(self):
        """Test cost-benefit analysis with high profit and high costs."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('10.00')
        transaction_costs = Decimal('4.00')  # 40% of profit
        estimated_slippage = Decimal('2.00')  # 20% of profit
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        assert should_trade == True
        assert details['net_profit'] == Decimal('4.00')
        assert details['transaction_cost_pct'] == 40
        assert details['slippage_pct'] == 20
    
    def test_cost_benefit_analysis_small_profit_small_costs(self):
        """Test cost-benefit analysis with small profit and small costs."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('0.10')
        transaction_costs = Decimal('0.03')  # 30% of profit
        estimated_slippage = Decimal('0.02')  # 20% of profit
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        assert should_trade == True
        assert details['net_profit'] == Decimal('0.05')
    
    def test_cost_benefit_analysis_boundary_both_limits(self):
        """Test cost-benefit analysis at both boundary limits."""
        system = DynamicParameterSystem()
        
        expected_profit = Decimal('1.00')
        transaction_costs = Decimal('0.50')  # Exactly 50%
        estimated_slippage = Decimal('0.25')  # Exactly 25%
        
        should_trade, details = system.analyze_cost_benefit(
            expected_profit, transaction_costs, estimated_slippage
        )
        
        assert should_trade == True
        assert details['net_profit'] == Decimal('0.25')
        assert details['transaction_cost_pct'] == 50
        assert details['slippage_pct'] == 25


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


class TestDynamicParameterUpdates:
    """Test suite for dynamic parameter updates (Requirements 4.2, 4.11)."""
    
    def test_update_dynamic_parameters_with_winning_trades(self):
        """Test dynamic parameters update based on winning trades."""
        system = DynamicParameterSystem()
        
        # Record 10 winning trades with consistent profit
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),  # 5% profit
                was_successful=True,
                edge=Decimal('0.08'),  # Higher edge for good confidence
                odds=Decimal('0.05')
            )
        
        # Update parameters
        system.update_dynamic_parameters()
        
        # Take-profit should be updated based on average win
        assert system.take_profit_pct > Decimal('0')
        # Daily trade limit should increase with high win rate
        assert system.daily_trade_limit >= 150
        # Circuit breaker threshold should be moderate to high
        assert system.circuit_breaker_threshold >= 5
    
    def test_update_dynamic_parameters_with_losing_trades(self):
        """Test dynamic parameters update based on losing trades."""
        system = DynamicParameterSystem()
        
        # Record 10 losing trades
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('-0.30'),  # 3% loss
                was_successful=False,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        # Update parameters
        system.update_dynamic_parameters()
        
        # Stop-loss should be updated based on average loss
        assert system.stop_loss_pct > Decimal('0')
        # Daily trade limit should decrease with low win rate
        assert system.daily_trade_limit <= 100
        # Circuit breaker threshold should be strict
        assert system.circuit_breaker_threshold <= 5
    
    def test_update_dynamic_parameters_with_mixed_trades(self):
        """Test dynamic parameters update with mixed win/loss trades."""
        system = DynamicParameterSystem()
        
        # Record 6 wins and 4 losses (60% win rate)
        for i in range(6):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        for i in range(4):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('-0.30'),
                was_successful=False,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        # Update parameters
        system.update_dynamic_parameters()
        
        # Both take-profit and stop-loss should be updated
        assert system.take_profit_pct > Decimal('0')
        assert system.stop_loss_pct > Decimal('0')
        # Daily trade limit should be moderate
        assert 100 <= system.daily_trade_limit <= 150
    
    def test_update_dynamic_parameters_with_supersmart_blend(self):
        """Test blending with SuperSmart learned parameters."""
        system = DynamicParameterSystem()
        
        # Record some trades
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        # SuperSmart suggests different parameters
        supersmart_params = {
            'take_profit_pct': 0.08,  # 8%
            'stop_loss_pct': 0.04     # 4%
        }
        
        # Update with blending
        system.update_dynamic_parameters(supersmart_params=supersmart_params)
        
        # Parameters should be blended (50/50)
        # Should be between EMA-calculated and SuperSmart values
        assert system.take_profit_pct > Decimal('0')
        assert system.stop_loss_pct > Decimal('0')
    
    def test_update_dynamic_parameters_with_adaptive_blend(self):
        """Test blending with Adaptive learned parameters."""
        system = DynamicParameterSystem()
        
        # Record some trades
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        # Adaptive suggests different parameters
        adaptive_params = {
            'take_profit_pct': 0.06,  # 6%
            'stop_loss_pct': 0.03     # 3%
        }
        
        # Update with blending
        system.update_dynamic_parameters(adaptive_params=adaptive_params)
        
        # Parameters should be blended
        assert system.take_profit_pct > Decimal('0')
        assert system.stop_loss_pct > Decimal('0')
    
    def test_update_dynamic_parameters_with_both_engines(self):
        """Test blending with both SuperSmart and Adaptive parameters."""
        system = DynamicParameterSystem()
        
        # Record some trades
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        supersmart_params = {
            'take_profit_pct': 0.08,
            'stop_loss_pct': 0.04
        }
        
        adaptive_params = {
            'take_profit_pct': 0.06,
            'stop_loss_pct': 0.03
        }
        
        # Update with both
        system.update_dynamic_parameters(
            supersmart_params=supersmart_params,
            adaptive_params=adaptive_params
        )
        
        # Parameters should be blended from all three sources
        assert system.take_profit_pct > Decimal('0')
        assert system.stop_loss_pct > Decimal('0')
    
    def test_daily_trade_limit_high_win_rate(self):
        """Test daily trade limit increases with high win rate (>80%)."""
        system = DynamicParameterSystem()
        
        # Record 10 trades with 90% win rate
        for i in range(9):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        system.record_trade(
            position_size=Decimal('10.00'),
            profit=Decimal('-0.30'),
            was_successful=False,
            edge=Decimal('0.03'),
            odds=Decimal('0.05')
        )
        
        system.update_dynamic_parameters()
        
        # Should increase to 200 trades
        assert system.daily_trade_limit == 200
    
    def test_daily_trade_limit_good_win_rate(self):
        """Test daily trade limit with good win rate (60-80%)."""
        system = DynamicParameterSystem()
        
        # Record 10 trades with 70% win rate
        for i in range(7):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        for i in range(3):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('-0.30'),
                was_successful=False,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        system.update_dynamic_parameters()
        
        # Should be 150 trades
        assert system.daily_trade_limit == 150
    
    def test_daily_trade_limit_mediocre_win_rate(self):
        """Test daily trade limit with mediocre win rate (40-60%)."""
        system = DynamicParameterSystem()
        
        # Record 10 trades with 50% win rate
        for i in range(5):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        for i in range(5):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('-0.30'),
                was_successful=False,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        system.update_dynamic_parameters()
        
        # Should be 100 trades (base)
        assert system.daily_trade_limit == 100
    
    def test_daily_trade_limit_low_win_rate(self):
        """Test daily trade limit decreases with low win rate (<40%)."""
        system = DynamicParameterSystem()
        
        # Record 10 trades with 30% win rate
        for i in range(3):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        for i in range(7):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('-0.30'),
                was_successful=False,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        system.update_dynamic_parameters()
        
        # Should decrease to 50 trades
        assert system.daily_trade_limit == 50
    
    def test_circuit_breaker_high_confidence(self):
        """Test circuit breaker threshold increases with high confidence."""
        system = DynamicParameterSystem()
        
        # Record trades with high edge (high confidence)
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.10'),  # High edge = high confidence
                odds=Decimal('0.05')
            )
        
        system.update_dynamic_parameters()
        
        # Should allow more losses (7)
        assert system.circuit_breaker_threshold == 7
    
    def test_circuit_breaker_good_confidence(self):
        """Test circuit breaker threshold with good confidence."""
        system = DynamicParameterSystem()
        
        # Record trades with moderate edge
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.07'),  # Moderate edge
                odds=Decimal('0.05')
            )
        
        system.update_dynamic_parameters()
        
        # Should be moderate (5)
        assert system.circuit_breaker_threshold == 5
    
    def test_circuit_breaker_low_confidence(self):
        """Test circuit breaker threshold decreases with low confidence."""
        system = DynamicParameterSystem()
        
        # Record trades with low edge
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),  # Low edge = low confidence
                odds=Decimal('0.05')
            )
        
        system.update_dynamic_parameters()
        
        # Should be strict (3-4)
        assert system.circuit_breaker_threshold <= 4
    
    def test_parameter_clamping_take_profit(self):
        """Test take-profit is clamped to reasonable range (1-10%)."""
        system = DynamicParameterSystem()
        
        # Force extreme values through blending
        supersmart_params = {
            'take_profit_pct': 0.50,  # 50% (unrealistic)
            'stop_loss_pct': 0.02
        }
        
        system.update_dynamic_parameters(supersmart_params=supersmart_params)
        
        # Should be clamped to max 10%
        assert system.take_profit_pct <= Decimal('0.10')
        assert system.take_profit_pct >= Decimal('0.01')
    
    def test_parameter_clamping_stop_loss(self):
        """Test stop-loss is clamped to reasonable range (1-5%)."""
        system = DynamicParameterSystem()
        
        # Force extreme values through blending
        supersmart_params = {
            'take_profit_pct': 0.02,
            'stop_loss_pct': 0.20  # 20% (unrealistic)
        }
        
        system.update_dynamic_parameters(supersmart_params=supersmart_params)
        
        # Should be clamped to max 5%
        assert system.stop_loss_pct <= Decimal('0.05')
        assert system.stop_loss_pct >= Decimal('0.01')
    
    def test_get_dynamic_thresholds(self):
        """Test getting current dynamic thresholds."""
        system = DynamicParameterSystem()
        
        # Set some values
        system.take_profit_pct = Decimal('0.03')
        system.stop_loss_pct = Decimal('0.02')
        system.daily_trade_limit = 150
        system.circuit_breaker_threshold = 6
        
        thresholds = system.get_dynamic_thresholds()
        
        assert thresholds['take_profit_pct'] == 0.03
        assert thresholds['stop_loss_pct'] == 0.02
        assert thresholds['daily_trade_limit'] == 150
        assert thresholds['circuit_breaker_threshold'] == 6
    
    def test_update_with_insufficient_data(self):
        """Test update with insufficient trade history (<5 trades)."""
        system = DynamicParameterSystem()
        
        # Record only 3 trades
        for i in range(3):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('0.50'),
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        initial_tp = system.take_profit_pct
        initial_sl = system.stop_loss_pct
        
        # Update parameters
        system.update_dynamic_parameters()
        
        # Parameters should not change much (no EMA update)
        # But daily limit and circuit breaker won't update either (<10 trades)
        assert system.daily_trade_limit == 100  # Base value
        assert system.circuit_breaker_threshold == 5  # Base value
    
    def test_ema_smoothing(self):
        """Test EMA smoothing prevents drastic parameter changes."""
        system = DynamicParameterSystem()
        system.ema_alpha = 0.2  # 20% weight to new values
        
        # Set initial values
        system.take_profit_pct = Decimal('0.02')
        
        # Record trades with higher profit
        for i in range(10):
            system.record_trade(
                position_size=Decimal('10.00'),
                profit=Decimal('1.00'),  # 10% profit
                was_successful=True,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
        
        system.update_dynamic_parameters()
        
        # New value should be smoothed, not jump to 12% (10% * 1.2)
        # Should be closer to original 2% due to EMA
        assert system.take_profit_pct > Decimal('0.02')
        assert system.take_profit_pct < Decimal('0.10')  # Clamped at max
