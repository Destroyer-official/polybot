"""
Task 8.1: Test enhanced trade statistics tracking

Tests for per-strategy, per-asset, execution time, and exit reason tracking.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy


@pytest.fixture
def strategy():
    """Create a strategy instance for testing."""
    with patch('src.fifteen_min_crypto_strategy.ClobClient'):
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=Mock(),
            trade_size=5.0,
            dry_run=True,
            enable_adaptive_learning=False
        )
        return strategy


def test_initial_stats_structure(strategy):
    """Test that initial stats structure includes all Task 8.1 fields."""
    # Check per-strategy stats exist
    assert "per_strategy" in strategy.stats
    assert isinstance(strategy.stats["per_strategy"], dict)
    
    # Check per-asset stats exist
    assert "per_asset" in strategy.stats
    assert isinstance(strategy.stats["per_asset"], dict)
    
    # Check exit reasons tracking exists
    assert "exit_reasons" in strategy.stats
    assert isinstance(strategy.stats["exit_reasons"], dict)
    
    # Check execution times tracking exists
    assert "execution_times" in strategy.stats
    assert "per_strategy" in strategy.stats["execution_times"]
    assert "per_asset" in strategy.stats["execution_times"]


def test_track_execution_time_per_strategy(strategy):
    """Test execution time tracking per strategy."""
    # Track execution times for different strategies
    strategy._track_execution_time(500.0, "sum_to_one", "BTC")
    strategy._track_execution_time(750.0, "sum_to_one", "ETH")
    strategy._track_execution_time(1200.0, "latency", "BTC")
    
    # Verify per-strategy tracking
    assert "sum_to_one" in strategy.stats["execution_times"]["per_strategy"]
    assert "latency" in strategy.stats["execution_times"]["per_strategy"]
    
    sum_to_one_times = strategy.stats["execution_times"]["per_strategy"]["sum_to_one"]
    assert len(sum_to_one_times) == 2
    assert 500.0 in sum_to_one_times
    assert 750.0 in sum_to_one_times
    
    latency_times = strategy.stats["execution_times"]["per_strategy"]["latency"]
    assert len(latency_times) == 1
    assert 1200.0 in latency_times


def test_track_execution_time_per_asset(strategy):
    """Test execution time tracking per asset."""
    # Track execution times for different assets
    strategy._track_execution_time(500.0, "sum_to_one", "BTC")
    strategy._track_execution_time(600.0, "latency", "BTC")
    strategy._track_execution_time(750.0, "directional", "ETH")
    
    # Verify per-asset tracking
    assert "BTC" in strategy.stats["execution_times"]["per_asset"]
    assert "ETH" in strategy.stats["execution_times"]["per_asset"]
    
    btc_times = strategy.stats["execution_times"]["per_asset"]["BTC"]
    assert len(btc_times) == 2
    assert 500.0 in btc_times
    assert 600.0 in btc_times
    
    eth_times = strategy.stats["execution_times"]["per_asset"]["ETH"]
    assert len(eth_times) == 1
    assert 750.0 in eth_times


def test_track_slow_executions(strategy):
    """Test that slow executions (>1s) are tracked."""
    initial_slow = strategy.stats["slow_executions"]
    
    # Track a fast execution
    strategy._track_execution_time(500.0, "sum_to_one", "BTC")
    assert strategy.stats["slow_executions"] == initial_slow
    
    # Track a slow execution
    strategy._track_execution_time(1500.0, "latency", "ETH")
    assert strategy.stats["slow_executions"] == initial_slow + 1


def test_record_trade_outcome_per_strategy(strategy):
    """Test per-strategy statistics tracking."""
    # Record winning trade for sum_to_one
    strategy._record_trade_outcome(
        asset="BTC",
        side="UP",
        strategy="sum_to_one",
        entry_price=Decimal("0.50"),
        exit_price=Decimal("0.52"),
        profit_pct=Decimal("0.04"),  # 4% profit
        hold_time_minutes=5.0,
        exit_reason="take_profit",
        position_size=Decimal("10.0")
    )
    
    # Verify per-strategy stats
    assert "sum_to_one" in strategy.stats["per_strategy"]
    sum_to_one_stats = strategy.stats["per_strategy"]["sum_to_one"]
    
    assert sum_to_one_stats["total_trades"] == 1
    assert sum_to_one_stats["wins"] == 1
    assert sum_to_one_stats["losses"] == 0
    assert sum_to_one_stats["win_rate"] == 100.0
    assert sum_to_one_stats["total_profit"] == Decimal("0.04")
    assert sum_to_one_stats["roi"] == 4.0
    
    # Record losing trade for latency
    strategy._record_trade_outcome(
        asset="ETH",
        side="DOWN",
        strategy="latency",
        entry_price=Decimal("0.60"),
        exit_price=Decimal("0.58"),
        profit_pct=Decimal("-0.033"),  # -3.3% loss
        hold_time_minutes=8.0,
        exit_reason="stop_loss",
        position_size=Decimal("15.0")
    )
    
    # Verify latency stats
    assert "latency" in strategy.stats["per_strategy"]
    latency_stats = strategy.stats["per_strategy"]["latency"]
    
    assert latency_stats["total_trades"] == 1
    assert latency_stats["wins"] == 0
    assert latency_stats["losses"] == 1
    assert latency_stats["win_rate"] == 0.0
    assert latency_stats["total_profit"] == Decimal("-0.033")


def test_record_trade_outcome_per_asset(strategy):
    """Test per-asset statistics tracking."""
    # Record winning trade for BTC
    strategy._record_trade_outcome(
        asset="BTC",
        side="UP",
        strategy="sum_to_one",
        entry_price=Decimal("0.50"),
        exit_price=Decimal("0.52"),
        profit_pct=Decimal("0.04"),
        hold_time_minutes=5.0,
        exit_reason="take_profit",
        position_size=Decimal("10.0")
    )
    
    # Verify per-asset stats
    assert "BTC" in strategy.stats["per_asset"]
    btc_stats = strategy.stats["per_asset"]["BTC"]
    
    assert btc_stats["total_trades"] == 1
    assert btc_stats["wins"] == 1
    assert btc_stats["losses"] == 0
    assert btc_stats["win_rate"] == 100.0
    assert btc_stats["total_profit"] == Decimal("0.04")
    
    # Record another trade for BTC (losing)
    strategy._record_trade_outcome(
        asset="BTC",
        side="DOWN",
        strategy="latency",
        entry_price=Decimal("0.55"),
        exit_price=Decimal("0.53"),
        profit_pct=Decimal("-0.036"),
        hold_time_minutes=7.0,
        exit_reason="stop_loss",
        position_size=Decimal("12.0")
    )
    
    # Verify updated BTC stats
    btc_stats = strategy.stats["per_asset"]["BTC"]
    assert btc_stats["total_trades"] == 2
    assert btc_stats["wins"] == 1
    assert btc_stats["losses"] == 1
    assert btc_stats["win_rate"] == 50.0


def test_exit_reason_tracking(strategy):
    """Test exit reason tracking."""
    # Record trades with different exit reasons
    strategy._record_trade_outcome(
        asset="BTC",
        side="UP",
        strategy="sum_to_one",
        entry_price=Decimal("0.50"),
        exit_price=Decimal("0.52"),
        profit_pct=Decimal("0.04"),
        hold_time_minutes=5.0,
        exit_reason="take_profit",
        position_size=Decimal("10.0")
    )
    
    strategy._record_trade_outcome(
        asset="ETH",
        side="DOWN",
        strategy="latency",
        entry_price=Decimal("0.60"),
        exit_price=Decimal("0.58"),
        profit_pct=Decimal("-0.033"),
        hold_time_minutes=8.0,
        exit_reason="stop_loss",
        position_size=Decimal("15.0")
    )
    
    strategy._record_trade_outcome(
        asset="SOL",
        side="UP",
        strategy="directional",
        entry_price=Decimal("0.45"),
        exit_price=Decimal("0.46"),
        profit_pct=Decimal("0.022"),
        hold_time_minutes=12.0,
        exit_reason="time_exit",
        position_size=Decimal("8.0")
    )
    
    # Verify exit reasons are tracked
    assert "take_profit" in strategy.stats["exit_reasons"]
    assert strategy.stats["exit_reasons"]["take_profit"] == 1
    
    assert "stop_loss" in strategy.stats["exit_reasons"]
    assert strategy.stats["exit_reasons"]["stop_loss"] == 1
    
    assert "time_exit" in strategy.stats["exit_reasons"]
    assert strategy.stats["exit_reasons"]["time_exit"] == 1


def test_get_comprehensive_stats(strategy):
    """Test comprehensive stats retrieval."""
    # Record some trades
    strategy._track_execution_time(500.0, "sum_to_one", "BTC")
    strategy._record_trade_outcome(
        asset="BTC",
        side="UP",
        strategy="sum_to_one",
        entry_price=Decimal("0.50"),
        exit_price=Decimal("0.52"),
        profit_pct=Decimal("0.04"),
        hold_time_minutes=5.0,
        exit_reason="take_profit",
        position_size=Decimal("10.0")
    )
    
    # Get comprehensive stats
    stats = strategy.get_comprehensive_stats()
    
    # Verify structure
    assert "overall" in stats
    assert "per_strategy" in stats
    assert "per_asset" in stats
    assert "exit_reasons" in stats
    assert "execution_times" in stats
    
    # Verify overall stats
    assert "total_trades" in stats["overall"]
    assert "win_rate" in stats["overall"]
    assert "avg_execution_time_ms" in stats["overall"]
    
    # Verify per-strategy stats include execution times
    assert "sum_to_one" in stats["per_strategy"]
    assert "avg_execution_time_ms" in stats["per_strategy"]["sum_to_one"]
    
    # Verify execution time breakdown
    assert "per_strategy" in stats["execution_times"]
    assert "sum_to_one" in stats["execution_times"]["per_strategy"]
    assert "avg" in stats["execution_times"]["per_strategy"]["sum_to_one"]
    assert "min" in stats["execution_times"]["per_strategy"]["sum_to_one"]
    assert "max" in stats["execution_times"]["per_strategy"]["sum_to_one"]


def test_multiple_strategies_and_assets(strategy):
    """Test tracking across multiple strategies and assets."""
    # Record trades for different strategy/asset combinations
    trades = [
        ("BTC", "sum_to_one", Decimal("0.04"), "take_profit", 500.0),
        ("BTC", "latency", Decimal("-0.02"), "stop_loss", 750.0),
        ("ETH", "sum_to_one", Decimal("0.03"), "take_profit", 600.0),
        ("ETH", "directional", Decimal("0.05"), "take_profit", 900.0),
        ("SOL", "latency", Decimal("-0.01"), "time_exit", 1100.0),
    ]
    
    for asset, strat, profit, reason, exec_time in trades:
        strategy._track_execution_time(exec_time, strat, asset)
        strategy._record_trade_outcome(
            asset=asset,
            side="UP",
            strategy=strat,
            entry_price=Decimal("0.50"),
            exit_price=Decimal("0.50") + profit,
            profit_pct=profit,
            hold_time_minutes=5.0,
            exit_reason=reason,
            position_size=Decimal("10.0")
        )
    
    # Verify all strategies tracked
    assert len(strategy.stats["per_strategy"]) == 3
    assert "sum_to_one" in strategy.stats["per_strategy"]
    assert "latency" in strategy.stats["per_strategy"]
    assert "directional" in strategy.stats["per_strategy"]
    
    # Verify all assets tracked
    assert len(strategy.stats["per_asset"]) == 3
    assert "BTC" in strategy.stats["per_asset"]
    assert "ETH" in strategy.stats["per_asset"]
    assert "SOL" in strategy.stats["per_asset"]
    
    # Verify win rates calculated correctly
    sum_to_one_stats = strategy.stats["per_strategy"]["sum_to_one"]
    assert sum_to_one_stats["total_trades"] == 2
    assert sum_to_one_stats["wins"] == 2
    assert sum_to_one_stats["win_rate"] == 100.0
    
    latency_stats = strategy.stats["per_strategy"]["latency"]
    assert latency_stats["total_trades"] == 2
    assert latency_stats["losses"] == 2
    assert latency_stats["win_rate"] == 0.0
    
    # Verify execution times tracked per strategy
    assert len(strategy.stats["execution_times"]["per_strategy"]["sum_to_one"]) == 2
    assert len(strategy.stats["execution_times"]["per_strategy"]["latency"]) == 2
    assert len(strategy.stats["execution_times"]["per_strategy"]["directional"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
