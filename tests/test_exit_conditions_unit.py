"""
Unit tests for exit condition logic in FifteenMinuteCryptoStrategy.

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
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position, CryptoMarket


@pytest.fixture
def mock_strategy():
    """Create a mock strategy instance for testing."""
    # Create mock dependencies
    mock_clob = MagicMock()
    mock_risk_manager = MagicMock()
    mock_orderbook = MagicMock()
    mock_ensemble = MagicMock()
    mock_binance = MagicMock()
    
    # Create strategy with mocked dependencies
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        risk_manager=mock_risk_manager,
        order_book_analyzer=mock_orderbook,
        ensemble_engine=mock_ensemble,
        binance_feed=mock_binance,
        trade_size=Decimal("10.0"),
        max_positions=5
    )
    
    # Mock the _close_position method
    strategy._close_position = AsyncMock(return_value=True)
    strategy._save_positions = MagicMock()
    strategy._record_trade_outcome = MagicMock()
    
    return strategy


@pytest.fixture
def sample_position():
    """Create a sample position for testing."""
    return Position(
        token_id="test_token_123",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        market_id="test_market",
        asset="BTC",
        strategy="directional",
        neg_risk=False,
        highest_price=Decimal("0.50")
    )


@pytest.fixture
def sample_market():
    """Create a sample market for testing."""
    return CryptoMarket(
        market_id="test_market",
        asset="BTC",
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=Decimal("0.52"),
        down_price=Decimal("0.48"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
        neg_risk=False
    )


class TestExitPriorityOrder:
    """Test that exit conditions are checked in the correct priority order."""
    
    @pytest.mark.asyncio
    async def test_priority_1_market_closing_overrides_all(self, mock_strategy, sample_position, sample_market):
        """
        Test Priority 1: Market closing (< 2 min) should trigger exit even if other conditions met.
        **Validates: Requirement 2.1**
        """
        # Setup: Market closing in 1 minute, position also meets take-profit
        sample_market.end_time = datetime.now(timezone.utc) + timedelta(minutes=1)
        sample_position.entry_price = Decimal("0.40")  # Would trigger take-profit
        sample_position.highest_price = Decimal("0.40")
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.take_profit_pct = Decimal("0.02")  # 2%
        
        # Execute
        await mock_strategy.check_exit_conditions(sample_market)
        
        # Verify: Position closed due to market closing (Priority 1)
        assert mock_strategy._close_position.called
        assert mock_strategy._record_trade_outcome.called
        
        # Check that exit reason is "market_closing"
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "market_closing"
    
    @pytest.mark.asyncio
    async def test_priority_2_time_exit_overrides_profit_conditions(self, mock_strategy, sample_position, sample_market):
        """
        Test Priority 2: Time exit (> 13 min) should trigger before take-profit/stop-loss.
        **Validates: Requirement 2.2**
        """
        # Setup: Position is 14 minutes old and meets take-profit
        sample_position.entry_time = datetime.now(timezone.utc) - timedelta(minutes=14)
        sample_position.entry_price = Decimal("0.40")  # Would trigger take-profit
        sample_position.highest_price = Decimal("0.40")
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.take_profit_pct = Decimal("0.02")  # 2%
        
        # Execute
        await mock_strategy.check_exit_conditions(sample_market)
        
        # Verify: Position closed due to time exit (Priority 2)
        assert mock_strategy._close_position.called
        assert mock_strategy._record_trade_outcome.called
        
        # Check that exit reason is "time_exit"
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "time_exit"
    
    @pytest.mark.asyncio
    async def test_priority_3_trailing_stop_overrides_take_profit(self, mock_strategy, sample_position, sample_market):
        """
        Test Priority 3: Trailing stop should trigger before take-profit.
        **Validates: Requirement 2.3**
        """
        # Setup: Position reached peak, dropped, and still meets take-profit
        sample_position.entry_price = Decimal("0.40")
        sample_position.highest_price = Decimal("0.60")  # Peak at 50% profit
        sample_market.up_price = Decimal("0.52")  # Current at 30% profit (still above TP)
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.trailing_activation_pct = Decimal("0.02")  # 2% activation
        mock_strategy.trailing_stop_pct = Decimal("0.02")  # 2% drop from peak
        mock_strategy.take_profit_pct = Decimal("0.02")  # 2% take-profit
        
        # Execute
        await mock_strategy.check_exit_conditions(sample_market)
        
        # Verify: Position closed due to trailing stop (Priority 3)
        assert mock_strategy._close_position.called
        assert mock_strategy._record_trade_outcome.called
        
        # Check that exit reason is "trailing_stop"
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "trailing_stop"
    
    @pytest.mark.asyncio
    async def test_priority_4_take_profit_triggers_before_stop_loss(self, mock_strategy, sample_position, sample_market):
        """
        Test Priority 4: Take-profit should be checked before stop-loss.
        **Validates: Requirement 2.4**
        """
        # Setup: Position meets take-profit threshold
        sample_position.entry_price = Decimal("0.50")
        sample_position.highest_price = Decimal("0.50")
        sample_market.up_price = Decimal("0.51")  # 2% profit
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.take_profit_pct = Decimal("0.02")  # 2%
        mock_strategy.stop_loss_pct = Decimal("0.02")  # 2%
        
        # Execute
        await mock_strategy.check_exit_conditions(sample_market)
        
        # Verify: Position closed due to take-profit (Priority 4)
        assert mock_strategy._close_position.called
        assert mock_strategy._record_trade_outcome.called
        
        # Check that exit reason is "take_profit"
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "take_profit"
    
    @pytest.mark.asyncio
    async def test_priority_5_stop_loss_triggers_last(self, mock_strategy, sample_position, sample_market):
        """
        Test Priority 5: Stop-loss should be checked last.
        **Validates: Requirement 2.4**
        """
        # Setup: Position meets stop-loss threshold
        sample_position.entry_price = Decimal("0.50")
        sample_position.highest_price = Decimal("0.50")
        sample_market.up_price = Decimal("0.49")  # 2% loss
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.stop_loss_pct = Decimal("0.02")  # 2%
        
        # Execute
        await mock_strategy.check_exit_conditions(sample_market)
        
        # Verify: Position closed due to stop-loss (Priority 5)
        assert mock_strategy._close_position.called
        assert mock_strategy._record_trade_outcome.called
        
        # Check that exit reason is "stop_loss"
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "stop_loss"


class TestMarketClosingExit:
    """Test market closing exit condition (Priority 1)."""
    
    @pytest.mark.asyncio
    async def test_market_closing_in_1_minute_triggers_exit(self, mock_strategy, sample_position, sample_market):
        """Market closing in 1 minute should force exit."""
        sample_market.end_time = datetime.now(timezone.utc) + timedelta(minutes=1)
        mock_strategy.positions = {sample_position.token_id: sample_position}
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        assert mock_strategy._close_position.called
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "market_closing"
    
    @pytest.mark.asyncio
    async def test_market_closing_in_3_minutes_no_exit(self, mock_strategy, sample_position, sample_market):
        """Market closing in 3 minutes should NOT force exit."""
        sample_market.end_time = datetime.now(timezone.utc) + timedelta(minutes=3)
        mock_strategy.positions = {sample_position.token_id: sample_position}
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        # Should not close (no other exit conditions met)
        assert not mock_strategy._close_position.called


class TestTimeExit:
    """Test time-based exit condition (Priority 2)."""
    
    @pytest.mark.asyncio
    async def test_position_age_14_minutes_triggers_exit(self, mock_strategy, sample_position, sample_market):
        """Position age > 13 minutes should force exit."""
        sample_position.entry_time = datetime.now(timezone.utc) - timedelta(minutes=14)
        mock_strategy.positions = {sample_position.token_id: sample_position}
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        assert mock_strategy._close_position.called
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "time_exit"
    
    @pytest.mark.asyncio
    async def test_position_age_12_minutes_no_exit(self, mock_strategy, sample_position, sample_market):
        """Position age < 13 minutes should NOT force exit."""
        sample_position.entry_time = datetime.now(timezone.utc) - timedelta(minutes=12)
        mock_strategy.positions = {sample_position.token_id: sample_position}
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        # Should not close (no other exit conditions met)
        assert not mock_strategy._close_position.called


class TestTrailingStopLoss:
    """Test trailing stop-loss exit condition (Priority 3)."""
    
    @pytest.mark.asyncio
    async def test_trailing_stop_activates_after_profit_threshold(self, mock_strategy, sample_position, sample_market):
        """Trailing stop should activate after reaching profit threshold."""
        sample_position.entry_price = Decimal("0.40")
        sample_position.highest_price = Decimal("0.60")  # Peak at 50% profit
        sample_market.up_price = Decimal("0.58")  # Dropped 3.3% from peak
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.trailing_activation_pct = Decimal("0.02")  # 2% activation
        mock_strategy.trailing_stop_pct = Decimal("0.02")  # 2% drop from peak
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        assert mock_strategy._close_position.called
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "trailing_stop"
    
    @pytest.mark.asyncio
    async def test_trailing_stop_not_activated_below_threshold(self, mock_strategy, sample_position, sample_market):
        """Trailing stop should NOT activate if profit never reached threshold."""
        sample_position.entry_price = Decimal("0.50")
        sample_position.highest_price = Decimal("0.505")  # Peak at 1% profit (below 2% threshold)
        sample_market.up_price = Decimal("0.49")  # Dropped below entry
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.trailing_activation_pct = Decimal("0.02")  # 2% activation
        mock_strategy.trailing_stop_pct = Decimal("0.02")  # 2% drop from peak
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        # Should not trigger trailing stop (never activated)
        # But might trigger stop-loss instead
        if mock_strategy._close_position.called:
            call_args = mock_strategy._record_trade_outcome.call_args
            assert call_args[1]['exit_reason'] != "trailing_stop"


class TestTakeProfitExit:
    """Test take-profit exit condition (Priority 4)."""
    
    @pytest.mark.asyncio
    async def test_take_profit_at_2_percent(self, mock_strategy, sample_position, sample_market):
        """Take-profit should trigger at 2% profit."""
        sample_position.entry_price = Decimal("0.50")
        sample_position.highest_price = Decimal("0.50")
        sample_market.up_price = Decimal("0.51")  # 2% profit
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.take_profit_pct = Decimal("0.02")  # 2%
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        assert mock_strategy._close_position.called
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "take_profit"
    
    @pytest.mark.asyncio
    async def test_take_profit_not_triggered_below_threshold(self, mock_strategy, sample_position, sample_market):
        """Take-profit should NOT trigger below threshold."""
        sample_position.entry_price = Decimal("0.50")
        sample_position.highest_price = Decimal("0.50")
        sample_market.up_price = Decimal("0.509")  # 1.8% profit (below 2%)
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.take_profit_pct = Decimal("0.02")  # 2%
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        assert not mock_strategy._close_position.called


class TestStopLossExit:
    """Test stop-loss exit condition (Priority 5)."""
    
    @pytest.mark.asyncio
    async def test_stop_loss_at_2_percent(self, mock_strategy, sample_position, sample_market):
        """Stop-loss should trigger at 2% loss."""
        sample_position.entry_price = Decimal("0.50")
        sample_position.highest_price = Decimal("0.50")
        sample_market.up_price = Decimal("0.49")  # 2% loss
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.stop_loss_pct = Decimal("0.02")  # 2%
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        assert mock_strategy._close_position.called
        call_args = mock_strategy._record_trade_outcome.call_args
        assert call_args[1]['exit_reason'] == "stop_loss"
    
    @pytest.mark.asyncio
    async def test_stop_loss_not_triggered_above_threshold(self, mock_strategy, sample_position, sample_market):
        """Stop-loss should NOT trigger above threshold."""
        sample_position.entry_price = Decimal("0.50")
        sample_position.highest_price = Decimal("0.50")
        sample_market.up_price = Decimal("0.491")  # 1.8% loss (above -2%)
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.stop_loss_pct = Decimal("0.02")  # 2%
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        assert not mock_strategy._close_position.called


class TestNoExitConditions:
    """Test that positions are not closed when no exit conditions are met."""
    
    @pytest.mark.asyncio
    async def test_no_exit_when_all_conditions_not_met(self, mock_strategy, sample_position, sample_market):
        """Position should remain open when no exit conditions are met."""
        # Setup: Position with no exit conditions met
        sample_position.entry_price = Decimal("0.50")
        sample_position.highest_price = Decimal("0.50")
        sample_position.entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        sample_market.up_price = Decimal("0.505")  # 1% profit (below TP threshold)
        sample_market.end_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        mock_strategy.positions = {sample_position.token_id: sample_position}
        mock_strategy.take_profit_pct = Decimal("0.02")  # 2%
        mock_strategy.stop_loss_pct = Decimal("0.02")  # 2%
        
        await mock_strategy.check_exit_conditions(sample_market)
        
        # Position should NOT be closed
        assert not mock_strategy._close_position.called
        assert sample_position.token_id in mock_strategy.positions
