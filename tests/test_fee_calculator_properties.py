"""
Property-based tests for Dynamic Fee Calculator.

Tests the 2025 dynamic fee formula using property-based testing with Hypothesis.
Validates Requirements 1.7, 2.1, and 2.5.
"""

import pytest
from hypothesis import given, strategies as st, settings
import rust_core


@given(
    price=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_dynamic_fee_calculation_accuracy(price):
    """
    **Validates: Requirements 1.7, 2.1**
    
    Feature: polymarket-arbitrage-bot, Property 1: Dynamic Fee Calculation Accuracy
    
    For any position price between 0.0 and 1.0, the calculated fee should equal
    max(0.001, 0.03 * (1.0 - abs(2.0 * price - 1.0))), with fees peaking at ~3%
    near 50% odds and approaching 0.1% at price extremes.
    """
    # Calculate fee using Rust module
    actual_fee = rust_core.calculate_fee(price)
    
    # Calculate expected fee using the formula
    certainty = abs(2.0 * price - 1.0)
    expected_fee = max(0.001, 0.03 * (1.0 - certainty))
    
    # Allow small floating-point tolerance
    tolerance = 1e-9
    assert abs(actual_fee - expected_fee) < tolerance, \
        f"Fee mismatch for price {price}: expected {expected_fee}, got {actual_fee}"
    
    # Additional invariants
    assert 0.001 <= actual_fee <= 0.03, \
        f"Fee out of bounds for price {price}: {actual_fee}"
    
    # Fee should peak at 50% odds
    if abs(price - 0.5) < 1e-6:
        assert abs(actual_fee - 0.03) < tolerance, \
            f"Fee should be 3% at 50% odds, got {actual_fee}"
    
    # Fee should be minimum at extremes
    if price < 1e-6 or abs(price - 1.0) < 1e-6:
        assert abs(actual_fee - 0.001) < tolerance, \
            f"Fee should be 0.1% at price extremes, got {actual_fee}"


@given(
    yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    no_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_total_cost_calculation_property(yes_price, no_price):
    """
    Property test for total cost calculation.
    
    Validates that total cost calculation is consistent with individual fee calculations.
    """
    # Calculate using individual functions
    yes_fee = rust_core.calculate_fee(yes_price)
    no_fee = rust_core.calculate_fee(no_price)
    expected_total = yes_price + no_price + (yes_price * yes_fee) + (no_price * no_fee)
    
    # Calculate using combined function
    actual_yes_fee, actual_no_fee, actual_total = rust_core.calculate_total_cost(yes_price, no_price)
    
    # Verify consistency
    tolerance = 1e-9
    assert abs(actual_yes_fee - yes_fee) < tolerance, "YES fee mismatch"
    assert abs(actual_no_fee - no_fee) < tolerance, "NO fee mismatch"
    assert abs(actual_total - expected_total) < tolerance, "Total cost mismatch"
    
    # Total cost should always be less than or equal to sum of prices + max fees
    max_possible_cost = yes_price + no_price + (yes_price * 0.03) + (no_price * 0.03)
    assert actual_total <= max_possible_cost, "Total cost exceeds maximum possible"
    
    # Total cost should always be greater than or equal to sum of prices + min fees
    min_possible_cost = yes_price + no_price + (yes_price * 0.001) + (no_price * 0.001)
    assert actual_total >= min_possible_cost, "Total cost below minimum possible"


@given(
    price=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_fee_symmetry_property(price):
    """
    Property test for fee symmetry.
    
    The fee at price p should equal the fee at price (1 - p) due to the
    symmetry of the formula around 0.5.
    """
    fee_at_price = rust_core.calculate_fee(price)
    fee_at_complement = rust_core.calculate_fee(1.0 - price)
    
    tolerance = 1e-9
    assert abs(fee_at_price - fee_at_complement) < tolerance, \
        f"Fee symmetry violated: fee({price}) = {fee_at_price}, fee({1.0 - price}) = {fee_at_complement}"


@given(
    price1=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
    price2=st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_fee_monotonicity_property(price1, price2):
    """
    Property test for fee monotonicity.
    
    As price moves away from 0.5 (towards 0 or 1), the fee should decrease.
    """
    # Calculate distances from 0.5
    dist1 = abs(price1 - 0.5)
    dist2 = abs(price2 - 0.5)
    
    fee1 = rust_core.calculate_fee(price1)
    fee2 = rust_core.calculate_fee(price2)
    
    # If price1 is closer to 0.5, its fee should be >= fee2
    if dist1 < dist2:
        assert fee1 >= fee2 - 1e-9, \
            f"Fee monotonicity violated: price closer to 0.5 should have higher fee"
    elif dist2 < dist1:
        assert fee2 >= fee1 - 1e-9, \
            f"Fee monotonicity violated: price closer to 0.5 should have higher fee"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


@given(
    price=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_fee_calculation_caching(price):
    """
    **Validates: Requirements 2.5**
    
    Feature: polymarket-arbitrage-bot, Property 6: Fee Calculation Caching
    
    For any price value, calling the fee calculator twice with the same price
    should return identical results, with the second call using cached data
    for performance optimization.
    """
    # Clear cache before test
    rust_core.clear_fee_cache()
    initial_cache_size = rust_core.get_cache_size()
    
    # First call - should calculate and cache
    fee1 = rust_core.calculate_fee(price)
    cache_size_after_first = rust_core.get_cache_size()
    
    # Cache should have grown by 1
    assert cache_size_after_first == initial_cache_size + 1, \
        f"Cache should grow after first calculation"
    
    # Second call - should use cache
    fee2 = rust_core.calculate_fee(price)
    cache_size_after_second = rust_core.get_cache_size()
    
    # Cache size should not change on second call
    assert cache_size_after_second == cache_size_after_first, \
        f"Cache size should not change when using cached value"
    
    # Both calls should return identical results
    assert fee1 == fee2, \
        f"Cached fee should match calculated fee: {fee1} != {fee2}"
    
    # Clean up
    rust_core.clear_fee_cache()


@given(
    prices=st.lists(
        # Use decimals with limited precision to avoid floating-point collisions
        st.decimals(min_value='0.01', max_value='0.99', places=4).map(float),
        min_size=5,
        max_size=20,
        unique=True
    )
)
@settings(max_examples=50)
def test_cache_accumulation_property(prices):
    """
    Property test for cache accumulation.
    
    When calculating fees for N unique prices (with 4 decimal places),
    the cache should grow appropriately and not change on recalculation.
    """
    # Clear cache before test
    rust_core.clear_fee_cache()
    initial_size = rust_core.get_cache_size()
    
    # Calculate fees for all prices
    fees = [rust_core.calculate_fee(p) for p in prices]
    
    # Cache should have grown
    cache_size = rust_core.get_cache_size()
    assert cache_size > initial_size, \
        f"Cache should grow after calculations"
    
    # Recalculating should not change cache size
    fees_again = [rust_core.calculate_fee(p) for p in prices]
    cache_size_after = rust_core.get_cache_size()
    
    assert cache_size_after == cache_size, \
        "Cache size should not change on recalculation"
    
    # Results should be identical
    for i, (fee1, fee2) in enumerate(zip(fees, fees_again)):
        assert fee1 == fee2, \
            f"Cached result mismatch at index {i}: {fee1} != {fee2}"
    
    # Clean up
    rust_core.clear_fee_cache()
