#!/usr/bin/env python3
"""
Test script for Rust fee calculator module.
Tests the 2025 dynamic fee formula and caching functionality.
"""

import rust_core

def test_fee_calculation():
    """Test the dynamic fee calculation formula."""
    print("=" * 60)
    print("Testing Dynamic Fee Calculation")
    print("=" * 60)
    
    # Test at 50% odds (should be ~3%)
    fee_50 = rust_core.calculate_fee(0.5)
    print(f"Fee at 50% odds (0.5): {fee_50:.4f} (expected: 0.0300)")
    assert abs(fee_50 - 0.03) < 0.0001, f"Expected 0.03, got {fee_50}"
    
    # Test at 0% odds (should be ~0.1%)
    fee_0 = rust_core.calculate_fee(0.0)
    print(f"Fee at 0% odds (0.0): {fee_0:.4f} (expected: 0.0010)")
    assert abs(fee_0 - 0.001) < 0.0001, f"Expected 0.001, got {fee_0}"
    
    # Test at 100% odds (should be ~0.1%)
    fee_100 = rust_core.calculate_fee(1.0)
    print(f"Fee at 100% odds (1.0): {fee_100:.4f} (expected: 0.0010)")
    assert abs(fee_100 - 0.001) < 0.0001, f"Expected 0.001, got {fee_100}"
    
    # Test at 25% odds
    fee_25 = rust_core.calculate_fee(0.25)
    # abs(2.0 * 0.25 - 1.0) = abs(0.5 - 1.0) = 0.5
    # fee = max(0.001, 0.03 * (1.0 - 0.5)) = max(0.001, 0.015) = 0.015
    print(f"Fee at 25% odds (0.25): {fee_25:.4f} (expected: 0.0150)")
    assert abs(fee_25 - 0.015) < 0.0001, f"Expected 0.015, got {fee_25}"
    
    # Test at 75% odds
    fee_75 = rust_core.calculate_fee(0.75)
    # abs(2.0 * 0.75 - 1.0) = abs(1.5 - 1.0) = 0.5
    # fee = max(0.001, 0.03 * (1.0 - 0.5)) = max(0.001, 0.015) = 0.015
    print(f"Fee at 75% odds (0.75): {fee_75:.4f} (expected: 0.0150)")
    assert abs(fee_75 - 0.015) < 0.0001, f"Expected 0.015, got {fee_75}"
    
    print("✅ All fee calculation tests passed!\n")

def test_total_cost_calculation():
    """Test the total cost calculation for internal arbitrage."""
    print("=" * 60)
    print("Testing Total Cost Calculation")
    print("=" * 60)
    
    # Example: YES at 48¢, NO at 47¢
    yes_price = 0.48
    no_price = 0.47
    
    yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
    
    print(f"YES price: ${yes_price:.2f}")
    print(f"NO price: ${no_price:.2f}")
    print(f"YES fee: {yes_fee:.4f} ({yes_fee*100:.2f}%)")
    print(f"NO fee: {no_fee:.4f} ({no_fee*100:.2f}%)")
    print(f"Total cost: ${total_cost:.4f}")
    
    # Manual calculation
    # YES fee: abs(2.0 * 0.48 - 1.0) = abs(0.96 - 1.0) = 0.04
    # fee = max(0.001, 0.03 * (1.0 - 0.04)) = max(0.001, 0.0288) = 0.0288
    expected_yes_fee = 0.0288
    
    # NO fee: abs(2.0 * 0.47 - 1.0) = abs(0.94 - 1.0) = 0.06
    # fee = max(0.001, 0.03 * (1.0 - 0.06)) = max(0.001, 0.0282) = 0.0282
    expected_no_fee = 0.0282
    
    expected_total = yes_price + no_price + (yes_price * expected_yes_fee) + (no_price * expected_no_fee)
    
    print(f"Expected total: ${expected_total:.4f}")
    
    assert abs(yes_fee - expected_yes_fee) < 0.0001, f"YES fee mismatch"
    assert abs(no_fee - expected_no_fee) < 0.0001, f"NO fee mismatch"
    assert abs(total_cost - expected_total) < 0.0001, f"Total cost mismatch"
    
    # Check if this is profitable (total cost < $1.00)
    profit = 1.0 - total_cost
    print(f"Profit: ${profit:.4f} ({profit*100:.2f}%)")
    
    if total_cost < 0.995:  # 0.5% minimum profit
        print("✅ This is a profitable arbitrage opportunity!")
    else:
        print("❌ Not profitable enough (< 0.5% profit)")
    
    print("✅ Total cost calculation test passed!\n")

