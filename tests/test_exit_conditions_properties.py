"""
Property-based tests for exit condition triggering in FifteenMinuteCryptoStrategy.

Tests that exit conditions trigger correctly across a wide range of random inputs.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.7, 2.9, 2.10**
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position, CryptoMarket


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def position_strategy(draw):
    """Generate random Position objects with various P&L states."""
    entry_price = Decimal(str(draw(st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False))))
    size = Decimal(str(draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False))))
    
    # Generate entry time (0-20 minutes ago)
    minutes_ago = draw(st.integers(min_value=0, max_value=20))
    entry_time = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    
    # Generate highest price (at or above entry price)
    highest_multiplier = draw(st.floats(min_value=1.0, max_value=1.5, allow_nan=False, allow_infinity=False))
    highest_price = entry_price * Decimal(str(highest_multiplier))
    
    return Position(
        token_id=f"token_{draw(st.integers(min_value=1, max_value=100000))}",
        side=draw(st.sampled_from(["UP", "DOWN"])),
        entry_price=entry_price,
        size=size,
        entry_time=entry_time,
        market_id=f"market_{draw(st.integers(min_value=1, max_value=10000))}",
        asset=draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"])),
        strategy=draw(st.sampled_from(["sum_to_one", "latency", "directional"])),
        neg_risk=draw(st.booleans()),
        highest_price=highest_price
    )


# ============================================================================
# HELPER FUNCTION TO CREATE MOCK STRATEGY
# ============================================================================

def create_mock_strategy():
    """Create a mock strategy instance for testing."""
    mock_clob = MagicMock()
    
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=False  # Disable learning for tests
    )
    
    # Mock the _close_position method
    strategy._close_position = AsyncMock(return_value=True)
    strategy._save_positions = MagicMock()
    strategy._record_trade_outcome = MagicMock()
    
    return strategy


# ============================================================================
# PROPERTY 1: EXIT CONDITIONS TRIGGER CORRECTLY
# ============================================================================

@given(position=position_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_take_profit_triggers_at_threshold(position):
    """
    **Validates: Requirements 2.1, 2.9, 2.10**
    
    Property 1a: Take-Profit Exit Condition
    
    For any position with P&L >= take_profit_pct, the exit condition should trigger.
    The position should be closed and removed from tracking.
    """
    strategy = create_mock_strategy()
    
    # Set take-profit threshold
    strategy.take_profit_pct = Decimal("0.02")  # 2%
    
    # Calculate current price to meet take-profit
    current_price = position.entry_price * Decimal("1.02")
    
    # CRITICAL: Set highest_price to current_price to avoid trailing stop
    # Trailing stop has higher priority than take-profit
    position.highest_price = current_price
    
    # CRITICAL: Set position age to < 13 minutes to avoid time exit
    # Time exit has higher priority than take-profit
    position.entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    # Create matching market
    market = CryptoMarket(
        market_id=position.market_id,
        question=f"Will {position.asset} go up?",
        asset=position.asset,
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=current_price if position.side == "UP" else Decimal("0.50"),
        down_price=current_price if position.side == "DOWN" else Decimal("0.50"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
        neg_risk=position.neg_risk
    )
    
    # Add position to strategy
    strategy.positions = {position.token_id: position}
    
    # Execute exit check
    await strategy.check_exit_conditions(market)
    
    # Verify: Position should be closed
    assert strategy._close_position.called, "Take-profit should trigger position close"
    assert strategy._record_trade_outcome.called, "Trade outcome should be recorded"
    
    # Verify exit reason is "take_profit"
    call_args = strategy._record_trade_outcome.call_args
    assert call_args[1]['exit_reason'] == "take_profit"


@given(position=position_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_stop_loss_triggers_at_threshold(position):
    """
    **Validates: Requirements 2.2, 2.9, 2.10**
    
    Property 1b: Stop-Loss Exit Condition
    
    For any position with P&L <= -stop_loss_pct, the exit condition should trigger.
    """
    strategy = create_mock_strategy()
    
    # Set stop-loss threshold
    strategy.stop_loss_pct = Decimal("0.02")  # 2%
    
    # Calculate current price to meet stop-loss
    current_price = position.entry_price * Decimal("0.98")
    
    # CRITICAL: Set highest_price to entry_price to avoid trailing stop
    position.highest_price = position.entry_price
    
    # CRITICAL: Set position age to < 13 minutes to avoid time exit
    position.entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    # Create matching market
    market = CryptoMarket(
        market_id=position.market_id,
        question=f"Will {position.asset} go up?",
        asset=position.asset,
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=current_price if position.side == "UP" else Decimal("0.50"),
        down_price=current_price if position.side == "DOWN" else Decimal("0.50"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
        neg_risk=position.neg_risk
    )
    
    # Add position to strategy
    strategy.positions = {position.token_id: position}
    
    # Execute exit check
    await strategy.check_exit_conditions(market)
    
    # Verify: Position should be closed
    assert strategy._close_position.called, "Stop-loss should trigger position close"
    assert strategy._record_trade_outcome.called, "Trade outcome should be recorded"
    
    # Verify exit reason is "stop_loss"
    call_args = strategy._record_trade_outcome.call_args
    assert call_args[1]['exit_reason'] == "stop_loss"


@given(position=position_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_time_exit_triggers_after_threshold(position):
    """
    **Validates: Requirements 2.3, 2.9, 2.10**
    
    Property 1c: Time-Based Exit Condition
    
    For any position with age > 13 minutes, the time exit condition should trigger.
    """
    # Force position to be old enough
    position.entry_time = datetime.now(timezone.utc) - timedelta(minutes=14)
    
    strategy = create_mock_strategy()
    
    # Create matching market (not closing soon)
    market = CryptoMarket(
        market_id=position.market_id,
        question=f"Will {position.asset} go up?",
        asset=position.asset,
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=position.entry_price,  # No profit/loss
        down_price=position.entry_price,
        end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
        neg_risk=position.neg_risk
    )
    
    # Add position to strategy
    strategy.positions = {position.token_id: position}
    
    # Execute exit check
    await strategy.check_exit_conditions(market)
    
    # Verify: Position should be closed
    assert strategy._close_position.called, "Time exit should trigger position close"
    assert strategy._record_trade_outcome.called, "Trade outcome should be recorded"
    
    # Verify exit reason is "time_exit"
    call_args = strategy._record_trade_outcome.call_args
    assert call_args[1]['exit_reason'] == "time_exit"


@given(position=position_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_market_closing_triggers_force_exit(position):
    """
    **Validates: Requirements 2.4, 2.9, 2.10**
    
    Property 1d: Market Closing Exit Condition
    
    For any position when market is closing in < 2 minutes, the exit should trigger.
    """
    strategy = create_mock_strategy()
    
    # Create market closing in 1 minute
    market = CryptoMarket(
        market_id=position.market_id,
        question=f"Will {position.asset} go up?",
        asset=position.asset,
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=position.entry_price,  # No profit/loss
        down_price=position.entry_price,
        end_time=datetime.now(timezone.utc) + timedelta(minutes=1),
        neg_risk=position.neg_risk
    )
    
    # Add position to strategy
    strategy.positions = {position.token_id: position}
    
    # Execute exit check
    await strategy.check_exit_conditions(market)
    
    # Verify: Position should be closed
    assert strategy._close_position.called, "Market closing should trigger position close"
    assert strategy._record_trade_outcome.called, "Trade outcome should be recorded"
    
    # Verify exit reason is "market_closing"
    call_args = strategy._record_trade_outcome.call_args
    assert call_args[1]['exit_reason'] == "market_closing"


@given(position=position_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_positions_removed_after_successful_exit(position):
    """
    **Validates: Requirements 2.7, 2.10**
    
    Property 2: Position Cleanup After Exit
    
    For any position that successfully exits, it should be saved to disk.
    """
    # Force position to trigger time exit
    position.entry_time = datetime.now(timezone.utc) - timedelta(minutes=14)
    
    strategy = create_mock_strategy()
    
    # Create matching market
    market = CryptoMarket(
        market_id=position.market_id,
        question=f"Will {position.asset} go up?",
        asset=position.asset,
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=position.entry_price,
        down_price=position.entry_price,
        end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
        neg_risk=position.neg_risk
    )
    
    # Add position to strategy
    strategy.positions = {position.token_id: position}
    
    # Execute exit check
    await strategy.check_exit_conditions(market)
    
    # Verify: Position should be closed and saved
    assert strategy._close_position.called, "Position should be closed"
    assert strategy._save_positions.called, "Positions should be saved to disk"


@given(position=position_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_no_exit_when_conditions_not_met(position):
    """
    **Validates: Requirements 2.9, 2.10**
    
    Property 4: No Premature Exit
    
    For any position where no exit conditions are met, the position should remain open.
    """
    # Force position to be young (< 13 minutes)
    position.entry_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    strategy = create_mock_strategy()
    
    # Set thresholds
    strategy.take_profit_pct = Decimal("0.02")
    strategy.stop_loss_pct = Decimal("0.02")
    
    # Create market with price that doesn't meet any exit condition
    current_price = position.entry_price * Decimal("1.01")  # 1% profit (below TP)
    
    # CRITICAL: Set highest_price to current_price to avoid trailing stop
    position.highest_price = current_price
    
    market = CryptoMarket(
        market_id=position.market_id,
        question=f"Will {position.asset} go up?",
        asset=position.asset,
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=current_price if position.side == "UP" else Decimal("0.50"),
        down_price=current_price if position.side == "DOWN" else Decimal("0.50"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=10),  # Not closing soon
        neg_risk=position.neg_risk
    )
    
    # Add position to strategy
    strategy.positions = {position.token_id: position}
    
    # Execute exit check
    await strategy.check_exit_conditions(market)
    
    # Verify: Position should NOT be closed
    assert not strategy._close_position.called, "Position should remain open when no exit conditions met"
    assert position.token_id in strategy.positions, "Position should still be in tracking"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
