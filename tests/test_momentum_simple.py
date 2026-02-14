"""
Simple unit test for directional momentum requirement.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from collections import deque

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket, BinancePriceFeed
from src.ensemble_decision_engine import EnsembleDecision, ModelDecision


@pytest.mark.asyncio
async def test_momentum_check_blocks_buy_yes_without_bullish_momentum():
    """Test that buy_yes is blocked when momentum is not bullish."""
    # Setup
    mock_clob = MagicMock()
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=False
    )
    
    # Mock LLM engine (required)
    strategy.llm_decision_engine = MagicMock()
    
    # Mock ensemble to approve buy_yes
    ensemble_decision = EnsembleDecision(
        action="buy_yes",
        confidence=75.0,
        consensus_score=60.0,
        reasoning="Test",
        model_votes={"llm": ModelDecision(model_name="llm", action="buy_yes", confidence=80.0, reasoning="Test")}
    )
    strategy.ensemble_engine = MagicMock()
    strategy.ensemble_engine.make_decision = AsyncMock(return_value=ensemble_decision)
    strategy.ensemble_engine.should_execute = MagicMock(return_value=True)
    
    # Setup Binance with NEUTRAL momentum (0.05% - below 0.1% threshold)
    strategy.binance_feed.get_price_change = MagicMock(return_value=Decimal("0.0005"))  # 0.05%
    strategy.binance_feed.prices = {"BTC": Decimal("50000")}
    strategy.binance_feed.price_history = {"BTC": deque()}
    
    # Mock other methods
    strategy._place_order = AsyncMock(return_value=True)
    strategy._verify_liquidity_before_entry = AsyncMock(return_value=(True, "OK"))
    strategy._calculate_position_size = MagicMock(return_value=Decimal("10.0"))
    
    # Reset state
    strategy.consecutive_losses = 0
    strategy.stats = {'daily_loss': Decimal('0'), 'trades_placed': 0}
    strategy.positions = {}
    strategy.last_llm_check = {}
    
    # Create market
    market = CryptoMarket(
        market_id="test_market",
        question="Will BTC go up?",
        asset="BTC",
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=Decimal("0.50"),
        down_price=Decimal("0.50"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        neg_risk=False
    )
    
    # Execute
    result = await strategy.check_directional_trade(market)
    
    # Verify: Trade should be blocked due to insufficient momentum
    assert result == False, "Trade should be blocked when momentum is neutral (< 0.1%)"
    assert not strategy._place_order.called, "Order should NOT be placed"


@pytest.mark.asyncio
async def test_momentum_check_allows_buy_yes_with_bullish_momentum():
    """Test that buy_yes is allowed when momentum is bullish (> 0.1%)."""
    # Setup
    mock_clob = MagicMock()
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=False
    )
    
    # Mock LLM engine (required)
    strategy.llm_decision_engine = MagicMock()
    
    # Mock ensemble to approve buy_yes
    ensemble_decision = EnsembleDecision(
        action="buy_yes",
        confidence=75.0,
        consensus_score=60.0,
        reasoning="Test",
        model_votes={"llm": ModelDecision(model_name="llm", action="buy_yes", confidence=80.0, reasoning="Test")}
    )
    strategy.ensemble_engine = MagicMock()
    strategy.ensemble_engine.make_decision = AsyncMock(return_value=ensemble_decision)
    strategy.ensemble_engine.should_execute = MagicMock(return_value=True)
    
    # Setup Binance with BULLISH momentum (0.2% - above 0.1% threshold)
    strategy.binance_feed.get_price_change = MagicMock(return_value=Decimal("0.002"))  # 0.2%
    strategy.binance_feed.prices = {"BTC": Decimal("50000")}
    strategy.binance_feed.price_history = {"BTC": deque()}
    
    # Mock other methods
    strategy._place_order = AsyncMock(return_value=True)
    strategy._verify_liquidity_before_entry = AsyncMock(return_value=(True, "OK"))
    strategy._calculate_position_size = MagicMock(return_value=Decimal("10.0"))
    
    # Reset state
    strategy.consecutive_losses = 0
    strategy.stats = {'daily_loss': Decimal('0'), 'trades_placed': 0}
    strategy.positions = {}
    strategy.last_llm_check = {}
    
    # Create market
    market = CryptoMarket(
        market_id="test_market",
        question="Will BTC go up?",
        asset="BTC",
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=Decimal("0.50"),
        down_price=Decimal("0.50"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        neg_risk=False
    )
    
    # Execute
    result = await strategy.check_directional_trade(market)
    
    # Verify: Trade should execute with sufficient bullish momentum
    assert result == True, "Trade should execute when momentum is bullish (> 0.1%)"
    assert strategy._place_order.called, "Order should be placed"


@pytest.mark.asyncio
async def test_momentum_check_blocks_buy_no_without_bearish_momentum():
    """Test that buy_no is blocked when momentum is not bearish."""
    # Setup
    mock_clob = MagicMock()
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=False
    )
    
    # Mock LLM engine (required)
    strategy.llm_decision_engine = MagicMock()
    
    # Mock ensemble to approve buy_no
    ensemble_decision = EnsembleDecision(
        action="buy_no",
        confidence=75.0,
        consensus_score=60.0,
        reasoning="Test",
        model_votes={"llm": ModelDecision(model_name="llm", action="buy_no", confidence=80.0, reasoning="Test")}
    )
    strategy.ensemble_engine = MagicMock()
    strategy.ensemble_engine.make_decision = AsyncMock(return_value=ensemble_decision)
    strategy.ensemble_engine.should_execute = MagicMock(return_value=True)
    
    # Setup Binance with NEUTRAL momentum (0.05% - below 0.1% threshold)
    strategy.binance_feed.get_price_change = MagicMock(return_value=Decimal("0.0005"))  # 0.05%
    strategy.binance_feed.prices = {"BTC": Decimal("50000")}
    strategy.binance_feed.price_history = {"BTC": deque()}
    
    # Mock other methods
    strategy._place_order = AsyncMock(return_value=True)
    strategy._verify_liquidity_before_entry = AsyncMock(return_value=(True, "OK"))
    strategy._calculate_position_size = MagicMock(return_value=Decimal("10.0"))
    
    # Reset state
    strategy.consecutive_losses = 0
    strategy.stats = {'daily_loss': Decimal('0'), 'trades_placed': 0}
    strategy.positions = {}
    strategy.last_llm_check = {}
    
    # Create market
    market = CryptoMarket(
        market_id="test_market",
        question="Will BTC go up?",
        asset="BTC",
        up_token_id="up_token",
        down_token_id="down_token",
        up_price=Decimal("0.50"),
        down_price=Decimal("0.50"),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        neg_risk=False
    )
    
    # Execute
    result = await strategy.check_directional_trade(market)
    
    # Verify: Trade should be blocked due to insufficient momentum
    assert result == False, "Trade should be blocked when momentum is neutral (not bearish)"
    assert not strategy._place_order.called, "Order should NOT be placed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
