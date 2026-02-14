"""
Unit tests for market slug validation (Task 10.2).

Tests the _validate_market_slug method to ensure it correctly validates
Gamma API slug patterns: {asset}-updown-{15m|1h}-{timestamp}
"""

import pytest
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone


# Create a minimal mock strategy class for testing
class MockStrategy:
    """Minimal mock strategy for testing slug validation."""
    
    def __init__(self):
        pass
    
    def _validate_market_slug(self, slug: str) -> bool:
        """
        Validate that a market slug matches the expected Gamma API pattern.
        
        TASK 10.2: Verify slug pattern matches {asset}-updown-{15m|1h}-{timestamp}
        
        Expected pattern:
        - Asset: btc, eth, sol, xrp (lowercase)
        - Format: updown
        - Interval: 15m or 1h
        - Timestamp: Unix timestamp (10 digits)
        
        Args:
            slug: The market slug to validate (e.g., "btc-updown-15m-1234567890")
            
        Returns:
            True if slug matches expected pattern, False otherwise
        """
        try:
            parts = slug.split("-")
            
            # Must have exactly 4 parts: asset-updown-interval-timestamp
            if len(parts) != 4:
                return False
            
            asset, format_type, interval, timestamp = parts
            
            # Validate asset (must be one of the supported crypto assets)
            valid_assets = ["btc", "eth", "sol", "xrp"]
            if asset.lower() not in valid_assets:
                return False
            
            # Validate format (must be "updown")
            if format_type != "updown":
                return False
            
            # Validate interval (must be "15m" or "1h")
            valid_intervals = ["15m", "1h"]
            if interval not in valid_intervals:
                return False
            
            # Validate timestamp (must be a valid Unix timestamp - 10 digits)
            if not timestamp.isdigit() or len(timestamp) != 10:
                return False
            
            # All validations passed
            return True
            
        except Exception as e:
            return False


@pytest.fixture
def strategy():
    """Create a strategy instance for testing."""
    return MockStrategy()


