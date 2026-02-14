"""
Unit tests for volatility-based parameter adjustments.

Tests the adjust_for_volatility() method in DynamicParameterSystem.
Validates Requirements 4.5, 4.6.
"""

import pytest
from decimal import Decimal
from src.dynamic_parameter_system import DynamicParameterSystem


class TestVolatilityAdjustments:
    """Test volatility-based take-profit and stop-loss adjustments."""
    
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
    
    def test_high_volatility_widens_stop_loss(self):
        """High volatility (>5%) should widen stop-loss (1.5-2.5×)."""
        # Test with 6% volatility
        result = self.system.adjust_for_volatility(Decimal('0.06'))
        
        assert result['volatility_regime'] == 'HIGH'
        assert result['stop_loss_pct'] > self.system.stop_loss_pct
        
        # Stop-loss should be widened by 1.5× to 2.5×
        sl_multiplier = result['sl_multiplier']
        assert Decimal('1.5') <= sl_multiplier <= Decimal('2.5')
        
        # Verify actual stop-loss is widened
        expected_sl = self.system.stop_loss_pct * sl_multiplier
        assert abs(result['stop_loss_pct'] - expected_sl) < Decimal('0.001')
    
    def test_high_volatility_tightens_take_profit(self):
        """High volatility (>5%) should tighten take-profit (0.5-0.8×)."""
        # Test with 7% volatility
        result = self.system.adjust_for_volatility(Decimal('0.07'))
        
        assert result['volatility_regime'] == 'HIGH'
        assert result['take_profit_pct'] < self.system.take_profit_pct
        
        # Take-profit should be tightened by 0.5× to 0.8×
        tp_multiplier = result['tp_multiplier']
        assert Decimal('0.5') <= tp_multiplier <= Decimal('0.8')
        
        # Verify actual take-profit is tightened
        expected_tp = self.system.take_profit_pct * tp_multiplier
        assert abs(result['take_profit_pct'] - expected_tp) < Decimal('0.001')
    
    def test_low_volatility_tightens_stop_loss(self):
        """Low volatility (<1%) should tighten stop-loss (0.7-0.9×)."""
        # Test with 0.5% volatility
        result = self.system.adjust_for_volatility(Decimal('0.005'))
        
        assert result['volatility_regime'] == 'LOW'
        assert result['stop_loss_pct'] < self.system.stop_loss_pct
        
        # Stop-loss should be tightened by 0.7× to 0.9×
        sl_multiplier = result['sl_multiplier']
        assert Decimal('0.7') <= sl_multiplier <= Decimal('0.9')
        
        # Verify actual stop-loss is tightened
        expected_sl = self.system.stop_loss_pct * sl_multiplier
        assert abs(result['stop_loss_pct'] - expected_sl) < Decimal('0.001')
    
    def test_low_volatility_widens_take_profit(self):
        """Low volatility (<1%) should widen take-profit (1.2-1.8×)."""
        # Test with 0.8% volatility
        result = self.system.adjust_for_volatility(Decimal('0.008'))
        
        assert result['volatility_regime'] == 'LOW'
        assert result['take_profit_pct'] > self.system.take_profit_pct
        
        # Take-profit should be widened by 1.2× to 1.8×
        tp_multiplier = result['tp_multiplier']
        assert Decimal('1.2') <= tp_multiplier <= Decimal('1.8')
        
        # Verify actual take-profit is widened
        expected_tp = self.system.take_profit_pct * tp_multiplier
        assert abs(result['take_profit_pct'] - expected_tp) < Decimal('0.001')
    
    def test_normal_volatility_uses_base_parameters(self):
        """Normal volatility (1-5%) should use base parameters."""
        # Test with 3% volatility
        result = self.system.adjust_for_volatility(Decimal('0.03'))
        
        assert result['volatility_regime'] == 'NORMAL'
        
        # Should use 1.0× multipliers (no change)
        assert result['tp_multiplier'] == Decimal('1.0')
        assert result['sl_multiplier'] == Decimal('1.0')
        
        # Parameters should match base values
        assert result['take_profit_pct'] == self.system.take_profit_pct
        assert result['stop_loss_pct'] == self.system.stop_loss_pct
    
    def test_extreme_high_volatility_caps_at_max(self):
        """Extreme high volatility should cap stop-loss at 2.5× and take-profit at 0.5×."""
        # Test with 20% volatility (extreme)
        result = self.system.adjust_for_volatility(Decimal('0.20'))
        
        assert result['volatility_regime'] == 'HIGH'
        
        # Stop-loss multiplier should be capped at 2.5×
        assert result['sl_multiplier'] <= Decimal('2.5')
        
        # Take-profit multiplier should be floored at 0.5×
        assert result['tp_multiplier'] >= Decimal('0.5')
    
    def test_extreme_low_volatility_uses_min_multipliers(self):
        """Extreme low volatility should use minimum multipliers."""
        # Test with 0.1% volatility (very low)
        result = self.system.adjust_for_volatility(Decimal('0.001'))
        
        assert result['volatility_regime'] == 'LOW'
        
        # Stop-loss should be at minimum (0.7×)
        assert result['sl_multiplier'] >= Decimal('0.7')
        
        # Take-profit should be at maximum (1.8×)
        assert result['tp_multiplier'] <= Decimal('1.8')
    
    def test_custom_base_parameters(self):
        """Should accept custom base parameters."""
        custom_tp = Decimal('0.03')  # 3%
        custom_sl = Decimal('0.015')  # 1.5%
        
        result = self.system.adjust_for_volatility(
            Decimal('0.06'),  # High volatility
            base_take_profit=custom_tp,
            base_stop_loss=custom_sl
        )
        
        # Should use custom base values for calculations
        assert result['take_profit_pct'] < custom_tp  # Tightened
        assert result['stop_loss_pct'] > custom_sl  # Widened
    
    def test_parameters_clamped_to_reasonable_ranges(self):
        """Adjusted parameters should be clamped to reasonable ranges."""
        # Test with extreme volatility
        result = self.system.adjust_for_volatility(Decimal('0.50'))
        
        # Take-profit should be >= 0.5% and <= 15%
        assert Decimal('0.005') <= result['take_profit_pct'] <= Decimal('0.15')
        
        # Stop-loss should be >= 0.5% and <= 10%
        assert Decimal('0.005') <= result['stop_loss_pct'] <= Decimal('0.10')
    
    def test_volatility_regime_boundaries(self):
        """Test volatility regime boundaries are correct."""
        # Test at 1% boundary (should be LOW)
        result_low = self.system.adjust_for_volatility(Decimal('0.0099'))
        assert result_low['volatility_regime'] == 'LOW'
        
        # Test at 1% boundary (should be NORMAL)
        result_normal_low = self.system.adjust_for_volatility(Decimal('0.01'))
        assert result_normal_low['volatility_regime'] == 'NORMAL'
        
        # Test at 5% boundary (should be NORMAL)
        result_normal_high = self.system.adjust_for_volatility(Decimal('0.05'))
        assert result_normal_high['volatility_regime'] == 'NORMAL'
        
        # Test at 5% boundary (should be HIGH)
        result_high = self.system.adjust_for_volatility(Decimal('0.0501'))
        assert result_high['volatility_regime'] == 'HIGH'
    
    def test_result_includes_all_fields(self):
        """Result should include all expected fields."""
        result = self.system.adjust_for_volatility(Decimal('0.03'))
        
        expected_fields = [
            'take_profit_pct',
            'stop_loss_pct',
            'volatility',
            'volatility_regime',
            'tp_multiplier',
            'sl_multiplier'
        ]
        
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
    
    def test_zero_volatility_handled(self):
        """Zero volatility should be handled gracefully."""
        result = self.system.adjust_for_volatility(Decimal('0'))
        
        # Should be treated as LOW volatility
        assert result['volatility_regime'] == 'LOW'
        assert result['volatility'] == Decimal('0')
        
        # Should still produce valid parameters
        assert result['take_profit_pct'] > Decimal('0')
        assert result['stop_loss_pct'] > Decimal('0')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
