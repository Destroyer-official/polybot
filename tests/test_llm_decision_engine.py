"""
Unit tests for LLM Decision Engine.

Tests:
- Decision parsing from LLM responses
- Fallback logic when LLM unavailable
- Confidence scoring and thresholds
- Position sizing calculations
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.llm_decision_engine import (
    LLMDecisionEngine,
    MarketContext,
    PortfolioState,
    TradeDecision,
    TradeAction,
    OrderType
)


class TestMarketContext:
    """Test MarketContext dataclass."""
    
    def test_to_prompt_context(self):
        """Test conversion to prompt string."""
        ctx = MarketContext(
            market_id="test-123",
            question="Will BTC be above $70k?",
            asset="BTC",
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.55"),
            yes_liquidity=Decimal("10000"),
            no_liquidity=Decimal("8000"),
            volume_24h=Decimal("50000"),
            time_to_resolution=15.0,
            spread=Decimal("0.02")
        )
        
        prompt = ctx.to_prompt_context()
        
        assert "BTC" in prompt
        assert "$70k" in prompt
        assert "0.45" in prompt
        assert "0.55" in prompt
        assert "15.0" in prompt


class TestPortfolioState:
    """Test PortfolioState dataclass."""
    
    def test_to_prompt_context(self):
        """Test conversion to prompt string."""
        state = PortfolioState(
            available_balance=Decimal("50.00"),
            total_balance=Decimal("100.00"),
            open_positions=[],
            daily_pnl=Decimal("5.00"),
            win_rate_today=0.75,
            trades_today=4,
            max_position_size=Decimal("5.00")
        )
        
        prompt = state.to_prompt_context()
        
        assert "$50.00" in prompt
        assert "$100.00" in prompt
        assert "75.0%" in prompt
        assert "4" in prompt


class TestTradeDecision:
    """Test TradeDecision dataclass."""
    
    def test_should_execute_high_confidence(self):
        """High confidence decisions should execute."""
        decision = TradeDecision(
            action=TradeAction.BUY_BOTH,
            confidence=85.0,
            position_size=Decimal("2.00"),
            order_type=OrderType.FOK,
            limit_price=None,
            reasoning="Clear arbitrage opportunity",
            risk_assessment="low",
            expected_profit=Decimal("0.10")
        )
        
        assert decision.should_execute is True
    
    def test_should_not_execute_low_confidence(self):
        """Low confidence decisions should not execute."""
        decision = TradeDecision(
            action=TradeAction.BUY_BOTH,
            confidence=50.0,
            position_size=Decimal("2.00"),
            order_type=OrderType.FOK,
            limit_price=None,
            reasoning="Uncertain opportunity",
            risk_assessment="medium",
            expected_profit=Decimal("0.05")
        )
        
        assert decision.should_execute is False
    
    def test_should_not_execute_skip_action(self):
        """SKIP actions should not execute regardless of confidence."""
        decision = TradeDecision(
            action=TradeAction.SKIP,
            confidence=95.0,
            position_size=Decimal("0"),
            order_type=OrderType.FOK,
            limit_price=None,
            reasoning="No opportunity",
            risk_assessment="low",
            expected_profit=Decimal("0")
        )
        
        assert decision.should_execute is False


class TestLLMDecisionEngine:
    """Test LLM Decision Engine."""
    
    @pytest.fixture
    def engine(self):
        """Create test engine with mock API."""
        return LLMDecisionEngine(
            nvidia_api_key="test-api-key",
            min_confidence_threshold=70.0,
            max_position_pct=5.0,
            decision_timeout=2.0
        )
    
    @pytest.fixture
    def market_context(self):
        """Create test market context."""
        return MarketContext(
            market_id="test-market-123",
            question="Will BTC price increase in next 15 minutes?",
            asset="BTC",
            yes_price=Decimal("0.48"),
            no_price=Decimal("0.50"),
            yes_liquidity=Decimal("5000"),
            no_liquidity=Decimal("4500"),
            volume_24h=Decimal("25000"),
            time_to_resolution=12.5,
            spread=Decimal("0.02")
        )
    
    @pytest.fixture
    def portfolio_state(self):
        """Create test portfolio state."""
        return PortfolioState(
            available_balance=Decimal("100.00"),
            total_balance=Decimal("100.00"),
            open_positions=[],
            daily_pnl=Decimal("0"),
            win_rate_today=0.5,
            trades_today=0,
            max_position_size=Decimal("5.00")
        )
    
    def test_fallback_decision_with_arbitrage(self, engine, market_context, portfolio_state):
        """Test fallback creates correct decision for clear arbitrage."""
        # Modify context so YES + NO < 0.97 (profitable)
        market_context.yes_price = Decimal("0.45")
        market_context.no_price = Decimal("0.48")  # Total = 0.93, profit margin > 0.04
        
        decision = engine._fallback_decision(market_context, portfolio_state)
        
        assert decision.action == TradeAction.BUY_BOTH
        assert decision.confidence >= 70.0
        assert decision.position_size > Decimal("0")
        assert "arbitrage" in decision.reasoning.lower()
    
    def test_fallback_decision_no_arbitrage(self, engine, market_context, portfolio_state):
        """Test fallback skips when no arbitrage opportunity."""
        # Modify context so YES + NO >= 1.00 (not profitable)
        market_context.yes_price = Decimal("0.50")
        market_context.no_price = Decimal("0.52")  # Total = 1.02, no profit
        
        decision = engine._fallback_decision(market_context, portfolio_state)
        
        assert decision.action == TradeAction.SKIP
        assert decision.confidence >= 70.0
        assert decision.position_size == Decimal("0")
    
    def test_parse_llm_response_valid_json(self, engine, market_context, portfolio_state):
        """Test parsing valid LLM JSON response."""
        response = '''
        {
            "action": "buy_both",
            "confidence": 85,
            "position_size_pct": 3.5,
            "order_type": "fok",
            "limit_price": null,
            "reasoning": "Clear arbitrage with 2% profit margin",
            "risk_assessment": "low",
            "expected_profit_pct": 2.0
        }
        '''
        
        decision = engine._parse_llm_response(response, market_context, portfolio_state)
        
        assert decision.action == TradeAction.BUY_BOTH
        assert decision.confidence == 85.0
        assert decision.order_type == OrderType.FOK
        assert "arbitrage" in decision.reasoning.lower()
    
    def test_parse_llm_response_with_markdown(self, engine, market_context, portfolio_state):
        """Test parsing LLM response wrapped in markdown code block."""
        response = '''
Here is my analysis:

```json
{
    "action": "skip",
    "confidence": 90,
    "position_size_pct": 0,
    "order_type": "fok",
    "limit_price": null,
    "reasoning": "Insufficient profit margin",
    "risk_assessment": "low",
    "expected_profit_pct": 0
}
```
        '''
        
        decision = engine._parse_llm_response(response, market_context, portfolio_state)
        
        assert decision.action == TradeAction.SKIP
        assert decision.confidence == 90.0
    
    def test_parse_llm_response_invalid_json(self, engine, market_context, portfolio_state):
        """Test fallback on invalid JSON response."""
        response = "This is not valid JSON at all"
        
        decision = engine._parse_llm_response(response, market_context, portfolio_state)
        
        # Should return fallback decision
        assert decision.action in [TradeAction.BUY_BOTH, TradeAction.SKIP]
    
    def test_position_size_respects_max(self, engine, market_context, portfolio_state):
        """Test position size is capped at max percentage."""
        response = '''
        {
            "action": "buy_both",
            "confidence": 95,
            "position_size_pct": 50.0,
            "order_type": "fok",
            "limit_price": null,
            "reasoning": "Very high profit",
            "risk_assessment": "low",
            "expected_profit_pct": 5.0
        }
        '''
        
        decision = engine._parse_llm_response(response, market_context, portfolio_state)
        
        # Position should be capped at max_position_pct (5%)
        max_allowed = portfolio_state.available_balance * Decimal("0.05")
        assert decision.position_size <= max_allowed
    
    def test_build_decision_prompt(self, engine, market_context, portfolio_state):
        """Test prompt building includes all context."""
        prompt = engine._build_decision_prompt(
            market_context, portfolio_state, "arbitrage"
        )
        
        assert "ARBITRAGE" in prompt.upper()
        assert market_context.question in prompt
        assert "Portfolio" in prompt or "PORTFOLIO" in prompt.upper()
    
    def test_statistics_tracking(self, engine):
        """Test statistics are tracked correctly."""
        stats = engine.get_statistics()
        
        assert stats["total_decisions"] == 0
        assert stats["fallback_rate"] == 0
        assert stats["avg_confidence"] == 0


class TestLLMDecisionEngineAsync:
    """Async tests for LLM Decision Engine."""
    
    @pytest.fixture
    def engine(self):
        """Create test engine."""
        return LLMDecisionEngine(
            nvidia_api_key="test-api-key",
            decision_timeout=1.0
        )
    
    @pytest.fixture
    def market_context(self):
        """Create test market context."""
        return MarketContext(
            market_id="test-123",
            question="Test market",
            asset="BTC",
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.48"),
            yes_liquidity=Decimal("5000"),
            no_liquidity=Decimal("5000"),
            volume_24h=Decimal("20000"),
            time_to_resolution=10.0,
            spread=Decimal("0.02")
        )
    
    @pytest.fixture
    def portfolio_state(self):
        """Create test portfolio state."""
        return PortfolioState(
            available_balance=Decimal("50.00"),
            total_balance=Decimal("50.00"),
            open_positions=[],
            daily_pnl=Decimal("0"),
            win_rate_today=0.5,
            trades_today=0,
            max_position_size=Decimal("2.50")
        )
    
    @pytest.mark.asyncio
    async def test_make_decision_timeout_uses_fallback(self, engine, market_context, portfolio_state):
        """Test timeout triggers fallback decision."""
        # Mock the LLM call to timeout
        async def slow_call(*args, **kwargs):
            await asyncio.sleep(5)  # Longer than timeout
        
        with patch.object(engine, '_call_llm', side_effect=asyncio.TimeoutError):
            decision = await engine.make_decision(
                market_context, portfolio_state, "arbitrage"
            )
        
        # Should use fallback
        assert decision is not None
        assert decision.action in [TradeAction.BUY_BOTH, TradeAction.SKIP]
    
    @pytest.mark.asyncio 
    async def test_make_decision_error_uses_fallback(self, engine, market_context, portfolio_state):
        """Test API error triggers fallback decision."""
        with patch.object(engine, '_call_llm', side_effect=Exception("API Error")):
            decision = await engine.make_decision(
                market_context, portfolio_state, "arbitrage"
            )
        
        # Should use fallback
        assert decision is not None
        assert decision.action in [TradeAction.BUY_BOTH, TradeAction.SKIP]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
