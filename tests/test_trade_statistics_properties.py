"""
Property-based tests for Trade Statistics Tracker.

Property 52: Trade Statistics Maintenance
**Validates: Requirements 19.2**

For any completed trade, the system should update running totals including
total_trades, successful_trades, failed_trades, total_profit_usd, and total_gas_cost_usd.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from decimal import Decimal
from datetime import datetime, timedelta
import tempfile
import os

from src.trade_history import TradeHistoryDB
from src.trade_statistics import TradeStatisticsTracker
from src.models import TradeResult, Opportunity


# Strategy for generating valid Decimal values
def decimal_strategy(min_value=0, max_value=1000):
    """Generate Decimal values for prices and amounts."""
    return st.decimals(
        min_value=min_value,
        max_value=max_value,
        allow_nan=False,
        allow_infinity=False,
        places=4
    )


# Counter for generating unique trade IDs
_trade_id_counter = 0

def get_unique_trade_id():
    """Generate a unique trade ID."""
    global _trade_id_counter
    _trade_id_counter += 1
    return f"trade_{_trade_id_counter}_{datetime.now().timestamp()}"

# Strategy for generating trade results
@st.composite
def trade_result_strategy(draw):
    """Generate valid TradeResult objects."""
    trade_id = get_unique_trade_id()
    market_id = f"market_{draw(st.integers(min_value=1, max_value=10000))}"
    strategy = draw(st.sampled_from(['internal', 'cross_platform', 'latency', 'resolution_farming']))
    
    # Generate prices
    yes_price = draw(decimal_strategy(min_value=0.01, max_value=0.99))
    no_price = draw(decimal_strategy(min_value=0.01, max_value=0.99))
    
    # Generate fees (0.1% to 3%)
    yes_fee = draw(decimal_strategy(min_value=0.001, max_value=0.03))
    no_fee = draw(decimal_strategy(min_value=0.001, max_value=0.03))
    
    # Calculate costs
    total_cost = yes_price + no_price + (yes_price * yes_fee) + (no_price * no_fee)
    expected_profit = Decimal('1.0') - total_cost
    profit_percentage = expected_profit / total_cost if total_cost > 0 else Decimal('0')
    
    position_size = draw(decimal_strategy(min_value=0.1, max_value=5.0))
    
    # Create opportunity
    opportunity = Opportunity(
        opportunity_id=f"opp_{trade_id}",
        market_id=market_id,
        strategy=strategy,
        timestamp=datetime.now(),
        yes_price=yes_price,
        no_price=no_price,
        yes_fee=yes_fee,
        no_fee=no_fee,
        total_cost=total_cost,
        expected_profit=expected_profit,
        profit_percentage=profit_percentage,
        position_size=position_size,
        gas_estimate=100000,
    )
    
    # Generate execution results
    status = draw(st.sampled_from(['success', 'failed']))
    yes_filled = status == 'success'
    no_filled = status == 'success'
    
    if status == 'success':
        actual_cost = total_cost * position_size
        actual_profit = expected_profit * position_size
        gas_cost = draw(decimal_strategy(min_value=0.01, max_value=0.1))
        net_profit = actual_profit - gas_cost
        error_message = None
    else:
        actual_cost = Decimal('0')
        actual_profit = Decimal('0')
        gas_cost = draw(decimal_strategy(min_value=0.01, max_value=0.05))
        net_profit = -gas_cost
        error_message = "Trade failed"
    
    return TradeResult(
        trade_id=trade_id,
        opportunity=opportunity,
        timestamp=datetime.now(),
        status=status,
        yes_order_id=f"yes_{trade_id}" if yes_filled else None,
        no_order_id=f"no_{trade_id}" if no_filled else None,
        yes_filled=yes_filled,
        no_filled=no_filled,
        yes_fill_price=yes_price if yes_filled else None,
        no_fill_price=no_price if no_filled else None,
        actual_cost=actual_cost,
        actual_profit=actual_profit,
        gas_cost=gas_cost,
        net_profit=net_profit,
        error_message=error_message,
    )


class TestTradeStatisticsProperties:
    """Property-based tests for trade statistics."""
    
    @given(trades=st.lists(trade_result_strategy(), min_size=1, max_size=50))
    @settings(max_examples=100, deadline=None)
    def test_property_52_trade_statistics_maintenance(self, trades):
        """
        Property 52: Trade Statistics Maintenance
        
        **Validates: Requirements 19.2**
        
        For any completed trade, the system should update running totals including
        total_trades, successful_trades, failed_trades, total_profit_usd, and
        total_gas_cost_usd.
        
        This property verifies that:
        1. Total trades count increases by 1 for each trade
        2. Successful/failed counts are accurate
        3. Total profit accumulates correctly
        4. Total gas cost accumulates correctly
        5. Win rate is calculated correctly
        6. Average profit per trade is accurate
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            # Initialize database and tracker
            db = TradeHistoryDB(db_path=temp_db)
            tracker = TradeStatisticsTracker(db)
            
            # Track expected values
            expected_total = 0
            expected_successful = 0
            expected_failed = 0
            expected_profit = Decimal('0')
            expected_gas = Decimal('0')
            
            # Process each trade
            for trade in trades:
                # Store trade in database
                db.insert_trade(trade)
                
                # Update tracker
                tracker.update_after_trade(trade)
                
                # Update expected values
                expected_total += 1
                if trade.was_successful():
                    expected_successful += 1
                else:
                    expected_failed += 1
                
                expected_profit += trade.actual_profit
                expected_gas += trade.gas_cost
                
                # Verify running totals
                assert tracker.total_trades == expected_total, \
                    f"Total trades mismatch: {tracker.total_trades} != {expected_total}"
                
                assert tracker.successful_trades == expected_successful, \
                    f"Successful trades mismatch: {tracker.successful_trades} != {expected_successful}"
                
                assert tracker.failed_trades == expected_failed, \
                    f"Failed trades mismatch: {tracker.failed_trades} != {expected_failed}"
                
                # Verify profit totals (allow small rounding differences)
                assert abs(tracker.total_profit - expected_profit) < Decimal('0.0001'), \
                    f"Total profit mismatch: {tracker.total_profit} != {expected_profit}"
                
                assert abs(tracker.total_gas_cost - expected_gas) < Decimal('0.0001'), \
                    f"Total gas cost mismatch: {tracker.total_gas_cost} != {expected_gas}"
            
            # Verify final calculations
            final_win_rate = tracker.get_win_rate()
            expected_win_rate = (Decimal(expected_successful) / Decimal(expected_total)) * Decimal('100')
            assert abs(final_win_rate - expected_win_rate) < Decimal('0.01'), \
                f"Win rate mismatch: {final_win_rate} != {expected_win_rate}"
            
            final_avg_profit = tracker.get_avg_profit_per_trade()
            expected_avg_profit = expected_profit / Decimal(expected_total)
            assert abs(final_avg_profit - expected_avg_profit) < Decimal('0.0001'), \
                f"Average profit mismatch: {final_avg_profit} != {expected_avg_profit}"
            
            final_net_profit = tracker.get_net_profit()
            expected_net_profit = expected_profit - expected_gas
            assert abs(final_net_profit - expected_net_profit) < Decimal('0.0001'), \
                f"Net profit mismatch: {final_net_profit} != {expected_net_profit}"
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
    
    @given(trades=st.lists(trade_result_strategy(), min_size=10, max_size=100))
    @settings(max_examples=50, deadline=None)
    def test_statistics_consistency_after_reload(self, trades):
        """
        Test that statistics remain consistent after reloading from database.
        
        This verifies that the tracker correctly loads state from the database
        on initialization.
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            # Initialize and populate database
            db = TradeHistoryDB(db_path=temp_db)
            tracker1 = TradeStatisticsTracker(db)
            
            for trade in trades:
                db.insert_trade(trade)
                tracker1.update_after_trade(trade)
            
            # Get statistics from first tracker
            stats1 = tracker1.get_statistics()
            
            # Create new tracker (should load from database)
            tracker2 = TradeStatisticsTracker(db)
            stats2 = tracker2.get_statistics()
            
            # Verify consistency
            assert stats1.total_trades == stats2.total_trades
            assert stats1.successful_trades == stats2.successful_trades
            assert stats1.failed_trades == stats2.failed_trades
            assert abs(stats1.total_profit - stats2.total_profit) < Decimal('0.0001')
            assert abs(stats1.total_gas_cost - stats2.total_gas_cost) < Decimal('0.0001')
            assert abs(stats1.win_rate - stats2.win_rate) < Decimal('0.01')
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
    
    @given(trades=st.lists(trade_result_strategy(), min_size=5, max_size=20))
    @settings(max_examples=50, deadline=None)
    def test_profit_factor_calculation(self, trades):
        """
        Test that profit factor is calculated correctly.
        
        Profit factor = Total gains / Total losses
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            db = TradeHistoryDB(db_path=temp_db)
            tracker = TradeStatisticsTracker(db)
            
            total_gains = Decimal('0')
            total_losses = Decimal('0')
            
            for trade in trades:
                db.insert_trade(trade)
                tracker.update_after_trade(trade)
                
                if trade.actual_profit > 0:
                    total_gains += trade.actual_profit
                else:
                    total_losses += abs(trade.actual_profit)
            
            stats = tracker.get_statistics()
            
            if total_losses == 0:
                # All trades profitable - profit factor should be very high
                assert stats.profit_factor > Decimal('100')
            else:
                expected_pf = total_gains / total_losses
                # Allow some tolerance for calculation differences
                assert abs(stats.profit_factor - expected_pf) < Decimal('0.1')
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
    
    @given(trades=st.lists(trade_result_strategy(), min_size=2, max_size=50))
    @settings(max_examples=50, deadline=None)
    def test_max_drawdown_calculation(self, trades):
        """
        Test that maximum drawdown is calculated correctly.
        
        Max drawdown is the largest peak-to-trough decline in cumulative profit.
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            db = TradeHistoryDB(db_path=temp_db)
            tracker = TradeStatisticsTracker(db)
            
            cumulative_profit = Decimal('0')
            peak_profit = Decimal('0')
            expected_max_drawdown = Decimal('0')
            
            for trade in trades:
                db.insert_trade(trade)
                tracker.update_after_trade(trade)
                
                cumulative_profit += trade.actual_profit
                
                if cumulative_profit > peak_profit:
                    peak_profit = cumulative_profit
                
                drawdown = peak_profit - cumulative_profit
                if drawdown > expected_max_drawdown:
                    expected_max_drawdown = drawdown
            
            stats = tracker.get_statistics()
            
            # Allow small tolerance for calculation differences
            assert abs(stats.max_drawdown - expected_max_drawdown) < Decimal('0.01'), \
                f"Max drawdown mismatch: {stats.max_drawdown} != {expected_max_drawdown}"
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
    
    @given(trades=st.lists(trade_result_strategy(), min_size=1, max_size=30))
    @settings(max_examples=50, deadline=None)
    def test_strategy_breakdown_accuracy(self, trades):
        """
        Test that strategy breakdown statistics are accurate.
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            db = TradeHistoryDB(db_path=temp_db)
            tracker = TradeStatisticsTracker(db)
            
            # Track expected values by strategy
            strategy_counts = {}
            
            for trade in trades:
                db.insert_trade(trade)
                tracker.update_after_trade(trade)
                
                strategy = trade.opportunity.strategy
                if strategy not in strategy_counts:
                    strategy_counts[strategy] = {
                        'total': 0,
                        'successful': 0,
                        'profit': Decimal('0'),
                        'gas': Decimal('0'),
                    }
                
                strategy_counts[strategy]['total'] += 1
                if trade.was_successful():
                    strategy_counts[strategy]['successful'] += 1
                strategy_counts[strategy]['profit'] += trade.actual_profit
                strategy_counts[strategy]['gas'] += trade.gas_cost
            
            stats = tracker.get_statistics()
            
            # Verify each strategy's statistics
            for strategy, expected in strategy_counts.items():
                assert strategy in stats.strategy_stats, \
                    f"Strategy {strategy} missing from breakdown"
                
                actual = stats.strategy_stats[strategy]
                
                assert actual['total'] == expected['total'], \
                    f"Strategy {strategy} total mismatch"
                
                assert actual['successful'] == expected['successful'], \
                    f"Strategy {strategy} successful count mismatch"
                
                assert abs(actual['profit'] - expected['profit']) < Decimal('0.0001'), \
                    f"Strategy {strategy} profit mismatch"
                
                assert abs(actual['gas_cost'] - expected['gas']) < Decimal('0.0001'), \
                    f"Strategy {strategy} gas cost mismatch"
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