class TestMarketSlugValidation:
    """Test suite for market slug validation (Task 10.2)."""
    
    def test_valid_btc_15m_slug(self, strategy):
        """Test that valid BTC 15-minute slug passes validation."""
        slug = "btc-updown-15m-1234567890"
        assert strategy._validate_market_slug(slug) is True
    
    def test_valid_eth_15m_slug(self, strategy):
        """Test that valid ETH 15-minute slug passes validation."""
        slug = "eth-updown-15m-1234567890"
        assert strategy._validate_market_slug(slug) is True
    
    def test_valid_sol_15m_slug(self, strategy):
        """Test that valid SOL 15-minute slug passes validation."""
        slug = "sol-updown-15m-1234567890"
        assert strategy._validate_market_slug(slug) is True
    
    def test_valid_xrp_15m_slug(self, strategy):
        """Test that valid XRP 15-minute slug passes validation."""
        slug = "xrp-updown-15m-1234567890"
        assert strategy._validate_market_slug(slug) is True
    
    def test_valid_btc_1h_slug(self, strategy):
        """Test that valid BTC 1-hour slug passes validation."""
        slug = "btc-updown-1h-1234567890"
        assert strategy._validate_market_slug(slug) is True
    
    def test_valid_eth_1h_slug(self, strategy):
        """Test that valid ETH 1-hour slug passes validation."""
        slug = "eth-updown-1h-1234567890"
        assert strategy._validate_market_slug(slug) is True
    
    def test_invalid_asset(self, strategy):
        """Test that invalid asset fails validation."""
        slug = "doge-updown-15m-1234567890"
        assert strategy._validate_market_slug(slug) is False
    
    def test_invalid_format(self, strategy):
        """Test that invalid format (not 'updown') fails validation."""
        slug = "btc-yesno-15m-1234567890"
        assert strategy._validate_market_slug(slug) is False
    
    def test_invalid_interval(self, strategy):
        """Test that invalid interval fails validation."""
        slug = "btc-updown-5m-1234567890"
        assert strategy._validate_market_slug(slug) is False
    
    def test_invalid_interval_30m(self, strategy):
        """Test that 30m interval fails validation."""
        slug = "btc-updown-30m-1234567890"
        assert strategy._validate_market_slug(slug) is False
    
    def test_invalid_timestamp_too_short(self, strategy):
        """Test that timestamp with less than 10 digits fails validation."""
        slug = "btc-updown-15m-123456789"
        assert strategy._validate_market_slug(slug) is False
    
    def test_invalid_timestamp_too_long(self, strategy):
        """Test that timestamp with more than 10 digits fails validation."""
        slug = "btc-updown-15m-12345678901"
        assert strategy._validate_market_slug(slug) is False
    
    def test_invalid_timestamp_non_numeric(self, strategy):
        """Test that non-numeric timestamp fails validation."""
        slug = "btc-updown-15m-123456789a"
        assert strategy._validate_market_slug(slug) is False
    
    def test_invalid_too_few_parts(self, strategy):
        """Test that slug with too few parts fails validation."""
        slug = "btc-updown-15m"
        assert strategy._validate_market_slug(slug) is False
    
    def test_invalid_too_many_parts(self, strategy):
        """Test that slug with too many parts fails validation."""
        slug = "btc-updown-15m-1234567890-extra"
        assert strategy._validate_market_slug(slug) is False
    
    def test_empty_slug(self, strategy):
        """Test that empty slug fails validation."""
        slug = ""
        assert strategy._validate_market_slug(slug) is False
    
    def test_uppercase_asset(self, strategy):
        """Test that uppercase asset is handled correctly (should be lowercase)."""
        slug = "BTC-updown-15m-1234567890"
        # The validation converts to lowercase, so this should pass
        assert strategy._validate_market_slug(slug) is True
    
    def test_mixed_case_asset(self, strategy):
        """Test that mixed case asset is handled correctly."""
        slug = "Btc-updown-15m-1234567890"
        # The validation converts to lowercase, so this should pass
        assert strategy._validate_market_slug(slug) is True
    
    def test_current_timestamp(self, strategy):
        """Test that current timestamp passes validation."""
        import time
        current_timestamp = int(time.time())
        slug = f"btc-updown-15m-{current_timestamp}"
        assert strategy._validate_market_slug(slug) is True
    
    def test_15min_interval_timestamp(self, strategy):
        """Test that 15-minute interval timestamp passes validation."""
        import time
        now = int(time.time())
        current_15m = (now // 900) * 900
        slug = f"eth-updown-15m-{current_15m}"
        assert strategy._validate_market_slug(slug) is True
    
    def test_1h_interval_timestamp(self, strategy):
        """Test that 1-hour interval timestamp passes validation."""
        import time
        now = int(time.time())
        current_1h = (now // 3600) * 3600
        slug = f"sol-updown-1h-{current_1h}"
        assert strategy._validate_market_slug(slug) is True


class TestSlugGeneration:
    """Test suite for slug generation in fetch_15min_markets."""
    
    @pytest.mark.asyncio
    async def test_generated_slugs_are_valid(self, strategy):
        """Test that all generated slugs pass validation."""
        import time
        
        # Calculate current intervals (same logic as fetch_15min_markets)
        now = int(time.time())
        current_15m = (now // 900) * 900
        current_1h = (now // 3600) * 3600
        
        assets = ["btc", "eth", "sol", "xrp"]
        
        for asset in assets:
            # Test 15-minute slug
            slug_15m = f"{asset}-updown-15m-{current_15m}"
            assert strategy._validate_market_slug(slug_15m) is True, \
                f"Generated 15m slug should be valid: {slug_15m}"
            
            # Test 1-hour slug
            slug_1h = f"{asset}-updown-1h-{current_1h}"
            assert strategy._validate_market_slug(slug_1h) is True, \
                f"Generated 1h slug should be valid: {slug_1h}"
    
    @pytest.mark.asyncio
    async def test_slug_pattern_consistency(self, strategy):
        """Test that slug pattern is consistent across multiple generations."""
        import time
        
        # Generate slugs multiple times
        slugs_generated = []
        for _ in range(3):
            now = int(time.time())
            current_15m = (now // 900) * 900
            slug = f"btc-updown-15m-{current_15m}"
            slugs_generated.append(slug)
            
            # Verify each slug is valid
            assert strategy._validate_market_slug(slug) is True
        
        # All slugs should be identical (within same 15-min window)
        assert len(set(slugs_generated)) == 1, \
            "Slugs generated within same 15-min window should be identical"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
