"""
Unit tests for the backtesting framework.

Tests basic functionality of data loader, simulator, and report generator.
"""

import pytest
import tempfile
import csv
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

from src.backtest_data_loader import BacktestDataLoader
from src.backtest_simulator import BacktestSimulator, BacktestConfig
from src.backtest_report import BacktestReport
from src.models import Market, Opportunity


class TestBacktestDataLoader:
    """Test BacktestDataLoader functionality."""
    
    def test_load_from_csv(self):
        """Test loading markets from CSV file."""
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'market_id', 'question', 'asset', 'outcomes',
                'yes_price', 'no_price', 'yes_token_id', 'no_token_id',
                'volume', 'liquidity', 'end_time', 'resolution_source'
            ])
            
            end_time = datetime.now() + timedelta(minutes=15)
            writer.writerow([
                '0x1234', 'BTC above $95000?', 'BTC', 'YES,NO',
                '0.48', '0.47', '0xyes', '0xno',
                '10000.0', '5000.0', end_time.isoformat(), 'CEX_PRICE'
            ])
            
            csv_path = f.name
        
        try:
            # Load data
            loader = BacktestDataLoader(csv_path)
            markets = loader.load_markets()
            
            assert len(markets) == 1
            assert markets[0].market_id == '0x1234'
            assert markets[0].asset == 'BTC'
            assert markets[0].yes_price == Decimal('0.48')
            assert markets[0].no_price == Decimal('0.47')
        
        finally:
            Path(csv_path).unlink()
    
    def test_date_range_filtering(self):
        """Test filtering markets by date range."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'market_id', 'question', 'asset', 'outcomes',
                'yes_price', 'no_price', 'yes_token_id', 'no_token_id',
                'volume', 'liquidity', 'end_time', 'resolution_source'
            ])
            
            # Add markets at different times
            base_time = datetime(2025, 1, 1, 12, 0, 0)
            for i in range(5):
                end_time = base_time + timedelta(hours=i)
                writer.writerow([
                    f'0x{i}', f'BTC above $95000?', 'BTC', 'YES,NO',
                    '0.48', '0.47', '0xyes', '0xno',
                    '10000.0', '5000.0', end_time.isoformat(), 'CEX_PRICE'
                ])
            
            csv_path = f.name
        
        try:
            loader = BacktestDataLoader(csv_path)
            
            # Filter to middle 3 markets
            start_date = base_time + timedelta(hours=1)
            end_date = base_time + timedelta(hours=3)
            
            markets = loader.load_markets(start_date=start_date, end_date=end_date)
            
            assert len(markets) == 3
        
        finally:
            Path(csv_path).unlink()
    
    def test_asset_filtering(self):
        """Test filtering markets by asset."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'market_id', 'question', 'asset', 'outcomes',
                'yes_price', 'no_price', 'yes_token_id', 'no_token_id',
                'volume', 'liquidity', 'end_time', 'resolution_source'
            ])
            
            end_time = datetime.now() + timedelta(minutes=15)
            assets = ['BTC', 'ETH', 'SOL', 'BTC', 'ETH']
            
            for i, asset in enumerate(assets):
                writer.writerow([
                    f'0x{i}', f'{asset} above $95000?', asset, 'YES,NO',
                    '0.48', '0.47', '0xyes', '0xno',
                    '10000.0', '5000.0', end_time.isoformat(), 'CEX_PRICE'
                ])
            
            csv_path = f.name
        
        try:
            loader = BacktestDataLoader(csv_path)
            
            # Filter to BTC only
            markets = loader.load_markets(asset_filter=['BTC'])
            
            assert len(markets) == 2
            assert all(m.asset == 'BTC' for m in markets)
        
        finally:
            Path(csv_path).unlink()


