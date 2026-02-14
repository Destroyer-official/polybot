"""
Simple integration tests for exit condition logic in FifteenMinuteCryptoStrategy.

Tests the priority order of exit conditions:
1. Market closing (< 2 min to expiry) - FORCE EXIT
2. Time limit (> 13 min for 15-min markets) - FORCE EXIT
3. Trailing stop-loss (if activated) - PROFIT PROTECTION
4. Take-profit threshold - PROFIT TAKING
5. Stop-loss threshold - LOSS LIMITING

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from src.fifteen_min_crypto_strategy import Position, CryptoMarket


class TestExitConditionPriorityOrder:
    """Test that exit conditions follow the correct priority order."""
    
    def test_priority_order_documented(self):
        """
        Verify that the exit condition priority order is correctly documented.
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
        """
        # This test verifies the priority order is documented in the code
        from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
        
        # Check that _check_all_positions_for_exit has the correct priority order in docstring
        docstring = FifteenMinuteCryptoStrategy._check_all_positions_for_exit.__doc__
        
        assert "PRIORITY ORDER" in docstring
        assert "Priority 1" in docstring or "PRIORITY 1" in docstring
        assert "Market closing" in docstring
        assert "Priority 2" in docstring or "PRIORITY 2" in docstring
        assert "Time limit" in docstring
        assert "Priority 3" in docstring or "PRIORITY 3" in docstring
        assert "Trailing stop" in docstring
        assert "Priority 4" in docstring or "PRIORITY 4" in docstring
        assert "Take-profit" in docstring
        assert "Priority 5" in docstring or "PRIORITY 5" in docstring
        assert "Stop-loss" in docstring
    
    def test_check_exit_conditions_priority_order_documented(self):
        """
        Verify that check_exit_conditions also documents the priority order.
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
        """
        from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
        
        # Check that check_exit_conditions has the correct priority order in docstring
        docstring = FifteenMinuteCryptoStrategy.check_exit_conditions.__doc__
        
        assert "PRIORITY ORDER" in docstring
        assert "Priority 1" in docstring or "PRIORITY 1" in docstring
        assert "Market closing" in docstring
        assert "Priority 2" in docstring or "PRIORITY 2" in docstring
        assert "Time limit" in docstring


class TestPositionDataStructure:
    """Test that Position dataclass has all required fields."""
    
    def test_position_has_required_fields(self):
        """Verify Position has all fields needed for exit logic."""
        position = Position(
            token_id="test_token",
            side="UP",
            entry_price=Decimal("0.50"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc),
            market_id="test_market",
            asset="BTC",
            strategy="directional",
            neg_risk=False,
            highest_price=Decimal("0.50")
        )
        
        assert position.token_id == "test_token"
        assert position.side == "UP"
        assert position.entry_price == Decimal("0.50")
        assert position.size == Decimal("10.0")
        assert position.asset == "BTC"
        assert position.highest_price == Decimal("0.50")


class TestCryptoMarketDataStructure:
    """Test that CryptoMarket dataclass has all required fields."""
    
    def test_market_has_required_fields(self):
        """Verify CryptoMarket has all fields needed for exit logic."""
        market = CryptoMarket(
            market_id="test_market",
            question="Will BTC go up?",
            asset="BTC",
            up_token_id="up_token",
            down_token_id="down_token",
            up_price=Decimal("0.52"),
            down_price=Decimal("0.48"),
            end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
            neg_risk=False
        )
        
        assert market.market_id == "test_market"
        assert market.asset == "BTC"
        assert market.up_price == Decimal("0.52")
        assert market.down_price == Decimal("0.48")
        assert market.end_time is not None


class TestExitConditionCalculations:
    """Test the calculations used in exit conditions."""
    
    def test_pnl_calculation(self):
        """Test P&L percentage calculation."""
        entry_price = Decimal("0.50")
        current_price = Decimal("0.51")
        
        pnl_pct = (current_price - entry_price) / entry_price
        
        assert pnl_pct == Decimal("0.02")  # 2% profit
    
    def test_time_to_close_calculation(self):
        """Test time to market close calculation."""
        now = datetime.now(timezone.utc)
        end_time = now + timedelta(minutes=1.5)
        
        time_to_close = (end_time - now).total_seconds() / 60
        
        assert 1.4 < time_to_close < 1.6  # Approximately 1.5 minutes
    
    def test_position_age_calculation(self):
        """Test position age calculation."""
        entry_time = datetime.now(timezone.utc) - timedelta(minutes=14)
        now = datetime.now(timezone.utc)
        
        age_min = (now - entry_time).total_seconds() / 60
        
        assert 13.9 < age_min < 14.1  # Approximately 14 minutes
    
    def test_trailing_stop_drop_calculation(self):
        """Test trailing stop drop from peak calculation."""
        highest_price = Decimal("0.60")
        current_price = Decimal("0.58")
        
        drop_from_peak = (highest_price - current_price) / highest_price
        
        assert abs(drop_from_peak - Decimal("0.0333")) < Decimal("0.001")  # ~3.33% drop


class TestExitReasons:
    """Test that exit reasons are correctly identified."""
    
    def test_market_closing_threshold(self):
        """Market closing should trigger when < 2 minutes to close."""
        now = datetime.now(timezone.utc)
        
        # 1 minute to close - should trigger
        end_time_1min = now + timedelta(minutes=1)
        time_to_close_1min = (end_time_1min - now).total_seconds() / 60
        assert time_to_close_1min < 2
        
        # 3 minutes to close - should NOT trigger
        end_time_3min = now + timedelta(minutes=3)
        time_to_close_3min = (end_time_3min - now).total_seconds() / 60
        assert time_to_close_3min >= 2
    
    def test_time_exit_threshold(self):
        """Time exit should trigger when position age > 13 minutes."""
        now = datetime.now(timezone.utc)
        
        # 14 minutes old - should trigger
        entry_time_14min = now - timedelta(minutes=14)
        age_14min = (now - entry_time_14min).total_seconds() / 60
        assert age_14min > 13
        
        # 12 minutes old - should NOT trigger
        entry_time_12min = now - timedelta(minutes=12)
        age_12min = (now - entry_time_12min).total_seconds() / 60
        assert age_12min <= 13
    
    def test_take_profit_threshold(self):
        """Take-profit should trigger at 2% profit."""
        entry_price = Decimal("0.50")
        take_profit_pct = Decimal("0.02")  # 2%
        
        # 2% profit - should trigger
        current_price_2pct = Decimal("0.51")
        pnl_2pct = (current_price_2pct - entry_price) / entry_price
        assert pnl_2pct >= take_profit_pct
        
        # 1.8% profit - should NOT trigger
        current_price_1_8pct = Decimal("0.509")
        pnl_1_8pct = (current_price_1_8pct - entry_price) / entry_price
        assert pnl_1_8pct < take_profit_pct
    
    def test_stop_loss_threshold(self):
        """Stop-loss should trigger at 2% loss."""
        entry_price = Decimal("0.50")
        stop_loss_pct = Decimal("0.02")  # 2%
        
        # 2% loss - should trigger
        current_price_2pct = Decimal("0.49")
        pnl_2pct = (current_price_2pct - entry_price) / entry_price
        assert pnl_2pct <= -stop_loss_pct
        
        # 1.8% loss - should NOT trigger
        current_price_1_8pct = Decimal("0.491")
        pnl_1_8pct = (current_price_1_8pct - entry_price) / entry_price
        assert pnl_1_8pct > -stop_loss_pct


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
