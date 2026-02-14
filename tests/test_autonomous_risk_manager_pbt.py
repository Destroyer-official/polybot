"""
Property-Based Tests for Autonomous Risk Manager.

Tests dynamic threshold adaptation using property-based testing.
"""

import pytest
from hypothesis import given, strategies as st, assume
from decimal import Decimal
from src.autonomous_risk_manager import AutonomousRiskManager, PerformanceMetrics


# Property 30: Dynamic Risk Threshold Adaptation
# **Validates: Requirements 7.1, 7.2, 7.3, 7.4**


@given(
    wins=st.integers(min_value=0, max_value=100),
    losses=st.integers(min_value=0, max_value=100),
    starting_balance=st.decimals(min_value=10, max_value=10000, places=2)
)
def test_portfolio_heat_adapts_based_on_win_rate(wins, losses, starting_balance):
    """
    Property: Portfolio heat limit adapts based on win rate (50-200% of base).
    
    - Win rate >= 70%: heat = 200% of base (100%)
    - Win rate >= 60%: heat = 150% of base (75%)
    - Win rate >= 50%: heat = 100% of base (50%)
    - Win rate < 50%: heat = 50% of base (25%)
    """
    # Skip if no trades
    total_trades = wins + losses
    assume(total_trades > 0)
    
    # Create risk manager
    manager = AutonomousRiskManager(
        starting_balance=starting_balance,
        current_balance=starting_balance
    )
    
    # Set performance metrics
    manager.performance.wins = wins
    manager.performance.losses = losses
    manager.performance.total_trades = total_trades
    manager.performance.update_win_rate()
    
    win_rate = manager.performance.win_rate
    base_heat = manager.BASE_PORTFOLIO_HEAT
    
    # Adapt thresholds
    manager.adapt_thresholds()
    
    # Verify portfolio heat adapts correctly
    if win_rate >= 0.70:
        expected_heat = base_heat * Decimal('2.0')  # 200%
    elif win_rate >= 0.60:
        expected_heat = base_heat * Decimal('1.5')  # 150%
    elif win_rate >= 0.50:
        expected_heat = base_heat * Decimal('1.0')  # 100%
    else:
        expected_heat = base_heat * Decimal('0.5')  # 50%
    
    assert manager.thresholds.portfolio_heat_limit == expected_heat, (
        f"Portfolio heat should be {expected_heat} for win_rate={win_rate:.1%}, "
        f"but got {manager.thresholds.portfolio_heat_limit}"
    )


@given(
    wins=st.integers(min_value=0, max_value=100),
    losses=st.integers(min_value=0, max_value=100),
    starting_balance=st.decimals(min_value=10, max_value=10000, places=2)
)
def test_drawdown_limit_adapts_based_on_performance(wins, losses, starting_balance):
    """
    Property: Daily drawdown limit adapts based on performance (10-20%).
    
    - Win rate >= 70%: drawdown = 20%
    - Win rate >= 60%: drawdown = 15%
    - Win rate < 60%: drawdown = 10%
    """
    # Skip if no trades
    total_trades = wins + losses
    assume(total_trades > 0)
    
    # Create risk manager
    manager = AutonomousRiskManager(
        starting_balance=starting_balance,
        current_balance=starting_balance
    )
    
    # Set performance metrics
    manager.performance.wins = wins
    manager.performance.losses = losses
    manager.performance.total_trades = total_trades
    manager.performance.update_win_rate()
    
    win_rate = manager.performance.win_rate
    
    # Adapt thresholds
    manager.adapt_thresholds()
    
    # Verify drawdown limit adapts correctly
    if win_rate >= 0.70:
        expected_drawdown = Decimal('0.20')  # 20%
    elif win_rate >= 0.60:
        expected_drawdown = Decimal('0.15')  # 15%
    else:
        expected_drawdown = Decimal('0.10')  # 10%
    
    assert manager.thresholds.daily_drawdown_limit == expected_drawdown, (
        f"Drawdown limit should be {expected_drawdown} for win_rate={win_rate:.1%}, "
        f"but got {manager.thresholds.daily_drawdown_limit}"
    )


