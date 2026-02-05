"""
Backtest report generator for analyzing strategy performance.

Calculates win rate, profit, drawdown, Sharpe ratio and generates detailed reports.
Validates 99.5%+ win rate before live trading.

Validates Requirement 12.3.
"""

import json
import csv
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional
import math

from src.backtest_simulator import BacktestSimulator, PortfolioSnapshot
from src.models import TradeResult

logger = logging.getLogger(__name__)


class BacktestReport:
    """
    Generates comprehensive backtest performance reports.
    
    Validates Requirement 12.3:
    - Calculate win rate, profit, drawdown, Sharpe ratio
    - Generate detailed report
    - Validate 99.5%+ win rate before live trading
    """
    
    def __init__(self, simulator: BacktestSimulator):
        """
        Initialize report generator with simulator results.
        
        Args:
            simulator: BacktestSimulator with completed backtest
        """
        self.simulator = simulator
        self.trades = simulator.get_trade_history()
        self.portfolio_history = simulator.get_portfolio_history()
        self.current_snapshot = simulator.get_current_snapshot()
        
        logger.info(f"Initialized BacktestReport with {len(self.trades)} trades")
    
    def calculate_metrics(self) -> Dict:
        """
        Calculate comprehensive performance metrics.
        
        Returns:
            Dict: Performance metrics including win rate, profit, drawdown, Sharpe ratio
            
        Validates Requirement 12.3: Calculate win rate, profit, drawdown, Sharpe ratio
        """
        if not self.trades:
            return self._empty_metrics()
        
        # Basic metrics
        total_trades = len(self.trades)
        successful_trades = sum(1 for t in self.trades if t.was_successful())
        failed_trades = total_trades - successful_trades
        
        win_rate = (Decimal(str(successful_trades)) / Decimal(str(total_trades))) * 100
        
        # Profit metrics
        total_profit = sum(t.actual_profit for t in self.trades)
        total_gas_cost = sum(t.gas_cost for t in self.trades)
        net_profit = total_profit - total_gas_cost
        
        avg_profit_per_trade = net_profit / Decimal(str(total_trades)) if total_trades > 0 else Decimal('0.0')
        
        # Calculate profit factor (gross profit / gross loss)
        gross_profit = sum(t.net_profit for t in self.trades if t.net_profit > 0)
        gross_loss = abs(sum(t.net_profit for t in self.trades if t.net_profit < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else Decimal('999.0')
        
        # Drawdown metrics
        max_drawdown = self._calculate_max_drawdown()
        max_drawdown_pct = max_drawdown * 100
        
        # Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio()
        
        # Return on investment
        initial_balance = self.simulator.initial_balance
        roi = (net_profit / initial_balance) * 100 if initial_balance > 0 else Decimal('0.0')
        
        # Time metrics
        if self.portfolio_history:
            start_time = self.portfolio_history[0].timestamp
            end_time = self.portfolio_history[-1].timestamp
            duration = end_time - start_time
            duration_hours = Decimal(str(duration.total_seconds() / 3600))
        else:
            duration_hours = Decimal('0.0')
        
        trades_per_hour = (
            Decimal(str(total_trades)) / duration_hours
            if duration_hours > 0
            else Decimal('0.0')
        )
        
        metrics = {
            # Trade statistics
            'total_trades': total_trades,
            'successful_trades': successful_trades,
            'failed_trades': failed_trades,
            'win_rate': float(win_rate),
            'win_rate_decimal': win_rate,
            
            # Profit metrics
            'total_profit': float(total_profit),
            'total_gas_cost': float(total_gas_cost),
            'net_profit': float(net_profit),
            'avg_profit_per_trade': float(avg_profit_per_trade),
            'profit_factor': float(profit_factor),
            'roi_percent': float(roi),
            
            # Balance metrics
            'initial_balance': float(self.simulator.initial_balance),
            'final_balance': float(self.current_snapshot.balance),
            'max_balance': float(self.current_snapshot.max_balance),
            
            # Risk metrics
            'max_drawdown': float(max_drawdown),
            'max_drawdown_percent': float(max_drawdown_pct),
            'sharpe_ratio': float(sharpe_ratio) if sharpe_ratio else None,
            
            # Time metrics
            'duration_hours': float(duration_hours),
            'trades_per_hour': float(trades_per_hour),
            
            # Validation
            'passes_win_rate_threshold': win_rate >= Decimal('99.5'),
            'ready_for_live_trading': self._validate_for_live_trading(win_rate, sharpe_ratio)
        }
        
        return metrics
    
    def _empty_metrics(self) -> Dict:
        """Return empty metrics when no trades executed."""
        return {
            'total_trades': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'win_rate': 0.0,
            'win_rate_decimal': Decimal('0.0'),
            'total_profit': 0.0,
            'total_gas_cost': 0.0,
            'net_profit': 0.0,
            'avg_profit_per_trade': 0.0,
            'profit_factor': 0.0,
            'roi_percent': 0.0,
            'initial_balance': float(self.simulator.initial_balance),
            'final_balance': float(self.simulator.initial_balance),
            'max_balance': float(self.simulator.initial_balance),
            'max_drawdown': 0.0,
            'max_drawdown_percent': 0.0,
            'sharpe_ratio': None,
            'duration_hours': 0.0,
            'trades_per_hour': 0.0,
            'passes_win_rate_threshold': False,
            'ready_for_live_trading': False
        }
    
    def _calculate_max_drawdown(self) -> Decimal:
        """
        Calculate maximum drawdown from portfolio history.
        
        Returns:
            Decimal: Maximum drawdown as a fraction (0.0 to 1.0)
        """
        if not self.portfolio_history:
            return Decimal('0.0')
        
        max_dd = Decimal('0.0')
        peak = self.portfolio_history[0].balance
        
        for snapshot in self.portfolio_history:
            if snapshot.balance > peak:
                peak = snapshot.balance
            
            drawdown = (peak - snapshot.balance) / peak if peak > 0 else Decimal('0.0')
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd
    
    def _calculate_sharpe_ratio(self, risk_free_rate: Decimal = Decimal('0.0')) -> Optional[Decimal]:
        """
        Calculate Sharpe ratio from trade returns.
        
        Sharpe Ratio = (Mean Return - Risk Free Rate) / Std Dev of Returns
        
        Args:
            risk_free_rate: Annual risk-free rate (default 0%)
            
        Returns:
            Optional[Decimal]: Sharpe ratio or None if insufficient data
        """
        if len(self.trades) < 2:
            return None
        
        # Calculate returns for each trade
        returns = [
            float(t.net_profit / self.simulator.initial_balance)
            for t in self.trades
        ]
        
        # Calculate mean and standard deviation
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return None
        
        # Annualize (assuming trades are independent)
        # For simplicity, we use the raw Sharpe ratio without annualization
        sharpe = (mean_return - float(risk_free_rate)) / std_dev
        
        return Decimal(str(sharpe))
    
    def _validate_for_live_trading(
        self,
        win_rate: Decimal,
        sharpe_ratio: Optional[Decimal]
    ) -> bool:
        """
        Validate if strategy is ready for live trading.
        
        Validates Requirement 12.3: Validate 99.5%+ win rate before live trading
        
        Args:
            win_rate: Win rate percentage
            sharpe_ratio: Sharpe ratio
            
        Returns:
            bool: True if strategy passes validation criteria
        """
        # Must have minimum number of trades
        if len(self.trades) < 100:
            logger.warning(
                f"Insufficient trades for validation: {len(self.trades)} < 100"
            )
            return False
        
        # Must achieve 99.5%+ win rate
        if win_rate < Decimal('99.5'):
            logger.warning(
                f"Win rate below threshold: {win_rate:.2f}% < 99.5%"
            )
            return False
        
        # Must have positive net profit
        if self.current_snapshot.net_profit <= 0:
            logger.warning(
                f"Net profit not positive: ${self.current_snapshot.net_profit:.2f}"
            )
            return False
        
        # Sharpe ratio should be positive (if calculable)
        if sharpe_ratio is not None and sharpe_ratio <= 0:
            logger.warning(
                f"Sharpe ratio not positive: {sharpe_ratio:.2f}"
            )
            return False
        
        logger.info(
            f"✓ Strategy validated for live trading: "
            f"Win rate={win_rate:.2f}%, Net profit=${self.current_snapshot.net_profit:.2f}"
        )
        
        return True
    
    def generate_report(self, output_format: str = 'text') -> str:
        """
        Generate formatted backtest report.
        
        Args:
            output_format: 'text', 'json', or 'markdown'
            
        Returns:
            str: Formatted report
        """
        metrics = self.calculate_metrics()
        
        if output_format == 'json':
            return self._generate_json_report(metrics)
        elif output_format == 'markdown':
            return self._generate_markdown_report(metrics)
        else:
            return self._generate_text_report(metrics)
    
    def _generate_text_report(self, metrics: Dict) -> str:
        """Generate plain text report."""
        lines = [
            "=" * 80,
            "BACKTEST PERFORMANCE REPORT",
            "=" * 80,
            "",
            "TRADE STATISTICS",
            "-" * 80,
            f"Total Trades:        {metrics['total_trades']}",
            f"Successful Trades:   {metrics['successful_trades']}",
            f"Failed Trades:       {metrics['failed_trades']}",
            f"Win Rate:            {metrics['win_rate']:.2f}% {'✓' if metrics['passes_win_rate_threshold'] else '✗'}",
            "",
            "PROFIT METRICS",
            "-" * 80,
            f"Initial Balance:     ${metrics['initial_balance']:.2f}",
            f"Final Balance:       ${metrics['final_balance']:.2f}",
            f"Total Profit:        ${metrics['total_profit']:.2f}",
            f"Total Gas Cost:      ${metrics['total_gas_cost']:.2f}",
            f"Net Profit:          ${metrics['net_profit']:.2f}",
            f"Avg Profit/Trade:    ${metrics['avg_profit_per_trade']:.4f}",
            f"Profit Factor:       {metrics['profit_factor']:.2f}x",
            f"ROI:                 {metrics['roi_percent']:.2f}%",
            "",
            "RISK METRICS",
            "-" * 80,
            f"Max Balance:         ${metrics['max_balance']:.2f}",
            f"Max Drawdown:        ${metrics['max_drawdown']:.4f} ({metrics['max_drawdown_percent']:.2f}%)",
            f"Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}" if metrics['sharpe_ratio'] else "Sharpe Ratio:        N/A",
            "",
            "TIME METRICS",
            "-" * 80,
            f"Duration:            {metrics['duration_hours']:.2f} hours",
            f"Trades per Hour:     {metrics['trades_per_hour']:.2f}",
            "",
            "VALIDATION",
            "-" * 80,
            f"Passes Win Rate Threshold (99.5%):  {'✓ YES' if metrics['passes_win_rate_threshold'] else '✗ NO'}",
            f"Ready for Live Trading:             {'✓ YES' if metrics['ready_for_live_trading'] else '✗ NO'}",
            "",
        ]
        
        if not metrics['ready_for_live_trading']:
            lines.extend([
                "⚠ WARNING: Strategy does not meet criteria for live trading",
                "  - Minimum 100 trades required",
                "  - Minimum 99.5% win rate required",
                "  - Positive net profit required",
                "  - Positive Sharpe ratio required",
                ""
            ])
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _generate_json_report(self, metrics: Dict) -> str:
        """Generate JSON report."""
        report = {
            'backtest_report': {
                'generated_at': datetime.now().isoformat(),
                'metrics': metrics,
                'validation': {
                    'passes_win_rate_threshold': metrics['passes_win_rate_threshold'],
                    'ready_for_live_trading': metrics['ready_for_live_trading'],
                    'min_trades_required': 100,
                    'min_win_rate_required': 99.5
                }
            }
        }
        
        return json.dumps(report, indent=2, default=str)
    
    def _generate_markdown_report(self, metrics: Dict) -> str:
        """Generate Markdown report."""
        lines = [
            "# Backtest Performance Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Trade Statistics",
            "",
            f"- **Total Trades:** {metrics['total_trades']}",
            f"- **Successful Trades:** {metrics['successful_trades']}",
            f"- **Failed Trades:** {metrics['failed_trades']}",
            f"- **Win Rate:** {metrics['win_rate']:.2f}% {'✓' if metrics['passes_win_rate_threshold'] else '✗'}",
            "",
            "## Profit Metrics",
            "",
            f"- **Initial Balance:** ${metrics['initial_balance']:.2f}",
            f"- **Final Balance:** ${metrics['final_balance']:.2f}",
            f"- **Total Profit:** ${metrics['total_profit']:.2f}",
            f"- **Total Gas Cost:** ${metrics['total_gas_cost']:.2f}",
            f"- **Net Profit:** ${metrics['net_profit']:.2f}",
            f"- **Avg Profit/Trade:** ${metrics['avg_profit_per_trade']:.4f}",
            f"- **Profit Factor:** {metrics['profit_factor']:.2f}x",
            f"- **ROI:** {metrics['roi_percent']:.2f}%",
            "",
            "## Risk Metrics",
            "",
            f"- **Max Balance:** ${metrics['max_balance']:.2f}",
            f"- **Max Drawdown:** {metrics['max_drawdown_percent']:.2f}%",
            f"- **Sharpe Ratio:** {metrics['sharpe_ratio']:.2f}" if metrics['sharpe_ratio'] else "- **Sharpe Ratio:** N/A",
            "",
            "## Time Metrics",
            "",
            f"- **Duration:** {metrics['duration_hours']:.2f} hours",
            f"- **Trades per Hour:** {metrics['trades_per_hour']:.2f}",
            "",
            "## Validation",
            "",
            f"- **Passes Win Rate Threshold (99.5%):** {'✓ YES' if metrics['passes_win_rate_threshold'] else '✗ NO'}",
            f"- **Ready for Live Trading:** {'✓ YES' if metrics['ready_for_live_trading'] else '✗ NO'}",
            "",
        ]
        
        if not metrics['ready_for_live_trading']:
            lines.extend([
                "## ⚠ Warning",
                "",
                "Strategy does not meet criteria for live trading:",
                "- Minimum 100 trades required",
                "- Minimum 99.5% win rate required",
                "- Positive net profit required",
                "- Positive Sharpe ratio required",
                ""
            ])
        
        return "\n".join(lines)
    
    def save_report(self, output_path: Path, output_format: str = 'text'):
        """
        Save report to file.
        
        Args:
            output_path: Path to save report
            output_format: 'text', 'json', or 'markdown'
        """
        report = self.generate_report(output_format)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Saved backtest report to: {output_path}")
    
    def export_trades_csv(self, output_path: Path):
        """
        Export trade history to CSV.
        
        Args:
            output_path: Path to save CSV file
        """
        if not self.trades:
            logger.warning("No trades to export")
            return
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'trade_id', 'timestamp', 'status', 'market_id', 'strategy',
                'yes_price', 'no_price', 'yes_fee', 'no_fee',
                'total_cost', 'actual_profit', 'gas_cost', 'net_profit',
                'yes_filled', 'no_filled', 'error_message'
            ])
            
            # Data rows
            for trade in self.trades:
                writer.writerow([
                    trade.trade_id,
                    trade.timestamp.isoformat(),
                    trade.status,
                    trade.opportunity.market_id,
                    trade.opportunity.strategy,
                    float(trade.opportunity.yes_price),
                    float(trade.opportunity.no_price),
                    float(trade.opportunity.yes_fee),
                    float(trade.opportunity.no_fee),
                    float(trade.actual_cost),
                    float(trade.actual_profit),
                    float(trade.gas_cost),
                    float(trade.net_profit),
                    trade.yes_filled,
                    trade.no_filled,
                    trade.error_message or ''
                ])
        
        logger.info(f"Exported {len(self.trades)} trades to: {output_path}")
    
    def print_summary(self):
        """Print summary report to console."""
        report = self.generate_report('text')
        print(report)
