"""
Test consensus threshold and approval rate tracking.
"""
import pytest
from src.ensemble_decision_engine import EnsembleDecisionEngine, EnsembleDecision, ModelDecision


class TestConsensusThreshold:
    """Test consensus threshold changes and approval rate tracking."""
    
    def test_default_threshold_is_15_percent(self):
        """Verify default min_consensus is 15.0%."""
        engine = EnsembleDecisionEngine()
        assert engine.min_consensus == 15.0
    
    def test_custom_threshold_can_be_set(self):
        """Verify custom threshold can be set."""
        engine = EnsembleDecisionEngine(min_consensus=25.0)
        assert engine.min_consensus == 25.0
    
    def test_approval_rate_tracking_starts_at_zero(self):
        """Verify approval rate starts at 0%."""
        engine = EnsembleDecisionEngine()
        assert engine.get_approval_rate() == 0.0
        assert engine.decisions_above_threshold == 0
        assert engine.decisions_below_threshold == 0
    
    def test_approval_rate_increases_with_approved_trades(self):
        """Verify approval rate increases when trades are approved."""
        engine = EnsembleDecisionEngine(min_consensus=15.0)
        
        # Create decision with consensus above threshold
        decision = EnsembleDecision(
            action="buy_yes",
            confidence=50.0,
            consensus_score=20.0,  # Above 15.0 threshold
            model_votes={},
            reasoning="Test"
        )
        
        # Check if should execute (should approve)
        result = engine.should_execute(decision)
        assert result is True
        assert engine.decisions_above_threshold == 1
        assert engine.decisions_below_threshold == 0
        assert engine.get_approval_rate() == 100.0
    
    def test_approval_rate_decreases_with_blocked_trades(self):
        """Verify approval rate decreases when trades are blocked."""
        engine = EnsembleDecisionEngine(min_consensus=15.0)
        
        # Create decision with consensus below threshold
        decision = EnsembleDecision(
            action="buy_yes",
            confidence=50.0,
            consensus_score=10.0,  # Below 15.0 threshold
            model_votes={},
            reasoning="Test"
        )
        
        # Check if should execute (should block)
        result = engine.should_execute(decision)
        assert result is False
        assert engine.decisions_above_threshold == 0
        assert engine.decisions_below_threshold == 1
        assert engine.get_approval_rate() == 0.0
    
    def test_approval_rate_calculates_correctly_with_mixed_results(self):
        """Verify approval rate calculates correctly with mixed approved/blocked."""
        engine = EnsembleDecisionEngine(min_consensus=15.0)
        
        # Approve 3 trades
        for _ in range(3):
            decision = EnsembleDecision(
                action="buy_yes",
                confidence=50.0,
                consensus_score=20.0,
                model_votes={},
                reasoning="Test"
            )
            engine.should_execute(decision)
        
        # Block 2 trades
        for _ in range(2):
            decision = EnsembleDecision(
                action="buy_yes",
                confidence=50.0,
                consensus_score=10.0,
                model_votes={},
                reasoning="Test"
            )
            engine.should_execute(decision)
        
        # Verify counts
        assert engine.decisions_above_threshold == 3
        assert engine.decisions_below_threshold == 2
        
        # Verify approval rate: 3/5 = 60%
        assert engine.get_approval_rate() == 60.0
    
    def test_skip_action_blocks_trade(self):
        """Verify skip action blocks trade regardless of consensus."""
        engine = EnsembleDecisionEngine(min_consensus=15.0)
        
        decision = EnsembleDecision(
            action="skip",
            confidence=50.0,
            consensus_score=90.0,  # High consensus but skip action
            model_votes={},
            reasoning="Test"
        )
        
        result = engine.should_execute(decision)
        assert result is False
        # Note: skip action doesn't increment threshold counters
        assert engine.decisions_above_threshold == 0
        assert engine.decisions_below_threshold == 0
    
    def test_low_confidence_blocks_trade(self):
        """Verify low confidence (<1%) blocks trade."""
        engine = EnsembleDecisionEngine(min_consensus=15.0)
        
        decision = EnsembleDecision(
            action="buy_yes",
            confidence=0.5,  # Below 1.0% threshold
            consensus_score=20.0,  # Above consensus threshold
            model_votes={},
            reasoning="Test"
        )
        
        result = engine.should_execute(decision)
        assert result is False
        # Note: low confidence check happens after consensus check
        # so it doesn't increment threshold counters
    
    def test_performance_summary_includes_approval_rate(self):
        """Verify performance summary includes approval rate."""
        engine = EnsembleDecisionEngine(min_consensus=15.0)
        
        # Manually set total_decisions to simulate make_decision() calls
        engine.total_decisions = 2
        
        # Make some decisions
        decision_approved = EnsembleDecision(
            action="buy_yes",
            confidence=50.0,
            consensus_score=20.0,
            model_votes={},
            reasoning="Test"
        )
        engine.should_execute(decision_approved)
        
        decision_blocked = EnsembleDecision(
            action="buy_yes",
            confidence=50.0,
            consensus_score=10.0,
            model_votes={},
            reasoning="Test"
        )
        engine.should_execute(decision_blocked)
        
        # Get summary
        summary = engine.get_performance_summary()
        
        # Verify summary contains approval rate info
        assert "Approval Rate:" in summary
        assert "50.0%" in summary  # 1 approved, 1 blocked = 50%
        assert "1 approved" in summary
        assert "1 blocked" in summary
        assert "Min Consensus: 15.0%" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
