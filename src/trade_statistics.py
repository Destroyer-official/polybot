"""
Trade Statistics Tracker for Polymarket Arbitrage Bot.

Tracks running totals and calculates performance metrics:
- Win rate
- Profit factor
- Sharpe ratio
- Maximum drawdown

Validates Requirements:
- 19.1: Track running totals (trades, profit, gas cost)
- 19.2: Calculate win rate, profit factor, Sharpe ratio
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, field
import math

from src.models import TradeResult
from src.trade_history import TradeHistoryDB
from src.logging_config import get_logger


@dataclass
class TradeStatistics:
    """Trade statistics summary"""
    # Trade counts
    total_trades: int
    successful_trades: int
    failed_trades: int
    
    # Win rate
    win_rate: Decimal  # Percentage (0-100)
    
    # Financial metrics
    total_profit: Decimal
    total_gas_cost: Decimal
    net_profit: Decimal
    avg_profit_per_trade: Decimal
    
    # Risk metrics
    profit_factor: Decimal  # Total profit / Total loss
    sharpe_ratio: Decimal  # Risk-adjusted return
    max_drawdown: Decimal  # Maximum peak-to-trough decline
    
    # Strategy breakdown
    strategy_stats: dict = field(default_factory=dict)
    
    # Time period
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TradeStatisticsTracker:
    """
    Tracks and calculates trade statistics.
    
    Validates Requirements:
    - 19.1: Track running totals
    - 19.2: Calculate performance metrics
    """
    
    def __init__(self, db: TradeHistoryDB):
        """
        Initialize statistics tracker.
        
        Args:
            db: TradeHistoryDB instance for querying trade history
        """
        self.logger = get_logger(__name__)
        self.db = db
        
        # Running totals (updated after each trade)
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_profit = Decimal('0')
        self.total_gas_cost = Decimal('0')
        
        # Load initial state from database
        self._load_from_database()
        
        self.logger.info("Trade statistics tracker initialized")
    
    def _load_from_database(self):
        """Load running totals from database on startup."""
        try:
            # Get all trades from database
            all_trades = self.db.get_recent_trades(limit=10000)  # Load last 10k trades
            
            if not all_trades:
                self.logger.info("No existing trades found in database")
                return
            
            # Calculate totals
            self.total_trades = len(all_trades)
            self.successful_trades = sum(1 for t in all_trades if t['status'] == 'success')
            self.failed_trades = self.total_trades - self.successful_trades
            
            self.total_profit = sum(
                Decimal(t['actual_profit']) for t in all_trades
            )
            self.total_gas_cost = sum(
                Decimal(t['gas_cost']) for t in all_trades
            )
            
            self.logger.info(
                f"Loaded statistics: {self.total_trades} trades, "
                f"{self.successful_trades} successful, "
                f"${self.total_profit:.2f} profit"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load statistics from database: {e}")
    
    def update_after_trade(self, trade: TradeResult) -> None:
        """
        Update running totals after a trade completes.
        
        Validates Requirement 19.2: Update after every trade
        
        Args:
            trade: TradeResult object
        """
        self.total_trades += 1
        
        if trade.was_successful():
            self.successful_trades += 1
        else:
            self.failed_trades += 1
        
        self.total_profit += trade.actual_profit
        self.total_gas_cost += trade.gas_cost
        
        self.logger.debug(
            f"Statistics updated: {self.total_trades} trades, "
            f"win rate: {self.get_win_rate():.2f}%"
        )
    
    def get_win_rate(self) -> Decimal:
        """
        Calculate win rate percentage.
        
        Returns:
            Decimal: Win rate as percentage (0-100)
        """
        if self.total_trades == 0:
            return Decimal('0')
        
        return (Decimal(self.successful_trades) / Decimal(self.total_trades)) * Decimal('100')
    
    def get_net_profit(self) -> Decimal:
        """
        Calculate net profit after gas costs.
        
        Returns:
            Decimal: Net profit in USDC
        """
        return self.total_profit - self.total_gas_cost
    
    def get_avg_profit_per_trade(self) -> Decimal:
        """
        Calculate average profit per trade.
        
        Returns:
            Decimal: Average profit in USDC
        """
        if self.total_trades == 0:
            return Decimal('0')
        
        return self.total_profit / Decimal(self.total_trades)
    
    def calculate_profit_factor(
        self,
        trades: Optional[List[dict]] = None,
    ) -> Decimal:
        """
        Calculate profit factor (total profit / total loss).
        
        A profit factor > 1 indicates profitability.
        
        Args:
            trades: Optional list of trade records (uses recent trades if None)
            
        Returns:
            Decimal: Profit factor
        """
        if trades is None:
            trades = self.db.get_recent_trades(limit=1000)
        
        if not trades:
            return Decimal('0')
        
        total_gains = Decimal('0')
        total_losses = Decimal('0')
        
        for trade in trades:
            profit = Decimal(trade['actual_profit'])
            if profit > 0:
                total_gains += profit
            else:
                total_losses += abs(profit)
        
        if total_losses == 0:
            # All trades profitable
            return Decimal('999.99') if total_gains > 0 else Decimal('0')
        
        return total_gains / total_losses
    
    def calculate_sharpe_ratio(
        self,
        trades: Optional[List[dict]] = None,
        risk_free_rate: Decimal = Decimal('0.05'),  # 5% annual
    ) -> Decimal:
        """
        Calculate Sharpe ratio (risk-adjusted return).
        
        Sharpe Ratio = (Mean Return - Risk Free Rate) / Std Dev of Returns
        
        Args:
            trades: Optional list of trade records (uses recent trades if None)
            risk_free_rate: Annual risk-free rate (default 5%)
            
        Returns:
            Decimal: Sharpe ratio
        """
        if trades is None:
            trades = self.db.get_recent_trades(limit=1000)
        
        if len(trades) < 2:
            return Decimal('0')
        
        # Calculate returns for each trade
        returns = [Decimal(t['actual_profit']) for t in trades]
        
        # Calculate mean return
        mean_return = sum(returns) / len(returns)
        
        # Calculate standard deviation
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = Decimal(math.sqrt(float(variance)))
        
        if std_dev == 0:
            return Decimal('0')
        
        # Annualize the risk-free rate to per-trade rate
        # Assuming ~100 trades per day, ~36,500 trades per year
        per_trade_risk_free = risk_free_rate / Decimal('36500')
        
        # Calculate Sharpe ratio
        sharpe = (mean_return - per_trade_risk_free) / std_dev
        
        return sharpe
    
    def calculate_max_drawdown(
        self,
        trades: Optional[List[dict]] = None,
    ) -> Decimal:
        """
        Calculate maximum drawdown (peak-to-trough decline).
        
        Args:
            trades: Optional list of trade records (uses recent trades if None)
            
        Returns:
            Decimal: Maximum drawdown as positive value
        """
        if trades is None:
            trades = self.db.get_recent_trades(limit=1000)
        
        if not trades:
            return Decimal('0')
        
        # Sort trades by timestamp (oldest first)
        sorted_trades = sorted(trades, key=lambda t: t['timestamp'])
        
        # Calculate cumulative profit
        cumulative_profit = Decimal('0')
        peak_profit = Decimal('0')
        max_drawdown = Decimal('0')
        
        for trade in sorted_trades:
            profit = Decimal(trade['actual_profit'])
            cumulative_profit += profit
            
            # Update peak
            if cumulative_profit > peak_profit:
                peak_profit = cumulative_profit
            
            # Calculate drawdown from peak
            drawdown = peak_profit - cumulative_profit
            
            # Update max drawdown
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def get_strategy_breakdown(
        self,
        trades: Optional[List[dict]] = None,
    ) -> dict:
        """
        Get statistics breakdown by strategy.
        
        Args:
            trades: Optional list of trade records (uses recent trades if None)
            
        Returns:
            dict: Strategy statistics
        """
        if trades is None:
            trades = self.db.get_recent_trades(limit=1000)
        
        strategy_stats = {}
        
        for trade in trades:
            strategy = trade['strategy']
            
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'total': 0,
                    'successful': 0,
                    'failed': 0,
                    'profit': Decimal('0'),
                    'gas_cost': Decimal('0'),
                }
            
            stats = strategy_stats[strategy]
            stats['total'] += 1
            
            if trade['status'] == 'success':
                stats['successful'] += 1
            else:
                stats['failed'] += 1
            
            stats['profit'] += Decimal(trade['actual_profit'])
            stats['gas_cost'] += Decimal(trade['gas_cost'])
        
        # Calculate win rates
        for strategy, stats in strategy_stats.items():
            if stats['total'] > 0:
                stats['win_rate'] = (Decimal(stats['successful']) / Decimal(stats['total'])) * Decimal('100')
            else:
                stats['win_rate'] = Decimal('0')
            
            stats['net_profit'] = stats['profit'] - stats['gas_cost']
        
        return strategy_stats
    
    def get_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> TradeStatistics:
        """
        Get comprehensive trade statistics.
        
        Args:
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            
        Returns:
            TradeStatistics object with all metrics
        """
        # Get trades for the specified period
        if start_date and end_date:
            trades = self.db.get_trades_by_date_range(start_date, end_date)
        else:
            trades = self.db.get_recent_trades(limit=10000)
        
        if not trades:
            return TradeStatistics(
                total_trades=0,
                successful_trades=0,
                failed_trades=0,
                win_rate=Decimal('0'),
                total_profit=Decimal('0'),
                total_gas_cost=Decimal('0'),
                net_profit=Decimal('0'),
                avg_profit_per_trade=Decimal('0'),
                profit_factor=Decimal('0'),
                sharpe_ratio=Decimal('0'),
                max_drawdown=Decimal('0'),
                strategy_stats={},
                start_date=start_date,
                end_date=end_date,
            )
        
        # Calculate metrics
        total_trades = len(trades)
        successful_trades = sum(1 for t in trades if t['status'] == 'success')
        failed_trades = total_trades - successful_trades
        
        total_profit = sum(Decimal(t['actual_profit']) for t in trades)
        total_gas_cost = sum(Decimal(t['gas_cost']) for t in trades)
        net_profit = total_profit - total_gas_cost
        
        win_rate = (Decimal(successful_trades) / Decimal(total_trades)) * Decimal('100') if total_trades > 0 else Decimal('0')
        avg_profit = total_profit / Decimal(total_trades) if total_trades > 0 else Decimal('0')
        
        profit_factor = self.calculate_profit_factor(trades)
        sharpe_ratio = self.calculate_sharpe_ratio(trades)
        max_drawdown = self.calculate_max_drawdown(trades)
        strategy_stats = self.get_strategy_breakdown(trades)
        
        return TradeStatistics(
            total_trades=total_trades,
            successful_trades=successful_trades,
            failed_trades=failed_trades,
            win_rate=win_rate,
            total_profit=total_profit,
            total_gas_cost=total_gas_cost,
            net_profit=net_profit,
            avg_profit_per_trade=avg_profit,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            strategy_stats=strategy_stats,
            start_date=start_date,
            end_date=end_date,
        )
    
    def get_daily_statistics(self) -> TradeStatistics:
        """Get statistics for the last 24 hours."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        return self.get_statistics(start_date, end_date)
    
    def get_weekly_statistics(self) -> TradeStatistics:
        """Get statistics for the last 7 days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        return self.get_statistics(start_date, end_date)
    
    def get_monthly_statistics(self) -> TradeStatistics:
        """Get statistics for the last 30 days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return self.get_statistics(start_date, end_date)
    
    def get_recent_win_rate(self, last_n: int = 10) -> Optional[float]:
        """
        Get win rate from the last N trades.
        
        Used for dynamic position sizing to reduce risk after losses.
        
        Args:
            last_n: Number of recent trades to consider (default: 10)
            
        Returns:
            Win rate as float (0.0 to 1.0), or None if insufficient trades
        """
        try:
            # Get last N trades
            recent_trades = self.db.get_recent_trades(limit=last_n)
            
            if not recent_trades or len(recent_trades) < 3:
                # Need at least 3 trades for meaningful win rate
                return None
            
            # Calculate win rate
            successful = sum(1 for t in recent_trades if t['status'] == 'success')
            win_rate = successful / len(recent_trades)
            
            self.logger.debug(
                f"Recent win rate: {win_rate:.2%} "
                f"({successful}/{len(recent_trades)} trades)"
            )
            
            return win_rate
            
        except Exception as e:
            self.logger.error(f"Failed to calculate recent win rate: {e}")
            return None
