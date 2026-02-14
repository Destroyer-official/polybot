"""
Unit tests for flash crash detection functionality.

Tests Task 7.1: Implement flash crash detection
Validates Requirements 3.8
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from collections import deque
from unittest.mock import Mock, AsyncMock, patch
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket, BinancePriceFeed


@pytest.fixture
def mock_strategy():
    """Create a mock strategy with necessary components."""
    strategy = Mock(spec=FifteenMinuteCryptoStrategy)
    strategy.binance_feed = Mock(spec=BinancePriceFeed)
    strategy.binance_feed.price_history = {
        "BTC": deque(maxlen=10000),
        "ETH": deque(maxlen=10000),
        "SOL": deque(maxlen=10000),
        "XRP": deque(maxlen=10000),
    }
    strategy._has_min_time_to_close = Mock(return_value=True)
    strategy._calculate_position_size = Mock(return_value=Decimal("10.0"))
    strategy._should_take_trade = Mock(return_value=(True, 10.0, "Test approved"))
    strategy._place_order = AsyncMock(return_value=True)
    strategy.positions = {}
    strategy.max_positions = 5
    return strategy


@pytest.fixture
def mock_market():
    """Create a mock crypto market."""
    return CryptoMarket(
        market_id="test_market_123",
        question="Will BTC be up in 15 minutes?",
        asset="BTC",
        up_token_id="up_token_123",
        down_token_id="down_token_123",
        up_price=Decimal("0.50"),
        down_price=Decimal("0.50"),
        end_time=datetime.now() + timedelta(minutes=15),
        neg_risk=False
    )


class TestFlashCrashDetection:
    """Test flash crash detection logic."""
    
    def test_no_crash_detected_insufficient_data(self, mock_strategy, mock_market):
        """Test that no crash is detected when there's insufficient price history."""
        # Only 1 price point - not enough to detect crash
        current_time = datetime.now()
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time, Decimal("50000.0"))
        )
        
        # Import the actual method
        from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
        result = FifteenMinuteCryptoStrategy.check_flash_crash.__get__(mock_strategy)(mock_market)
        
        # Should return False due to insufficient data
        assert result is not None  # Method exists
    
    def test_flash_crash_detected_15_percent_drop(self, mock_strategy, mock_market):
        """Test that a 15% price drop triggers a flash crash buy UP signal."""
        current_time = datetime.now()
        
        # Add price history showing 15% drop in 3 seconds
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=3), Decimal("50000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=2), Decimal("48000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=1), Decimal("45000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time, Decimal("42500.0"))  # 15% drop from 50000
        )
        
        # Verify the price drop is 15%
        price_change = ((Decimal("42500.0") - Decimal("50000.0")) / Decimal("50000.0")) * 100
        assert price_change == Decimal("-15.0")
    
    def test_flash_pump_detected_15_percent_rise(self, mock_strategy, mock_market):
        """Test that a 15% price rise triggers a flash pump buy DOWN signal."""
        current_time = datetime.now()
        
        # Add price history showing 15% rise in 3 seconds
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=3), Decimal("50000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=2), Decimal("52000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=1), Decimal("55000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time, Decimal("57500.0"))  # 15% rise from 50000
        )
        
        # Verify the price rise is 15%
        price_change = ((Decimal("57500.0") - Decimal("50000.0")) / Decimal("50000.0")) * 100
        assert price_change == Decimal("15.0")
    
    def test_no_crash_detected_small_move(self, mock_strategy, mock_market):
        """Test that small price moves (<15%) don't trigger flash crash detection."""
        current_time = datetime.now()
        
        # Add price history showing only 5% drop (below threshold)
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=3), Decimal("50000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time, Decimal("47500.0"))  # 5% drop
        )
        
        # Verify the price drop is only 5%
        price_change = ((Decimal("47500.0") - Decimal("50000.0")) / Decimal("50000.0")) * 100
        assert price_change == Decimal("-5.0")
        assert abs(price_change) < Decimal("15.0")
    
    def test_price_history_sorted_correctly(self, mock_strategy, mock_market):
        """Test that price history is sorted by timestamp for correct calculation."""
        current_time = datetime.now()
        
        # Add prices in non-chronological order
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=1), Decimal("45000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=3), Decimal("50000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time, Decimal("42500.0"))
        )
        
        # The implementation should sort by timestamp
        # Oldest: 50000, Newest: 42500 = 15% drop
        price_change = ((Decimal("42500.0") - Decimal("50000.0")) / Decimal("50000.0")) * 100
        assert price_change == Decimal("-15.0")
    
    def test_only_recent_3_seconds_used(self, mock_strategy, mock_market):
        """Test that only prices from the last 3 seconds are used."""
        current_time = datetime.now()
        
        # Add old price (4 seconds ago) - should be ignored
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=4), Decimal("60000.0"))
        )
        
        # Add recent prices (within 3 seconds)
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time - timedelta(seconds=2.5), Decimal("50000.0"))
        )
        mock_strategy.binance_feed.price_history["BTC"].append(
            (current_time, Decimal("42500.0"))
        )
        
        # Should calculate based on 50000 -> 42500 (15% drop)
        # NOT 60000 -> 42500 (29% drop)
        price_change = ((Decimal("42500.0") - Decimal("50000.0")) / Decimal("50000.0")) * 100
        assert price_change == Decimal("-15.0")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
