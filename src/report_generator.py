"""
Report Generator for Polymarket Arbitrage Bot.

Generates performance reports in various formats:
- Console output
- CSV export
- JSON export

Validates Requirements:
- 19.3: Generate daily/weekly/monthly reports
- 19.5: Export to CSV/JSON
"""

import logging
import json
import csv
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from src.trade_history import TradeHistoryDB
from src.trade_statistics import TradeStatisticsTracker, TradeStatistics
from src.logging_config import get_logger


class ReportGenerator:
    """
    Generates performance reports in multiple formats.
    
    Validates Requirements:
    - 19.3: Generate reports with performance metrics
    - 19.5: Export to CSV/JSON
    """
    
    def __init__(
        self,
        db: TradeHistoryDB,
        stats_tracker: TradeStatisticsTracker,
        output_dir: str = "reports",
    ):
        """
        Initialize report generator.
        
        Args:
            db: TradeHistoryDB instance
            stats_tracker: TradeStatisticsTracker instance
            output_dir: Directory for report output files
        """
        self.logger = get_logger(__name__)
        self.db = db
        self.stats_tracker = stats_tracker
        self.output_dir = output_dir
        
        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Report generator initialized: {output_dir}")
    
    def generate_console_report(
        self,
        period: str = "daily",
        stats: Optional[TradeStatistics] = None,
    ) -> str:
        """
        Generate formatted console report.
        
        Args:
            period: Report period (daily, weekly, monthly, all)
            stats: Optional pre-calculated statistics
            
        Returns:
            str: Formatted report text
        """
        if stats is None:
            if period == "daily":
                stats = self.stats_tracker.get_daily_statistics()
            elif period == "weekly":
                stats = self.stats_tracker.get_weekly_statistics()
            elif period == "monthly":
                stats = self.stats_tracker.get_monthly_statistics()
            else:
                stats = self.stats_tracker.get_statistics()
        
        # Build report
        lines = []
        lines.append("=" * 80)
        lines.append(f"POLYMARKET ARBITRAGE BOT - {period.upper()} REPORT")
        lines.append("=" * 80)
        
        if stats.start_date and stats.end_date:
            lines.append(f"Period: {stats.start_date.strftime('%Y-%m-%d %H:%M')} to {stats.end_date.strftime('%Y-%m-%d %H:%M')}")
        else:
            lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        lines.append("")
        lines.append("TRADE SUMMARY")
        lines.append("-" * 80)
        lines.append(f"  Total Trades:       {stats.total_trades:,}")
        lines.append(f"  Successful:         {stats.successful_trades:,}")
        lines.append(f"  Failed:             {stats.failed_trades:,}")
        lines.append(f"  Win Rate:           {stats.win_rate:.2f}% {'✓' if stats.win_rate >= 99.5 else '✗'}")
        
        lines.append("")
        lines.append("FINANCIAL PERFORMANCE")
        lines.append("-" * 80)
        lines.append(f"  Total Profit:       ${stats.total_profit:,.2f}")
        lines.append(f"  Total Gas Cost:     ${stats.total_gas_cost:,.2f}")
        lines.append(f"  Net Profit:         ${stats.net_profit:,.2f}")
        lines.append(f"  Avg Profit/Trade:   ${stats.avg_profit_per_trade:.4f}")
        
        lines.append("")
        lines.append("RISK METRICS")
        lines.append("-" * 80)
        lines.append(f"  Profit Factor:      {stats.profit_factor:.2f}x")
        lines.append(f"  Sharpe Ratio:       {stats.sharpe_ratio:.2f}")
        lines.append(f"  Max Drawdown:       ${stats.max_drawdown:.2f}")
        
        if stats.strategy_stats:
            lines.append("")
            lines.append("STRATEGY BREAKDOWN")
            lines.append("-" * 80)
            
            for strategy, strategy_data in stats.strategy_stats.items():
                lines.append(f"  {strategy.upper()}:")
                lines.append(f"    Trades:           {strategy_data['total']:,}")
                lines.append(f"    Win Rate:         {strategy_data['win_rate']:.2f}%")
                lines.append(f"    Total Profit:     ${strategy_data['profit']:,.2f}")
                lines.append(f"    Gas Cost:         ${strategy_data['gas_cost']:,.2f}")
                lines.append(f"    Net Profit:       ${strategy_data['net_profit']:,.2f}")
                lines.append("")
        
        lines.append("=" * 80)
        
        report = "\n".join(lines)
        return report
    
    def print_console_report(self, period: str = "daily") -> None:
        """
        Print report to console.
        
        Args:
            period: Report period (daily, weekly, monthly, all)
        """
        report = self.generate_console_report(period)
        print(report)
    
    def export_to_csv(
        self,
        period: str = "daily",
        filename: Optional[str] = None,
    ) -> str:
        """
        Export trade data to CSV file.
        
        Validates Requirement 19.5: Export to CSV
        
        Args:
            period: Report period (daily, weekly, monthly, all)
            filename: Optional custom filename
            
        Returns:
            str: Path to generated CSV file
        """
        # Get trades for period
        if period == "daily":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            trades = self.db.get_trades_by_date_range(start_date, end_date)
        elif period == "weekly":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            trades = self.db.get_trades_by_date_range(start_date, end_date)
        elif period == "monthly":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            trades = self.db.get_trades_by_date_range(start_date, end_date)
        else:
            trades = self.db.get_recent_trades(limit=10000)
        
        # Generate filename
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"trades_{period}_{timestamp}.csv"
        
        filepath = Path(self.output_dir) / filename
        
        # Write CSV
        try:
            with open(filepath, 'w', newline='') as csvfile:
                if not trades:
                    self.logger.warning("No trades to export")
                    return str(filepath)
                
                # Define CSV columns
                fieldnames = [
                    'trade_id', 'timestamp', 'market_id', 'strategy', 'status',
                    'yes_price', 'no_price', 'total_cost', 'expected_profit',
                    'actual_profit', 'gas_cost', 'net_profit',
                    'yes_filled', 'no_filled', 'error_message'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for trade in trades:
                    # Calculate net profit
                    net_profit = Decimal(trade['actual_profit']) - Decimal(trade['gas_cost'])
                    
                    writer.writerow({
                        'trade_id': trade['trade_id'],
                        'timestamp': trade['timestamp'],
                        'market_id': trade['market_id'],
                        'strategy': trade['strategy'],
                        'status': trade['status'],
                        'yes_price': trade['yes_price'],
                        'no_price': trade['no_price'],
                        'total_cost': trade['total_cost'],
                        'expected_profit': trade['expected_profit'],
                        'actual_profit': trade['actual_profit'],
                        'gas_cost': trade['gas_cost'],
                        'net_profit': str(net_profit),
                        'yes_filled': trade['yes_filled'],
                        'no_filled': trade['no_filled'],
                        'error_message': trade.get('error_message', ''),
                    })
            
            self.logger.info(f"CSV report exported: {filepath} ({len(trades)} trades)")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to export CSV: {e}")
            raise
    
    def export_to_json(
        self,
        period: str = "daily",
        filename: Optional[str] = None,
        include_statistics: bool = True,
    ) -> str:
        """
        Export trade data and statistics to JSON file.
        
        Validates Requirement 19.5: Export to JSON
        
        Args:
            period: Report period (daily, weekly, monthly, all)
            filename: Optional custom filename
            include_statistics: Whether to include statistics summary
            
        Returns:
            str: Path to generated JSON file
        """
        # Get trades for period
        if period == "daily":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            trades = self.db.get_trades_by_date_range(start_date, end_date)
            stats = self.stats_tracker.get_daily_statistics()
        elif period == "weekly":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            trades = self.db.get_trades_by_date_range(start_date, end_date)
            stats = self.stats_tracker.get_weekly_statistics()
        elif period == "monthly":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            trades = self.db.get_trades_by_date_range(start_date, end_date)
            stats = self.stats_tracker.get_monthly_statistics()
        else:
            trades = self.db.get_recent_trades(limit=10000)
            stats = self.stats_tracker.get_statistics()
        
        # Generate filename
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"trades_{period}_{timestamp}.json"
        
        filepath = Path(self.output_dir) / filename
        
        # Build JSON structure
        report_data = {
            'report_metadata': {
                'period': period,
                'generated_at': datetime.now().isoformat(),
                'trade_count': len(trades),
            },
            'trades': trades,
        }
        
        if include_statistics:
            # Convert Decimal to float for JSON serialization
            report_data['statistics'] = {
                'total_trades': stats.total_trades,
                'successful_trades': stats.successful_trades,
                'failed_trades': stats.failed_trades,
                'win_rate': float(stats.win_rate),
                'total_profit': float(stats.total_profit),
                'total_gas_cost': float(stats.total_gas_cost),
                'net_profit': float(stats.net_profit),
                'avg_profit_per_trade': float(stats.avg_profit_per_trade),
                'profit_factor': float(stats.profit_factor),
                'sharpe_ratio': float(stats.sharpe_ratio),
                'max_drawdown': float(stats.max_drawdown),
                'strategy_breakdown': {
                    strategy: {
                        'total': data['total'],
                        'successful': data['successful'],
                        'failed': data['failed'],
                        'win_rate': float(data['win_rate']),
                        'profit': float(data['profit']),
                        'gas_cost': float(data['gas_cost']),
                        'net_profit': float(data['net_profit']),
                    }
                    for strategy, data in stats.strategy_stats.items()
                },
            }
        
        # Write JSON
        try:
            with open(filepath, 'w') as jsonfile:
                json.dump(report_data, jsonfile, indent=2, default=str)
            
            self.logger.info(f"JSON report exported: {filepath} ({len(trades)} trades)")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to export JSON: {e}")
            raise
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """
        Generate a summary report with key metrics.
        
        Returns:
            Dict: Summary report data
        """
        stats = self.stats_tracker.get_statistics()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_trades': stats.total_trades,
            'win_rate': float(stats.win_rate),
            'net_profit': float(stats.net_profit),
            'profit_factor': float(stats.profit_factor),
            'sharpe_ratio': float(stats.sharpe_ratio),
            'max_drawdown': float(stats.max_drawdown),
            'strategies': list(stats.strategy_stats.keys()),
        }