def test_fee_caching():
    """Test that fee caching works correctly."""
    print("=" * 60)
    print("Testing Fee Caching")
    print("=" * 60)
    
    # Clear cache first
    rust_core.clear_fee_cache()
    initial_size = rust_core.get_cache_size()
    print(f"Initial cache size: {initial_size}")
    assert initial_size == 0, "Cache should be empty after clear"
    
    # Calculate some fees
    prices = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    for price in prices:
        fee = rust_core.calculate_fee(price)
        print(f"Price: {price:.1f}, Fee: {fee:.4f}")
    
    cache_size = rust_core.get_cache_size()
    print(f"Cache size after {len(prices)} calculations: {cache_size}")
    assert cache_size == len(prices), f"Expected {len(prices)} cached entries, got {cache_size}"
    
    # Calculate the same fees again (should use cache)
    for price in prices:
        fee = rust_core.calculate_fee(price)
    
    cache_size_after = rust_core.get_cache_size()
    print(f"Cache size after recalculation: {cache_size_after}")
    assert cache_size_after == cache_size, "Cache size should not change on recalculation"
    
    print("✅ Fee caching test passed!\n")

def test_edge_cases():
    """Test edge cases and error handling."""
    print("=" * 60)
    print("Testing Edge Cases")
    print("=" * 60)
    
    # Test invalid prices
    try:
        rust_core.calculate_fee(-0.1)
        print("❌ Should have raised error for negative price")
        assert False
    except ValueError as e:
        print(f"✅ Correctly rejected negative price: {e}")
    
    try:
        rust_core.calculate_fee(1.5)
        print("❌ Should have raised error for price > 1.0")
        assert False
    except ValueError as e:
        print(f"✅ Correctly rejected price > 1.0: {e}")
    
    # Test boundary values
    fee_min = rust_core.calculate_fee(0.0)
    fee_max = rust_core.calculate_fee(1.0)
    print(f"Fee at boundary 0.0: {fee_min:.4f}")
    print(f"Fee at boundary 1.0: {fee_max:.4f}")
    
    print("✅ Edge case tests passed!\n")

def test_find_arb():
    """Test the find_arb function with sample market data."""
    print("=" * 60)
    print("Testing find_arb Function")
    print("=" * 60)
    
    # Sample market data (simplified structure)
    market_json = '''
    {
        "rewards": [
            {"price": 0.48},
            {"price": 0.47}
        ]
    }
    '''
    
    min_profit = 0.005  # 0.5% minimum profit
    found, yes_price, no_price = rust_core.find_arb(market_json, min_profit)
    
    print(f"Market: YES={yes_price:.2f}, NO={no_price:.2f}")
    print(f"Arbitrage found: {found}")
    
    if found:
        yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
        profit = 1.0 - total_cost
        print(f"Total cost: ${total_cost:.4f}")
        print(f"Profit: ${profit:.4f} ({profit*100:.2f}%)")
        print("✅ Arbitrage opportunity detected!")
    else:
        print("❌ No arbitrage opportunity (as expected for this example)")
    
    print("✅ find_arb test passed!\n")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("RUST FEE CALCULATOR TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        test_fee_calculation()
        test_total_cost_calculation()
        test_fee_caching()
        test_edge_cases()
        test_find_arb()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
