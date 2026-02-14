"""
Property-based tests for directional trade momentum requirement.

Tests that directional trades only execute when momentum > 0.1% in the trade direction.

**Validates: Requirements 3.10**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock
from collections import deque

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket, BinancePriceFeed
from src.ensemble_decision_engine import EnsembleDecisionEngine, EnsembleDecision, ModelDecision


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def binance_price_sequence(draw):
    """Generate random Binance price sequences with various momentum patterns."""
    # Starting price
    start_price = Decimal(str(draw(st.floats(min_value=1000.0, max_value=100000.0, allow_nan=False, allow_infinity=False))))
    
    # Generate price change percentage (-2% to +2%)
    change_pct = Decimal(str(draw(st.floats(min_value=-0.02, max_value=0.02, allow_nan=False, allow_infinity=False))))
    
    # Calculate end price
    end_price = start_price * (Decimal("1") + change_pct)
    
    # Generate timestamps (10 seconds apart)
    now = datetime.now()
    timestamps = [now - timedelta(seconds=10), now]
    
    return {
        'start_price': start_price,
        'end_price': end_price,
        'change_pct': change_pct,
        'timestamps': timestamps
    }


@st.composite
def crypto_market_strategy(draw):
    """Generate random CryptoMarket objects."""
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    up_price = Decimal(str(draw(st.floats(min_value=0.40, max_value=0.60, allow_nan=False, allow_infinity=False))))
    down_price = Decimal("1.0") - up_price
    
    return CryptoMarket(
        market_id=f"market_{draw(st.integers(min_value=1, max_value=10000))}",
        question=f"Will {asset} go up in the next 15 minutes?",
        asset=asset,
        up_token_id=f"up_token_{draw(st.integers(min_value=1, max_value=10000))}",
        down_token_id=f"down_token_{draw(st.integers(min_value=1, max_value=10000))}",
        up_price=up_price,
        down_price=down_price,
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        neg_risk=draw(st.booleans())
    )


# ============================================================================
# HELPER FUNCTION TO CREATE MOCK STRATEGY
# ============================================================================

def create_mock_strategy_with_binance(price_sequence):
    """Create a mock strategy instance with Binance feed for testing."""
    mock_clob = MagicMock()
    
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=False  # Disable learning for tests
    )
    
    # Initialize stats dictionary (required by check_directional_trade)
    strategy.stats = {
        'trades_won': 0,
        'trades_lost': 0,
        'total_profit': Decimal('0'),
        'trades_placed': 0,
        'daily_loss': Decimal('0')
    }
    
    # Mock the LLM decision engine (required for directional trades)
    strategy.llm_decision_engine = MagicMock()
    
    # Mock the ensemble engine to return predictable decisions
    strategy.ensemble_engine = MagicMock(spec=EnsembleDecisionEngine)
    
    # Mock the _place_order method
    strategy._place_order = AsyncMock(return_value=True)
    strategy._verify_liquidity_before_entry = AsyncMock(return_value=(True, "OK"))
    strategy._calculate_position_size = MagicMock(return_value=Decimal("10.0"))
    
    # Mock circuit breaker and limit checks
    strategy._check_circuit_breaker = MagicMock(return_value=True)
    strategy._check_daily_loss_limit = MagicMock(return_value=True)
    strategy._check_daily_limit = MagicMock(return_value=True)
    strategy._check_asset_exposure = MagicMock(return_value=True)
    strategy._has_min_time_to_close = MagicMock(return_value=True)
    strategy._track_execution_time = MagicMock()
    
    # Mock risk manager
    strategy.risk_manager = MagicMock()
    strategy.risk_manager.check_confidence_requirement = MagicMock(return_value=(True, "OK"))
    
    # Setup Binance feed with price history
    strategy.binance_feed = MagicMock(spec=BinancePriceFeed)
    strategy.binance_feed.price_history = {}
    strategy.binance_feed.prices = {}
    
    return strategy


# ============================================================================
# PROPERTY 18: DIRECTIONAL TRADE MOMENTUM REQUIREMENT
# ============================================================================

@given(
    price_seq=binance_price_sequence(),
    market=crypto_market_strategy(),
    trade_direction=st.sampled_from(["buy_yes", "buy_no"])
)
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_directional_trades_require_momentum(price_seq, market, trade_direction):
    """
    **Validates: Requirements 3.10**
    
    Property 18: Directional Trade Momentum Requirement
    
    For any directional trade (buy_yes or buy_no), the trade should only execute
    if Binance momentum > 0.1% in the trade direction.
    
    - buy_yes requires bullish momentum (> +0.1%)
    - buy_no requires bearish momentum (< -0.1%)
    - Trades should be skipped if momentum is insufficient or contradicts direction
    """
    strategy = create_mock_strategy_with_binance(price_seq)
    
    # Setup Binance price history for the asset
    asset = market.asset
    strategy.binance_feed.price_history[asset] = deque([
        (price_seq['timestamps'][0], price_seq['start_price']),
        (price_seq['timestamps'][1], price_seq['end_price'])
    ])
    strategy.binance_feed.prices[asset] = price_seq['end_price']
    
    # Calculate actual price change
    price_change = (price_seq['end_price'] - price_seq['start_price']) / price_seq['start_price']
    
    # Mock get_price_change to return the calculated change
    strategy.binance_feed.get_price_change = MagicMock(return_value=price_change)
    
    # Setup ensemble to approve the trade
    ensemble_decision = EnsembleDecision(
        action=trade_direction,
        confidence=75.0,
        consensus_score=60.0,
        reasoning="Test decision",
        model_votes={
            "llm": ModelDecision(model_name="llm", action=trade_direction, confidence=80.0, reasoning="Test"),
            "rl": ModelDecision(model_name="rl", action=trade_direction, confidence=70.0, reasoning="Test")
        }
    )
    strategy.ensemble_engine.make_decision = AsyncMock(return_value=ensemble_decision)
    strategy.ensemble_engine.should_execute = MagicMock(return_value=True)
    
    # Reset circuit breakers and limits
    strategy.consecutive_losses = 0
    strategy.stats = {'daily_loss': Decimal('0'), 'trades_placed': 0}
    strategy.positions = {}
    strategy.last_llm_check = {}
    
    # Execute directional trade check
    result = await strategy.check_directional_trade(market)
    
    # Determine expected behavior based on momentum and trade direction
    momentum_threshold = Decimal("0.001")  # 0.1%
    
    if trade_direction == "buy_yes":
        # Buying YES requires bullish momentum (> +0.1%)
        should_execute = price_change > momentum_threshold
    else:  # buy_no
        # Buying NO requires bearish momentum (< -0.1%)
        should_execute = price_change < -momentum_threshold
    
    # Verify behavior matches requirement
    if should_execute:
        # Trade should execute - momentum is sufficient and in correct direction
        assert result == True, f"Trade should execute with {trade_direction} and momentum {price_change:.4%}"
        assert strategy._place_order.called, "Order should be placed when momentum is sufficient"
    else:
        # Trade should be skipped - momentum is insufficient or contradicts direction
        assert result == False, f"Trade should be skipped with {trade_direction} and momentum {price_change:.4%}"
        assert not strategy._place_order.called, "Order should NOT be placed when momentum is insufficient"


@given(
    market=crypto_market_strategy(),
    momentum_pct=st.floats(min_value=-0.0009, max_value=0.0009, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_neutral_momentum_blocks_all_directional_trades(market, momentum_pct):
    """
    **Validates: Requirements 3.10**
    
    Property 18b: Neutral Momentum Blocks Trades
    
    When momentum is between -0.1% and +0.1% (neutral), all directional trades
    should be blocked regardless of ensemble decision.
    """
    # Create price sequence with neutral momentum
    start_price = Decimal("50000.0")
    change = Decimal(str(momentum_pct))
    end_price = start_price * (Decimal("1") + change)
    
    now = datetime.now()
    price_seq = {
        'start_price': start_price,
        'end_price': end_price,
        'change_pct': change,
        'timestamps': [now - timedelta(seconds=10), now]
    }
    
    strategy = create_mock_strategy_with_binance(price_seq)
    
    # Setup Binance price history
    asset = market.asset
    strategy.binance_feed.price_history[asset] = deque([
        (price_seq['timestamps'][0], price_seq['start_price']),
        (price_seq['timestamps'][1], price_seq['end_price'])
    ])
    strategy.binance_feed.prices[asset] = price_seq['end_price']
    strategy.binance_feed.get_price_change = MagicMock(return_value=change)
    
    # Test both buy_yes and buy_no
    for trade_direction in ["buy_yes", "buy_no"]:
        # Setup ensemble to approve the trade
        ensemble_decision = EnsembleDecision(
            action=trade_direction,
            confidence=75.0,
            consensus_score=60.0,
            reasoning="Test decision",
            model_votes={
                "llm": ModelDecision(model_name="llm", action=trade_direction, confidence=80.0, reasoning="Test")
            }
        )
        strategy.ensemble_engine.make_decision = AsyncMock(return_value=ensemble_decision)
        strategy.ensemble_engine.should_execute = MagicMock(return_value=True)
        
        # Reset state
        strategy.consecutive_losses = 0
        strategy.stats = {'daily_loss': Decimal('0'), 'trades_placed': 0}
        strategy.positions = {}
        strategy.last_llm_check = {}
        strategy._place_order.reset_mock()
        
        # Execute directional trade check
        result = await strategy.check_directional_trade(market)
        
        # Verify: Trade should be blocked due to neutral momentum
        assert result == False, f"Trade {trade_direction} should be blocked with neutral momentum {change:.4%}"
        assert not strategy._place_order.called, f"Order should NOT be placed with neutral momentum"


@given(
    market=crypto_market_strategy(),
    strong_momentum_pct=st.floats(min_value=0.002, max_value=0.05, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_strong_momentum_allows_aligned_trades(market, strong_momentum_pct):
    """
    **Validates: Requirements 3.10**
    
    Property 18c: Strong Momentum Allows Aligned Trades
    
    When momentum is strong (> 0.2%) and aligned with trade direction,
    the trade should execute successfully.
    """
    # Create price sequence with strong bullish momentum
    start_price = Decimal("50000.0")
    change = Decimal(str(strong_momentum_pct))
    end_price = start_price * (Decimal("1") + change)
    
    now = datetime.now()
    price_seq = {
        'start_price': start_price,
        'end_price': end_price,
        'change_pct': change,
        'timestamps': [now - timedelta(seconds=10), now]
    }
    
    strategy = create_mock_strategy_with_binance(price_seq)
    
    # Setup Binance price history
    asset = market.asset
    strategy.binance_feed.price_history[asset] = deque([
        (price_seq['timestamps'][0], price_seq['start_price']),
        (price_seq['timestamps'][1], price_seq['end_price'])
    ])
    strategy.binance_feed.prices[asset] = price_seq['end_price']
    strategy.binance_feed.get_price_change = MagicMock(return_value=change)
    
    # Setup ensemble to approve buy_yes (aligned with bullish momentum)
    ensemble_decision = EnsembleDecision(
        action="buy_yes",
        confidence=75.0,
        consensus_score=60.0,
        reasoning="Test decision",
        model_votes={
            "llm": ModelDecision(model_name="llm", action="buy_yes", confidence=80.0, reasoning="Test")
        }
    )
    strategy.ensemble_engine.make_decision = AsyncMock(return_value=ensemble_decision)
    strategy.ensemble_engine.should_execute = MagicMock(return_value=True)
    
    # Reset state
    strategy.consecutive_losses = 0
    strategy.stats = {'daily_loss': Decimal('0'), 'trades_placed': 0}
    strategy.positions = {}
    strategy.last_llm_check = {}
    
    # Execute directional trade check
    result = await strategy.check_directional_trade(market)
    
    # Verify: Trade should execute with strong aligned momentum
    assert result == True, f"Trade should execute with strong bullish momentum {change:.4%}"
    assert strategy._place_order.called, "Order should be placed with strong aligned momentum"


@given(
    market=crypto_market_strategy()
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_buy_both_converted_to_directional_requires_momentum(market):
    """
    **Validates: Requirements 3.10**
    
    Property 18d: Buy Both Conversion Requires Momentum
    
    When ensemble votes "buy_both" and it's converted to directional trade,
    the momentum requirement should still apply.
    """
    # Create strong bullish momentum
    start_price = Decimal("50000.0")
    change = Decimal("0.002")  # 0.2% bullish
    end_price = start_price * (Decimal("1") + change)
    
    now = datetime.now()
    price_seq = {
        'start_price': start_price,
        'end_price': end_price,
        'change_pct': change,
        'timestamps': [now - timedelta(seconds=10), now]
    }
    
    strategy = create_mock_strategy_with_binance(price_seq)
    
    # CRITICAL: Ensure UP price is cheaper so buy_both converts to YES (aligned with bullish momentum)
    # This ensures the momentum check will pass
    market.up_price = Decimal("0.45")
    market.down_price = Decimal("0.55")
    
    # Setup Binance price history
    asset = market.asset
    strategy.binance_feed.price_history[asset] = deque([
        (price_seq['timestamps'][0], price_seq['start_price']),
        (price_seq['timestamps'][1], price_seq['end_price'])
    ])
    strategy.binance_feed.prices[asset] = price_seq['end_price']
    strategy.binance_feed.get_price_change = MagicMock(return_value=change)
    
    # Setup ensemble to vote buy_both
    ensemble_decision = EnsembleDecision(
        action="buy_both",
        confidence=75.0,
        consensus_score=60.0,
        reasoning="Test decision",
        model_votes={
            "llm": ModelDecision(model_name="llm", action="buy_both", confidence=80.0, reasoning="Test")
        }
    )
    strategy.ensemble_engine.make_decision = AsyncMock(return_value=ensemble_decision)
    strategy.ensemble_engine.should_execute = MagicMock(return_value=True)
    
    # Reset state
    strategy.consecutive_losses = 0
    strategy.stats = {'daily_loss': Decimal('0'), 'trades_placed': 0}
    strategy.positions = {}
    strategy.last_llm_check = {}
    
    # Execute directional trade check
    result = await strategy.check_directional_trade(market)
    
    # Verify: Trade should execute (buy_both converted to buy_yes with bullish momentum)
    assert result == True, "Buy_both should convert to directional and execute with sufficient momentum"
    assert strategy._place_order.called, "Order should be placed after buy_both conversion"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
