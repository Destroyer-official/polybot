"""
Property-based tests for Trade History Database.

Property 53: Trade History Persistence
**Validates: Requirements 19.4**

For any completed trade, the system should store the full trade record
(timestamp, market_id, strategy, prices, profit, gas_cost) in the SQLite database.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from decimal import Decimal
from datetime import datetime, timedelta
import tempfile
import os

from src.trade_history import TradeHistoryDB
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
    yes_price = draw(decimal_strategy(min_value=Decimal('0.01'), max_value=Decimal('0.99')))
    no_price = draw(decimal_strategy(min_value=Decimal('0.01'), max_value=Decimal('0.99')))
    
    # Generate fees (0.1% to 3%)
    yes_fee = draw(decimal_strategy(min_value=Decimal('0.001'), max_value=Decimal('0.03')))
    no_fee = draw(decimal_strategy(min_value=Decimal('0.001'), max_value=Decimal('0.03')))
    
    # Calculate costs
    total_cost = yes_price + no_price + (yes_price * yes_fee) + (no_price * no_fee)
    expected_profit = Decimal('1.0') - total_cost
    profit_percentage = expected_profit / total_cost if total_cost > 0 else Decimal('0')
    
    position_size = draw(decimal_strategy(min_value=Decimal('0.1'), max_value=Decimal('5.0')))
    
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
        gas_cost = draw(decimal_strategy(min_value=Decimal('0.01'), max_value=Decimal('0.1')))
        net_profit = actual_profit - gas_cost
        error_message = None
    else:
        actual_cost = Decimal('0')
        actual_profit = Decimal('0')
        gas_cost = draw(decimal_strategy(min_value=Decimal('0.01'), max_value=Decimal('0.05')))
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


class TestTradeHistoryProperties:
    """Property-based tests for trade history persistence."""
    
    @given(trade=trade_result_strategy())
    @settings(max_examples=100, deadline=None)
    def test_property_53_trade_history_persistence(self, trade):
        """
        Property 53: Trade History Persistence
        
        **Validates: Requirements 19.4**
        
        For any completed trade, the system should store the full trade record
        (timestamp, market_id, strategy, prices, profit, gas_cost) in the SQLite database.
        
        This property verifies that:
        1. Trade can be inserted into database
        2. Trade can be retrieved with same ID
        3. All fields are persisted correctly
        4. Decimal values maintain precision
        5. Optional fields are handled correctly
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            # Initialize database
            db = TradeHistoryDB(db_path=temp_db)
            
            # Insert trade
            success = db.insert_trade(trade)
            assert success, "Trade insertion should succeed"
            
            # Retrieve trade
            retrieved = db.get_trade(trade.trade_id)
            assert retrieved is not None, "Trade should be retrievable"
            
            # Verify all required fields
            assert retrieved['trade_id'] == trade.trade_id
            assert retrieved['market_id'] == trade.opportunity.market_id
            assert retrieved['strategy'] == trade.opportunity.strategy
            assert retrieved['status'] == trade.status
            
            # Verify prices (convert back to Decimal for comparison)
            assert abs(Decimal(retrieved['yes_price']) - trade.opportunity.yes_price) < Decimal('0.0001')
            assert abs(Decimal(retrieved['no_price']) - trade.opportunity.no_price) < Decimal('0.0001')
            assert abs(Decimal(retrieved['yes_fee']) - trade.opportunity.yes_fee) < Decimal('0.0001')
            assert abs(Decimal(retrieved['no_fee']) - trade.opportunity.no_fee) < Decimal('0.0001')
            
            # Verify financial results
            assert abs(Decimal(retrieved['actual_profit']) - trade.actual_profit) < Decimal('0.0001')
            assert abs(Decimal(retrieved['gas_cost']) - trade.gas_cost) < Decimal('0.0001')
            assert abs(Decimal(retrieved['net_profit']) - trade.net_profit) < Decimal('0.0001')
            
            # Verify boolean fields
            assert retrieved['yes_filled'] == (1 if trade.yes_filled else 0)
            assert retrieved['no_filled'] == (1 if trade.no_filled else 0)
            
            # Verify optional fields
            if trade.yes_order_id:
                assert retrieved['yes_order_id'] == trade.yes_order_id
            if trade.error_message:
                assert retrieved['error_message'] == trade.error_message
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
    
    @given(trades=st.lists(trade_result_strategy(), min_size=1, max_size=50))
    @settings(max_examples=50, deadline=None)
    def test_multiple_trades_persistence(self, trades):
        """
        Test that multiple trades can be stored and retrieved correctly.
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            db = TradeHistoryDB(db_path=temp_db)
            
            # Insert all trades
            for trade in trades:
                success = db.insert_trade(trade)
                assert success, f"Failed to insert trade {trade.trade_id}"
            
            # Verify count
            total_count = db.get_total_trade_count()
            assert total_count == len(trades), \
                f"Trade count mismatch: {total_count} != {len(trades)}"
            
            # Retrieve and verify each trade
            for trade in trades:
                retrieved = db.get_trade(trade.trade_id)
                assert retrieved is not None, f"Trade {trade.trade_id} not found"
                assert retrieved['trade_id'] == trade.trade_id
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
    
    @given(trades=st.lists(trade_result_strategy(), min_size=5, max_size=30))
    @settings(max_examples=50, deadline=None)
    def test_query_by_strategy(self, trades):
        """
        Test that trades can be queried by strategy type.
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            db = TradeHistoryDB(db_path=temp_db)
            
            # Insert all trades
            for trade in trades:
                db.insert_trade(trade)
            
            # Count trades by strategy
            strategy_counts = {}
            for trade in trades:
                strategy = trade.opportunity.strategy
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            
            # Query and verify each strategy
            for strategy, expected_count in strategy_counts.items():
                retrieved = db.get_trades_by_strategy(strategy)
                assert len(retrieved) == expected_count, \
                    f"Strategy {strategy} count mismatch: {len(retrieved)} != {expected_count}"
                
                # Verify all retrieved trades have correct strategy
                for trade_data in retrieved:
                    assert trade_data['strategy'] == strategy
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
    
    @given(trades=st.lists(trade_result_strategy(), min_size=5, max_size=30))
    @settings(max_examples=50, deadline=None)
    def test_query_successful_and_failed_trades(self, trades):
        """
        Test that trades can be filtered by success/failure status.
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            db = TradeHistoryDB(db_path=temp_db)
            
            # Insert all trades
            for trade in trades:
                db.insert_trade(trade)
            
            # Count successful and failed trades
            successful_count = sum(1 for t in trades if t.was_successful())
            failed_count = len(trades) - successful_count
            
            # Query successful trades
            successful_trades = db.get_successful_trades()
            assert len(successful_trades) == successful_count, \
                f"Successful trades count mismatch: {len(successful_trades)} != {successful_count}"
            
            # Verify all are successful
            for trade_data in successful_trades:
                assert trade_data['status'] == 'success'
            
            # Query failed trades
            failed_trades = db.get_failed_trades()
            assert len(failed_trades) == failed_count, \
                f"Failed trades count mismatch: {len(failed_trades)} != {failed_count}"
            
            # Verify all are failed
            for trade_data in failed_trades:
                assert trade_data['status'] != 'success'
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
    
    @given(trade=trade_result_strategy())
    @settings(max_examples=50, deadline=None)
    def test_duplicate_trade_prevention(self, trade):
        """
        Test that duplicate trades (same trade_id) cannot be inserted.
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            db = TradeHistoryDB(db_path=temp_db)
            
            # Insert trade first time
            success1 = db.insert_trade(trade)
            assert success1, "First insertion should succeed"
            
            # Try to insert same trade again
            success2 = db.insert_trade(trade)
            assert not success2, "Duplicate insertion should fail"
            
            # Verify only one trade exists
            total_count = db.get_total_trade_count()
            assert total_count == 1, "Should only have one trade"
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
    
    @given(trades=st.lists(trade_result_strategy(), min_size=10, max_size=50))
    @settings(max_examples=30, deadline=None)
    def test_recent_trades_limit(self, trades):
        """
        Test that get_recent_trades respects the limit parameter.
        """
        # Create temporary database
        fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            db = TradeHistoryDB(db_path=temp_db)
            
            # Insert all trades
            for trade in trades:
                db.insert_trade(trade)
            
            # Test various limits
            for limit in [5, 10, 20]:
                if limit <= len(trades):
                    retrieved = db.get_recent_trades(limit=limit)
                    assert len(retrieved) == limit, \
                        f"Should return exactly {limit} trades"
        
        finally:
            # Cleanup
            if os.path.exists(temp_db):
                os.unlink(temp_db)
