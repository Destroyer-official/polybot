"""
Task 8.2: Daily Performance Summary Tracker

This module provides daily performance tracking functionality that can be integrated
into the FifteenMinuteCryptoStrategy class.

Validates Requirements:
- 9.3: Daily performance summary with win rate, profit, ROI
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class DailyPerformanceTracker:
    """
    Tracks daily trading performance with automatic UTC midnight reset.
    
    Features:
    - Daily win rate, profit, and ROI tracking
    - Per-strategy breakdown
    - Per-asset breakdown
    - Automatic reset at UTC midnight
    - Comprehensive daily summary logging
    """
    
    def __init__(self, starting_capital: Decimal):
        """
        Initialize daily performance tracker.
        
        Args:
            starting_capital: Starting capital for ROI calculations
        """
        self.daily_stats = {
            "date": datetime.now(timezone.utc).date(),
            "trades_placed": 0,
            "trades_won": 0,
            "trades_lost": 0,
            "total_profit": Decimal("0"),
            "starting_capital": starting_capital,
            "per_strategy": {},  # {strategy: {wins, losses, profit}}
            "per_asset": {}  # {asset: {wins, losses, profit}}
        }
        self.last_daily_reset = datetime.now(timezone.utc).date()
    
    def check_and_reset(self, current_capital: Decimal) -> None:
        """
        Check if it's a new day (UTC) and reset daily statistics.
        Log daily summary before resetting.
        
        Args:
            current_capital: Current capital for new day's starting capital
        """
        current_date = datetime.now(timezone.utc).date()
        
        # Check if we've crossed into a new day
        if current_date > self.last_daily_reset:
            # Log yesterday's summary before resetting
            self.log_summary()
            
            # Reset daily stats for new day
            logger.info(f"\n🌅 NEW DAY: Resetting daily statistics for {current_date}")
            self.daily_stats = {
                "date": current_date,
                "trades_placed": 0,
                "trades_won": 0,
                "trades_lost": 0,
                "total_profit": Decimal("0"),
                "starting_capital": current_capital,
                "per_strategy": {},
                "per_asset": {}
            }
            self.last_daily_reset = current_date
            
            logger.info("✅ Daily statistics reset complete")
    
    def record_trade(self, strategy: str, asset: str, profit: Decimal, is_win: bool) -> None:
        """
        Record a trade outcome to daily statistics.
        
        Args:
            strategy: Strategy name (e.g., "sum_to_one", "latency", "directional")
            asset: Asset name (e.g., "BTC", "ETH")
            profit: Profit/loss as decimal (e.g., 0.02 for 2% profit)
            is_win: Whether the trade was profitable
        """
        # Update overall stats
        self.daily_stats["trades_placed"] += 1
        if is_win:
            self.daily_stats["trades_won"] += 1
        else:
            self.daily_stats["trades_lost"] += 1
        self.daily_stats["total_profit"] += profit
        
        # Update per-strategy stats
        if strategy not in self.daily_stats["per_strategy"]:
            self.daily_stats["per_strategy"][strategy] = {
                "wins": 0,
                "losses": 0,
                "profit": Decimal("0")
            }
        if is_win:
            self.daily_stats["per_strategy"][strategy]["wins"] += 1
        else:
            self.daily_stats["per_strategy"][strategy]["losses"] += 1
        self.daily_stats["per_strategy"][strategy]["profit"] += profit
        
        # Update per-asset stats
        if asset not in self.daily_stats["per_asset"]:
            self.daily_stats["per_asset"][asset] = {
                "wins": 0,
                "losses": 0,
                "profit": Decimal("0")
            }
        if is_win:
            self.daily_stats["per_asset"][asset]["wins"] += 1
        else:
            self.daily_stats["per_asset"][asset]["losses"] += 1
        self.daily_stats["per_asset"][asset]["profit"] += profit
    
    def log_summary(self) -> None:
        """
        Log comprehensive daily performance summary.
        
        Includes:
        - Overall win rate, profit, ROI
        - Breakdown by strategy
        - Breakdown by asset
        """
        if self.daily_stats["trades_placed"] == 0:
            logger.info("\n📊 DAILY SUMMARY: No trades today")
            return
        
        # Calculate overall metrics
        win_rate = (self.daily_stats["trades_won"] / self.daily_stats["trades_placed"] * 100) if self.daily_stats["trades_placed"] > 0 else 0.0
        total_profit = float(self.daily_stats["total_profit"])
        starting_capital = float(self.daily_stats["starting_capital"])
        roi = (total_profit / starting_capital * 100) if starting_capital > 0 else 0.0
        
        logger.info("=" * 80)
        logger.info(f"📊 DAILY PERFORMANCE SUMMARY - {self.daily_stats['date']}")
        logger.info("=" * 80)
        
        # Overall performance
        logger.info(f"OVERALL:")
        logger.info(f"  Total Trades: {self.daily_stats['trades_placed']}")
        logger.info(f"  Win Rate: {win_rate:.1f}% ({self.daily_stats['trades_won']}W / {self.daily_stats['trades_lost']}L)")
        logger.info(f"  Total Profit: ${total_profit:.2f}")
        logger.info(f"  ROI: {roi:.2f}%")
        logger.info(f"  Starting Capital: ${starting_capital:.2f}")
        logger.info(f"  Ending Capital: ${starting_capital + total_profit:.2f}")
        
        # Per-strategy breakdown
        if self.daily_stats["per_strategy"]:
            logger.info(f"\nBY STRATEGY:")
            for strategy, data in self.daily_stats["per_strategy"].items():
                total_trades = data["wins"] + data["losses"]
                strategy_win_rate = (data["wins"] / total_trades * 100) if total_trades > 0 else 0.0
                strategy_profit = float(data["profit"])
                strategy_roi = (strategy_profit / starting_capital * 100) if starting_capital > 0 else 0.0
                
                logger.info(f"  {strategy.upper()}:")
                logger.info(f"    Trades: {total_trades} | Win Rate: {strategy_win_rate:.1f}% | Profit: ${strategy_profit:.2f} | ROI: {strategy_roi:.2f}%")
        
        # Per-asset breakdown
        if self.daily_stats["per_asset"]:
            logger.info(f"\nBY ASSET:")
            for asset, data in self.daily_stats["per_asset"].items():
                total_trades = data["wins"] + data["losses"]
                asset_win_rate = (data["wins"] / total_trades * 100) if total_trades > 0 else 0.0
                asset_profit = float(data["profit"])
                asset_roi = (asset_profit / starting_capital * 100) if starting_capital > 0 else 0.0
                
                logger.info(f"  {asset}:")
                logger.info(f"    Trades: {total_trades} | Win Rate: {asset_win_rate:.1f}% | Profit: ${asset_profit:.2f} | ROI: {asset_roi:.2f}%")
        
        logger.info("=" * 80)
