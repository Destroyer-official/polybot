"""
Example script demonstrating how to use the backtesting framework.

This script shows how to:
1. Create sample historical data
2. Run a backtest
3. Generate and review reports
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import csv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtest_runner import BacktestRunner
from src.backtest_simulator import BacktestConfig


def create_sample_data(output_path: Path, num_markets: int = 100):
    """
    Create sample historical market data for testing.
    
    Args:
        output_path: Path to save CSV file
        num_markets: Number of sample markets to generate
    """
    print(f"Creating {num_markets} sample markets...")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'market_id', 'question', 'asset', 'outcomes',
            'yes_price', 'no_price', 'yes_token_id', 'no_token_id',
            'volume', 'liquidity', 'end_time', 'resolution_source'
        ])
        
        # Generate sample markets
        base_time = datetime.now()
        assets = ['BTC', 'ETH', 'SOL', 'XRP']
        
        for i in range(num_markets):
            asset = assets[i % len(assets)]
            market_time = base_time + timedelta(minutes=15 * i)
            
            # Create arbitrage opportunities (YES + NO < 1.00)
            # Some profitable, some not
            if i % 3 == 0:
                # Profitable arbitrage
                yes_price = 0.45 + (i % 10) * 0.01
                no_price = 0.48 + (i % 8) * 0.01
            elif i % 3 == 1:
                # Marginal arbitrage
                yes_price = 0.49
                no_price = 0.49
            else:
                # No arbitrage
                yes_price = 0.52
                no_price = 0.50
            
            writer.writerow([
                f"0x{i:064x}",  # market_id
                f"{asset} above $95000 in 15 minutes?",  # question
                asset,  # asset
                "YES,NO",  # outcomes
                f"{yes_price:.4f}",  # yes_price
                f"{no_price:.4f}",  # no_price
                f"0x{i:064x}01",  # yes_token_id
                f"0x{i:064x}02",  # no_token_id
                "10000.0",  # volume
                "5000.0",  # liquidity
                market_time.isoformat(),  # end_time
                "CEX_PRICE"  # resolution_source
            ])
    
    print(f"✓ Created sample data: {output_path}")


def run_example_backtest():
    """Run an example backtest with sample data."""
    print("\n" + "=" * 80)
    print("BACKTEST FRAMEWORK EXAMPLE")
    print("=" * 80 + "\n")
    
    # Create sample data
    data_path = Path("backtest_data/sample_markets.csv")
    create_sample_data(data_path, num_markets=200)
    
    # Configure backtest
    config = BacktestConfig(
        initial_balance=Decimal('100.0'),
        fill_rate=Decimal('0.95'),  # 95% fill rate
        slippage_rate=Decimal('0.001'),  # 0.1% slippage
        gas_cost_per_trade=Decimal('0.02'),  # $0.02 gas
        simulate_failures=True,
        random_seed=42  # For reproducible results
    )
    
    print("\nBacktest Configuration:")
    print(f"  Initial Balance: ${config.initial_balance}")
    print(f"  Fill Rate: {float(config.fill_rate) * 100}%")
    print(f"  Slippage: {float(config.slippage_rate) * 100}%")
    print(f"  Gas Cost: ${config.gas_cost_per_trade}")
    print(f"  Random Seed: {config.random_seed}")
    
    # Run backtest
    print("\n" + "-" * 80)
    print("Running backtest...")
    print("-" * 80 + "\n")
    
    runner = BacktestRunner(str(data_path), config)
    
    # Run and save results
    output_dir = Path("backtest_results")
    runner.run_and_save(
        output_dir=output_dir,
        asset_filter=['BTC', 'ETH', 'SOL', 'XRP']
    )
    
    print(f"\n✓ Backtest complete! Results saved to: {output_dir}")
    print("\nGenerated files:")
    print(f"  - backtest_report_*.txt (human-readable report)")
    print(f"  - backtest_report_*.json (machine-readable report)")
    print(f"  - backtest_report_*.md (markdown report)")
    print(f"  - backtest_trades_*.csv (detailed trade history)")


if __name__ == '__main__':
    run_example_backtest()
