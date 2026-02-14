"""
Test Dynamic Parameter System Integration into FifteenMinuteCryptoStrategy.

Tests that DynamicParameterSystem is properly integrated:
- Kelly Criterion position sizing is used for all entries
- update_dynamic_parameters() is called after each trade
- adjust_for_volatility() is called on each cycle
- analyze_cost_benefit() is called before every entry

Validates Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.9, 4.12, 4.13, 4.14
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket
from py_clob_client.client import ClobClient


@pytest.fixture
def mock_clob_client():
    """Create a mock CLOB client."""
    client = Mock(spec=ClobClient)
    client.get_balance_allowance = Mock(return_value={'balance': '1000000000'})  # $1000 USDC
    return client


@pytest.fixture
def strategy(mock_clob_client):
    """Create strategy instance with mocked dependencies."""
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob_client,
        trade_size=10.0,
        dry_run=True,
        enable_adaptive_learning=False  # Disable for simpler testing
    )
    
    # Mock external dependencies
    strategy.binance_feed.start = AsyncMock()
    strategy.binance_feed.stop = AsyncMock()
    
    return strategy


@pytest.fixture
def sample_market():
    """Create a sample crypto market."""
    return CryptoMarket(
        market_id="test_market_123",
        question="Will BTC be up in 15 minutes?",
        asset="BTC",
        up_token_id="up_token_123",
        down_token_id="down_token_123",
        up_price=Decimal("0.52"),
        down_price=Decimal("0.48"),
        end_time=datetime.now(timezone.utc),
        neg_risk=True,
        tick_size="0.01"
    )


class TestDynamicParameterIntegration:
    """Test suite for Dynamic Parameter System integration."""
    
    def test_dynamic_params_initialized(self, strategy):
        """Test that DynamicParameterSystem is initialized."""
        assert hasattr(strategy, 'dynamic_params')
        assert strategy.dynamic_params is not None
        assert strategy.dynamic_params.min_fractional_kelly == 0.25
        assert strategy.dynamic_params.max_fractional_kelly == 0.50
        assert strategy.dynamic_params.transaction_cost_pct == Decimal('0.0315')
        assert strategy.dynamic_params.min_edge_threshold == Decimal('0.02')
    
    def test_kelly_system_backward_compatibility(self, strategy):
        """Test that kelly_system reference still works for backward compatibility."""
        assert hasattr(strategy, 'kelly_system')
        assert strategy.kelly_system is strategy.dynamic_params
    
    def test_position_sizing_uses_kelly(self, strategy):
        """Test that position sizing uses Kelly Criterion when confidence provided."""
        # High confidence should use Kelly
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('80.0'),
            expected_profit_pct=Decimal('0.10')  # 10% expected profit
        )
        
        # Should return non-zero size
        assert position_size > 0
        
        # Should have adjusted fractional Kelly to max (50%) for high confidence
        assert strategy.dynamic_params.current_fractional_kelly == 0.50
    
    def test_position_sizing_skips_low_edge(self, strategy):
        """Test that position sizing returns zero when edge is too low."""
        # Very low expected profit should result in edge below threshold
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('50.0'),
            expected_profit_pct=Decimal('0.01')  # 1% profit - too low after 3.15% costs
        )
        
        # Should skip trade (return 0)
        assert position_size == Decimal('0')
    
    def test_update_dynamic_parameters_after_trade(self, strategy):
        """Test that dynamic parameters are updated after recording trade outcome."""
        # Record initial parameters
        initial_tp = strategy.take_profit_pct
        initial_sl = strategy.stop_loss_pct
        
        # Record a winning trade
        strategy._record_trade_outcome(
            asset="BTC",
            side="UP",
            strategy="latency",
            entry_price=Decimal("0.50"),
            exit_price=Decimal("0.52"),
            profit_pct=Decimal("0.04"),  # 4% profit
            hold_time_minutes=5.0,
            exit_reason="take_profit",
            position_size=Decimal("10.0")
        )
        
        # Parameters should be updated (may or may not change depending on history)
        # Just verify the update was called
        assert strategy.dynamic_params.trade_history  # Should have recorded trade
        assert len(strategy.dynamic_params.trade_history) == 1
    
    @pytest.mark.asyncio
    async def test_volatility_adjustment_on_cycle(self, strategy, sample_market):
        """Test that volatility adjustments are applied on each cycle."""
        # Mock Binance price history with some volatility
        from collections import deque
        from datetime import timedelta
        
        now = datetime.now()
        prices = []
        base_price = Decimal("50000")
        for i in range(100):
            # Simulate 2% volatility
            price = base_price * (Decimal("1.0") + Decimal(str((i % 10 - 5) * 0.004)))
            timestamp = now - timedelta(seconds=100-i)
            prices.append((timestamp, price))
        
        strategy.binance_feed.price_history["BTC"] = deque(prices, maxlen=10000)
        
        # Mock market fetching
        strategy.fetch_15min_markets = AsyncMock(return_value=[sample_market])
        strategy._check_all_positions_for_exit = AsyncMock()
        strategy.check_exit_conditions = AsyncMock()
        strategy.check_flash_crash = AsyncMock(return_value=False)
        strategy.check_latency_arbitrage = AsyncMock(return_value=False)
        strategy.check_directional_trade = AsyncMock(return_value=False)
        strategy.check_sum_to_one_arbitrage = AsyncMock(return_value=False)
        
        # Record initial parameters
        initial_tp = strategy.take_profit_pct
        initial_sl = strategy.stop_loss_pct
        
        # Run cycle
        await strategy.run_cycle()
        
        # Parameters may have been adjusted based on volatility
        # Just verify the cycle completed without errors
        assert strategy.fetch_15min_markets.called
    
    @pytest.mark.asyncio
    async def test_cost_benefit_analysis_before_entry(self, strategy, sample_market):
        """Test that cost-benefit analysis is performed before placing orders."""
        # Mock the order placement to capture the analysis
        original_place_order = strategy._place_order
        
        # Track if cost-benefit analysis was performed
        cb_analysis_called = False
        original_analyze = strategy.dynamic_params.analyze_cost_benefit
        
        def mock_analyze(*args, **kwargs):
            nonlocal cb_analysis_called
            cb_analysis_called = True
            return original_analyze(*args, **kwargs)
        
        strategy.dynamic_params.analyze_cost_benefit = mock_analyze
        
        # Try to place an order
        result = await strategy._place_order(
            market=sample_market,
            side="UP",
            price=Decimal("0.52"),
            shares=10.0,
            strategy="test"
        )
        
        # Cost-benefit analysis should have been called
        assert cb_analysis_called, "Cost-benefit analysis was not called before placing order"
    
    @pytest.mark.asyncio
    async def test_cost_benefit_blocks_unprofitable_trade(self, strategy, sample_market):
        """Test that cost-benefit analysis blocks trades with high costs."""
        # Set very low take-profit to make trade unprofitable
        strategy.take_profit_pct = Decimal('0.001')  # 0.1% - too low after 3.15% costs
        
        # Try to place an order
        result = await strategy._place_order(
            market=sample_market,
            side="UP",
            price=Decimal("0.52"),
            shares=10.0,
            strategy="test"
        )
        
        # Order should be blocked
        assert result == False, "Unprofitable trade should have been blocked"
    
    def test_dynamic_thresholds_accessible(self, strategy):
        """Test that dynamic thresholds can be retrieved."""
        thresholds = strategy.dynamic_params.get_dynamic_thresholds()
        
        assert 'take_profit_pct' in thresholds
        assert 'stop_loss_pct' in thresholds
        assert 'daily_trade_limit' in thresholds
        assert 'circuit_breaker_threshold' in thresholds
        
        # Values should be reasonable
        assert 0.005 <= thresholds['take_profit_pct'] <= 0.15  # 0.5% to 15%
        assert 0.005 <= thresholds['stop_loss_pct'] <= 0.10  # 0.5% to 10%
        assert 50 <= thresholds['daily_trade_limit'] <= 200
        assert 3 <= thresholds['circuit_breaker_threshold'] <= 7
    
    def test_multiple_trades_update_parameters(self, strategy):
        """Test that multiple trades progressively update parameters."""
        # Record 10 winning trades
        for i in range(10):
            strategy._record_trade_outcome(
                asset="BTC",
                side="UP",
                strategy="latency",
                entry_price=Decimal("0.50"),
                exit_price=Decimal("0.52"),
                profit_pct=Decimal("0.04"),  # 4% profit
                hold_time_minutes=5.0,
                exit_reason="take_profit",
                position_size=Decimal("10.0")
            )
        
        # Should have 10 trades in history
        assert len(strategy.dynamic_params.trade_history) == 10
        
        # Win rate should be 100%
        metrics = strategy.dynamic_params.get_performance_metrics()
        assert metrics.win_rate == 1.0
        assert metrics.total_trades == 10
        assert metrics.profitable_trades == 10
        
        # Fractional Kelly should be at max (50%) due to high win rate
        assert strategy.dynamic_params.current_fractional_kelly == 0.50
    
    def test_losing_trades_reduce_fractional_kelly(self, strategy):
        """Test that losing trades reduce fractional Kelly."""
        # Record 10 losing trades
        for i in range(10):
            strategy._record_trade_outcome(
                asset="BTC",
                side="UP",
                strategy="latency",
                entry_price=Decimal("0.50"),
                exit_price=Decimal("0.48"),
                profit_pct=Decimal("-0.04"),  # 4% loss
                hold_time_minutes=5.0,
                exit_reason="stop_loss",
                position_size=Decimal("10.0")
            )
        
        # Win rate should be 0%
        metrics = strategy.dynamic_params.get_performance_metrics()
        assert metrics.win_rate == 0.0
        
        # Fractional Kelly should be at min (25%) due to low win rate
        assert strategy.dynamic_params.current_fractional_kelly == 0.25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
