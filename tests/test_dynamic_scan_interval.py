"""
Unit tests for dynamic scan interval adjustment.

Tests the implementation of task 5.6:
- Calculate volatility from Binance price history
- High volatility threshold: >5%
- Reduce scan interval to 50% during high volatility
- Log interval changes
"""

import pytest
from decimal import Decimal
from collections import deque
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from src.main_orchestrator import MainOrchestrator


class TestDynamicScanInterval:
    """Test dynamic scan interval adjustment based on Binance volatility."""
    
    def test_high_volatility_reduces_interval_to_50_percent(self):
        """Test that high volatility (>5%) reduces scan interval to 50%."""
        # Create mock orchestrator with minimal setup
        orchestrator = Mock(spec=MainOrchestrator)
        orchestrator._base_scan_interval = 2.0
        orchestrator._current_scan_interval = 2.0
        
        # Create mock Binance feed with high volatility
        mock_binance_feed = Mock()
        mock_binance_feed.is_running = True
        
        # Simulate 6% price change (high volatility)
        mock_binance_feed.get_price_change = Mock(return_value=Decimal("0.06"))
        
        # Create mock fifteen_min_strategy
        mock_strategy = Mock()
        mock_strategy.binance_feed = mock_binance_feed
        orchestrator.fifteen_min_strategy = mock_strategy
        
        # Call the actual method
        MainOrchestrator._adjust_scan_interval(orchestrator, [])
        
        # Verify interval was reduced to 50%
        assert orchestrator._current_scan_interval == 1.0  # 2.0 * 0.5
    
    def test_normal_volatility_uses_base_interval(self):
        """Test that normal volatility (<=5%) uses base scan interval."""
        # Create mock orchestrator
        orchestrator = Mock(spec=MainOrchestrator)
        orchestrator._base_scan_interval = 2.0
        orchestrator._current_scan_interval = 1.0  # Previously reduced
        
        # Create mock Binance feed with normal volatility
        mock_binance_feed = Mock()
        mock_binance_feed.is_running = True
        
        # Simulate 2% price change (normal volatility)
        mock_binance_feed.get_price_change = Mock(return_value=Decimal("0.02"))
        
        # Create mock fifteen_min_strategy
        mock_strategy = Mock()
        mock_strategy.binance_feed = mock_binance_feed
        orchestrator.fifteen_min_strategy = mock_strategy
        
        # Call the actual method
        MainOrchestrator._adjust_scan_interval(orchestrator, [])
        
        # Verify interval was restored to base
        assert orchestrator._current_scan_interval == 2.0
    
    def test_uses_maximum_volatility_across_assets(self):
        """Test that the maximum volatility across all assets is used."""
        # Create mock orchestrator
        orchestrator = Mock(spec=MainOrchestrator)
        orchestrator._base_scan_interval = 2.0
        orchestrator._current_scan_interval = 2.0
        
        # Create mock Binance feed with varying volatility per asset
        mock_binance_feed = Mock()
        mock_binance_feed.is_running = True
        
        # BTC: 2%, ETH: 7%, SOL: 3%, XRP: 1%
        # Maximum is 7% (ETH) which exceeds 5% threshold
        volatility_map = {
            "BTC": Decimal("0.02"),
            "ETH": Decimal("0.07"),  # Highest
            "SOL": Decimal("0.03"),
            "XRP": Decimal("0.01")
        }
        mock_binance_feed.get_price_change = lambda asset, seconds: volatility_map.get(asset)
        
        # Create mock fifteen_min_strategy
        mock_strategy = Mock()
        mock_strategy.binance_feed = mock_binance_feed
        orchestrator.fifteen_min_strategy = mock_strategy
        
        # Call the actual method
        MainOrchestrator._adjust_scan_interval(orchestrator, [])
        
        # Verify interval was reduced (because max volatility 7% > 5%)
        assert orchestrator._current_scan_interval == 1.0  # 2.0 * 0.5
    
    def test_no_volatility_data_uses_base_interval(self):
        """Test that missing volatility data defaults to base interval."""
        # Create mock orchestrator
        orchestrator = Mock(spec=MainOrchestrator)
        orchestrator._base_scan_interval = 2.0
        orchestrator._current_scan_interval = 1.0  # Previously reduced
        
        # Create mock Binance feed with no data
        mock_binance_feed = Mock()
        mock_binance_feed.is_running = True
        mock_binance_feed.get_price_change = Mock(return_value=None)
        
        # Create mock fifteen_min_strategy
        mock_strategy = Mock()
        mock_strategy.binance_feed = mock_binance_feed
        orchestrator.fifteen_min_strategy = mock_strategy
        
        # Call the actual method
        MainOrchestrator._adjust_scan_interval(orchestrator, [])
        
        # Verify interval was restored to base
        assert orchestrator._current_scan_interval == 2.0
    
    def test_binance_feed_not_running_no_adjustment(self):
        """Test that no adjustment occurs if Binance feed is not running."""
        # Create mock orchestrator
        orchestrator = Mock(spec=MainOrchestrator)
        orchestrator._base_scan_interval = 2.0
        orchestrator._current_scan_interval = 2.0
        
        # Create mock Binance feed that's not running
        mock_binance_feed = Mock()
        mock_binance_feed.is_running = False
        
        # Create mock fifteen_min_strategy
        mock_strategy = Mock()
        mock_strategy.binance_feed = mock_binance_feed
        orchestrator.fifteen_min_strategy = mock_strategy
        
        # Call the actual method
        MainOrchestrator._adjust_scan_interval(orchestrator, [])
        
        # Verify interval was not changed
        assert orchestrator._current_scan_interval == 2.0
    
    def test_exact_threshold_uses_base_interval(self):
        """Test that exactly 5% volatility uses base interval (not high)."""
        # Create mock orchestrator
        orchestrator = Mock(spec=MainOrchestrator)
        orchestrator._base_scan_interval = 2.0
        orchestrator._current_scan_interval = 2.0
        
        # Create mock Binance feed with exactly 5% volatility
        mock_binance_feed = Mock()
        mock_binance_feed.is_running = True
        mock_binance_feed.get_price_change = Mock(return_value=Decimal("0.05"))
        
        # Create mock fifteen_min_strategy
        mock_strategy = Mock()
        mock_strategy.binance_feed = mock_binance_feed
        orchestrator.fifteen_min_strategy = mock_strategy
        
        # Call the actual method
        MainOrchestrator._adjust_scan_interval(orchestrator, [])
        
        # Verify interval was NOT reduced (5% is not > 5%)
        assert orchestrator._current_scan_interval == 2.0
    
    def test_negative_volatility_treated_as_absolute(self):
        """Test that negative price changes (bearish) are treated as volatility."""
        # Create mock orchestrator
        orchestrator = Mock(spec=MainOrchestrator)
        orchestrator._base_scan_interval = 2.0
        orchestrator._current_scan_interval = 2.0
        
        # Create mock Binance feed with -6% price change (bearish)
        mock_binance_feed = Mock()
        mock_binance_feed.is_running = True
        mock_binance_feed.get_price_change = Mock(return_value=Decimal("-0.06"))
        
        # Create mock fifteen_min_strategy
        mock_strategy = Mock()
        mock_strategy.binance_feed = mock_binance_feed
        orchestrator.fifteen_min_strategy = mock_strategy
        
        # Call the actual method
        MainOrchestrator._adjust_scan_interval(orchestrator, [])
        
        # Verify interval was reduced (|-6%| = 6% > 5%)
        assert orchestrator._current_scan_interval == 1.0  # 2.0 * 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
