"""
Property-based tests for Kelly Criterion position sizing in DynamicParameterSystem.

Tests the Kelly Criterion position sizing formula and clamping constraints.
**Validates: Requirements 4.3, 4.12**

Feature: ultimate-polymarket-crypto-bot, Property 20: Kelly Criterion Position Sizing
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
import logging

from src.dynamic_parameter_system import DynamicParameterSystem

logger = logging.getLogger(__name__)


@given(
    balance=st.decimals(min_value='1.00', max_value='10000.00', places=2),
    profit_pct=st.decimals(min_value='0.03', max_value='0.50', places=4),
    cost=st.decimals(min_value='0.10', max_value='10.00', places=2)
)
@settings(max_examples=100)
def test_kelly_criterion_position_sizing_formula(balance, profit_pct, cost):
    """
    **Validates: Requirements 4.3**
    
    Feature: ultimate-polymarket-crypto-bot, Property 20: Kelly Criterion Position Sizing
    
    For any valid balance, profit percentage, and cost, the position size should be calculated
    using the Kelly Criterion formula: position_size = balance × fractional_kelly × (edge / odds)
    
    The formula ensures optimal position sizing based on expected edge and odds.
    """
    system = DynamicParameterSystem()
    win_prob = Decimal('0.995')
    
    # Calculate position size
    position_size, details = system.calculate_position_size(
        bankroll=balance,
        profit_pct=profit_pct,
        cost=cost,
        win_probability=win_prob
    )
    
    # Skip if position size is 0 (edge too low or other constraints)
    assume(position_size > 0)
    
    # Replicate the calculation from the implementation
    # Calculate edge
    edge = system.calculate_edge(profit_pct, win_prob)
    
    # Calculate odds
    profit = cost * profit_pct
    odds = profit / cost  # This simplifies to profit_pct
    
    # Calculate Kelly fraction
    kelly_fraction = system.calculate_kelly_fraction(edge, odds)
    
    # Apply fractional Kelly
    fractional_kelly = Decimal(str(system.current_fractional_kelly))
    adjusted_kelly = kelly_fraction * fractional_kelly
    
    # Calculate expected position size (before clamping)
    expected_position = balance * adjusted_kelly
    
    # Apply maximum position limit (20% of bankroll)
    max_position = balance * system.max_position_pct
    expected_position = min(expected_position, max_position)
    
    # Ensure we don't exceed bankroll
    expected_position = min(expected_position, balance)
    
    # Position size should match expected calculation (within tolerance)
    tolerance = Decimal('0.02')
    assert abs(position_size - expected_position) < tolerance, \
        f"Position size {position_size} doesn't match expected {expected_position} " \
        f"(balance={balance}, profit_pct={profit_pct}, cost={cost}, " \
        f"edge={edge}, odds={odds}, kelly={kelly_fraction}, fractional={fractional_kelly})"


@given(
    balance=st.decimals(min_value='10.00', max_value='10000.00', places=2),
    profit_pct=st.decimals(min_value='0.03', max_value='0.50', places=4),
    cost=st.decimals(min_value='0.10', max_value='10.00', places=2)
)
@settings(max_examples=100)
def test_position_size_clamped_to_minimum(balance, profit_pct, cost):
    """
    **Validates: Requirements 4.12**
    
    Feature: ultimate-polymarket-crypto-bot, Property 20: Kelly Criterion Position Sizing
    
    Position size should be clamped to a minimum of $1.00.
    If the calculated position size is below $1.00, it should be set to $0 (skip trade).
    """
    system = DynamicParameterSystem(min_position_size=Decimal('1.00'))
    win_prob = Decimal('0.995')
    
    # Calculate position size
    position_size, details = system.calculate_position_size(
        bankroll=balance,
        profit_pct=profit_pct,
        cost=cost,
        win_probability=win_prob
    )
    
    # Position size should be either 0 or >= $1.00
    assert position_size == 0 or position_size >= Decimal('1.00'), \
        f"Position size {position_size} violates minimum constraint of $1.00"


@given(
    balance=st.decimals(min_value='10.00', max_value='10000.00', places=2),
    profit_pct=st.decimals(min_value='0.03', max_value='0.50', places=4),
    cost=st.decimals(min_value='0.10', max_value='10.00', places=2)
)
@settings(max_examples=100)
def test_position_size_clamped_to_maximum_percentage(balance, profit_pct, cost):
    """
    **Validates: Requirements 4.12**
    
    Feature: ultimate-polymarket-crypto-bot, Property 20: Kelly Criterion Position Sizing
    
    Position size should be clamped to a maximum of 10% of balance.
    This ensures conservative position sizing even when Kelly suggests larger positions.
    """
    system = DynamicParameterSystem(max_position_pct=Decimal('0.10'))
    win_prob = Decimal('0.995')
    
    # Calculate position size
    position_size, details = system.calculate_position_size(
        bankroll=balance,
        profit_pct=profit_pct,
        cost=cost,
        win_probability=win_prob
    )
    
    # Position size should not exceed 10% of balance
    max_allowed = balance * Decimal('0.10')
    assert position_size <= max_allowed, \
        f"Position size {position_size} exceeds 10% of balance ({max_allowed})"


@given(
    balance=st.decimals(min_value='10.00', max_value='10000.00', places=2),
    profit_pct=st.decimals(min_value='0.03', max_value='0.50', places=4),
    cost=st.decimals(min_value='0.10', max_value='10.00', places=2)
)
@settings(max_examples=100)
def test_position_size_never_exceeds_balance(balance, profit_pct, cost):
    """
    **Validates: Requirements 4.3, 4.12**
    
    Feature: ultimate-polymarket-crypto-bot, Property 20: Kelly Criterion Position Sizing
    
    Position size should never exceed the available balance, regardless of
    what the Kelly Criterion formula suggests.
    """
    system = DynamicParameterSystem()
    win_prob = Decimal('0.995')
    
    # Calculate position size
    position_size, details = system.calculate_position_size(
        bankroll=balance,
        profit_pct=profit_pct,
        cost=cost,
        win_probability=win_prob
    )
    
    # Position size should not exceed balance
    assert position_size <= balance, \
        f"Position size {position_size} exceeds balance {balance}"


@given(
    balance=st.decimals(min_value='10.00', max_value='10000.00', places=2),
    profit_pct=st.decimals(min_value='0.03', max_value='0.50', places=4),
    cost=st.decimals(min_value='0.10', max_value='10.00', places=2)
)
@settings(max_examples=100)
def test_fractional_kelly_reduces_position_size(balance, profit_pct, cost):
    """
    **Validates: Requirements 4.3**
    
    Feature: ultimate-polymarket-crypto-bot, Property 20: Kelly Criterion Position Sizing
    
    Fractional Kelly (25-50%) should reduce the position size compared to full Kelly,
    providing a safety margin and reducing variance.
    """
    system = DynamicParameterSystem()
    win_prob = Decimal('0.995')
    
    # Calculate position size with fractional Kelly
    position_size, details = system.calculate_position_size(
        bankroll=balance,
        profit_pct=profit_pct,
        cost=cost,
        win_probability=win_prob
    )
    
    # Skip if position size is 0
    assume(position_size > 0)
    
    # Replicate the calculation to get edge and odds
    edge = system.calculate_edge(profit_pct, win_prob)
    profit = cost * profit_pct
    odds = profit / cost  # Simplifies to profit_pct
    
    # Calculate full Kelly position (without fractional reduction)
    kelly_fraction = system.calculate_kelly_fraction(edge, odds)
    full_kelly_position = balance * kelly_fraction
    
    # Apply same constraints as actual calculation
    max_position = balance * system.max_position_pct
    full_kelly_position = min(full_kelly_position, max_position)
    full_kelly_position = min(full_kelly_position, balance)
    
    # Fractional Kelly position should be <= full Kelly position
    # (allowing for small rounding differences)
    tolerance = Decimal('0.02')
    assert position_size <= full_kelly_position + tolerance, \
        f"Fractional Kelly position {position_size} exceeds full Kelly {full_kelly_position} " \
        f"(fractional_kelly={system.current_fractional_kelly})"


@given(
    balance=st.decimals(min_value='10.00', max_value='10000.00', places=2),
    profit_pct=st.decimals(min_value='0.03', max_value='0.50', places=4),
    cost=st.decimals(min_value='0.10', max_value='10.00', places=2)
)
@settings(max_examples=100)
def test_position_size_is_non_negative(balance, profit_pct, cost):
    """
    **Validates: Requirements 4.3**
    
    Feature: ultimate-polymarket-crypto-bot, Property 20: Kelly Criterion Position Sizing
    
    Position size should always be non-negative (>= 0).
    Negative position sizes are invalid.
    """
    system = DynamicParameterSystem()
    win_prob = Decimal('0.995')
    
    # Calculate position size
    position_size, details = system.calculate_position_size(
        bankroll=balance,
        profit_pct=profit_pct,
        cost=cost,
        win_probability=win_prob
    )
    
    # Position size should be non-negative
    assert position_size >= 0, \
        f"Position size {position_size} is negative"


@given(
    balance=st.decimals(min_value='10.00', max_value='10000.00', places=2),
    profit_pct=st.decimals(min_value='0.01', max_value='0.05', places=4)
)
@settings(max_examples=100)
def test_edge_below_threshold_returns_zero(balance, profit_pct):
    """
    **Validates: Requirements 4.3**
    
    Feature: ultimate-polymarket-crypto-bot, Property 20: Kelly Criterion Position Sizing
    
    If the edge is below the minimum threshold (2.5%), the position size should be 0
    (trade should be skipped).
    """
    # Use a high minimum edge threshold for this test
    system = DynamicParameterSystem(min_edge_threshold=Decimal('0.10'))
    win_prob = Decimal('0.995')
    cost = Decimal('1.0')
    
    # Calculate edge from profit_pct
    edge = system.calculate_edge(profit_pct, win_prob)
    
    # Only test cases where edge is below threshold
    assume(edge < system.min_edge_threshold)
    
    # Calculate position size
    position_size, details = system.calculate_position_size(
        bankroll=balance,
        profit_pct=profit_pct,
        cost=cost,
        win_probability=win_prob
    )
    
    # Position size should be 0 when edge is below threshold
    assert position_size == 0, \
        f"Position size {position_size} should be 0 when edge {edge} is below threshold {system.min_edge_threshold}"
    
    # Details should indicate the reason
    assert details.get('reason') == 'edge_too_low', \
        f"Expected reason 'edge_too_low', got {details.get('reason')}"
