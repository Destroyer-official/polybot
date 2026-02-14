"""
Property-based tests for cost-benefit analysis.

Uses Hypothesis to test cost-benefit analysis logic across a wide range of inputs.
Validates Requirements 4.13, 4.14.

**Validates: Requirements 4.13, 4.14**
"""

import pytest
from decimal import Decimal
from hypothesis import given, strategies as st, settings, assume
from src.dynamic_parameter_system import DynamicParameterSystem


class TestCostBenefitAnalysisProperties:
    """Property-based tests for cost-benefit analysis."""
    
    def setup_method(self):
        """Create a DynamicParameterSystem instance for testing."""
        self.system = DynamicParameterSystem(
            min_fractional_kelly=0.25,
            max_fractional_kelly=0.50,
            transaction_cost_pct=Decimal('0.02'),
            min_edge_threshold=Decimal('0.025')
        )
    
    @given(
        expected_profit=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('100.00'),
            places=4
        ),
        transaction_cost_pct=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('0.99'),
            places=4
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_21_transaction_costs_threshold(self, expected_profit, transaction_cost_pct):
        """
        Property 21a: Trade skipped when transaction costs > 50% of expected profit.
        
        **Validates: Requirements 4.13**
        - 4.13: Check if transaction costs > 50% of expected profit
        """
        # Calculate transaction costs
        transaction_costs = expected_profit * transaction_cost_pct
        
        # Zero slippage for this test
        estimated_slippage = Decimal('0')
        
        # Analyze cost-benefit
        should_trade, details = self.system.analyze_cost_benefit(
            expected_profit=expected_profit,
            transaction_costs=transaction_costs,
            estimated_slippage=estimated_slippage
        )
        
        # Verify behavior based on transaction cost percentage
        if transaction_cost_pct > Decimal('0.50'):
            # Transaction costs > 50% of profit → should NOT trade
            assert should_trade is False, \
                f"Should skip trade when transaction costs ({transaction_cost_pct*100:.1f}%) > 50% of profit"
            assert details['reason'] == 'transaction_costs_too_high', \
                f"Expected reason 'transaction_costs_too_high', got '{details['reason']}'"
            assert 'transaction_cost_pct' in details, \
                "Details should include transaction_cost_pct"
        else:
            # Transaction costs <= 50% of profit → should trade (if net profit > 0)
            net_profit = expected_profit - transaction_costs
            if net_profit > 0:
                assert should_trade is True, \
                    f"Should trade when transaction costs ({transaction_cost_pct*100:.1f}%) <= 50% of profit"
                assert 'net_profit' in details, \
                    "Details should include net_profit"
                assert details['net_profit'] == net_profit, \
                    f"Net profit mismatch: expected {net_profit}, got {details['net_profit']}"
    
    @given(
        expected_profit=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('100.00'),
            places=4
        ),
        slippage_pct=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('0.99'),
            places=4
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_21_slippage_threshold(self, expected_profit, slippage_pct):
        """
        Property 21b: Trade skipped when estimated slippage > 25% of expected profit.
        
        **Validates: Requirements 4.14**
        - 4.14: Check if estimated slippage > 25% of expected profit
        """
        # Calculate slippage
        estimated_slippage = expected_profit * slippage_pct
        
        # Zero transaction costs for this test
        transaction_costs = Decimal('0')
        
        # Analyze cost-benefit
        should_trade, details = self.system.analyze_cost_benefit(
            expected_profit=expected_profit,
            transaction_costs=transaction_costs,
            estimated_slippage=estimated_slippage
        )
        
        # Verify behavior based on slippage percentage
        if slippage_pct > Decimal('0.25'):
            # Slippage > 25% of profit → should NOT trade
            assert should_trade is False, \
                f"Should skip trade when slippage ({slippage_pct*100:.1f}%) > 25% of profit"
            assert details['reason'] == 'slippage_too_high', \
                f"Expected reason 'slippage_too_high', got '{details['reason']}'"
            assert 'slippage_pct' in details, \
                "Details should include slippage_pct"
        else:
            # Slippage <= 25% of profit → should trade (if net profit > 0)
            net_profit = expected_profit - estimated_slippage
            if net_profit > 0:
                assert should_trade is True, \
                    f"Should trade when slippage ({slippage_pct*100:.1f}%) <= 25% of profit"
                assert 'net_profit' in details, \
                    "Details should include net_profit"
                assert details['net_profit'] == net_profit, \
                    f"Net profit mismatch: expected {net_profit}, got {details['net_profit']}"
    
    @given(
        expected_profit=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('100.00'),
            places=4
        ),
        transaction_cost_pct=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('0.60'),
            places=4
        ),
        slippage_pct=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('0.60'),
            places=4
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_21_net_profit_threshold(self, expected_profit, transaction_cost_pct, slippage_pct):
        """
        Property 21c: Trade skipped when net profit <= 0 after all costs.
        
        **Validates: Requirements 4.13, 4.14**
        - Verifies that trades are skipped when total costs exceed expected profit
        """
        # Calculate costs
        transaction_costs = expected_profit * transaction_cost_pct
        estimated_slippage = expected_profit * slippage_pct
        total_costs = transaction_costs + estimated_slippage
        net_profit = expected_profit - total_costs
        
        # Analyze cost-benefit
        should_trade, details = self.system.analyze_cost_benefit(
            expected_profit=expected_profit,
            transaction_costs=transaction_costs,
            estimated_slippage=estimated_slippage
        )
        
        # Verify behavior based on net profit
        if net_profit <= 0:
            # Net profit <= 0 → should NOT trade
            assert should_trade is False, \
                f"Should skip trade when net profit (${net_profit:.4f}) <= 0"
            assert details['reason'] in ['transaction_costs_too_high', 'slippage_too_high', 'net_profit_negative'], \
                f"Expected cost-related reason, got '{details['reason']}'"
        else:
            # Net profit > 0 → check if individual thresholds are met
            if transaction_cost_pct <= Decimal('0.50') and slippage_pct <= Decimal('0.25'):
                # Both thresholds met → should trade
                assert should_trade is True, \
                    f"Should trade when net profit (${net_profit:.4f}) > 0 and thresholds met"
                assert details['net_profit'] == net_profit, \
                    f"Net profit mismatch: expected {net_profit}, got {details['net_profit']}"
                assert details['total_costs'] == total_costs, \
                    f"Total costs mismatch: expected {total_costs}, got {details['total_costs']}"
    
    @given(
        expected_profit=st.decimals(
            min_value=Decimal('-10.00'),
            max_value=Decimal('0.00'),
            places=4
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_property_21_negative_profit(self, expected_profit):
        """
        Property 21d: Trade always skipped when expected profit <= 0.
        
        **Validates: Requirements 4.13, 4.14**
        - Verifies that trades with no expected profit are always rejected
        """
        # Any costs (even zero)
        transaction_costs = Decimal('0')
        estimated_slippage = Decimal('0')
        
        # Analyze cost-benefit
        should_trade, details = self.system.analyze_cost_benefit(
            expected_profit=expected_profit,
            transaction_costs=transaction_costs,
            estimated_slippage=estimated_slippage
        )
        
        # Should never trade with non-positive expected profit
        assert should_trade is False, \
            f"Should never trade when expected profit (${expected_profit:.4f}) <= 0"
        assert details['reason'] == 'no_profit_expected', \
            f"Expected reason 'no_profit_expected', got '{details['reason']}'"
    
    @given(
        expected_profit=st.decimals(
            min_value=Decimal('1.00'),
            max_value=Decimal('100.00'),
            places=4
        ),
        transaction_cost_pct=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('0.40'),
            places=4
        ),
        slippage_pct=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('0.20'),
            places=4
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_21_profitable_trades_accepted(self, expected_profit, transaction_cost_pct, slippage_pct):
        """
        Property 21e: Trade accepted when all thresholds met and net profit > 0.
        
        **Validates: Requirements 4.13, 4.14**
        - Verifies that profitable trades passing all checks are accepted
        """
        # Calculate costs (both below thresholds)
        transaction_costs = expected_profit * transaction_cost_pct
        estimated_slippage = expected_profit * slippage_pct
        total_costs = transaction_costs + estimated_slippage
        net_profit = expected_profit - total_costs
        
        # Assume net profit is positive (filter out edge cases)
        assume(net_profit > Decimal('0.01'))
        
        # Analyze cost-benefit
        should_trade, details = self.system.analyze_cost_benefit(
            expected_profit=expected_profit,
            transaction_costs=transaction_costs,
            estimated_slippage=estimated_slippage
        )
        
        # Should trade when all conditions are favorable
        assert should_trade is True, \
            f"Should trade when costs are reasonable and net profit (${net_profit:.4f}) > 0"
        
        # Verify details are complete
        assert 'expected_profit' in details
        assert 'transaction_costs' in details
        assert 'transaction_cost_pct' in details
        assert 'estimated_slippage' in details
        assert 'slippage_pct' in details
        assert 'total_costs' in details
        assert 'net_profit' in details
        assert 'net_profit_pct' in details
        
        # Verify calculations
        assert details['expected_profit'] == expected_profit
        assert details['transaction_costs'] == transaction_costs
        assert details['estimated_slippage'] == estimated_slippage
        assert details['total_costs'] == total_costs
        assert details['net_profit'] == net_profit
        
        # Verify percentages
        assert abs(details['transaction_cost_pct'] - (transaction_cost_pct * 100)) < Decimal('0.1'), \
            "Transaction cost percentage should be accurate"
        assert abs(details['slippage_pct'] - (slippage_pct * 100)) < Decimal('0.1'), \
            "Slippage percentage should be accurate"
    
    @given(
        expected_profit=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('100.00'),
            places=4
        ),
        transaction_cost_pct=st.decimals(
            min_value=Decimal('0.51'),
            max_value=Decimal('0.99'),
            places=4
        ),
        slippage_pct=st.decimals(
            min_value=Decimal('0.26'),
            max_value=Decimal('0.99'),
            places=4
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_property_21_both_thresholds_exceeded(self, expected_profit, transaction_cost_pct, slippage_pct):
        """
        Property 21f: Trade skipped when both cost thresholds are exceeded.
        
        **Validates: Requirements 4.13, 4.14**
        - Verifies that trades are rejected when both costs are too high
        """
        # Calculate costs (both above thresholds)
        transaction_costs = expected_profit * transaction_cost_pct
        estimated_slippage = expected_profit * slippage_pct
        
        # Analyze cost-benefit
        should_trade, details = self.system.analyze_cost_benefit(
            expected_profit=expected_profit,
            transaction_costs=transaction_costs,
            estimated_slippage=estimated_slippage
        )
        
        # Should NOT trade when both thresholds exceeded
        assert should_trade is False, \
            f"Should skip trade when both transaction costs ({transaction_cost_pct*100:.1f}%) " \
            f"and slippage ({slippage_pct*100:.1f}%) exceed thresholds"
        
        # Reason should be one of the cost-related reasons
        # (transaction_costs_too_high is checked first in the implementation)
        assert details['reason'] in ['transaction_costs_too_high', 'slippage_too_high', 'net_profit_negative'], \
            f"Expected cost-related reason, got '{details['reason']}'"
