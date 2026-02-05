"""
Main backtest runner that orchestrates the backtesting framework.

Loads historical data, runs simulations, and generates reports.
"""

import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from src.backtest_data_loader import BacktestDataLoader
from src.backtest_simulator import BacktestSimulator, BacktestConfig
from src.backtest_report import BacktestReport
from src.models import Market, Opportunity
from src.internal_arbitrage_engine import InternalArbitrageEngine

logger = logging.getLogger(__name__)


class BacktestRunner:
    """
    Orchestrates the complete backtesting workflow.
    
    Workflow:
    1. Load historical market data
    2. Scan for arbitrage opportunities
    3. Simulate trade execution
    4. Generate performance report
    5. Validate readiness for live trading
    """
    
    def __init__(
        self,
        data_source: str,
        config: Optional[BacktestConfig] = None
    ):
        """
        Initialize backtest runner.
        
        Args:
            data_source: Path to CSV or SQLite database with historical data
            config: Optional backtest configuration (uses defaults if not provided)
        """
        self.data_loader = BacktestDataLoader(data_source)
        self.config = config or BacktestConfig()
        self.simulator = BacktestSimulator(self.config)
        
        logger.info(f"Initialized BacktestRunner with data source: {data_source}")
    
    def run(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        asset_filter: Optional[List[str]] = None,
        strategy_engine = None
    ) -> BacktestReport:
        """
        Run complete backtest.
        
        Args:
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            asset_filter: Optional list of assets to filter
            strategy_engine: Optional strategy engine (defaults to InternalArbitrageEngine)
            
        Returns:
            BacktestReport: Performance report with metrics
        """
        logger.info("=" * 80)
        logger.info("STARTING BACKTEST")
        logger.info("=" * 80)
        
        # Load historical data
        logger.info("Loading historical market data...")
        markets = self.data_loader.load_markets(
            start_date=start_date,
            end_date=end_date,
            asset_filter=asset_filter
        )
        
        if not markets:
            logger.warning("No markets loaded - cannot run backtest")
            return BacktestReport(self.simulator)
        
        logger.info(f"Loaded {len(markets)} markets")
        
        # Initialize strategy engine if not provided
        if strategy_engine is None:
            from rust_core import DynamicFeeCalculator
            fee_calculator = DynamicFeeCalculator()
            strategy_engine = InternalArbitrageEngine(None, fee_calculator)
            logger.info("Using InternalArbitrageEngine for backtest")
        
        # Scan for opportunities and simulate trades
        logger.info("Scanning for arbitrage opportunities...")
        opportunities_found = 0
        trades_executed = 0
        
        for market in markets:
            # Scan for opportunities
            opportunities = strategy_engine.scan_opportunities([market])
            
            for opportunity in opportunities:
                opportunities_found += 1
                
                # Simulate trade execution
                trade_result = self.simulator.simulate_trade(opportunity)
                trades_executed += 1
                
                if trade_result.was_successful():
                    logger.debug(
                        f"Trade {trades_executed}: SUCCESS - "
                        f"Market: {market.market_id[:8]}..., "
                        f"Profit: ${trade_result.net_profit:.4f}"
                    )
                else:
                    logger.debug(
                        f"Trade {trades_executed}: FAILED - "
                        f"Reason: {trade_result.error_message}"
                    )
        
        logger.info(f"Found {opportunities_found} opportunities")
        logger.info(f"Executed {trades_executed} trades")
        
        # Generate report
        logger.info("Generating performance report...")
        report = BacktestReport(self.simulator)
        
        logger.info("=" * 80)
        logger.info("BACKTEST COMPLETE")
        logger.info("=" * 80)
        
        return report
    
    def run_and_save(
        self,
        output_dir: Path,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        asset_filter: Optional[List[str]] = None,
        strategy_engine = None
    ):
        """
        Run backtest and save all outputs.
        
        Args:
            output_dir: Directory to save reports
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            asset_filter: Optional list of assets to filter
            strategy_engine: Optional strategy engine
        """
        # Run backtest
        report = self.run(
            start_date=start_date,
            end_date=end_date,
            asset_filter=asset_filter,
            strategy_engine=strategy_engine
        )
        
        # Create output directory
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamp for filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save reports in multiple formats
        report.save_report(
            output_dir / f"backtest_report_{timestamp}.txt",
            output_format='text'
        )
        report.save_report(
            output_dir / f"backtest_report_{timestamp}.json",
            output_format='json'
        )
        report.save_report(
            output_dir / f"backtest_report_{timestamp}.md",
            output_format='markdown'
        )
        
        # Export trade history
        report.export_trades_csv(
            output_dir / f"backtest_trades_{timestamp}.csv"
        )
        
        logger.info(f"Saved all reports to: {output_dir}")
        
        # Print summary to console
        print("\n")
        report.print_summary()
        
        # Check if ready for live trading
        metrics = report.calculate_metrics()
        if metrics['ready_for_live_trading']:
            print("\n✓ Strategy is validated and ready for live trading!")
        else:
            print("\n✗ Strategy does not meet criteria for live trading")
            print("  Review the report for details")


def main():
    """Example usage of backtest runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run backtest on historical data')
    parser.add_argument('data_source', help='Path to CSV or SQLite database')
    parser.add_argument('--output-dir', default='backtest_results', help='Output directory')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--assets', help='Comma-separated list of assets (e.g., BTC,ETH)')
    parser.add_argument('--initial-balance', type=float, default=100.0, help='Initial balance')
    parser.add_argument('--fill-rate', type=float, default=0.95, help='Order fill rate (0.0-1.0)')
    parser.add_argument('--slippage', type=float, default=0.001, help='Slippage rate')
    parser.add_argument('--gas-cost', type=float, default=0.02, help='Gas cost per trade')
    parser.add_argument('--seed', type=int, help='Random seed for reproducibility')
    
    args = parser.parse_args()
    
    # Parse dates
    start_date = datetime.fromisoformat(args.start_date) if args.start_date else None
    end_date = datetime.fromisoformat(args.end_date) if args.end_date else None
    
    # Parse assets
    asset_filter = args.assets.split(',') if args.assets else None
    
    # Create config
    config = BacktestConfig(
        initial_balance=Decimal(str(args.initial_balance)),
        fill_rate=Decimal(str(args.fill_rate)),
        slippage_rate=Decimal(str(args.slippage)),
        gas_cost_per_trade=Decimal(str(args.gas_cost)),
        random_seed=args.seed
    )
    
    # Run backtest
    runner = BacktestRunner(args.data_source, config)
    runner.run_and_save(
        output_dir=Path(args.output_dir),
        start_date=start_date,
        end_date=end_date,
        asset_filter=asset_filter
    )


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
