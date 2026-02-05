"""
Property-based tests for Kelly Position Sizer.

Tests the Kelly Criterion position sizing using property-based testing with Hypothesis.
Validates Requirements 11.1, 11.2, 11.3, 11.4.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime

from src.kelly_position_sizer import KellyPositionSizer, PositionSizingConfig
from src.models import Opportunity


# Strategy for generating valid Opportunity objects
@st.composite
def opportunity_strategy(draw):
    """Generate valid Opportunity objects for testing."""
    yes_price = Decimal(str(draw(st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False))))
    no_price = Decimal(str(draw(st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False))))
    
    # Calculate fees (simplified for testing)
    yes_fee = yes_price * Decimal('0.03')
    no_fee = no_price * Decimal('0.03')
    
    total_cost = yes_price + no_price + yes_fee + no_fee
    expected_profit = Decimal('1.0') - total_cost
    profit_percentage = expected_profit / total_cost if total_cost > 0 else Decimal('0')
    
    return Opportunity(
        opportunity_id=f"test_{draw(st.integers(min_value=1, max_value=100000))}",
        market_id=f"market_{draw(st.integers(min_value=1, max_value=10000))}",
        strategy="internal",
        timestamp=datetime.now(),
        yes_price=yes_price,
        no_price=no_price,
        yes_fee=yes_fee,
        no_fee=no_fee,
        total_cost=total_cost,
        expected_profit=expected_profit,
        profit_percentage=profit_percentage,
        position_size=Decimal('0'),
        gas_estimate=100000
    )


@given(
    opportunity=opportunity_strategy(),
    bankroll=st.decimals(min_value='10.0', max_value='10000.0', places=2)
)
@settings(max_examples=100)
def test_kelly_criterion_position_sizing(opportunity, bankroll):
    """
    **Validates: Requirements 11.1**
    
    Feature: polymarket-arbitrage-bot, Property 35: Kelly Criterion Position Sizing
    
    For any valid opportunity and bankroll, the position size should be calculated
    using the Kelly Criterion formula: f = (bp - q) / b, where:
    - b = odds (profit / cost)
    - p = win probability (0.995 for arbitrage)
    - q = loss probability (0.005)
    
    The calculated position size should be proportional to the expected edge
    and inversely proportional to the variance.
    """
    sizer = KellyPositionSizer()
    
    # Calculate position size
    position_size = sizer.calculate_position_size(opportunity, bankroll)
    
    # Position size should be non-negative
    assert position_size >= 0, f"Position size should be non-negative, got {position_size}"
    
    # Position size should not exceed bankroll
    assert position_size <= bankroll, \
        f"Position size {position_size} exceeds bankroll {bankroll}"
    
    # Calculate expected Kelly fraction manually
    win_prob = Decimal('0.995')
    loss_prob = Decimal('0.005')
    
    if opportunity.total_cost > 0:
        odds = opportunity.expected_profit / opportunity.total_cost
        
        if odds > 0:
            kelly_fraction = (odds * win_prob - loss_prob) / odds
            kelly_fraction = min(kelly_fraction, Decimal('0.05'))  # 5% cap
            kelly_fraction = max(kelly_fraction, Decimal('0'))
            
            expected_position = bankroll * kelly_fraction
            
            # Apply bankroll-specific constraints
            if bankroll < Decimal('100.0'):
                expected_position = min(expected_position, Decimal('1.0'))
                expected_position = max(expected_position, Decimal('0.1'))
            else:
                expected_position = min(expected_position, Decimal('5.0'))
            
            # Position size should match expected calculation
            tolerance = Decimal('0.01')
            assert abs(position_size - expected_position) < tolerance, \
                f"Position size {position_size} doesn't match expected {expected_position}"


@given(
    opportunity=opportunity_strategy(),
    bankroll=st.decimals(min_value='10.0', max_value='10000.0', places=2)
)
@settings(max_examples=100)
def test_position_size_cap(opportunity, bankroll):
    """
    **Validates: Requirements 11.2**
    
    Feature: polymarket-arbitrage-bot, Property 36: Kelly Position Size Cap
    
    For any opportunity and bankroll, the position size should never exceed
    5% of the bankroll, ensuring conservative position sizing even when
    Kelly Criterion suggests larger positions.
    """
    sizer = KellyPositionSizer()
    
    # Calculate position size
    position_size = sizer.calculate_position_size(opportunity, bankroll)
    
    # Position size should not exceed 5% of bankroll
    max_kelly_position = bankroll * Decimal('0.05')
    assert position_size <= max_kelly_position, \
        f"Position size {position_size} exceeds 5% of bankroll ({max_kelly_position})"
    
    # Position size should also respect absolute maximum
    assert position_size <= Decimal('5.0'), \
        f"Position size {position_size} exceeds absolute maximum of $5.00"


@given(
    opportunity=opportunity_strategy(),
    bankroll=st.decimals(min_value='10.0', max_value='99.99', places=2)
)
@settings(max_examples=100)
def test_small_bankroll_fixed_sizing(opportunity, bankroll):
    """
    **Validates: Requirements 11.3**
    
    Feature: polymarket-arbitrage-bot, Property 37: Small Bankroll Fixed Sizing
    
    For bankrolls below $100, position sizes should be constrained to fixed
    sizes between $0.10 and $1.00, preventing over-leveraging small accounts.
    """
    sizer = KellyPositionSizer()
    
    # Calculate position size
    position_size = sizer.calculate_position_size(opportunity, bankroll)
    
    # Position size should be between $0.10 and $1.00 for small bankrolls
    assert Decimal('0.1') <= position_size <= Decimal('1.0'), \
        f"Position size {position_size} outside small bankroll range [$0.10, $1.00]"
    
    # Position size should not exceed bankroll
    assert position_size <= bankroll, \
        f"Position size {position_size} exceeds bankroll {bankroll}"


@given(
    opportunity=opportunity_strategy(),
    bankroll=st.decimals(min_value='100.01', max_value='10000.0', places=2)
)
@settings(max_examples=100)
def test_large_bankroll_proportional_sizing(opportunity, bankroll):
    """
    **Validates: Requirements 11.4**
    
    Feature: polymarket-arbitrage-bot, Property 38: Large Bankroll Proportional Sizing
    
    For bankrolls above $100, position sizes should scale proportionally
    with bankroll up to a maximum of $5.00, allowing larger positions
    while maintaining risk control.
    """
    sizer = KellyPositionSizer()
    
    # Calculate position size
    position_size = sizer.calculate_position_size(opportunity, bankroll)
    
    # Position size should not exceed $5.00 for large bankrolls
    assert position_size <= Decimal('5.0'), \
        f"Position size {position_size} exceeds maximum of $5.00"
    
    # Position size should be proportional to bankroll (up to cap)
    # For large bankrolls, Kelly fraction is applied without small bankroll constraints
    win_prob = Decimal('0.995')
    loss_prob = Decimal('0.005')
    
    if opportunity.total_cost > 0:
        odds = opportunity.expected_profit / opportunity.total_cost
        
        if odds > 0:
            kelly_fraction = (odds * win_prob - loss_prob) / odds
            kelly_fraction = min(kelly_fraction, Decimal('0.05'))
            kelly_fraction = max(kelly_fraction, Decimal('0'))
            
            expected_position = bankroll * kelly_fraction
            expected_position = min(expected_position, Decimal('5.0'))
            
            # Position size should match expected calculation
            tolerance = Decimal('0.01')
            assert abs(position_size - expected_position) < tolerance, \
                f"Position size {position_size} doesn't match expected {expected_position}"


@given(
    opportunity=opportunity_strategy(),
    bankroll=st.decimals(min_value='10.0', max_value='10000.0', places=2)
)
@settings(max_examples=100)
def test_position_size_monotonicity(opportunity, bankroll):
    """
    Property test for position size monotonicity.
    
    For a fixed opportunity with positive profit, position size should increase 
    (or stay constant) as bankroll increases, respecting the maximum constraints.
    """
    # Skip opportunities with non-positive profit
    assume(opportunity.expected_profit > 0)
    
    sizer = KellyPositionSizer()
    
    # Calculate position size for current bankroll
    position_size_1 = sizer.calculate_position_size(opportunity, bankroll)
    
    # Calculate position size for larger bankroll (staying in same category)
    if bankroll < Decimal('100.0'):
        # Stay in small bankroll category
        larger_bankroll = min(bankroll * Decimal('1.2'), Decimal('99.0'))
    else:
        # Stay in large bankroll category
        larger_bankroll = bankroll * Decimal('1.5')
    
    position_size_2 = sizer.calculate_position_size(opportunity, larger_bankroll)
    
    # Position size should not decrease with larger bankroll
    # (unless hitting maximum constraints)
    if position_size_1 < Decimal('5.0'):
        assert position_size_2 >= position_size_1, \
            f"Position size decreased from {position_size_1} to {position_size_2} with larger bankroll"


@given(
    opportunity=opportunity_strategy(),
    bankroll=st.decimals(min_value='10.0', max_value='10000.0', places=2)
)
@settings(max_examples=100)
def test_position_size_bounds(opportunity, bankroll):
    """
    Property test for position size bounds.
    
    Position size should always be within valid bounds regardless of inputs.
    """
    sizer = KellyPositionSizer()
    
    # Calculate position size
    position_size = sizer.calculate_position_size(opportunity, bankroll)
    
    # Position size should be non-negative
    assert position_size >= 0, f"Position size should be non-negative, got {position_size}"
    
    # Position size should not exceed bankroll
    assert position_size <= bankroll, \
        f"Position size {position_size} exceeds bankroll {bankroll}"
    
    # Position size should not exceed absolute maximum
    assert position_size <= Decimal('5.0'), \
        f"Position size {position_size} exceeds absolute maximum of $5.00"
    
    # Position size should respect minimum for small bankrolls
    if bankroll >= Decimal('0.1'):
        if bankroll < Decimal('100.0'):
            assert position_size >= Decimal('0.1') or position_size == 0, \
                f"Position size {position_size} below minimum for small bankroll"
