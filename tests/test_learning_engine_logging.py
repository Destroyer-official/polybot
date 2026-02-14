"""
Test learning engine confidence logging (Task 8.3).

Validates that:
1. Ensemble votes are logged for each decision
2. Parameter updates are logged after each trade
3. Parameters are logged when loaded on startup
"""

import pytest
import logging
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import json
import tempfile

from src.ensemble_decision_engine import EnsembleDecisionEngine, ModelDecision, VoteWeight
from src.reinforcement_learning_engine import ReinforcementLearningEngine
from src.super_smart_learning import SuperSmartLearning
from src.adaptive_learning_engine import AdaptiveLearningEngine, TradeOutcome


@pytest.fixture
def mock_engines():
    """Create mock engines for testing."""
    llm_engine = Mock()
    rl_engine = Mock()
    historical_tracker = Mock()
    multi_tf_analyzer = Mock()
    
    return {
        'llm_engine': llm_engine,
        'rl_engine': rl_engine,
        'historical_tracker': historical_tracker,
        'multi_tf_analyzer': multi_tf_analyzer
    }


@pytest.mark.asyncio
async def test_ensemble_votes_logged(mock_engines, caplog):
    """Test that ensemble votes are logged with detailed breakdown."""
    caplog.set_level(logging.INFO)
    
    # Create ensemble engine
    ensemble = EnsembleDecisionEngine(
        llm_engine=mock_engines['llm_engine'],
        rl_engine=mock_engines['rl_engine'],
        historical_tracker=mock_engines['historical_tracker'],
        multi_tf_analyzer=mock_engines['multi_tf_analyzer'],
        min_consensus=15.0
    )
    
    # Mock LLM decision - create a simple mock object with required attributes
    llm_decision = Mock()
    llm_decision.action = Mock()
    llm_decision.action.value = "buy_yes"
    llm_decision.confidence = 80.0
    llm_decision.reasoning = "Strong bullish signal"
    mock_engines['llm_engine'].make_decision = AsyncMock(return_value=llm_decision)
    
    # Mock RL decision
    mock_engines['rl_engine'].select_strategy.return_value = ("latency", 70.0)
    
    # Mock Historical decision
    mock_engines['historical_tracker'].should_trade.return_value = (True, 60.0, "Good history")
    
    # Mock Technical decision
    mock_engines['multi_tf_analyzer'].get_multi_timeframe_signal.return_value = ("bullish", 75.0, ["1m", "5m"])
    
    # Make decision
    market_context = {
        "yes_price": 0.55,
        "no_price": 0.45,
        "volatility": 0.02,
        "trend": "bullish",
        "liquidity": 1000
    }
    portfolio_state = {"balance": 100}
    
    decision = await ensemble.make_decision("BTC", market_context, portfolio_state, "latency")
    
    # Verify ensemble decision is logged
    assert any("🎯 Ensemble Decision:" in record.message for record in caplog.records)
    
    # Verify model votes breakdown is logged
    assert any("📊 Model Votes Breakdown:" in record.message for record in caplog.records)
    
    # Verify each model's vote is logged with weight and contribution
    assert any("LLM (weight=40%)" in record.message for record in caplog.records)
    assert any("RL (weight=35%)" in record.message for record in caplog.records)
    assert any("Historical (weight=20%)" in record.message for record in caplog.records)
    assert any("Technical (weight=5%)" in record.message for record in caplog.records)
    
    # Verify contribution percentages are logged
    assert any("contribution=" in record.message for record in caplog.records)


def test_rl_parameter_update_logged(caplog):
    """Test that RL parameter updates are logged after each trade."""
    caplog.set_level(logging.INFO)
    
    # Create temporary data file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = Path(f.name)
    
    try:
        # Create RL engine
        rl_engine = ReinforcementLearningEngine(data_file=str(temp_file))
        
        # Update Q-value (simulating a trade)
        rl_engine.update_q_value(
            asset="BTC",
            strategy="latency",
            reward=0.05,
            volatility=Decimal("0.02"),
            trend="bullish",
            liquidity=Decimal("1000")
        )
        
        # Verify parameter update is logged
        assert any("🧠 RL Parameter Update:" in record.message for record in caplog.records)
        assert any("reward=" in record.message for record in caplog.records)
        assert any("Q-value:" in record.message for record in caplog.records)
        assert any("exploration_rate=" in record.message for record in caplog.records)
        assert any("episode=" in record.message for record in caplog.records)
        
    finally:
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()


def test_rl_parameters_loaded_on_startup(caplog):
    """Test that RL parameters are logged when loaded on startup."""
    caplog.set_level(logging.INFO)
    
    # Create temporary data file with existing Q-table
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = Path(f.name)
        data = {
            "q_table": {
                "BTC_low_bullish_high": {
                    "latency": 0.5,
                    "directional": 0.3,
                    "sum_to_one": 0.1
                }
            },
            "total_episodes": 100,
            "total_reward": 5.5,
            "exploration_rate": 0.05
        }
        json.dump(data, f)
    
    try:
        # Create RL engine (should load data)
        rl_engine = ReinforcementLearningEngine(data_file=str(temp_file))
        
        # Verify startup logging
        assert any("🔄 RL Parameters Loaded on Startup:" in record.message for record in caplog.records)
        assert any("states=" in record.message for record in caplog.records)
        assert any("episodes=100" in record.message for record in caplog.records)
        assert any("total_reward=5.5" in record.message for record in caplog.records)
        assert any("exploration_rate=0.05" in record.message for record in caplog.records)
        
        # Verify top Q-values are logged
        assert any("📊 Top Q-values by state:" in record.message for record in caplog.records)
        
    finally:
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()