class TestBacktestSimulator:
    """Test BacktestSimulator functionality."""
    
    def test_successful_trade_simulation(self):
        """Test simulating a successful trade."""
        config = BacktestConfig(
            initial_balance=Decimal('100.0'),
            fill_rate=Decimal('1.0'),  # Always fill
            slippage_rate=Decimal('0.0'),  # No slippage
            gas_cost_per_trade=Decimal('0.02'),
            simulate_failures=False
        )
        
        simulator = BacktestSimulator(config)
        
        # Create opportunity
        opportunity = Opportunity(
            opportunity_id='test_1',
            market_id='0x1234',
            strategy='internal',
            timestamp=datetime.now(),
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_fee=Decimal('0.028'),
            no_fee=Decimal('0.029'),
            total_cost=Decimal('0.9748'),
            expected_profit=Decimal('0.0252'),
            profit_percentage=Decimal('0.0252'),
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        # Simulate trade
        result = simulator.simulate_trade(opportunity)
        
        assert result.was_successful()
        assert result.yes_filled
        assert result.no_filled
        assert result.net_profit > 0
        assert simulator.balance > config.initial_balance
    
    def test_failed_trade_simulation(self):
        """Test simulating a failed trade."""
        config = BacktestConfig(
            initial_balance=Decimal('100.0'),
            fill_rate=Decimal('0.0'),  # Never fill
            simulate_failures=True
        )
        
        simulator = BacktestSimulator(config)
        
        opportunity = Opportunity(
            opportunity_id='test_1',
            market_id='0x1234',
            strategy='internal',
            timestamp=datetime.now(),
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_fee=Decimal('0.028'),
            no_fee=Decimal('0.029'),
            total_cost=Decimal('0.9748'),
            expected_profit=Decimal('0.0252'),
            profit_percentage=Decimal('0.0252'),
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        result = simulator.simulate_trade(opportunity)
        
        assert not result.was_successful()
        assert result.status == 'failed'
        assert result.net_profit < 0  # Lost gas cost
    
    def test_insufficient_balance(self):
        """Test trade fails when balance is insufficient."""
        config = BacktestConfig(
            initial_balance=Decimal('0.50'),  # Very low balance
            fill_rate=Decimal('1.0')
        )
        
        simulator = BacktestSimulator(config)
        
        opportunity = Opportunity(
            opportunity_id='test_1',
            market_id='0x1234',
            strategy='internal',
            timestamp=datetime.now(),
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_fee=Decimal('0.028'),
            no_fee=Decimal('0.029'),
            total_cost=Decimal('0.9748'),
            expected_profit=Decimal('0.0252'),
            profit_percentage=Decimal('0.0252'),
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        result = simulator.simulate_trade(opportunity)
        
        assert not result.was_successful()
        assert 'Insufficient balance' in result.error_message
    
    def test_portfolio_tracking(self):
        """Test portfolio history is tracked correctly."""
        config = BacktestConfig(
            initial_balance=Decimal('100.0'),
            fill_rate=Decimal('1.0'),
            simulate_failures=False
        )
        
        simulator = BacktestSimulator(config)
        
        # Execute multiple trades
        for i in range(5):
            opportunity = Opportunity(
                opportunity_id=f'test_{i}',
                market_id=f'0x{i}',
                strategy='internal',
                timestamp=datetime.now(),
                yes_price=Decimal('0.48'),
                no_price=Decimal('0.47'),
                yes_fee=Decimal('0.028'),
                no_fee=Decimal('0.029'),
                total_cost=Decimal('0.9748'),
                expected_profit=Decimal('0.0252'),
                profit_percentage=Decimal('0.0252'),
                position_size=Decimal('1.0'),
                gas_estimate=100000
            )
            
            simulator.simulate_trade(opportunity)
        
        # Check portfolio history
        history = simulator.get_portfolio_history()
        assert len(history) == 5
        
        # Balance should increase over time
        assert history[-1].balance > history[0].balance


class TestBacktestReport:
    """Test BacktestReport functionality."""
    
    def test_calculate_metrics(self):
        """Test metrics calculation."""
        config = BacktestConfig(
            initial_balance=Decimal('100.0'),
            fill_rate=Decimal('1.0'),
            simulate_failures=False
        )
        
        simulator = BacktestSimulator(config)
        
        # Execute trades
        for i in range(10):
            opportunity = Opportunity(
                opportunity_id=f'test_{i}',
                market_id=f'0x{i}',
                strategy='internal',
                timestamp=datetime.now(),
                yes_price=Decimal('0.48'),
                no_price=Decimal('0.47'),
                yes_fee=Decimal('0.028'),
                no_fee=Decimal('0.029'),
                total_cost=Decimal('0.9748'),
                expected_profit=Decimal('0.0252'),
                profit_percentage=Decimal('0.0252'),
                position_size=Decimal('1.0'),
                gas_estimate=100000
            )
            
            simulator.simulate_trade(opportunity)
        
        # Generate report
        report = BacktestReport(simulator)
        metrics = report.calculate_metrics()
        
        assert metrics['total_trades'] == 10
        assert metrics['successful_trades'] == 10
        assert metrics['failed_trades'] == 0
        assert metrics['win_rate'] == 100.0
        assert metrics['net_profit'] > 0
        assert metrics['passes_win_rate_threshold']
    
    def test_win_rate_validation(self):
        """Test win rate threshold validation."""
        config = BacktestConfig(
            initial_balance=Decimal('100.0'),
            fill_rate=Decimal('0.99'),  # 99% fill rate
            simulate_failures=True,
            random_seed=42
        )
        
        simulator = BacktestSimulator(config)
        
        # Execute many trades to get realistic win rate
        for i in range(200):
            opportunity = Opportunity(
                opportunity_id=f'test_{i}',
                market_id=f'0x{i}',
                strategy='internal',
                timestamp=datetime.now(),
                yes_price=Decimal('0.48'),
                no_price=Decimal('0.47'),
                yes_fee=Decimal('0.028'),
                no_fee=Decimal('0.029'),
                total_cost=Decimal('0.9748'),
                expected_profit=Decimal('0.0252'),
                profit_percentage=Decimal('0.0252'),
                position_size=Decimal('1.0'),
                gas_estimate=100000
            )
            
            simulator.simulate_trade(opportunity)
        
        report = BacktestReport(simulator)
        metrics = report.calculate_metrics()
        
        # With 99% fill rate and 200 trades, should be close to 99%
        assert metrics['win_rate'] >= 95.0  # Allow some variance
        assert metrics['total_trades'] == 200
    
    def test_report_generation(self):
        """Test report generation in different formats."""
        config = BacktestConfig(initial_balance=Decimal('100.0'))
        simulator = BacktestSimulator(config)
        
        # Execute one trade
        opportunity = Opportunity(
            opportunity_id='test_1',
            market_id='0x1234',
            strategy='internal',
            timestamp=datetime.now(),
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_fee=Decimal('0.028'),
            no_fee=Decimal('0.029'),
            total_cost=Decimal('0.9748'),
            expected_profit=Decimal('0.0252'),
            profit_percentage=Decimal('0.0252'),
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        simulator.simulate_trade(opportunity)
        
        report = BacktestReport(simulator)
        
        # Test different formats
        text_report = report.generate_report('text')
        assert 'BACKTEST PERFORMANCE REPORT' in text_report
        assert 'Win Rate:' in text_report
        
        json_report = report.generate_report('json')
        assert 'backtest_report' in json_report
        assert 'metrics' in json_report
        
        md_report = report.generate_report('markdown')
        assert '# Backtest Performance Report' in md_report
        assert '## Trade Statistics' in md_report


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
