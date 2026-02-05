"""
Property-based tests for Internal Arbitrage Engine.

Tests arbitrage detection and profit calculation using property-based testing with Hypothesis.
Validates Requirements 1.1, 1.2, and 2.4.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timedelta
import asyncio

import rust_core
from src.models import Market, Opportunity
from src.internal_arbitrage_engine import InternalArbitrageEngine
from src.ai_safety_guard import AISafetyGuard
from src.kelly_position_sizer import KellyPositionSizer
from src.order_manager import OrderManager
from src.position_merger import PositionMerger
from src.transaction_manager import TransactionManager


# Helper function to create a test market
def create_test_market(
    market_id: str,
    yes_price: Decimal,
    no_price: Decimal,
    asset: str = "BTC"
) -> Market:
    """Create a test market with given prices."""
    return Market(
        market_id=market_id,
        question=f"Will {asset} be above $95,000 in 15 minutes?",
        asset=asset,
        outcomes=["YES", "NO"],
        yes_price=yes_price,
        no_price=no_price,
        yes_token_id=f"yes_token_{market_id}",
        no_token_id=f"no_token_{market_id}",
        volume=Decimal('10000.0'),
        liquidity=Decimal('5000.0'),
        end_time=datetime.now() + timedelta(minutes=15),
        resolution_source="CEX"
    )


@given(
    yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_internal_arbitrage_detection(yes_price, no_price):
    """
    **Validates: Requirements 1.1, 1.2**
    
    Feature: polymarket-arbitrage-bot, Property 2: Internal Arbitrage Detection
    
    For any market with YES and NO prices, if total cost < $0.995,
    the system should identify it as a valid internal arbitrage opportunity.
    
    Property: For all (yes_price, no_price) where:
        total_cost = yes_price + no_price + yes_fee + no_fee
        If total_cost < 0.995, then opportunity is detected
        If total_cost >= 0.995, then opportunity is not detected
    """
    # Calculate total cost using Rust fee calculator (Requirement 1.1)
    yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
    
    # Create test market
    market = create_test_market(
        market_id="test_market_001",
        yes_price=Decimal(str(yes_price)),
        no_price=Decimal(str(no_price))
    )
    
    # Create minimal engine for testing (no real dependencies needed for detection)
    engine = InternalArbitrageEngine(
        clob_client=None,
        order_manager=None,
        position_merger=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')  # 0.5%
    )
    
    # Scan for opportunities
    opportunities = asyncio.run(engine.scan_opportunities([market]))
    
    # Verify detection logic (Requirement 1.2)
    if total_cost < 0.995:
        # Should detect opportunity
        profit = 1.0 - total_cost
        profit_percentage = profit / total_cost if total_cost > 0 else 0
        
        if profit_percentage >= 0.005:  # Above minimum threshold
            assert len(opportunities) == 1, \
                f"Should detect opportunity when total_cost={total_cost:.6f} < 0.995 " \
                f"and profit%={profit_percentage*100:.2f}% >= 0.5%"
            
            opp = opportunities[0]
            assert opp.strategy == "internal_arbitrage"
            assert opp.market_id == market.market_id
            
            # Verify cost calculation
            assert abs(float(opp.total_cost) - total_cost) < 1e-6, \
                "Total cost mismatch in opportunity"
            
            # Verify profit calculation
            expected_profit = 1.0 - total_cost
            assert abs(float(opp.expected_profit) - expected_profit) < 1e-6, \
                "Profit calculation mismatch"
        else:
            # Below minimum threshold, should not detect
            assert len(opportunities) == 0, \
                f"Should not detect opportunity when profit%={profit_percentage*100:.2f}% < 0.5%"
    else:
        # Should not detect opportunity
        assert len(opportunities) == 0, \
            f"Should not detect opportunity when total_cost={total_cost:.6f} >= 0.995"


@given(
    yes_price=st.floats(min_value=0.01, max_value=0.49, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.49, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_profitable_arbitrage_always_detected(yes_price, no_price):
    """
    Property test: All profitable arbitrage opportunities are detected.
    
    When YES + NO prices are low enough to guarantee profit after fees,
    the system must detect the opportunity.
    """
    # Ensure prices are low enough to be profitable
    assume(yes_price + no_price < 0.95)
    
    # Calculate total cost
    yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
    
    # If total cost is profitable, it should be detected
    if total_cost < 0.995:
        market = create_test_market(
            market_id="test_market_002",
            yes_price=Decimal(str(yes_price)),
            no_price=Decimal(str(no_price))
        )
        
        engine = InternalArbitrageEngine(
            clob_client=None,
            order_manager=None,
            position_merger=None,
            ai_safety_guard=None,
            kelly_sizer=None,
            min_profit_threshold=Decimal('0.005')
        )
        
        opportunities = asyncio.run(engine.scan_opportunities([market]))
        
        profit = 1.0 - total_cost
        profit_percentage = profit / total_cost if total_cost > 0 else 0
        
        if profit_percentage >= 0.005:
            assert len(opportunities) >= 1, \
                f"Profitable opportunity not detected: yes={yes_price}, no={no_price}, " \
                f"total_cost={total_cost}, profit={profit}"


@given(
    yes_price=st.floats(min_value=0.50, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.50, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_unprofitable_arbitrage_never_detected(yes_price, no_price):
    """
    Property test: Unprofitable opportunities are never detected.
    
    When YES + NO prices are too high, the system must not detect
    an arbitrage opportunity.
    """
    # Ensure prices are high enough to be unprofitable
    assume(yes_price + no_price > 1.0)
    
    # Calculate total cost
    yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
    
    # Should definitely be unprofitable
    assert total_cost >= 0.995, "Sanity check: high prices should be unprofitable"
    
    market = create_test_market(
        market_id="test_market_003",
        yes_price=Decimal(str(yes_price)),
        no_price=Decimal(str(no_price))
    )
    
    engine = InternalArbitrageEngine(
        clob_client=None,
        order_manager=None,
        position_merger=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')
    )
    
    opportunities = asyncio.run(engine.scan_opportunities([market]))
    
    assert len(opportunities) == 0, \
        f"Unprofitable opportunity incorrectly detected: yes={yes_price}, no={no_price}, " \
        f"total_cost={total_cost}"


@given(
    yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_arbitrage_detection_consistency(yes_price, no_price):
    """
    Property test: Detection is consistent across multiple scans.
    
    Scanning the same market multiple times should yield identical results.
    """
    market = create_test_market(
        market_id="test_market_004",
        yes_price=Decimal(str(yes_price)),
        no_price=Decimal(str(no_price))
    )
    
    engine = InternalArbitrageEngine(
        clob_client=None,
        order_manager=None,
        position_merger=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')
    )
    
    # Scan multiple times
    opportunities1 = asyncio.run(engine.scan_opportunities([market]))
    opportunities2 = asyncio.run(engine.scan_opportunities([market]))
    opportunities3 = asyncio.run(engine.scan_opportunities([market]))
    
    # Results should be consistent
    assert len(opportunities1) == len(opportunities2) == len(opportunities3), \
        "Detection results should be consistent across scans"
    
    if len(opportunities1) > 0:
        # Verify profit calculations are identical
        assert opportunities1[0].expected_profit == opportunities2[0].expected_profit, \
            "Profit calculations should be consistent"
        assert opportunities1[0].total_cost == opportunities2[0].total_cost, \
            "Cost calculations should be consistent"


@given(
    yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_minimum_profit_threshold_enforcement(yes_price, no_price):
    """
    Property test: Minimum profit threshold is enforced.
    
    Opportunities below the 0.5% profit threshold should not be detected,
    even if technically profitable.
    """
    # Calculate total cost and profit
    yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
    profit = 1.0 - total_cost
    profit_percentage = profit / total_cost if total_cost > 0 else 0
    
    market = create_test_market(
        market_id="test_market_005",
        yes_price=Decimal(str(yes_price)),
        no_price=Decimal(str(no_price))
    )
    
    engine = InternalArbitrageEngine(
        clob_client=None,
        order_manager=None,
        position_merger=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')  # 0.5%
    )
    
    opportunities = asyncio.run(engine.scan_opportunities([market]))
    
    # Verify threshold enforcement
    if profit_percentage < 0.005:
        assert len(opportunities) == 0, \
            f"Should not detect opportunity below threshold: " \
            f"profit%={profit_percentage*100:.4f}% < 0.5%"
    elif total_cost < 0.995:
        assert len(opportunities) == 1, \
            f"Should detect opportunity above threshold: " \
            f"profit%={profit_percentage*100:.4f}% >= 0.5%"



@given(
    yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_arbitrage_profit_calculation(yes_price, no_price):
    """
    **Validates: Requirement 2.4**
    
    Feature: polymarket-arbitrage-bot, Property 3: Arbitrage Profit Calculation
    
    For any internal arbitrage opportunity, the calculated profit should equal
    $1.00 minus the total cost (including both position prices and fees),
    ensuring accurate profit estimation.
    
    Property: For all (yes_price, no_price):
        profit = 1.00 - (yes_price + no_price + yes_fee + no_fee)
        where yes_fee = yes_price * fee_rate(yes_price)
              no_fee = no_price * fee_rate(no_price)
    """
    # Create engine for testing
    engine = InternalArbitrageEngine(
        clob_client=None,
        order_manager=None,
        position_merger=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')
    )
    
    # Calculate profit using engine
    calculated_profit = engine.calculate_profit(
        Decimal(str(yes_price)),
        Decimal(str(no_price))
    )
    
    # Calculate expected profit manually
    yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
    expected_profit = 1.0 - total_cost
    
    # Verify profit calculation accuracy
    if expected_profit > 0:
        assert calculated_profit is not None, \
            f"Should return profit for profitable opportunity: " \
            f"yes={yes_price}, no={no_price}, expected_profit={expected_profit}"
        
        # Allow small floating-point tolerance
        tolerance = 1e-6
        assert abs(float(calculated_profit) - expected_profit) < tolerance, \
            f"Profit calculation mismatch: expected {expected_profit}, " \
            f"got {calculated_profit}"
    else:
        # Unprofitable, should return None
        assert calculated_profit is None, \
            f"Should return None for unprofitable opportunity: " \
            f"yes={yes_price}, no={no_price}, expected_profit={expected_profit}"


@given(
    yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_profit_includes_all_fees(yes_price, no_price):
    """
    Property test: Profit calculation includes all fees.
    
    The profit calculation must account for both YES and NO position fees,
    not just the position prices.
    """
    # Calculate fees
    yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
    
    # Calculate profit
    engine = InternalArbitrageEngine(
        clob_client=None,
        order_manager=None,
        position_merger=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')
    )
    
    calculated_profit = engine.calculate_profit(
        Decimal(str(yes_price)),
        Decimal(str(no_price))
    )
    
    # Verify fees are included in cost calculation
    cost_without_fees = yes_price + no_price
    cost_with_fees = total_cost
    
    # Fees should increase the cost
    assert cost_with_fees > cost_without_fees, \
        "Total cost should include fees"
    
    # Profit should be less when fees are included
    if calculated_profit is not None:
        profit_without_fees = 1.0 - cost_without_fees
        profit_with_fees = float(calculated_profit)
        
        assert profit_with_fees < profit_without_fees, \
            "Profit should be lower when fees are included"


@given(
    yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_profit_calculation_monotonicity(yes_price, no_price):
    """
    Property test: Profit decreases as prices increase.
    
    For any fixed NO price, as YES price increases, profit should decrease
    (or stay the same if already unprofitable).
    """
    engine = InternalArbitrageEngine(
        clob_client=None,
        order_manager=None,
        position_merger=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')
    )
    
    # Calculate profit at current prices
    profit1 = engine.calculate_profit(
        Decimal(str(yes_price)),
        Decimal(str(no_price))
    )
    
    # Calculate profit with slightly higher YES price
    higher_yes_price = min(yes_price + 0.01, 0.99)
    profit2 = engine.calculate_profit(
        Decimal(str(higher_yes_price)),
        Decimal(str(no_price))
    )
    
    # Profit should decrease (or both be None)
    if profit1 is not None and profit2 is not None:
        assert profit2 <= profit1, \
            f"Profit should decrease as prices increase: " \
            f"profit1={profit1} at yes={yes_price}, " \
            f"profit2={profit2} at yes={higher_yes_price}"


@given(
    yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_profit_bounded_by_redemption_value(yes_price, no_price):
    """
    Property test: Profit is bounded by redemption value.
    
    The maximum possible profit is $1.00 (if positions were free),
    and the minimum is negative (loss).
    """
    engine = InternalArbitrageEngine(
        clob_client=None,
        order_manager=None,
        position_merger=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')
    )
    
    calculated_profit = engine.calculate_profit(
        Decimal(str(yes_price)),
        Decimal(str(no_price))
    )
    
    if calculated_profit is not None:
        # Profit should be positive (since we filter negatives)
        assert calculated_profit > 0, \
            "Returned profit should be positive"
        
        # Profit should be less than $1.00 (redemption value)
        assert calculated_profit < Decimal('1.0'), \
            f"Profit cannot exceed redemption value: {calculated_profit}"
        
        # For very low prices, profit should approach $1.00
        if yes_price < 0.05 and no_price < 0.05:
            # With minimal prices, profit should be close to $1.00
            assert calculated_profit > Decimal('0.90'), \
                f"Profit should be high for very low prices: {calculated_profit}"


@given(
    yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_profit_calculation_precision(yes_price, no_price):
    """
    Property test: Profit calculation maintains precision.
    
    Using Decimal types should prevent floating-point precision errors.
    """
    engine = InternalArbitrageEngine(
        clob_client=None,
        order_manager=None,
        position_merger=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')
    )
    
    # Calculate profit multiple times
    profit1 = engine.calculate_profit(
        Decimal(str(yes_price)),
        Decimal(str(no_price))
    )
    
    profit2 = engine.calculate_profit(
        Decimal(str(yes_price)),
        Decimal(str(no_price))
    )
    
    # Results should be identical (exact equality)
    assert profit1 == profit2, \
        "Profit calculation should be deterministic and precise"
    
    # If profitable, verify precision is maintained
    if profit1 is not None:
        # Verify the profit is a Decimal type (maintains precision)
        assert isinstance(profit1, Decimal), \
            "Profit should be returned as Decimal type for precision"
        
        # Verify profit has reasonable precision (can represent small values)
        # Test by checking if we can distinguish small differences
        small_diff = Decimal('0.000001')
        assert profit1 + small_diff != profit1, \
            "Decimal should maintain precision for small differences"
