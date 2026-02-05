#!/usr/bin/env python3
"""
CLI tool for generating trade reports.

Usage:
    python generate_report.py --period daily --format console
    python generate_report.py --period weekly --format csv
    python generate_report.py --period monthly --format json
    python generate_report.py --period all --format all

Validates Requirement 19.3: Create CLI command for reports
"""

import argparse
import sys
from pathlib import Path

from src.trade_history import TradeHistoryDB
from src.trade_statistics import TradeStatisticsTracker
from src.report_generator import ReportGenerator


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Polymarket Arbitrage Bot trade reports"
    )
    
    parser.add_argument(
        '--period',
        choices=['daily', 'weekly', 'monthly', 'all'],
        default='daily',
        help='Report period (default: daily)'
    )
    
    parser.add_argument(
        '--format',
        choices=['console', 'csv', 'json', 'all'],
        default='console',
        help='Output format (default: console)'
    )
    
    parser.add_argument(
        '--output-dir',
        default='reports',
        help='Output directory for files (default: reports)'
    )
    
    parser.add_argument(
        '--db-path',
        default='data/trade_history.db',
        help='Path to trade history database (default: data/trade_history.db)'
    )
    
    args = parser.parse_args()
    
    # Check if database exists
    if not Path(args.db_path).exists():
        print(f"Error: Database not found at {args.db_path}")
        print("No trades have been recorded yet.")
        sys.exit(1)
    
    try:
        # Initialize components
        print(f"Loading trade history from {args.db_path}...")
        db = TradeHistoryDB(db_path=args.db_path)
        stats_tracker = TradeStatisticsTracker(db)
        report_gen = ReportGenerator(db, stats_tracker, output_dir=args.output_dir)
        
        # Generate reports based on format
        if args.format == 'console' or args.format == 'all':
            print("\n")
            report_gen.print_console_report(period=args.period)
        
        if args.format == 'csv' or args.format == 'all':
            csv_path = report_gen.export_to_csv(period=args.period)
            print(f"\nCSV report saved to: {csv_path}")
        
        if args.format == 'json' or args.format == 'all':
            json_path = report_gen.export_to_json(period=args.period)
            print(f"JSON report saved to: {json_path}")
        
        print("\nReport generation complete!")
        
    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
