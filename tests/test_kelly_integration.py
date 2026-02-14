"""
Integration tests for Kelly Criterion position sizing in FifteenMinuteCryptoStrategy.

Tests that Kelly-based position sizing is properly integrated into the trading strategy
and that position sizes are calculated correctly based on ensemble confidence and expected profit.

Validates Requirements 4.3, 4.12
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
from src.dynamic_parameter_system import DynamicParameterSystem


class TestKellyIntegration:
    """Test suite for Kelly Criterion integration."""
    
    @pytest.fixture
    def mock_clob_client(self):
        """Create a mock CLOB client."""
        client = Mock()
        client.create_order = Mock()
        client.post_order = Mock(return_value={"success": True, "orderID": "test123"})
        return client
    
    @pytest.fixture
    def strategy(self, mock_clob_client):
        """Create a strategy instance with Kelly system enabled."""
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_clob_client,
            trade_size=10.0,
            dry_run=True,
            initial_capital=100.0
        )
        return strategy
    
    def test_kelly_system_initialized(self, strategy):
        """Test that Kelly system is properly initialized."""
        assert strategy.kelly_system is not None
        assert isinstance(strategy.kelly_system, DynamicParameterSystem)
        assert strategy.kelly_system.min_fractional_kelly == 0.25
        assert strategy.kelly_system.max_fractional_kelly == 0.50
        assert strategy.kelly_system.transaction_cost_pct == Decimal('0.0315')
        assert strategy.kelly_system.min_edge_threshold == Decimal('0.02')
    
    def test_calculate_position_size_with_kelly_high_confidence(self, strategy):
        """Test position sizing with high confidence uses 50% Kelly."""
        # High confidence (>70%) should use max fractional Kelly (50%)
        # Need higher expected profit to overcome 3.15% transaction costs + 2% min edge
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('80.0'),
            expected_profit_pct=Decimal('0.10')  # 10% expected profit
        )
        
        # Should return a valid position size
        assert position_size > Decimal('0')
        assert position_size <= Decimal('10.0')  # Max 10% of $100 balance
        
        # Verify fractional Kelly was set to max
        assert strategy.kelly_system.current_fractional_kelly == 0.50
    
    def test_calculate_position_size_with_kelly_normal_confidence(self, strategy):
        """Test position sizing with normal confidence uses 37.5% Kelly."""
        # Normal confidence (40-70%) should use midpoint fractional Kelly (37.5%)
        # Need higher expected profit to overcome 3.15% transaction costs + 2% min edge
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('55.0'),
            expected_profit_pct=Decimal('0.10')  # 10% expected profit
        )
        
        # Should return a valid position size
        assert position_size > Decimal('0')
        assert position_size <= Decimal('10.0')  # Max 10% of $100 balance
        
        # Verify fractional Kelly was set to midpoint
        assert strategy.kelly_system.current_fractional_kelly == 0.375
    
    def test_calculate_position_size_with_kelly_low_confidence(self, strategy):
        """Test position sizing with low confidence uses 25% Kelly."""
        # Low confidence (<40%) should use min fractional Kelly (25%)
        # Need much higher expected profit to overcome 3.15% transaction costs + 2% min edge
        # With 30% confidence: 0.30 * 0.20 = 0.06 (6%) - 3.15% = 2.85% edge (above 2% threshold)
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('30.0'),
            expected_profit_pct=Decimal('0.20')  # 20% expected profit (higher for low confidence)
        )
        
        # Should return a valid position size
        assert position_size > Decimal('0')
        assert position_size <= Decimal('10.0')  # Max 10% of $100 balance
        
        # Verify fractional Kelly was set to min
        assert strategy.kelly_system.current_fractional_kelly == 0.25
    
    def test_calculate_position_size_edge_too_low(self, strategy):
        """Test position sizing returns zero when edge is too low."""
        # Very low expected profit should result in edge below threshold
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('50.0'),
            expected_profit_pct=Decimal('0.01')  # 1% profit - too low after 3.15% costs
        )
        
        # Should return zero (trade skipped)
        assert position_size == Decimal('0')
    
    def test_calculate_position_size_fallback_to_progressive(self, strategy):
        """Test position sizing falls back to progressive sizing when Kelly inputs unavailable."""
        # No confidence or profit provided - should use progressive sizing
        position_size = strategy._calculate_position_size()
        
        # Should return base trade size (no wins/losses yet)
        assert position_size > Decimal('0')
        # Should be close to base trade size ($10) but may be adjusted by risk manager
        assert position_size <= Decimal('10.0')
    
    def test_calculate_position_size_respects_risk_manager(self, strategy):
        """Test position sizing respects risk manager limits."""
        # Set up risk manager to have very low available capital
        strategy.risk_manager.current_capital = Decimal('2.0')
        
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('80.0'),
            expected_profit_pct=Decimal('0.10')  # 10% profit
        )
        
        # Position size should be limited by risk manager
        # With $2 balance and SMART mode, should allow up to 80% = $1.60
        # But Kelly might calculate less
        assert position_size <= Decimal('2.0')
    
    def test_calculate_position_size_clamped_to_minimum(self, strategy):
        """Test position sizing is clamped to $1.00 minimum."""
        # Very small balance should still meet minimum
        strategy.risk_manager.current_capital = Decimal('5.0')
        
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('50.0'),
            expected_profit_pct=Decimal('0.05')
        )
        
        # Should be at least $1.00 (Polymarket minimum)
        if position_size > Decimal('0'):
            assert position_size >= Decimal('1.0')
    
    def test_calculate_position_size_clamped_to_maximum(self, strategy):
        """Test position sizing is clamped to 10% of balance."""
        # Large expected profit should be capped
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('95.0'),
            expected_profit_pct=Decimal('0.50')  # 50% profit (unrealistic but tests cap)
        )
        
        # Should be capped at 10% of $100 balance = $10
        assert position_size <= Decimal('10.0')
    
    def test_record_trade_outcome_updates_kelly_system(self, strategy):
        """Test that trade outcomes are recorded to Kelly system."""
        # Record a winning trade
        strategy._record_trade_outcome(
            asset="BTC",
            side="UP",
            strategy="latency",
            entry_price=Decimal('0.50'),
            exit_price=Decimal('0.52'),
            profit_pct=Decimal('0.04'),  # 4% profit
            hold_time_minutes=5.0,
            exit_reason="take_profit",
            position_size=Decimal('10.0')
        )
        
        # Verify Kelly system was updated
        assert len(strategy.kelly_system.trade_history) == 1
        trade = strategy.kelly_system.trade_history[0]
        assert trade.position_size == Decimal('10.0')
        assert trade.profit == Decimal('0.40')  # 10.0 * 0.04
        assert trade.was_successful == True
    
    def test_record_trade_outcome_losing_trade(self, strategy):
        """Test that losing trades are recorded correctly."""
        # Record a losing trade
        strategy._record_trade_outcome(
            asset="ETH",
            side="DOWN",
            strategy="directional",
            entry_price=Decimal('0.60'),
            exit_price=Decimal('0.58'),
            profit_pct=Decimal('-0.0333'),  # -3.33% loss
            hold_time_minutes=8.0,
            exit_reason="stop_loss",
            position_size=Decimal('5.0')
        )
        
        # Verify Kelly system was updated
        assert len(strategy.kelly_system.trade_history) == 1
        trade = strategy.kelly_system.trade_history[0]
        assert trade.position_size == Decimal('5.0')
        assert trade.profit < Decimal('0')  # Negative profit
        assert trade.was_successful == False
    
    def test_kelly_system_adjusts_after_multiple_trades(self, strategy):
        """Test that Kelly system adjusts fractional Kelly based on performance."""
        # Record 20 winning trades (high win rate)
        for i in range(20):
            strategy._record_trade_outcome(
                asset="BTC",
                side="UP",
                strategy="latency",
                entry_price=Decimal('0.50'),
                exit_price=Decimal('0.52'),
                profit_pct=Decimal('0.04'),
                hold_time_minutes=5.0,
                exit_reason="take_profit",
                position_size=Decimal('10.0')
            )
        
        # Fractional Kelly should increase to max (50%)
        assert strategy.kelly_system.current_fractional_kelly == 0.50
        
        # Performance metrics should reflect high win rate
        metrics = strategy.kelly_system.get_performance_metrics()
        assert metrics.win_rate == 1.0
        assert metrics.total_trades == 20
    
    def test_kelly_system_decreases_after_losses(self, strategy):
        """Test that Kelly system decreases fractional Kelly after losses."""
        # Record 20 trades: 15 losses, 5 wins (25% win rate)
        for i in range(15):
            strategy._record_trade_outcome(
                asset="BTC",
                side="UP",
                strategy="latency",
                entry_price=Decimal('0.50'),
                exit_price=Decimal('0.48'),
                profit_pct=Decimal('-0.04'),
                hold_time_minutes=5.0,
                exit_reason="stop_loss",
                position_size=Decimal('10.0')
            )
        
        for i in range(5):
            strategy._record_trade_outcome(
                asset="BTC",
                side="UP",
                strategy="latency",
                entry_price=Decimal('0.50'),
                exit_price=Decimal('0.52'),
                profit_pct=Decimal('0.04'),
                hold_time_minutes=5.0,
                exit_reason="take_profit",
                position_size=Decimal('10.0')
            )
        
        # Fractional Kelly should decrease to min (25%)
        assert strategy.kelly_system.current_fractional_kelly == 0.25
        
        # Performance metrics should reflect low win rate
        metrics = strategy.kelly_system.get_performance_metrics()
        assert metrics.win_rate < 0.30


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
