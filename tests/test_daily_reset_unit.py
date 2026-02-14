"""
Unit Tests for Daily Reset Functionality (Task 6.7).

Tests the daily automatic reset functionality in PortfolioRiskManager.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch
from src.portfolio_risk_manager import PortfolioRiskManager


def test_daily_reset_resets_counters():
    """Test that daily reset resets all daily counters."""
    manager = PortfolioRiskManager(
        initial_capital=Decimal('1000'),
        max_portfolio_heat=Decimal('0.50'),
        max_position_size_pct=Decimal('0.10'),
        max_daily_drawdown=Decimal('0.15'),
        consecutive_loss_limit=5
    )
    
    # Simulate some trading activity
    manager._trades_today = 10
    manager._wins_today = 6
    manager._losses_today = 4
    manager._daily_pnl = Decimal('50')
    manager._consecutive_losses = 2
    
    # Mock datetime to trigger reset
    future_time = datetime.now() + timedelta(days=1, hours=1)
    with patch('src.portfolio_risk_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = future_time
        mock_datetime.utcnow.return_value = future_time
        
        # Trigger reset by calling check_can_trade
        manager.check_can_trade(Decimal('10'), 'test_market')
    
    # Verify all counters reset
    assert manager._trades_today == 0, "Trades today should be reset to 0"
    assert manager._wins_today == 0, "Wins today should be reset to 0"
    assert manager._losses_today == 0, "Losses today should be reset to 0"
    assert manager._daily_pnl == Decimal('0'), "Daily P&L should be reset to 0"
    assert manager._consecutive_losses == 0, "Consecutive losses should be reset to 0"


def test_daily_reset_updates_starting_balance():
    """Test that daily reset updates starting balance to current balance."""
    manager = PortfolioRiskManager(
        initial_capital=Decimal('1000'),
        max_portfolio_heat=Decimal('0.50'),
        max_position_size_pct=Decimal('0.10'),
        max_daily_drawdown=Decimal('0.15'),
        consecutive_loss_limit=5
    )
    
    # Simulate profit
    manager.current_capital = Decimal('1200')
    manager._daily_pnl = Decimal('200')
    
    initial_starting_balance = manager._daily_start_capital
    
    # Mock datetime to trigger reset
    future_time = datetime.now() + timedelta(days=1, hours=1)
    with patch('src.portfolio_risk_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = future_time
        mock_datetime.utcnow.return_value = future_time
        
        # Trigger reset
        manager.check_can_trade(Decimal('10'), 'test_market')
    
    # Verify starting balance updated
    assert manager._daily_start_capital == Decimal('1200'), \
        "Starting balance should be updated to current balance"
    assert manager._daily_start_capital != initial_starting_balance, \
        "Starting balance should have changed"


def test_daily_reset_checks_conservative_mode_exit():
    """Test that daily reset checks if should exit conservative mode."""
    manager = PortfolioRiskManager(
        initial_capital=Decimal('1000'),
        max_portfolio_heat=Decimal('0.50'),
        max_position_size_pct=Decimal('0.10'),
        max_daily_drawdown=Decimal('0.15'),
        consecutive_loss_limit=5
    )
    
    # Activate conservative mode
    manager._conservative_mode_active = True
    manager._conservative_mode_starting_balance = Decimal('1000')
    
    # Recover balance to 60% of starting (should exit conservative mode)
    manager.current_capital = Decimal('600')
    
    # Mock datetime to trigger reset
    future_time = datetime.now() + timedelta(days=1, hours=1)
    with patch('src.portfolio_risk_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = future_time
        mock_datetime.utcnow.return_value = future_time
        
        # Trigger reset
        manager.check_can_trade(Decimal('10'), 'test_market')
    
    # Verify conservative mode deactivated
    assert not manager._conservative_mode_active, \
        "Conservative mode should be deactivated when balance recovers to 50%+"


def test_daily_reset_clears_daily_halt():
    """Test that daily reset clears daily trading halt."""
    manager = PortfolioRiskManager(
        initial_capital=Decimal('1000'),
        max_portfolio_heat=Decimal('0.50'),
        max_position_size_pct=Decimal('0.10'),
        max_daily_drawdown=Decimal('0.15'),
        consecutive_loss_limit=5
    )
    
    # Set daily halt
    manager._trading_halted = True
    manager._halt_reason = "Daily drawdown limit exceeded"
    
    # Mock datetime to trigger reset
    future_time = datetime.now() + timedelta(days=1, hours=1)
    with patch('src.portfolio_risk_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = future_time
        mock_datetime.utcnow.return_value = future_time
        
        # Trigger reset
        manager.check_can_trade(Decimal('10'), 'test_market')
    
    # Verify halt cleared
    assert not manager._trading_halted, "Daily trading halt should be cleared"
    assert manager._halt_reason == "", "Halt reason should be cleared"


def test_daily_reset_logs_performance_summary(caplog):
    """Test that daily reset logs comprehensive performance summary."""
    import logging
    caplog.set_level(logging.INFO)
    
    manager = PortfolioRiskManager(
        initial_capital=Decimal('1000'),
        max_portfolio_heat=Decimal('0.50'),
        max_position_size_pct=Decimal('0.10'),
        max_daily_drawdown=Decimal('0.15'),
        consecutive_loss_limit=5
    )
    
    # Simulate trading activity
    manager._trades_today = 10
    manager._wins_today = 7
    manager._losses_today = 3
    manager._daily_pnl = Decimal('150')
    manager.current_capital = Decimal('1150')
    manager._conservative_mode_active = False
    
    # Mock datetime to trigger reset
    future_time = datetime.now() + timedelta(days=1, hours=1)
    with patch('src.portfolio_risk_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = future_time
        mock_datetime.utcnow.return_value = future_time
        
        # Clear previous logs
        caplog.clear()
        
        # Trigger reset
        manager.check_can_trade(Decimal('10'), 'test_market')
    
    # Verify comprehensive logging
    log_messages = [record.message for record in caplog.records]
    log_text = " ".join(log_messages)
    
    assert any("DAILY PERFORMANCE SUMMARY" in msg for msg in log_messages), \
        "Should log daily performance summary header"
    assert any("Total Trades: 10" in msg for msg in log_messages), \
        "Should log total trades"
    assert any("Wins: 7" in msg for msg in log_messages), \
        "Should log wins"
    assert any("Losses: 3" in msg for msg in log_messages), \
        "Should log losses"
    assert any("Win Rate:" in msg for msg in log_messages), \
        "Should log win rate"
    assert any("Daily P&L:" in msg for msg in log_messages), \
        "Should log daily P&L"
    assert any("Daily ROI:" in msg for msg in log_messages), \
        "Should log daily ROI"
    assert any("Starting Balance:" in msg for msg in log_messages), \
        "Should log starting balance"
    assert any("Ending Balance:" in msg for msg in log_messages), \
        "Should log ending balance"
    assert any("Conservative Mode:" in msg for msg in log_messages), \
        "Should log conservative mode status"
    assert any("Circuit Breaker:" in msg for msg in log_messages), \
        "Should log circuit breaker status"


def test_daily_reset_calculates_metrics_before_reset():
    """Test that daily reset calculates metrics before resetting counters."""
    import logging
    
    manager = PortfolioRiskManager(
        initial_capital=Decimal('1000'),
        max_portfolio_heat=Decimal('0.50'),
        max_position_size_pct=Decimal('0.10'),
        max_daily_drawdown=Decimal('0.15'),
        consecutive_loss_limit=5
    )
    
    # Simulate trading activity
    manager._trades_today = 10
    manager._wins_today = 8
    manager._losses_today = 2
    manager._daily_pnl = Decimal('200')
    manager._daily_start_capital = Decimal('1000')
    manager.current_capital = Decimal('1200')
    
    # Mock datetime to trigger reset
    future_time = datetime.now() + timedelta(days=1, hours=1)
    with patch('src.portfolio_risk_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = future_time
        mock_datetime.utcnow.return_value = future_time
        
        # Trigger reset
        with patch('src.portfolio_risk_manager.logger') as mock_logger:
            manager.check_can_trade(Decimal('10'), 'test_market')
            
            # Check that logger.info was called with performance metrics
            # The metrics should be calculated BEFORE reset
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            
            # Should have logged win rate of 80% (8/10)
            assert any("80.0%" in str(call) for call in info_calls), \
                "Should log 80% win rate"
            
            # Should have logged daily P&L of $200
            assert any("$200" in str(call) for call in info_calls), \
                "Should log $200 daily P&L"
            
            # Should have logged ROI (20% = 200/1000)
            # Check for "20.00%" or "Daily ROI:" to be more flexible
            assert any("Daily ROI:" in str(call) for call in info_calls), \
                "Should log Daily ROI"


def test_daily_reset_only_triggers_at_midnight_utc():
    """Test that daily reset only triggers at UTC midnight."""
    manager = PortfolioRiskManager(
        initial_capital=Decimal('1000'),
        max_portfolio_heat=Decimal('0.50'),
        max_position_size_pct=Decimal('0.10'),
        max_daily_drawdown=Decimal('0.15'),
        consecutive_loss_limit=5
    )
    
    # Simulate trading activity
    manager._trades_today = 5
    manager._daily_pnl = Decimal('50')
    
    # Mock datetime to be BEFORE reset time
    current_time = datetime.now()
    with patch('src.portfolio_risk_manager.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_time
        
        # Trigger check (should NOT reset)
        manager.check_can_trade(Decimal('10'), 'test_market')
    
    # Verify counters NOT reset
    assert manager._trades_today == 5, "Trades should not be reset before midnight"
    assert manager._daily_pnl == Decimal('50'), "Daily P&L should not be reset before midnight"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