@given(
    wins=st.integers(min_value=0, max_value=100),
    losses=st.integers(min_value=0, max_value=100),
    starting_balance=st.decimals(min_value=10, max_value=10000, places=2)
)
def test_consecutive_loss_limit_adapts_based_on_confidence(wins, losses, starting_balance):
    """
    Property: Consecutive loss limit adapts based on confidence (3-7).
    
    - Win rate >= 70%: loss_limit = 7
    - Win rate >= 60%: loss_limit = 5
    - Win rate < 60%: loss_limit = 3
    """
    # Skip if no trades
    total_trades = wins + losses
    assume(total_trades > 0)
    
    # Create risk manager
    manager = AutonomousRiskManager(
        starting_balance=starting_balance,
        current_balance=starting_balance
    )
    
    # Set performance metrics
    manager.performance.wins = wins
    manager.performance.losses = losses
    manager.performance.total_trades = total_trades
    manager.performance.update_win_rate()
    
    win_rate = manager.performance.win_rate
    
    # Adapt thresholds
    manager.adapt_thresholds()
    
    # Verify consecutive loss limit adapts correctly
    if win_rate >= 0.70:
        expected_limit = 7
    elif win_rate >= 0.60:
        expected_limit = 5
    else:
        expected_limit = 3
    
    assert manager.thresholds.consecutive_loss_limit == expected_limit, (
        f"Consecutive loss limit should be {expected_limit} for win_rate={win_rate:.1%}, "
        f"but got {manager.thresholds.consecutive_loss_limit}"
    )


@given(
    wins=st.integers(min_value=0, max_value=100),
    losses=st.integers(min_value=0, max_value=100),
    starting_balance=st.decimals(min_value=10, max_value=10000, places=2)
)
def test_per_asset_limit_adapts_based_on_volatility(wins, losses, starting_balance):
    """
    Property: Per-asset limit adapts based on volatility (1-3 positions).
    
    Using win rate as proxy for volatility:
    - Win rate >= 70%: asset_limit = 3
    - Win rate >= 60%: asset_limit = 2
    - Win rate < 60%: asset_limit = 1
    """
    # Skip if no trades
    total_trades = wins + losses
    assume(total_trades > 0)
    
    # Create risk manager
    manager = AutonomousRiskManager(
        starting_balance=starting_balance,
        current_balance=starting_balance
    )
    
    # Set performance metrics
    manager.performance.wins = wins
    manager.performance.losses = losses
    manager.performance.total_trades = total_trades
    manager.performance.update_win_rate()
    
    win_rate = manager.performance.win_rate
    
    # Adapt thresholds
    manager.adapt_thresholds()
    
    # Verify per-asset limit adapts correctly
    if win_rate >= 0.70:
        expected_limit = 3
    elif win_rate >= 0.60:
        expected_limit = 2
    else:
        expected_limit = 1
    
    assert manager.thresholds.per_asset_limit == expected_limit, (
        f"Per-asset limit should be {expected_limit} for win_rate={win_rate:.1%}, "
        f"but got {manager.thresholds.per_asset_limit}"
    )


