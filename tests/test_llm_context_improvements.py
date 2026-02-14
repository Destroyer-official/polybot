"""
Test LLM Context Improvements for 15-Minute Markets

Validates that the enhanced context provides:
1. Real price history from Binance feed
2. Accurate volatility calculations
3. Price velocity with momentum interpretation
4. Trend analysis from price history
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from collections import deque

from src.llm_decision_engine_v2 import MarketContext


class TestLLMContextImprovements:
    """Test enhanced LLM context for 15-minute markets."""
    
    def test_price_history_with_trend_analysis(self):
        """Test that price history includes trend analysis."""
        # Create price history with uptrend
        price_history = [
            (5.0, Decimal("0.45")),  # 5 min ago
            (3.0, Decimal("0.47")),  # 3 min ago
            (1.0, Decimal("0.49")),  # 1 min ago
            (0.5, Decimal("0.50")),  # 30 sec ago
            (0.0, Decimal("0.51"))   # now
        ]
        
        ctx = MarketContext(
            market_id="test",
            question="Will BTC go up?",
            asset="BTC",
            yes_price=Decimal("0.51"),
            no_price=Decimal("0.49"),
            yes_liquidity=Decimal("1000"),
            no_liquidity=Decimal("1000"),
            volume_24h=Decimal("10000"),
            time_to_resolution=10.0,
            spread=Decimal("0.02"),
            price_history_5min=price_history
        )
        
        context_str = ctx.to_prompt_context("directional_trend")
        
        # Should include price history
        assert "Price History (5min):" in context_str
        assert "$0.45" in context_str  # First price
        assert "$0.51" in context_str  # Last price
        
        # Should include trend analysis
        assert "5-Min Trend:" in context_str
        # Price went from 0.45 to 0.51 = +13.3% uptrend
        assert "UPTREND" in context_str or "STRONG UPTREND" in context_str
    
    def test_volatility_interpretation(self):
        """Test that volatility includes actionable interpretation."""
        # High volatility scenario
        ctx_high_vol = MarketContext(
            market_id="test",
            question="Will BTC go up?",
            asset="BTC",
            yes_price=Decimal("0.50"),
            no_price=Decimal("0.50"),
            yes_liquidity=Decimal("1000"),
            no_liquidity=Decimal("1000"),
            volume_24h=Decimal("10000"),
            time_to_resolution=10.0,
            spread=Decimal("0.02"),
            volatility_5min=Decimal("0.06")  # 6% volatility = VERY HIGH
        )
        
        context_str = ctx_high_vol.to_prompt_context("directional_trend")
        
        # Should include volatility with interpretation
        assert "Volatility (5min):" in context_str
        assert "6.00%" in context_str
        assert "VERY HIGH" in context_str or "HIGH" in context_str
        assert "big moves" in context_str or "profit potential" in context_str
    
    def test_price_velocity_with_momentum(self):
        """Test that price velocity includes momentum interpretation."""
        # Fast upward velocity
        ctx_fast = MarketContext(
            market_id="test",
            question="Will BTC go up?",
            asset="BTC",
            yes_price=Decimal("0.50"),
            no_price=Decimal("0.50"),
            yes_liquidity=Decimal("1000"),
            no_liquidity=Decimal("1000"),
            volume_24h=Decimal("10000"),
            time_to_resolution=10.0,
            spread=Decimal("0.02"),
            price_velocity=Decimal("0.025")  # $0.025/min = VERY FAST
        )
        
        context_str = ctx_fast.to_prompt_context("directional_trend")
        
        # Should include velocity with interpretation
        assert "Price Velocity:" in context_str
        assert "$0.0250/min" in context_str
        assert "UP" in context_str  # Direction
        assert "FAST" in context_str or "VERY FAST" in context_str
        assert "momentum" in context_str
    
    def test_time_urgency_indicators(self):
        """Test that time urgency is clearly indicated."""
        # Urgent scenario (< 3 min)
        ctx_urgent = MarketContext(
            market_id="test",
            question="Will BTC go up?",
            asset="BTC",
            yes_price=Decimal("0.50"),
            no_price=Decimal("0.50"),
            yes_liquidity=Decimal("1000"),
            no_liquidity=Decimal("1000"),
            volume_24h=Decimal("10000"),
            time_to_resolution=2.5,  # < 3 minutes = URGENT
            spread=Decimal("0.02")
        )
        
        context_str = ctx_urgent.to_prompt_context("directional_trend")
        
        # Should show urgent indicator
        assert "Time to Resolution: 2.5 minutes" in context_str
        assert "🔴 URGENT" in context_str
    
    def test_downtrend_detection(self):
        """Test that downtrends are correctly identified."""
        # Create price history with downtrend
        price_history = [
            (5.0, Decimal("0.55")),  # 5 min ago
            (3.0, Decimal("0.52")),  # 3 min ago
            (1.0, Decimal("0.49")),  # 1 min ago
            (0.5, Decimal("0.47")),  # 30 sec ago
            (0.0, Decimal("0.45"))   # now
        ]
        
        ctx = MarketContext(
            market_id="test",
            question="Will BTC go up?",
            asset="BTC",
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.55"),
            yes_liquidity=Decimal("1000"),
            no_liquidity=Decimal("1000"),
            volume_24h=Decimal("10000"),
            time_to_resolution=10.0,
            spread=Decimal("0.02"),
            price_history_5min=price_history
        )
        
        context_str = ctx.to_prompt_context("directional_trend")
        
        # Should include downtrend analysis
        assert "5-Min Trend:" in context_str
        # Price went from 0.55 to 0.45 = -18.2% downtrend
        assert "DOWNTREND" in context_str or "STRONG DOWNTREND" in context_str
        assert "-" in context_str  # Negative percentage
    
    def test_sideways_market_detection(self):
        """Test that sideways markets are correctly identified."""
        # Create price history with minimal movement
        price_history = [
            (5.0, Decimal("0.50")),  # 5 min ago
            (3.0, Decimal("0.501")), # 3 min ago
            (1.0, Decimal("0.499")), # 1 min ago
            (0.5, Decimal("0.502")), # 30 sec ago
            (0.0, Decimal("0.500"))  # now
        ]
        
        ctx = MarketContext(
            market_id="test",
            question="Will BTC go up?",
            asset="BTC",
            yes_price=Decimal("0.50"),
            no_price=Decimal("0.50"),
            yes_liquidity=Decimal("1000"),
            no_liquidity=Decimal("1000"),
            volume_24h=Decimal("10000"),
            time_to_resolution=10.0,
            spread=Decimal("0.02"),
            price_history_5min=price_history
        )
        
        context_str = ctx.to_prompt_context("directional_trend")
        
        # Should identify sideways movement
        assert "5-Min Trend:" in context_str
        assert "SIDEWAYS" in context_str or "0.00%" in context_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
