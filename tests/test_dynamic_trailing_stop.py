"""
Test dynamic trailing stop-loss implementation (Task 6.4).

This test verifies that:
1. Trailing stop thresholds are dynamically adjusted based on volatility
2. Trailing stop thresholds are dynamically adjusted based on confidence
3. Peak prices are tracked and persisted
4. Trailing stop triggers correctly with dynamic thresholds
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position


@dataclass
class MockClobClient:
    """Mock CLOB client for testing."""
    pass


@pytest.fixture
def mock_strategy():
    """Create a mock strategy instance for testing."""
    mock_client = MockClobClient()
    
    with patch('src.fifteen_min_crypto_strategy.BinancePriceFeed'), \
         patch('src.fifteen_min_crypto_strategy.MultiTimeframeAnalyzer'), \
         patch('src.fifteen_min_crypto_strategy.OrderBookAnalyzer'), \
         patch('src.fifteen_min_crypto_strategy.HistoricalSuccessTracker'), \
         patch('src.fifteen_min_crypto_strategy.ReinforcementLearningEngine'), \
         patch('src.fast_execution_engine.FastExecutionEngine'), \
         patch('src.polymarket_websocket_feed.PolymarketWebSocketFeed'), \
         patch('src.fifteen_min_crypto_strategy.EnsembleDecisionEngine'), \
         patch('src.fifteen_min_crypto_strategy.ContextOptimizer'), \
         patch('src.portfolio_risk_manager.PortfolioRiskManager'), \
         patch('src.dynamic_parameter_system.DynamicParameterSystem'), \
         patch('src.fifteen_min_crypto_strategy.AdaptiveLearningEngine'):
        
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_client,
            trade_size=5.0,
            dry_run=True,
            enable_adaptive_learning=False
        )
        
        # Mock methods that would normally interact with external systems
        strategy._save_positions = Mock()
        strategy._close_position = AsyncMock(return_value=True)
        
        return strategy


def test_dynamic_trailing_stop_initialization(mock_strategy):
    """Test that dynamic trailing stop thresholds are initialized correctly."""
    # Verify dynamic ranges are set
    assert mock_strategy.trailing_stop_pct_min == Decimal("0.01")  # 1%
    assert mock_strategy.trailing_stop_pct_max == Decimal("0.03")  # 3%
    assert mock_strategy.trailing_activation_pct_min == Decimal("0.003")  # 0.3%
    assert mock_strategy.trailing_activation_pct_max == Decimal("0.010")  # 1.0%
    
    # Verify starting values are in the middle
    assert mock_strategy.trailing_stop_pct == Decimal("0.02")  # 2%
    assert mock_strategy.trailing_activation_pct == Decimal("0.005")  # 0.5%


def test_adjust_trailing_stop_high_volatility(mock_strategy):
    """Test that high volatility tightens activation threshold."""
    # High volatility (>5%)
    mock_strategy._adjust_trailing_stop_thresholds(volatility=Decimal("0.06"))
    
    # Should use minimum activation (easier to activate)
    assert mock_strategy.trailing_activation_pct == mock_strategy.trailing_activation_pct_min
    assert mock_strategy.trailing_activation_pct == Decimal("0.003")  # 0.3%


def test_adjust_trailing_stop_low_volatility(mock_strategy):
    """Test that low volatility widens activation threshold."""
    # Low volatility (<1%)
    mock_strategy._adjust_trailing_stop_thresholds(volatility=Decimal("0.005"))
    
    # Should use maximum activation (harder to activate)
    assert mock_strategy.trailing_activation_pct == mock_strategy.trailing_activation_pct_max
    assert mock_strategy.trailing_activation_pct == Decimal("0.010")  # 1.0%


def test_adjust_trailing_stop_medium_volatility(mock_strategy):
    """Test that medium volatility scales activation threshold."""
    # Medium volatility (3%)
    mock_strategy._adjust_trailing_stop_thresholds(volatility=Decimal("0.03"))
    
    # Should be between min and max
    assert mock_strategy.trailing_activation_pct > mock_strategy.trailing_activation_pct_min
    assert mock_strategy.trailing_activation_pct < mock_strategy.trailing_activation_pct_max
    
    # At 3% volatility (midpoint of 1-5% range), should be around middle
    expected = Decimal("0.0065")  # Approximately middle of 0.3-1.0%
    assert abs(mock_strategy.trailing_activation_pct - expected) < Decimal("0.001")


def test_adjust_trailing_stop_high_confidence(mock_strategy):
    """Test that high confidence tightens stop threshold."""
    # High confidence (>70%)
    mock_strategy._adjust_trailing_stop_thresholds(confidence=Decimal("80"))
    
    # Should use minimum stop (protect profits more aggressively)
    assert mock_strategy.trailing_stop_pct == mock_strategy.trailing_stop_pct_min
    assert mock_strategy.trailing_stop_pct == Decimal("0.01")  # 1%


def test_adjust_trailing_stop_low_confidence(mock_strategy):
    """Test that low confidence widens stop threshold."""
    # Low confidence (<40%)
    mock_strategy._adjust_trailing_stop_thresholds(confidence=Decimal("30"))
    
    # Should use maximum stop (give more room)
    assert mock_strategy.trailing_stop_pct == mock_strategy.trailing_stop_pct_max
    assert mock_strategy.trailing_stop_pct == Decimal("0.03")  # 3%


def test_adjust_trailing_stop_medium_confidence(mock_strategy):
    """Test that medium confidence scales stop threshold."""
    # Medium confidence (55%)
    mock_strategy._adjust_trailing_stop_thresholds(confidence=Decimal("55"))
    
    # Should be between min and max
    assert mock_strategy.trailing_stop_pct > mock_strategy.trailing_stop_pct_min
    assert mock_strategy.trailing_stop_pct < mock_strategy.trailing_stop_pct_max
    
    # At 55% confidence (midpoint of 40-70% range), should be around middle
    expected = Decimal("0.02")  # Middle of 1-3%
    assert abs(mock_strategy.trailing_stop_pct - expected) < Decimal("0.001")


def test_position_includes_confidence(mock_strategy):
    """Test that Position dataclass includes confidence field."""
    position = Position(
        token_id="test_token",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market",
        asset="BTC",
        strategy="directional",
        neg_risk=True,
        highest_price=Decimal("0.50"),
        used_orderbook_entry=False,
        confidence=Decimal("75")
    )
    
    assert position.confidence == Decimal("75")


def test_position_confidence_default(mock_strategy):
    """Test that Position confidence defaults to 50 if not provided."""
    position = Position(
        token_id="test_token",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market",
        asset="BTC"
    )
    
    assert position.confidence == Decimal("50")


def test_position_persistence_includes_confidence(mock_strategy):
    """Test that position persistence includes confidence field."""
    # Create a position with confidence
    position = Position(
        token_id="test_token",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market",
        asset="BTC",
        confidence=Decimal("80")
    )
    
    mock_strategy.positions["test_token"] = position
    
    # Mock the file operations
    import json
    import os
    saved_data = None
    
    def mock_dump(data, f, indent=None):
        nonlocal saved_data
        saved_data = data
    
    # Create a mock file object
    mock_file = Mock()
    mock_open = Mock(return_value=mock_file)
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=False)
    
    with patch('builtins.open', mock_open), \
         patch('json.dump', mock_dump), \
         patch('os.makedirs'):
        # Reset the mock to avoid the error from __init__
        mock_strategy._save_positions = FifteenMinuteCryptoStrategy._save_positions.__get__(mock_strategy)
        mock_strategy._save_positions()
    
    # Verify confidence is saved
    assert saved_data is not None
    assert "test_token" in saved_data
    assert saved_data["test_token"]["confidence"] == "80"


@pytest.mark.asyncio
async def test_trailing_stop_with_dynamic_thresholds(mock_strategy):
    """Test that trailing stop uses dynamically adjusted thresholds."""
    # Set high confidence (should use tight 1% stop)
    mock_strategy._adjust_trailing_stop_thresholds(confidence=Decimal("80"))
    
    # Create position that reached peak
    position = Position(
        token_id="test_token",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10"),
        entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        market_id="test_market",
        asset="BTC",
        strategy="directional",
        highest_price=Decimal("0.52"),  # Reached 4% profit (activates trailing stop)
        confidence=Decimal("80")
    )
    
    mock_strategy.positions["test_token"] = position
    
    # Current price dropped 1.5% from peak (should trigger with 1% threshold)
    current_price = Decimal("0.5122")  # 1.5% drop from 0.52
    
    # Check if trailing stop triggers
    positions_to_close = []
    result = await mock_strategy._check_trailing_stop(
        position=position,
        current_price=current_price,
        pnl_pct=Decimal("0.024"),  # Still in profit
        age_min=5.0,
        token_id="test_token",
        positions_to_close=positions_to_close,
        used_orderbook_exit=False
    )
    
    # Should trigger because 1.5% drop > 1% threshold
    assert result is True
    assert "test_token" in positions_to_close


@pytest.mark.asyncio
async def test_trailing_stop_respects_low_confidence(mock_strategy):
    """Test that trailing stop gives more room with low confidence."""
    # Set low confidence (should use wide 3% stop)
    mock_strategy._adjust_trailing_stop_thresholds(confidence=Decimal("30"))
    
    # Create position that reached peak
    position = Position(
        token_id="test_token",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10"),
        entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
        market_id="test_market",
        asset="BTC",
        strategy="directional",
        highest_price=Decimal("0.52"),  # Reached 4% profit
        confidence=Decimal("30")
    )
    
    mock_strategy.positions["test_token"] = position
    
    # Current price dropped 2% from peak (should NOT trigger with 3% threshold)
    current_price = Decimal("0.5096")  # 2% drop from 0.52
    
    # Check if trailing stop triggers
    positions_to_close = []
    result = await mock_strategy._check_trailing_stop(
        position=position,
        current_price=current_price,
        pnl_pct=Decimal("0.019"),  # Still in profit
        age_min=5.0,
        token_id="test_token",
        positions_to_close=positions_to_close,
        used_orderbook_exit=False
    )
    
    # Should NOT trigger because 2% drop < 3% threshold
    assert result is False
    assert len(positions_to_close) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
