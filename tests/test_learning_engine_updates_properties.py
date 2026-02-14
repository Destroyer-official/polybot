"""
Property-based tests for learning engine updates.

Tests that trade outcomes are recorded to SuperSmart, RL, and Adaptive engines
and that data persists to disk.

**Validates: Requirements 2.8**
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock, patch, call
import tempfile
import os
import json

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def trade_outcome_strategy(draw):
    """Generate random trade outcome data."""
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    side = draw(st.sampled_from(["UP", "DOWN"]))
    strategy = draw(st.sampled_from(["sum_to_one", "latency", "directional"]))
    
    entry_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    exit_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    
    # Calculate profit percentage
    profit_pct = ((exit_price - entry_price) / entry_price) * Decimal("100")
    
    hold_time_minutes = draw(st.floats(min_value=0.5, max_value=15.0, allow_nan=False, allow_infinity=False))
    exit_reason = draw(st.sampled_from([
        "take_profit", "stop_loss", "time_exit", "trailing_stop", 
        "emergency_exit", "market_closing"
    ]))
    
    return {
        "asset": asset,
        "side": side,
        "strategy": strategy,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "profit_pct": profit_pct,
        "hold_time_minutes": hold_time_minutes,
        "exit_reason": exit_reason
    }


# ============================================================================
# HELPER FUNCTION TO CREATE MOCK STRATEGY
# ============================================================================

def create_mock_strategy_with_learning_engines():
    """Create a mock strategy instance with mocked learning engines."""
    mock_clob = MagicMock()
    
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=10.0,
        max_positions=5,
        enable_adaptive_learning=True  # Enable learning engines
    )
    
    # Create mock learning engines
    mock_super_smart = Mock()
    mock_super_smart.record_trade = Mock()
    mock_super_smart._save_data = Mock()
    
    mock_rl_engine = Mock()
    mock_rl_engine.update_q_value = Mock()
    mock_rl_engine._save_q_table = Mock()
    
    mock_adaptive = Mock()
    mock_adaptive.record_trade = Mock()
    mock_adaptive._save_data = Mock()
    
    # Inject mocked learning engines
    strategy.super_smart = mock_super_smart
    strategy.rl_engine = mock_rl_engine
    strategy.adaptive_learning = mock_adaptive
    
    return strategy, mock_super_smart, mock_rl_engine, mock_adaptive


# ============================================================================
# PROPERTY 4: TRADE OUTCOMES RECORDED TO ALL LEARNING ENGINES
# ============================================================================

@given(outcome=trade_outcome_strategy())
@settings(max_examples=100, deadline=None)
def test_property_all_learning_engines_receive_updates(outcome):
    """
    **Validates: Requirements 2.8**
    
    Property 4a: All Three Learning Engines Receive Updates
    
    When a trade outcome is recorded, ALL three learning engines must receive
    the update:
    - SuperSmart (40% weight): Pattern recognition
    - RL Engine (35% weight): Q-learning strategy optimization
    - Adaptive (25% weight): Historical parameter tuning
    """
    strategy, mock_super_smart, mock_rl_engine, mock_adaptive = create_mock_strategy_with_learning_engines()
    
    # Record trade outcome
    strategy._record_trade_outcome(
        asset=outcome["asset"],
        side=outcome["side"],
        strategy=outcome["strategy"],
        entry_price=outcome["entry_price"],
        exit_price=outcome["exit_price"],
        profit_pct=outcome["profit_pct"],
        hold_time_minutes=outcome["hold_time_minutes"],
        exit_reason=outcome["exit_reason"]
    )
    
    # Verify: SuperSmart received update
    assert mock_super_smart.record_trade.called, \
        "SuperSmart learning engine should receive trade outcome"
    
    # Verify: RL Engine received update
    assert mock_rl_engine.update_q_value.called, \
        "RL engine should receive trade outcome"
    
    # Verify: Adaptive Learning received update
    assert mock_adaptive.record_trade.called, \
        "Adaptive learning engine should receive trade outcome"
    
    # Verify: All three engines were called exactly once
    assert mock_super_smart.record_trade.call_count == 1, \
        "SuperSmart should be called exactly once"
    assert mock_rl_engine.update_q_value.call_count == 1, \
        "RL engine should be called exactly once"
    assert mock_adaptive.record_trade.call_count == 1, \
        "Adaptive learning should be called exactly once"


@given(outcome=trade_outcome_strategy())
@settings(max_examples=100, deadline=None)
def test_property_learning_engines_receive_correct_data(outcome):
    """
    **Validates: Requirements 2.8**
    
    Property 4b: Learning Engines Receive Correct Data
    
    Each learning engine must receive the correct trade outcome data with
    proper parameters.
    """
    strategy, mock_super_smart, mock_rl_engine, mock_adaptive = create_mock_strategy_with_learning_engines()
    
    # Record trade outcome
    strategy._record_trade_outcome(
        asset=outcome["asset"],
        side=outcome["side"],
        strategy=outcome["strategy"],
        entry_price=outcome["entry_price"],
        exit_price=outcome["exit_price"],
        profit_pct=outcome["profit_pct"],
        hold_time_minutes=outcome["hold_time_minutes"],
        exit_reason=outcome["exit_reason"]
    )
    
    # Verify: SuperSmart received correct parameters
    super_smart_call = mock_super_smart.record_trade.call_args
    assert super_smart_call is not None, "SuperSmart should be called"
    
    # Check keyword arguments
    kwargs = super_smart_call[1]
    assert kwargs["asset"] == outcome["asset"], "SuperSmart should receive correct asset"
    assert kwargs["side"] == outcome["side"], "SuperSmart should receive correct side"
    assert kwargs["entry_price"] == outcome["entry_price"], "SuperSmart should receive correct entry_price"
    assert kwargs["exit_price"] == outcome["exit_price"], "SuperSmart should receive correct exit_price"
    assert kwargs["profit_pct"] == outcome["profit_pct"], "SuperSmart should receive correct profit_pct"
    assert kwargs["strategy_used"] == outcome["strategy"], "SuperSmart should receive correct strategy"
    
    # Verify: RL Engine received correct parameters
    rl_call = mock_rl_engine.update_q_value.call_args
    assert rl_call is not None, "RL engine should be called"
    
    rl_kwargs = rl_call[1]
    assert rl_kwargs["asset"] == outcome["asset"], "RL engine should receive correct asset"
    assert rl_kwargs["strategy"] == outcome["strategy"], "RL engine should receive correct strategy"
    assert rl_kwargs["reward"] == float(outcome["profit_pct"]), "RL engine should receive profit as reward"
    
    # Verify: Adaptive Learning received correct parameters
    adaptive_call = mock_adaptive.record_trade.call_args
    assert adaptive_call is not None, "Adaptive learning should be called"
    
    # Adaptive receives a TradeOutcome object
    adaptive_args = adaptive_call[0]
    assert len(adaptive_args) > 0, "Adaptive learning should receive TradeOutcome object"
    
    trade_outcome_obj = adaptive_args[0]
    assert trade_outcome_obj.asset == outcome["asset"], "Adaptive should receive correct asset"
    assert trade_outcome_obj.side == outcome["side"], "Adaptive should receive correct side"
    assert trade_outcome_obj.entry_price == outcome["entry_price"], "Adaptive should receive correct entry_price"
    assert trade_outcome_obj.exit_price == outcome["exit_price"], "Adaptive should receive correct exit_price"
    assert trade_outcome_obj.profit_pct == outcome["profit_pct"], "Adaptive should receive correct profit_pct"
    assert trade_outcome_obj.strategy_used == outcome["strategy"], "Adaptive should receive correct strategy"


@given(outcomes=st.lists(trade_outcome_strategy(), min_size=1, max_size=10))
@settings(max_examples=50, deadline=None)
def test_property_multiple_outcomes_recorded_sequentially(outcomes):
    """
    **Validates: Requirements 2.8**
    
    Property 4c: Multiple Trade Outcomes Recorded Sequentially
    
    When multiple trade outcomes are recorded, each one should be properly
    recorded to all three learning engines in sequence.
    """
    strategy, mock_super_smart, mock_rl_engine, mock_adaptive = create_mock_strategy_with_learning_engines()
    
    # Record multiple trade outcomes
    for outcome in outcomes:
        strategy._record_trade_outcome(
            asset=outcome["asset"],
            side=outcome["side"],
            strategy=outcome["strategy"],
            entry_price=outcome["entry_price"],
            exit_price=outcome["exit_price"],
            profit_pct=outcome["profit_pct"],
            hold_time_minutes=outcome["hold_time_minutes"],
            exit_reason=outcome["exit_reason"]
        )
    
    # Verify: Each engine was called once per outcome
    expected_calls = len(outcomes)
    
    assert mock_super_smart.record_trade.call_count == expected_calls, \
        f"SuperSmart should be called {expected_calls} times for {expected_calls} outcomes"
    
    assert mock_rl_engine.update_q_value.call_count == expected_calls, \
        f"RL engine should be called {expected_calls} times for {expected_calls} outcomes"
    
    assert mock_adaptive.record_trade.call_count == expected_calls, \
        f"Adaptive learning should be called {expected_calls} times for {expected_calls} outcomes"


@given(outcome=trade_outcome_strategy())
@settings(max_examples=50, deadline=None)
def test_property_learning_engines_persist_data_to_disk(outcome):
    """
    **Validates: Requirements 2.8**
    
    Property 4d: Learning Engine Data Persists to Disk
    
    After recording a trade outcome, each learning engine should persist its
    updated data to disk. This ensures data survives bot restarts.
    """
    # Create temporary files for each engine
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as super_smart_file, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as rl_file, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as adaptive_file:
        
        super_smart_path = super_smart_file.name
        rl_path = rl_file.name
        adaptive_path = adaptive_file.name
    
    try:
        # Create real learning engines with temporary files
        from src.super_smart_learning import SuperSmartLearning
        from src.reinforcement_learning_engine import ReinforcementLearningEngine
        from src.adaptive_learning_engine import AdaptiveLearningEngine, TradeOutcome
        
        super_smart = SuperSmartLearning(data_file=super_smart_path)
        rl_engine = ReinforcementLearningEngine(data_file=rl_path)
        adaptive = AdaptiveLearningEngine(data_file=adaptive_path)
        
        # Record trade outcome to each engine
        super_smart.record_trade(
            asset=outcome["asset"],
            side=outcome["side"],
            entry_price=outcome["entry_price"],
            exit_price=outcome["exit_price"],
            profit_pct=outcome["profit_pct"],
            hold_time_minutes=outcome["hold_time_minutes"],
            exit_reason=outcome["exit_reason"],
            strategy_used=outcome["strategy"]
        )
        
        rl_engine.update_q_value(
            asset=outcome["asset"],
            strategy=outcome["strategy"],
            reward=float(outcome["profit_pct"])
        )
        
        trade_outcome_obj = TradeOutcome(
            timestamp=datetime.now(timezone.utc),
            asset=outcome["asset"],
            side=outcome["side"],
            entry_price=outcome["entry_price"],
            exit_price=outcome["exit_price"],
            profit_pct=outcome["profit_pct"],
            hold_time_minutes=outcome["hold_time_minutes"],
            exit_reason=outcome["exit_reason"],
            strategy_used=outcome["strategy"],
            time_of_day=datetime.now(timezone.utc).hour
        )
        adaptive.record_trade(trade_outcome_obj)
        
        # Verify: All files exist and contain data
        assert os.path.exists(super_smart_path), "SuperSmart data file should exist"
        assert os.path.exists(rl_path), "RL engine data file should exist"
        assert os.path.exists(adaptive_path), "Adaptive learning data file should exist"
        
        # Verify: Files are not empty
        assert os.path.getsize(super_smart_path) > 0, "SuperSmart data file should not be empty"
        assert os.path.getsize(rl_path) > 0, "RL engine data file should not be empty"
        assert os.path.getsize(adaptive_path) > 0, "Adaptive learning data file should not be empty"
        
        # Verify: Files contain valid JSON
        with open(super_smart_path, 'r') as f:
            super_smart_data = json.load(f)
            assert "total_trades" in super_smart_data, "SuperSmart data should contain total_trades"
            assert super_smart_data["total_trades"] >= 1, "SuperSmart should have recorded at least 1 trade"
        
        with open(rl_path, 'r') as f:
            rl_data = json.load(f)
            assert "q_table" in rl_data, "RL data should contain q_table"
        
        with open(adaptive_path, 'r') as f:
            adaptive_data = json.load(f)
            assert "total_trades" in adaptive_data, "Adaptive data should contain total_trades"
            assert adaptive_data["total_trades"] >= 1, "Adaptive should have recorded at least 1 trade"
        
    finally:
        # Cleanup temporary files
        for path in [super_smart_path, rl_path, adaptive_path]:
            if os.path.exists(path):
                os.unlink(path)


@given(outcome=trade_outcome_strategy())
@settings(max_examples=50, deadline=None)
def test_property_learning_engines_handle_errors_gracefully(outcome):
    """
    **Validates: Requirements 2.8**
    
    Property 4e: Learning Engines Handle Errors Gracefully
    
    If one learning engine fails to record a trade outcome, the other engines
    should still receive their updates. No single engine failure should block
    the entire recording process.
    """
    strategy, mock_super_smart, mock_rl_engine, mock_adaptive = create_mock_strategy_with_learning_engines()
    
    # Make SuperSmart raise an exception
    mock_super_smart.record_trade.side_effect = Exception("SuperSmart error")
    
    # Record trade outcome (should not raise exception)
    try:
        strategy._record_trade_outcome(
            asset=outcome["asset"],
            side=outcome["side"],
            strategy=outcome["strategy"],
            entry_price=outcome["entry_price"],
            exit_price=outcome["exit_price"],
            profit_pct=outcome["profit_pct"],
            hold_time_minutes=outcome["hold_time_minutes"],
            exit_reason=outcome["exit_reason"]
        )
    except Exception as e:
        pytest.fail(f"_record_trade_outcome should not raise exception even if one engine fails: {e}")
    
    # Verify: SuperSmart was called (but failed)
    assert mock_super_smart.record_trade.called, "SuperSmart should be called"
    
    # Verify: RL Engine and Adaptive still received updates
    assert mock_rl_engine.update_q_value.called, \
        "RL engine should still receive update even if SuperSmart fails"
    assert mock_adaptive.record_trade.called, \
        "Adaptive learning should still receive update even if SuperSmart fails"


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("TESTING: Trade Outcomes Recorded to All Learning Engines")
    print("Task 1.10 - Property 4 - Validates Requirement 2.8")
    print("=" * 80)
    print()
    
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