def test_supersmart_parameter_update_logged(caplog):
    """Test that SuperSmart parameter updates are logged after each trade."""
    caplog.set_level(logging.INFO)
    
    # Create temporary data file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = Path(f.name)
    
    try:
        # Create SuperSmart engine
        supersmart = SuperSmartLearning(data_file=str(temp_file))
        
        # Record a winning trade that should trigger parameter update
        supersmart.record_trade(
            asset="BTC",
            side="UP",
            entry_price=Decimal("0.50"),
            exit_price=Decimal("0.58"),
            profit_pct=Decimal("0.16"),  # 16% profit (should raise take-profit)
            hold_time_minutes=5.0,
            exit_reason="take_profit",
            strategy_used="latency",
            confidence=Decimal("0.8")
        )
        
        # Verify parameter update is logged
        assert any("🧠 SuperSmart Parameter Update:" in record.message for record in caplog.records)
        assert any("take_profit_pct" in record.message for record in caplog.records)
        assert any("reason:" in record.message for record in caplog.records)
        
    finally:
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()


def test_supersmart_parameters_loaded_on_startup(caplog):
    """Test that SuperSmart parameters are logged when loaded on startup."""
    caplog.set_level(logging.INFO)
    
    # Create temporary data file with existing data
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = Path(f.name)
        data = {
            "total_trades": 50,
            "total_wins": 35,
            "total_profit": "25.50",
            "consecutive_wins": 3,
            "consecutive_losses": 0,
            "best_win_streak": 5,
            "worst_loss_streak": 2,
            "optimal_params": {
                "take_profit_pct": "0.03",
                "stop_loss_pct": "0.02",
                "time_exit_minutes": 10,
                "position_size_multiplier": "1.2",
                "min_confidence": "0.65"
            },
            "strategy_stats": {},
            "asset_performance": {},
            "winning_patterns": [],
            "losing_patterns": []
        }
        json.dump(data, f)
    
    try:
        # Create SuperSmart engine (should load data)
        supersmart = SuperSmartLearning(data_file=str(temp_file))
        
        # Verify startup logging
        assert any("🔄 SuperSmart Parameters Loaded on Startup:" in record.message for record in caplog.records)
        assert any("trades=50" in record.message for record in caplog.records)
        assert any("win_rate=70.0%" in record.message for record in caplog.records)
        assert any("total_profit=$25.50" in record.message for record in caplog.records)
        
        # Verify optimal parameters are logged
        assert any("📊 Optimal Parameters:" in record.message for record in caplog.records)
        assert any("TP=3.0%" in record.message for record in caplog.records)
        assert any("SL=2.0%" in record.message for record in caplog.records)
        
        # Verify streaks are logged
        assert any("📈 Streaks:" in record.message for record in caplog.records)
        
    finally:
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()


def test_adaptive_parameter_update_logged(caplog):
    """Test that Adaptive parameter updates are logged after learning."""
    caplog.set_level(logging.INFO)
    
    # Create temporary data file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = Path(f.name)
    
    try:
        # Create Adaptive engine
        adaptive = AdaptiveLearningEngine(data_file=str(temp_file))
        
        # Record multiple winning trades to trigger parameter adaptation
        for i in range(20):
            outcome = TradeOutcome(
                timestamp=datetime.now(),
                asset="BTC",
                side="UP",
                entry_price=Decimal("0.50"),
                exit_price=Decimal("0.55"),  # 10% profit
                profit_pct=Decimal("0.10"),
                hold_time_minutes=5.0,
                exit_reason="take_profit",
                strategy_used="latency"
            )
            adaptive.record_trade(outcome)
        
        # Verify parameter update is logged
        assert any("🧠 Adaptive Parameter Update:" in record.message for record in caplog.records)
        assert any("reason:" in record.message for record in caplog.records)
        
    finally:
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()


def test_adaptive_parameters_loaded_on_startup(caplog):
    """Test that Adaptive parameters are logged when loaded on startup."""
    caplog.set_level(logging.INFO)
    
    # Create temporary data file with existing data
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = Path(f.name)
        data = {
            "total_trades": 75,
            "winning_trades": 50,
            "losing_trades": 25,
            "total_profit": "30.25",
            "consecutive_wins": 2,
            "consecutive_losses": 0,
            "current_params": {
                "take_profit_pct": "0.025",
                "stop_loss_pct": "0.018",
                "time_exit_minutes": 11,
                "position_size_multiplier": "1.15",
                "confidence_threshold": "0.62"
            },
            "strategy_performance": {},
            "asset_performance": {},
            "hourly_performance": {},
            "trade_outcomes": []
        }
        json.dump(data, f)
    
    try:
        # Create Adaptive engine (should load data)
        adaptive = AdaptiveLearningEngine(data_file=str(temp_file))
        
        # Verify startup logging
        assert any("🔄 Adaptive Parameters Loaded on Startup:" in record.message for record in caplog.records)
        assert any("trades=75" in record.message for record in caplog.records)
        assert any("win_rate=66.7%" in record.message for record in caplog.records)
        assert any("total_profit=$30.25" in record.message for record in caplog.records)
        
        # Verify current parameters are logged
        assert any("📊 Current Parameters:" in record.message for record in caplog.records)
        assert any("TP=2.50%" in record.message for record in caplog.records)
        assert any("SL=1.80%" in record.message for record in caplog.records)
        
        # Verify streaks are logged
        assert any("📈 Streaks:" in record.message for record in caplog.records)
        
    finally:
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()
