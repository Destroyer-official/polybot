"""
Unit tests for Dynamic Fee Calculator edge cases.

Tests specific examples and edge cases for the 2025 dynamic fee formula.
Validates Requirements 2.2 and 2.3.
"""

import pytest
import rust_core


class TestFeeEdgeCases:
    """Test fee calculation at specific edge cases."""
    
    def test_fee_at_50_percent_odds(self):
        """
        **Validates: Requirements 2.2**
        
        Test fee at 50% odds (should be ~3%).
        At 50% odds, the fee should be at its maximum of 3%.
        """
        fee = rust_core.calculate_fee(0.5)
        expected = 0.03
        
        assert abs(fee - expected) < 1e-9, \
            f"Fee at 50% odds should be 3%, got {fee}"
    
    def test_fee_at_0_percent_odds(self):
        """
        **Validates: Requirements 2.3**
        
        Test fee at 0% odds (should be ~0.1%).
        At price extremes, the fee should be at its minimum of 0.1%.
        """
        fee = rust_core.calculate_fee(0.0)
        expected = 0.001
        
        assert abs(fee - expected) < 1e-9, \
            f"Fee at 0% odds should be 0.1%, got {fee}"
    
    def test_fee_at_100_percent_odds(self):
        """
        **Validates: Requirements 2.3**
        
        Test fee at 100% odds (should be ~0.1%).
        At price extremes, the fee should be at its minimum of 0.1%.
        """
        fee = rust_core.calculate_fee(1.0)
        expected = 0.001
        
        assert abs(fee - expected) < 1e-9, \
            f"Fee at 100% odds should be 0.1%, got {fee}"
    
    def test_fee_at_25_percent_odds(self):
        """
        Test fee at 25% odds.
        
        Formula: abs(2.0 * 0.25 - 1.0) = abs(0.5 - 1.0) = 0.5
        fee = max(0.001, 0.03 * (1.0 - 0.5)) = 0.015 (1.5%)
        """
        fee = rust_core.calculate_fee(0.25)
        expected = 0.015
        
        assert abs(fee - expected) < 1e-9, \
            f"Fee at 25% odds should be 1.5%, got {fee}"
    
    def test_fee_at_75_percent_odds(self):
        """
        Test fee at 75% odds.
        
        Formula: abs(2.0 * 0.75 - 1.0) = abs(1.5 - 1.0) = 0.5
        fee = max(0.001, 0.03 * (1.0 - 0.5)) = 0.015 (1.5%)
        """
        fee = rust_core.calculate_fee(0.75)
        expected = 0.015
        
        assert abs(fee - expected) < 1e-9, \
            f"Fee at 75% odds should be 1.5%, got {fee}"
    
    def test_fee_at_10_percent_odds(self):
        """
        Test fee at 10% odds (near minimum).
        
        Formula: abs(2.0 * 0.1 - 1.0) = abs(0.2 - 1.0) = 0.8
        fee = max(0.001, 0.03 * (1.0 - 0.8)) = max(0.001, 0.006) = 0.006 (0.6%)
        """
        fee = rust_core.calculate_fee(0.1)
        expected = 0.006
        
        assert abs(fee - expected) < 1e-9, \
            f"Fee at 10% odds should be 0.6%, got {fee}"
    
    def test_fee_at_90_percent_odds(self):
        """
        Test fee at 90% odds (near minimum).
        
        Formula: abs(2.0 * 0.9 - 1.0) = abs(1.8 - 1.0) = 0.8
        fee = max(0.001, 0.03 * (1.0 - 0.8)) = max(0.001, 0.006) = 0.006 (0.6%)
        """
        fee = rust_core.calculate_fee(0.9)
        expected = 0.006
        
        assert abs(fee - expected) < 1e-9, \
            f"Fee at 90% odds should be 0.6%, got {fee}"
    
    def test_fee_symmetry(self):
        """
        Test that fee(p) == fee(1-p) due to formula symmetry.
        """
        test_prices = [0.1, 0.2, 0.3, 0.4, 0.45]
        
        for price in test_prices:
            fee_at_price = rust_core.calculate_fee(price)
            fee_at_complement = rust_core.calculate_fee(1.0 - price)
            
            assert abs(fee_at_price - fee_at_complement) < 1e-9, \
                f"Fee symmetry violated: fee({price}) = {fee_at_price}, fee({1.0 - price}) = {fee_at_complement}"