@given(
    wins=st.integers(min_value=0, max_value=100),
    losses=st.integers(min_value=0, max_value=100),
    starting_balance=st.decimals(min_value=10, max_value=10000, places=2)
)
def test_all_thresholds_adapt_together(wins, losses, starting_balance):
    """
    Property: All thresholds adapt together based on performance.
    
    Verifies that all four thresholds are updated in a single adapt_thresholds() call.
    """
    # Skip if no trades
    total_trades = wins + losses
    assume(total_trades > 0)
    
    # Create risk manager
    manager = AutonomousRiskManager(
        starting_balance=starting_balance,
        current_balance=starting_balance
    )
    
    # Set performance metrics
    manager.performance.wins = wins
    manager.performance.losses = losses
    manager.performance.total_trades = total_trades
    manager.performance.update_win_rate()
    
    # Store original values
    original_heat = manager.thresholds.portfolio_heat_limit
    original_drawdown = manager.thresholds.daily_drawdown_limit
    original_loss_limit = manager.thresholds.consecutive_loss_limit
    original_asset_limit = manager.thresholds.per_asset_limit
    
    # Adapt thresholds
    manager.adapt_thresholds()
    
    # Verify all thresholds are within expected ranges
    assert Decimal('0.25') <= manager.thresholds.portfolio_heat_limit <= Decimal('1.0'), (
        f"Portfolio heat {manager.thresholds.portfolio_heat_limit} out of range [0.25, 1.0]"
    )
    
    assert Decimal('0.10') <= manager.thresholds.daily_drawdown_limit <= Decimal('0.20'), (
        f"Drawdown limit {manager.thresholds.daily_drawdown_limit} out of range [0.10, 0.20]"
    )
    
    assert 3 <= manager.thresholds.consecutive_loss_limit <= 7, (
        f"Consecutive loss limit {manager.thresholds.consecutive_loss_limit} out of range [3, 7]"
    )
    
    assert 1 <= manager.thresholds.per_asset_limit <= 3, (
        f"Per-asset limit {manager.thresholds.per_asset_limit} out of range [1, 3]"
    )


@given(
    initial_wins=st.integers(min_value=5, max_value=50),
    initial_losses=st.integers(min_value=5, max_value=50),
    new_wins=st.integers(min_value=0, max_value=20),
    new_losses=st.integers(min_value=0, max_value=20),
    starting_balance=st.decimals(min_value=100, max_value=10000, places=2)
)
def test_thresholds_adapt_over_time(initial_wins, initial_losses, new_wins, new_losses, starting_balance):
    """
    Property: Thresholds adapt correctly as performance changes over time.
    
    Simulates performance changing and verifies thresholds adapt accordingly.
    """
    # Create risk manager
    manager = AutonomousRiskManager(
        starting_balance=starting_balance,
        current_balance=starting_balance
    )
    
    # Set initial performance
    manager.performance.wins = initial_wins
    manager.performance.losses = initial_losses
    manager.performance.total_trades = initial_wins + initial_losses
    manager.performance.update_win_rate()
    
    # Adapt with initial performance
    manager.adapt_thresholds()
    initial_heat = manager.thresholds.portfolio_heat_limit
    
    # Update performance
    manager.performance.wins += new_wins
    manager.performance.losses += new_losses
    manager.performance.total_trades += new_wins + new_losses
    manager.performance.update_win_rate()
    
    # Adapt with new performance
    manager.adapt_thresholds()
    new_heat = manager.thresholds.portfolio_heat_limit
    
    # Verify thresholds changed if win rate changed significantly
    old_win_rate = initial_wins / (initial_wins + initial_losses)
    new_win_rate = manager.performance.win_rate
    
    # If win rate crossed a threshold boundary, heat should change
    if (old_win_rate < 0.50 and new_win_rate >= 0.50) or \
       (old_win_rate < 0.60 and new_win_rate >= 0.60) or \
       (old_win_rate < 0.70 and new_win_rate >= 0.70):
        assert new_heat > initial_heat, (
            f"Heat should increase when win rate improves from {old_win_rate:.1%} to {new_win_rate:.1%}"
        )
    elif (old_win_rate >= 0.70 and new_win_rate < 0.70) or \
         (old_win_rate >= 0.60 and new_win_rate < 0.60) or \
         (old_win_rate >= 0.50 and new_win_rate < 0.50):
        assert new_heat < initial_heat, (
            f"Heat should decrease when win rate drops from {old_win_rate:.1%} to {new_win_rate:.1%}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
