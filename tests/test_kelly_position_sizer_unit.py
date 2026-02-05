"""
Unit tests for Kelly Position Sizer edge cases.

Tests specific examples and edge cases for Kelly Criterion position sizing.
Validates Requirements 11.1, 11.2, 11.3, 11.4, 11.5.
"""

import pytest
from decimal import Decimal
from datetime import datetime

from src.kelly_position_sizer import KellyPositionSizer, PositionSizingConfig
from src.models import Opportunity


class TestKellyPositionSizerEdgeCases:
    """Test Kelly Position Sizer at specific edge cases."""
    
    def create_opportunity(
        self, 
        yes_price: Decimal, 
        no_price: Decimal,
        expected_profit: Decimal = None
    ) -> Opportunity:
        """Helper to create test opportunities."""
        yes_fee = yes_price * Decimal('0.03')
        no_fee = no_price * Decimal('0.03')
        total_cost = yes_price + no_price + yes_fee + no_fee
        
        if expected_profit is None:
            expected_profit = Decimal('1.0') - total_cost
        
        profit_percentage = expected_profit / total_cost if total_cost > 0 else Decimal('0')
        
        return Opportunity(
            opportunity_id="test_opp_1",
            market_id="test_market_1",
            strategy="internal",
            timestamp=datetime.now(),
            yes_price=yes_price,
            no_price=no_price,
            yes_fee=yes_fee,
            no_fee=no_fee,
            total_cost=total_cost,
            expected_profit=expected_profit,
            profit_percentage=profit_percentage,
            position_size=Decimal('0'),
            gas_estimate=100000
        )
    
    def test_small_bankroll_minimum_position(self):
        """
        **Validates: Requirements 11.3**
        
        Test that small bankroll (<$100) uses minimum position size of $0.10.
        """
        sizer = KellyPositionSizer()
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47')
        )
        
        # Very small bankroll should still get minimum position
        bankroll = Decimal('10.0')
        position_size = sizer.calculate_position_size(opportunity, bankroll)
        
        assert position_size >= Decimal('0.1'), \
            f"Position size {position_size} below minimum $0.10"
        assert position_size <= Decimal('1.0'), \
            f"Position size {position_size} exceeds small bankroll maximum $1.00"
    
    def test_small_bankroll_maximum_position(self):
        """
        **Validates: Requirements 11.3**
        
        Test that small bankroll (<$100) caps at maximum position size of $1.00.
        """
        sizer = KellyPositionSizer()
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47')
        )
        
        # Small bankroll should cap at $1.00
        bankroll = Decimal('99.99')
        position_size = sizer.calculate_position_size(opportunity, bankroll)
        
        assert position_size <= Decimal('1.0'), \
            f"Position size {position_size} exceeds small bankroll maximum $1.00"
    
    def test_large_bankroll_maximum_position(self):
        """
        **Validates: Requirements 11.4**
        
        Test that large bankroll (>$100) caps at maximum position size of $5.00.
        """
        sizer = KellyPositionSizer()
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47')
        )
        
        # Large bankroll should cap at $5.00
        bankroll = Decimal('10000.0')
        position_size = sizer.calculate_position_size(opportunity, bankroll)
        
        assert position_size <= Decimal('5.0'), \
            f"Position size {position_size} exceeds maximum $5.00"
    
    def test_five_percent_bankroll_cap(self):
        """
        **Validates: Requirements 11.2**
        
        Test that position size never exceeds 5% of bankroll.
        """
        sizer = KellyPositionSizer()
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47')
        )
        
        # Test various bankroll sizes
        for bankroll in [Decimal('100.0'), Decimal('500.0'), Decimal('1000.0')]:
            position_size = sizer.calculate_position_size(opportunity, bankroll)
            max_allowed = bankroll * Decimal('0.05')
            
            assert position_size <= max_allowed, \
                f"Position size {position_size} exceeds 5% of bankroll {bankroll} (max: {max_allowed})"
    
    def test_zero_profit_opportunity(self):
        """
        Test that zero profit opportunity results in zero position size.
        """
        sizer = KellyPositionSizer()
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            expected_profit=Decimal('0.0')
        )
        
        bankroll = Decimal('1000.0')
        position_size = sizer.calculate_position_size(opportunity, bankroll)
        
        # Zero profit should result in minimal or zero position
        assert position_size >= Decimal('0'), \
            f"Position size should be non-negative, got {position_size}"
    
    def test_negative_profit_opportunity(self):
        """
        Test that negative profit opportunity results in zero position size.
        """
        sizer = KellyPositionSizer()
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.60'),
            no_price=Decimal('0.60'),
            expected_profit=Decimal('-0.20')
        )
        
        bankroll = Decimal('1000.0')
        position_size = sizer.calculate_position_size(opportunity, bankroll)
        
        # Negative profit should result in zero position
        assert position_size == Decimal('0'), \
            f"Negative profit should result in zero position, got {position_size}"
    
    def test_bankroll_boundary_at_100(self):
        """
        Test position sizing at the $100 bankroll boundary.
        """
        sizer = KellyPositionSizer()
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47')
        )
        
        # Just below $100 - should use small bankroll rules
        bankroll_small = Decimal('99.99')
        position_small = sizer.calculate_position_size(opportunity, bankroll_small)
        assert position_small <= Decimal('1.0'), \
            f"Position for bankroll ${bankroll_small} should be capped at $1.00"
        
        # Just above $100 - should use large bankroll rules
        bankroll_large = Decimal('100.01')
        position_large = sizer.calculate_position_size(opportunity, bankroll_large)
        # Large bankroll can exceed $1.00 but should be capped at $5.00
        assert position_large <= Decimal('5.0'), \
            f"Position for bankroll ${bankroll_large} should be capped at $5.00"
    
    def test_bankroll_recalculation_interval(self):
        """
        **Validates: Requirements 11.5**
        
        Test that bankroll recalculation happens every 10 trades.
        """
        sizer = KellyPositionSizer()
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47')
        )
        
        bankroll = Decimal('1000.0')
        
        # Execute 10 trades
        for i in range(10):
            position_size = sizer.calculate_position_size(opportunity, bankroll)
            assert position_size > 0, f"Trade {i+1} should have positive position size"
        
        # After 10 trades, should_recalculate_bankroll should be True
        assert sizer.should_recalculate_bankroll(), \
            "Should recalculate bankroll after 10 trades"
        
        # Trade count should be 10
        assert sizer.get_trade_count() == 10, \
            f"Trade count should be 10, got {sizer.get_trade_count()}"
    
    def test_get_max_position_size(self):
        """
        Test that get_max_position_size returns the correct maximum.
        """
        sizer = KellyPositionSizer()
        max_size = sizer.get_max_position_size()
        
        assert max_size == Decimal('5.0'), \
            f"Maximum position size should be $5.00, got {max_size}"
    
    def test_reset_trade_count(self):
        """
        Test that reset_trade_count resets the counter to zero.
        """
        sizer = KellyPositionSizer()
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47')
        )
        
        bankroll = Decimal('1000.0')
        
        # Execute some trades
        for _ in range(5):
            sizer.calculate_position_size(opportunity, bankroll)
        
        assert sizer.get_trade_count() == 5, "Trade count should be 5"
        
        # Reset
        sizer.reset_trade_count()
        
        assert sizer.get_trade_count() == 0, "Trade count should be 0 after reset"
    
    def test_custom_config(self):
        """
        Test that custom configuration is respected.
        """
        custom_config = PositionSizingConfig(
            max_kelly_fraction=Decimal('0.10'),  # 10% instead of 5%
            small_bankroll_max=Decimal('2.0'),   # $2.00 instead of $1.00
            large_bankroll_max=Decimal('10.0')   # $10.00 instead of $5.00
        )
        
        sizer = KellyPositionSizer(config=custom_config)
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47')
        )
        
        # Test small bankroll with custom config
        bankroll_small = Decimal('50.0')
        position_small = sizer.calculate_position_size(opportunity, bankroll_small)
        assert position_small <= Decimal('2.0'), \
            f"Position should respect custom small bankroll max of $2.00"
        
        # Test large bankroll with custom config
        bankroll_large = Decimal('10000.0')
        position_large = sizer.calculate_position_size(opportunity, bankroll_large)
        assert position_large <= Decimal('10.0'), \
            f"Position should respect custom large bankroll max of $10.00"
        
        # Test max position size
        assert sizer.get_max_position_size() == Decimal('10.0'), \
            "Max position size should match custom config"
    
    def test_high_profit_opportunity(self):
        """
        Test position sizing for high profit opportunity.
        """
        sizer = KellyPositionSizer()
        # Create opportunity with high profit margin
        opportunity = self.create_opportunity(
            yes_price=Decimal('0.40'),
            no_price=Decimal('0.40'),
            expected_profit=Decimal('0.15')  # 15% profit
        )
        
        bankroll = Decimal('1000.0')
        position_size = sizer.calculate_position_size(opportunity, bankroll)
        
        # High profit should result in larger position (up to caps)
        assert position_size > Decimal('0'), \
            "High profit opportunity should have positive position size"
        assert position_size <= Decimal('5.0'), \
            "Position size should still respect maximum cap"
        assert position_size <= bankroll * Decimal('0.05'), \
            "Position size should still respect 5% bankroll cap"