class TestInvalidInputs:
    """Test error handling for invalid inputs."""
    
    def test_negative_price_raises_error(self):
        """Test that negative prices raise ValueError."""
        with pytest.raises(ValueError, match="Price must be between 0.0 and 1.0"):
            rust_core.calculate_fee(-0.1)
    
    def test_price_above_one_raises_error(self):
        """Test that prices above 1.0 raise ValueError."""
        with pytest.raises(ValueError, match="Price must be between 0.0 and 1.0"):
            rust_core.calculate_fee(1.5)
    
    def test_price_slightly_above_one_raises_error(self):
        """Test that prices slightly above 1.0 raise ValueError."""
        with pytest.raises(ValueError, match="Price must be between 0.0 and 1.0"):
            rust_core.calculate_fee(1.0001)
    
    def test_price_slightly_below_zero_raises_error(self):
        """Test that prices slightly below 0.0 raise ValueError."""
        with pytest.raises(ValueError, match="Price must be between 0.0 and 1.0"):
            rust_core.calculate_fee(-0.0001)


class TestTotalCostCalculation:
    """Test total cost calculation for internal arbitrage."""
    
    def test_total_cost_example_1(self):
        """
        Test total cost calculation with YES=0.48, NO=0.47.
        
        YES fee: abs(2.0 * 0.48 - 1.0) = 0.04, fee = 0.03 * (1.0 - 0.04) = 0.0288
        NO fee: abs(2.0 * 0.47 - 1.0) = 0.06, fee = 0.03 * (1.0 - 0.06) = 0.0282
        Total: 0.48 + 0.47 + (0.48 * 0.0288) + (0.47 * 0.0282) = 0.9776
        """
        yes_price = 0.48
        no_price = 0.47
        
        yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
        
        expected_yes_fee = 0.0288
        expected_no_fee = 0.0282
        expected_total = yes_price + no_price + (yes_price * expected_yes_fee) + (no_price * expected_no_fee)
        
        assert abs(yes_fee - expected_yes_fee) < 1e-9, f"YES fee mismatch"
        assert abs(no_fee - expected_no_fee) < 1e-9, f"NO fee mismatch"
        assert abs(total_cost - expected_total) < 1e-9, f"Total cost mismatch"
        
        # This should be profitable (< $1.00)
        assert total_cost < 1.0, "Should be profitable"
        profit = 1.0 - total_cost
        assert profit > 0.02, f"Profit should be > 2%, got {profit}"
    
    def test_total_cost_at_50_50(self):
        """
        Test total cost when both prices are 0.5 (maximum fees).
        
        Both fees should be 3%, total cost = 0.5 + 0.5 + (0.5 * 0.03) + (0.5 * 0.03) = 1.03
        This should NOT be profitable.
        """
        yes_price = 0.5
        no_price = 0.5
        
        yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
        
        assert abs(yes_fee - 0.03) < 1e-9, "YES fee should be 3%"
        assert abs(no_fee - 0.03) < 1e-9, "NO fee should be 3%"
        assert total_cost > 1.0, "Should NOT be profitable at 50/50 with max fees"
    
    def test_total_cost_at_extremes(self):
        """
        Test total cost at price extremes (minimum fees).
        
        At 0.01 and 0.99, fees should be near minimum.
        """
        yes_price = 0.01
        no_price = 0.99
        
        yes_fee, no_fee, total_cost = rust_core.calculate_total_cost(yes_price, no_price)
        
        # Both should have low fees (near 0.1%)
        assert yes_fee < 0.002, f"YES fee should be low, got {yes_fee}"
        assert no_fee < 0.002, f"NO fee should be low, got {no_fee}"
        
        # Total should be close to 1.0 (sum of prices)
        assert total_cost < 1.01, f"Total cost should be close to 1.0, got {total_cost}"


class TestCacheOperations:
    """Test cache management operations."""
    
    def test_clear_cache(self):
        """Test that clear_cache empties the cache."""
        # Add some entries
        rust_core.calculate_fee(0.1)
        rust_core.calculate_fee(0.2)
        rust_core.calculate_fee(0.3)
        
        assert rust_core.get_cache_size() > 0, "Cache should have entries"
        
        # Clear cache
        rust_core.clear_fee_cache()
        
        assert rust_core.get_cache_size() == 0, "Cache should be empty after clear"
    
    def test_cache_size_increases(self):
        """Test that cache size increases with unique calculations."""
        rust_core.clear_fee_cache()
        initial_size = rust_core.get_cache_size()
        
        # Calculate fees for different prices
        prices = [0.1, 0.2, 0.3, 0.4, 0.5]
        for price in prices:
            rust_core.calculate_fee(price)
        
        final_size = rust_core.get_cache_size()
        assert final_size == initial_size + len(prices), \
            f"Cache should grow by {len(prices)}, grew by {final_size - initial_size}"
        
        # Clean up
        rust_core.clear_fee_cache()
    
    def test_cache_does_not_grow_on_repeat(self):
        """Test that cache doesn't grow when calculating same price."""
        rust_core.clear_fee_cache()
        
        # Calculate same price multiple times
        price = 0.42
        for _ in range(10):
            rust_core.calculate_fee(price)
        
        cache_size = rust_core.get_cache_size()
        assert cache_size == 1, f"Cache should have 1 entry, got {cache_size}"
        
        # Clean up
        rust_core.clear_fee_cache()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
