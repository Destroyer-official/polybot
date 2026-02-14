"""
Property-based tests for volatility-based parameter adjustments.

Uses Hypothesis to test volatility adjustment logic across a wide range of inputs.
Validates Requirements 4.5, 4.6.
"""

import pytest
from decimal import Decimal
from hypothesis import given, strategies as st, settings
from src.dynamic_parameter_system import DynamicParameterSystem


class TestVolatilityAdjustmentProperties:
    """Property-based tests for volatility adjustments."""
    
    def setup_method(self):
        """Create a DynamicParameterSystem instance for testing."""
        self.system = DynamicParameterSystem(
            min_fractional_kelly=0.25,
            max_fractional_kelly=0.50,
            transaction_cost_pct=Decimal('0.02'),
            min_edge_threshold=Decimal('0.025')
        )
        
        # Set base parameters
        self.system.take_profit_pct = Decimal('0.02')  # 2%
        self.system.stop_loss_pct = Decimal('0.02')  # 2%
    
    @given(
        volatility=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('0.50'),
            places=4
        )
    )
    @settings(max_examples=100)
    def test_property_high_volatility_adjustments(self, volatility):
        """
        Property: High volatility (>5%) always widens stop-loss and tightens take-profit.
        
        Validates Requirement 4.5:
        - High volatility (>5%): widen stop-loss (1.5-2.5×), tighten take-profit (0.5-0.8×)
        """
        result = self.system.adjust_for_volatility(volatility)
        
        if volatility > Decimal('0.05'):
            # High volatility regime
            assert result['volatility_regime'] == 'HIGH', \
                f"Volatility {volatility*100:.2f}% should be HIGH regime"
            
            # Stop-loss should be widened (multiplier > 1.0)
            assert result['sl_multiplier'] >= Decimal('1.5'), \
                f"High volatility should widen stop-loss (got {result['sl_multiplier']}×)"
            assert result['sl_multiplier'] <= Decimal('2.5'), \
                f"Stop-loss multiplier should be capped at 2.5× (got {result['sl_multiplier']}×)"
            
            # Take-profit should be tightened (multiplier < 1.0)
            assert result['tp_multiplier'] >= Decimal('0.5'), \
                f"Take-profit multiplier should be floored at 0.5× (got {result['tp_multiplier']}×)"
            assert result['tp_multiplier'] <= Decimal('0.8'), \
                f"High volatility should tighten take-profit (got {result['tp_multiplier']}×)"
            
            # Verify actual adjustments
            assert result['stop_loss_pct'] > self.system.stop_loss_pct, \
                "High volatility should increase stop-loss percentage"
            assert result['take_profit_pct'] < self.system.take_profit_pct, \
                "High volatility should decrease take-profit percentage"
    
    @given(
        volatility=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('0.01'),
            places=4
        )
    )
    @settings(max_examples=100)
    def test_property_low_volatility_adjustments(self, volatility):
        """
        Property: Low volatility (<1%) always tightens stop-loss and widens take-profit.
        
        Validates Requirement 4.6:
        - Low volatility (<1%): tighten stop-loss (0.7-0.9×), widen take-profit (1.2-1.8×)
        """
        result = self.system.adjust_for_volatility(volatility)
        
        if volatility < Decimal('0.01'):
            # Low volatility regime
            assert result['volatility_regime'] == 'LOW', \
                f"Volatility {volatility*100:.2f}% should be LOW regime"
            
            # Stop-loss should be tightened (multiplier < 1.0)
            assert result['sl_multiplier'] >= Decimal('0.7'), \
                f"Stop-loss multiplier should be floored at 0.7× (got {result['sl_multiplier']}×)"
            assert result['sl_multiplier'] <= Decimal('0.9'), \
                f"Low volatility should tighten stop-loss (got {result['sl_multiplier']}×)"
            
            # Take-profit should be widened (multiplier > 1.0)
            assert result['tp_multiplier'] >= Decimal('1.2'), \
                f"Low volatility should widen take-profit (got {result['tp_multiplier']}×)"
            assert result['tp_multiplier'] <= Decimal('1.8'), \
                f"Take-profit multiplier should be capped at 1.8× (got {result['tp_multiplier']}×)"
            
            # Verify actual adjustments
            assert result['stop_loss_pct'] < self.system.stop_loss_pct, \
                "Low volatility should decrease stop-loss percentage"
            assert result['take_profit_pct'] > self.system.take_profit_pct, \
                "Low volatility should increase take-profit percentage"
    
    @given(
        volatility=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('0.05'),
            places=4
        )
    )
    @settings(max_examples=100)
    def test_property_normal_volatility_adjustments(self, volatility):
        """
        Property: Normal volatility (1-5%) uses base parameters with 1.0× multipliers.
        
        Validates Requirement 4.6:
        - Normal volatility: use base parameters
        """
        result = self.system.adjust_for_volatility(volatility)
        
        # Normal volatility regime
        assert result['volatility_regime'] == 'NORMAL', \
            f"Volatility {volatility*100:.2f}% should be NORMAL regime"
        
        # Should use 1.0× multipliers
        assert result['sl_multiplier'] == Decimal('1.0'), \
            f"Normal volatility should use 1.0× stop-loss multiplier (got {result['sl_multiplier']}×)"
        assert result['tp_multiplier'] == Decimal('1.0'), \
            f"Normal volatility should use 1.0× take-profit multiplier (got {result['tp_multiplier']}×)"
        
        # Parameters should match base values
        assert result['stop_loss_pct'] == self.system.stop_loss_pct, \
            "Normal volatility should keep stop-loss unchanged"
        assert result['take_profit_pct'] == self.system.take_profit_pct, \
            "Normal volatility should keep take-profit unchanged"
    
    @given(
        volatility=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('1.0'),
            places=4
        )
    )
    @settings(max_examples=200)
    def test_property_parameters_always_positive(self, volatility):
        """
        Property: Adjusted parameters are always positive regardless of volatility.
        """
        result = self.system.adjust_for_volatility(volatility)
        
        assert result['take_profit_pct'] > Decimal('0'), \
            f"Take-profit must be positive (got {result['take_profit_pct']})"
        assert result['stop_loss_pct'] > Decimal('0'), \
            f"Stop-loss must be positive (got {result['stop_loss_pct']})"
    
    @given(
        volatility=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('1.0'),
            places=4
        )
    )
    @settings(max_examples=200)
    def test_property_parameters_within_reasonable_ranges(self, volatility):
        """
        Property: Adjusted parameters are always within reasonable ranges.
        
        - Take-profit: 0.5% to 15%
        - Stop-loss: 0.5% to 10%
        """
        result = self.system.adjust_for_volatility(volatility)
        
        # Take-profit range
        assert Decimal('0.005') <= result['take_profit_pct'] <= Decimal('0.15'), \
            f"Take-profit {result['take_profit_pct']*100:.2f}% outside range [0.5%, 15%]"
        
        # Stop-loss range
        assert Decimal('0.005') <= result['stop_loss_pct'] <= Decimal('0.10'), \
            f"Stop-loss {result['stop_loss_pct']*100:.2f}% outside range [0.5%, 10%]"
    
    @given(
        volatility=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('1.0'),
            places=4
        ),
        base_tp=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('0.10'),
            places=4
        ),
        base_sl=st.decimals(
            min_value=Decimal('0.01'),
            max_value=Decimal('0.10'),
            places=4
        )
    )
    @settings(max_examples=200)
    def test_property_custom_base_parameters_respected(self, volatility, base_tp, base_sl):
        """
        Property: Custom base parameters are used correctly in calculations.
        """
        result = self.system.adjust_for_volatility(
            volatility,
            base_take_profit=base_tp,
            base_stop_loss=base_sl
        )
        
        # Verify multipliers are applied to custom base values
        expected_tp = base_tp * result['tp_multiplier']
        expected_sl = base_sl * result['sl_multiplier']
        
        # Allow small tolerance for clamping
        if Decimal('0.005') <= expected_tp <= Decimal('0.15'):
            assert abs(result['take_profit_pct'] - expected_tp) < Decimal('0.001'), \
                f"Take-profit calculation incorrect: expected {expected_tp}, got {result['take_profit_pct']}"
        
        if Decimal('0.005') <= expected_sl <= Decimal('0.10'):
            assert abs(result['stop_loss_pct'] - expected_sl) < Decimal('0.001'), \
                f"Stop-loss calculation incorrect: expected {expected_sl}, got {result['stop_loss_pct']}"
    
    @given(
        volatility=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('1.0'),
            places=4
        )
    )
    @settings(max_examples=200)
    def test_property_result_completeness(self, volatility):
        """
        Property: Result always contains all required fields.
        """
        result = self.system.adjust_for_volatility(volatility)
        
        required_fields = [
            'take_profit_pct',
            'stop_loss_pct',
            'volatility',
            'volatility_regime',
            'tp_multiplier',
            'sl_multiplier'
        ]
        
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
            assert result[field] is not None, f"Field {field} is None"
    
    @given(
        volatility=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('1.0'),
            places=4
        )
    )
    @settings(max_examples=200)
    def test_property_volatility_regime_consistency(self, volatility):
        """
        Property: Volatility regime is always consistent with volatility value.
        """
        result = self.system.adjust_for_volatility(volatility)
        
        if volatility > Decimal('0.05'):
            assert result['volatility_regime'] == 'HIGH', \
                f"Volatility {volatility*100:.2f}% should be HIGH regime"
        elif volatility < Decimal('0.01'):
            assert result['volatility_regime'] == 'LOW', \
                f"Volatility {volatility*100:.2f}% should be LOW regime"
        else:
            assert result['volatility_regime'] == 'NORMAL', \
                f"Volatility {volatility*100:.2f}% should be NORMAL regime"
    
    @given(
        volatility1=st.decimals(
            min_value=Decimal('0.06'),
            max_value=Decimal('1.0'),
            places=4
        ),
        volatility2=st.decimals(
            min_value=Decimal('0.06'),
            max_value=Decimal('1.0'),
            places=4
        )
    )
    @settings(max_examples=100)
    def test_property_higher_volatility_wider_stop_loss(self, volatility1, volatility2):
        """
        Property: Higher volatility always results in wider stop-loss in HIGH regime.
        """
        if volatility1 == volatility2:
            return  # Skip equal values
        
        result1 = self.system.adjust_for_volatility(volatility1)
        result2 = self.system.adjust_for_volatility(volatility2)
        
        # Both should be in HIGH regime
        assert result1['volatility_regime'] == 'HIGH'
        assert result2['volatility_regime'] == 'HIGH'
        
        # Higher volatility should have wider stop-loss
        if volatility1 > volatility2:
            assert result1['stop_loss_pct'] >= result2['stop_loss_pct'], \
                f"Higher volatility ({volatility1*100:.2f}%) should have wider stop-loss than lower ({volatility2*100:.2f}%)"
        else:
            assert result2['stop_loss_pct'] >= result1['stop_loss_pct'], \
                f"Higher volatility ({volatility2*100:.2f}%) should have wider stop-loss than lower ({volatility1*100:.2f}%)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
