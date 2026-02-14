"""
Unit tests for ensemble decision engine error handling.

Tests that individual model failures are handled gracefully with neutral votes.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from src.ensemble_decision_engine import EnsembleDecisionEngine, ModelDecision


class TestEnsembleErrorHandling:
    """Test graceful error handling for model failures."""
    
    @pytest.fixture
    def mock_engines(self):
        """Create mock engines for testing."""
        llm_engine = Mock()
        rl_engine = Mock()
        historical_tracker = Mock()
        multi_tf_analyzer = Mock()
        
        return {
            'llm_engine': llm_engine,
            'rl_engine': rl_engine,
            'historical_tracker': historical_tracker,
            'multi_tf_analyzer': multi_tf_analyzer
        }
    
    @pytest.fixture
    def ensemble_engine(self, mock_engines):
        """Create ensemble engine with mocked components."""
        return EnsembleDecisionEngine(
            llm_engine=mock_engines['llm_engine'],
            rl_engine=mock_engines['rl_engine'],
            historical_tracker=mock_engines['historical_tracker'],
            multi_tf_analyzer=mock_engines['multi_tf_analyzer']
        )
    
    @pytest.mark.asyncio
    async def test_llm_failure_returns_neutral_vote(self, ensemble_engine, mock_engines):
        """Test that LLM failure returns neutral vote (skip, 0% confidence)."""
        # Arrange: Make LLM raise an exception
        mock_engines['llm_engine'].make_decision = AsyncMock(
            side_effect=Exception("LLM API timeout")
        )
        
        # Mock other engines to return valid responses
        mock_engines['rl_engine'].select_strategy.return_value = ("skip", 0.0)
        mock_engines['historical_tracker'].should_trade.return_value = (False, 0.0, "No history")
        mock_engines['multi_tf_analyzer'].get_multi_timeframe_signal.return_value = ("neutral", 0.0, [])
        
        market_context = {"volatility": 0.02, "trend": "neutral", "liquidity": 1000}
        portfolio_state = {"balance": 100}
        
        # Act
        decision = await ensemble_engine.make_decision(
            asset="BTC",
            market_context=market_context,
            portfolio_state=portfolio_state,
            opportunity_type="latency"
        )
        
        # Assert: Decision should still be made with remaining models
        assert decision is not None
        assert decision.action == "skip"  # All models voting skip
        
    @pytest.mark.asyncio
    async def test_rl_failure_returns_neutral_vote(self, ensemble_engine, mock_engines):
        """Test that RL failure returns neutral vote (skip, 0% confidence)."""
        # Arrange: Make RL raise an exception
        mock_engines['rl_engine'].select_strategy.side_effect = Exception("RL model error")
        
        # Mock other engines
        llm_decision = Mock()
        llm_decision.action.value = "skip"
        llm_decision.confidence = 0.0
        llm_decision.reasoning = "No opportunity"
        mock_engines['llm_engine'].make_decision = AsyncMock(return_value=llm_decision)
        
        mock_engines['historical_tracker'].should_trade.return_value = (False, 0.0, "No history")
        mock_engines['multi_tf_analyzer'].get_multi_timeframe_signal.return_value = ("neutral", 0.0, [])
        
        market_context = {"volatility": 0.02, "trend": "neutral", "liquidity": 1000}
        portfolio_state = {"balance": 100}
        
        # Act
        decision = await ensemble_engine.make_decision(
            asset="BTC",
            market_context=market_context,
            portfolio_state=portfolio_state,
            opportunity_type="latency"
        )
        
        # Assert
        assert decision is not None
        assert decision.action == "skip"
        
    @pytest.mark.asyncio
    async def test_historical_failure_returns_neutral_vote(self, ensemble_engine, mock_engines):
        """Test that Historical tracker failure returns neutral vote."""
        # Arrange: Make Historical raise an exception
        mock_engines['historical_tracker'].should_trade.side_effect = Exception("Database error")
        
        # Mock other engines
        llm_decision = Mock()
        llm_decision.action.value = "skip"
        llm_decision.confidence = 0.0
        llm_decision.reasoning = "No opportunity"
        mock_engines['llm_engine'].make_decision = AsyncMock(return_value=llm_decision)
        
        mock_engines['rl_engine'].select_strategy.return_value = ("skip", 0.0)
        mock_engines['multi_tf_analyzer'].get_multi_timeframe_signal.return_value = ("neutral", 0.0, [])
        
        market_context = {"volatility": 0.02, "trend": "neutral", "liquidity": 1000}
        portfolio_state = {"balance": 100}
        
        # Act
        decision = await ensemble_engine.make_decision(
            asset="BTC",
            market_context=market_context,
            portfolio_state=portfolio_state,
            opportunity_type="latency"
        )
        
        # Assert
        assert decision is not None
        assert decision.action == "skip"
        
    @pytest.mark.asyncio
    async def test_technical_failure_returns_neutral_vote(self, ensemble_engine, mock_engines):
        """Test that Technical analyzer failure returns neutral vote."""
        # Arrange: Make Technical raise an exception
        mock_engines['multi_tf_analyzer'].get_multi_timeframe_signal.side_effect = Exception("Data feed error")
        
        # Mock other engines
        llm_decision = Mock()
        llm_decision.action.value = "skip"
        llm_decision.confidence = 0.0
        llm_decision.reasoning = "No opportunity"
        mock_engines['llm_engine'].make_decision = AsyncMock(return_value=llm_decision)
        
        mock_engines['rl_engine'].select_strategy.return_value = ("skip", 0.0)
        mock_engines['historical_tracker'].should_trade.return_value = (False, 0.0, "No history")
        
        market_context = {"volatility": 0.02, "trend": "neutral", "liquidity": 1000}
        portfolio_state = {"balance": 100}
        
        # Act
        decision = await ensemble_engine.make_decision(
            asset="BTC",
            market_context=market_context,
            portfolio_state=portfolio_state,
            opportunity_type="latency"
        )
        
        # Assert
        assert decision is not None
        assert decision.action == "skip"
        
    @pytest.mark.asyncio
    async def test_multiple_failures_still_makes_decision(self, ensemble_engine, mock_engines):
        """Test that multiple model failures still allow decision with remaining models."""
        # Arrange: Make LLM and RL fail
        mock_engines['llm_engine'].make_decision = AsyncMock(
            side_effect=Exception("LLM timeout")
        )
        mock_engines['rl_engine'].select_strategy.side_effect = Exception("RL error")
        
        # Only Historical and Technical work
        mock_engines['historical_tracker'].should_trade.return_value = (True, 80.0, "Good history")
        mock_engines['multi_tf_analyzer'].get_multi_timeframe_signal.return_value = ("bullish", 70.0, ["1m", "5m"])
        
        market_context = {"volatility": 0.02, "trend": "bullish", "liquidity": 1000}
        portfolio_state = {"balance": 100}
        
        # Act
        decision = await ensemble_engine.make_decision(
            asset="BTC",
            market_context=market_context,
            portfolio_state=portfolio_state,
            opportunity_type="latency"
        )
        
        # Assert: Should still make a decision with remaining 2 models
        assert decision is not None
        # With Historical (20% weight) and Technical (15% weight) both positive,
        # and LLM/RL returning neutral (skip, 0%), the decision should favor buy_yes
        assert decision.action in ["buy_yes", "skip"]  # Depends on consensus threshold
        
    @pytest.mark.asyncio
    async def test_all_failures_returns_skip_decision(self, ensemble_engine, mock_engines):
        """Test that all model failures result in skip decision."""
        # Arrange: Make all models fail
        mock_engines['llm_engine'].make_decision = AsyncMock(
            side_effect=Exception("LLM timeout")
        )
        mock_engines['rl_engine'].select_strategy.side_effect = Exception("RL error")
        mock_engines['historical_tracker'].should_trade.side_effect = Exception("DB error")
        mock_engines['multi_tf_analyzer'].get_multi_timeframe_signal.side_effect = Exception("Feed error")
        
        market_context = {"volatility": 0.02, "trend": "neutral", "liquidity": 1000}
        portfolio_state = {"balance": 100}
        
        # Act
        decision = await ensemble_engine.make_decision(
            asset="BTC",
            market_context=market_context,
            portfolio_state=portfolio_state,
            opportunity_type="latency"
        )
        
        # Assert: All models return neutral votes, so decision should be skip
        assert decision is not None
        assert decision.action == "skip"
        assert decision.confidence == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
