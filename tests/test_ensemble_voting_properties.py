"""
Property-based tests for ensemble voting correctness.

Tests that ensemble voting calculations are correct across a wide range of random inputs.

**Validates: Requirements 3.1, 3.2**
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from typing import Dict

from src.ensemble_decision_engine import (
    EnsembleDecisionEngine,
    ModelDecision,
    VoteWeight
)


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def model_votes_strategy(draw):
    """Generate random model votes with various confidence levels."""
    votes = {}
    
    # Generate vote for each model
    for model_name in ["LLM", "RL", "Historical", "Technical"]:
        action = draw(st.sampled_from(["buy_yes", "buy_no", "skip"]))
        confidence = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
        
        votes[model_name] = ModelDecision(
            model_name=model_name,
            action=action,
            confidence=confidence,
            reasoning=f"{model_name} reasoning"
        )
    
    return votes


@st.composite
def aligned_votes_strategy(draw, action: str):
    """Generate votes where all models agree on the same action."""
    votes = {}
    
    for model_name in ["LLM", "RL", "Historical", "Technical"]:
        confidence = draw(st.floats(min_value=50.0, max_value=100.0, allow_nan=False, allow_infinity=False))
        
        votes[model_name] = ModelDecision(
            model_name=model_name,
            action=action,
            confidence=confidence,
            reasoning=f"{model_name} reasoning"
        )
    
    return votes


@st.composite
def low_confidence_votes_strategy(draw):
    """Generate votes with low confidence (should result in skip)."""
    votes = {}
    
    for model_name in ["LLM", "RL", "Historical", "Technical"]:
        action = draw(st.sampled_from(["buy_yes", "buy_no", "skip"]))
        # Low confidence: 0-10%
        confidence = draw(st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False))
        
        votes[model_name] = ModelDecision(
            model_name=model_name,
            action=action,
            confidence=confidence,
            reasoning=f"{model_name} reasoning"
        )
    
    return votes


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_expected_weighted_score(votes: Dict[str, ModelDecision], action: str) -> float:
    """
    Calculate expected weighted score for a given action.
    
    This replicates the ensemble engine's calculation logic.
    """
    score = 0.0
    total_weight = 0.0
    
    for model_name, vote in votes.items():
        # Get model weight
        if model_name == "LLM":
            weight = VoteWeight.LLM.value
        elif model_name == "RL":
            weight = VoteWeight.RL.value
        elif model_name == "Historical":
            weight = VoteWeight.HISTORICAL.value
        elif model_name == "Technical":
            weight = VoteWeight.TECHNICAL.value
        else:
            weight = 0.1
        
        # Weight by confidence (0-100 -> 0-1)
        confidence_weight = vote.confidence / 100.0
        
        # Add weighted vote if action matches
        if vote.action == action:
            score += weight * confidence_weight
        
        total_weight += weight
    
    # Normalize
    if total_weight > 0:
        score /= total_weight
    
    return score


def get_expected_action(votes: Dict[str, ModelDecision]) -> str:
    """Calculate which action should win based on weighted voting."""
    action_scores = {}
    
    for action in ["buy_yes", "buy_no", "skip"]:
        action_scores[action] = calculate_expected_weighted_score(votes, action)
    
    # Return action with highest score
    return max(action_scores, key=action_scores.get)


# ============================================================================
# PROPERTY 10: ENSEMBLE VOTING WEIGHT CORRECTNESS
# ============================================================================

@given(votes=model_votes_strategy())
@settings(max_examples=100, deadline=None)
def test_property_weighted_score_calculation_correct(votes):
    """
    **Validates: Requirements 3.1, 3.2**
    
    Property 10a: Weighted Score Calculation
    
    For any set of model votes, the ensemble should calculate weighted scores correctly:
    - Each model's vote is weighted by its model weight (LLM=40%, RL=25%, Historical=20%, Technical=15%)
    - Each vote is further weighted by the model's confidence (0-100%)
    - The final score for each action is the sum of weighted votes
    """
    engine = EnsembleDecisionEngine(min_consensus=15.0)
    
    # Calculate ensemble decision
    decision = engine._calculate_ensemble(votes)
    
    # Calculate expected scores for each action
    expected_scores = {}
    for action in ["buy_yes", "buy_no", "skip"]:
        expected_scores[action] = calculate_expected_weighted_score(votes, action)
    
    # Get expected winning action
    expected_action = max(expected_scores, key=expected_scores.get)
    expected_consensus = expected_scores[expected_action] * 100
    
    # Special case: If all scores are equal (or all zero), ensemble defaults to skip
    if len(set(expected_scores.values())) == 1:
        expected_action = "skip"
        expected_consensus = 0.0
    
    # Verify: Ensemble should select the action with highest weighted score
    assert decision.action == expected_action, (
        f"Expected action {expected_action} (score: {expected_consensus:.1f}%), "
        f"got {decision.action} (score: {decision.consensus_score:.1f}%)"
    )
    
    # Verify: Consensus score should match expected score (within 0.1% tolerance)
    assert abs(decision.consensus_score - expected_consensus) < 0.1, (
        f"Expected consensus {expected_consensus:.1f}%, got {decision.consensus_score:.1f}%"
    )


@given(votes=aligned_votes_strategy(action="buy_yes"))
@settings(max_examples=50, deadline=None)
def test_property_unanimous_votes_high_consensus(votes):
    """
    **Validates: Requirements 3.1, 3.2**
    
    Property 10b: Unanimous Votes Result in High Consensus
    
    When all models vote for the same action with high confidence (>50%),
    the consensus score should be high (>50%).
    """
    engine = EnsembleDecisionEngine(min_consensus=15.0)
    
    # Calculate ensemble decision
    decision = engine._calculate_ensemble(votes)
    
    # Verify: Action should be buy_yes (all models voted for it)
    assert decision.action == "buy_yes", (
        f"Expected buy_yes when all models agree, got {decision.action}"
    )
    
    # Verify: Consensus should be high (>=50%)
    assert decision.consensus_score >= 50.0, (
        f"Expected high consensus (>=50%) for unanimous votes, got {decision.consensus_score:.1f}%"
    )


@given(votes=low_confidence_votes_strategy())
@settings(max_examples=50, deadline=None)
def test_property_low_confidence_results_in_low_consensus(votes):
    """
    **Validates: Requirements 3.1, 3.2**
    
    Property 10c: Low Confidence Results in Low Consensus
    
    When all models have low confidence (<10%), the consensus score should be low (<15%).
    """
    engine = EnsembleDecisionEngine(min_consensus=15.0)
    
    # Calculate ensemble decision
    decision = engine._calculate_ensemble(votes)
    
    # Verify: Consensus should be low (<15%)
    assert decision.consensus_score < 15.0, (
        f"Expected low consensus (<15%) for low confidence votes, got {decision.consensus_score:.1f}%"
    )


@given(votes=model_votes_strategy())
@settings(max_examples=100, deadline=None)
def test_property_skip_action_when_below_threshold(votes):
    """
    **Validates: Requirements 3.1, 3.2**
    
    Property 10d: Skip Action When Below Threshold
    
    When the consensus score is below the minimum threshold (15%),
    the decision should not be executed (should_execute returns False).
    """
    engine = EnsembleDecisionEngine(min_consensus=15.0)
    
    # Calculate ensemble decision
    decision = engine._calculate_ensemble(votes)
    
    # Check if should execute
    should_execute = engine.should_execute(decision)
    
    # Verify: If consensus < 15% and action != skip, should_execute should be False
    if decision.consensus_score < 15.0 and decision.action != "skip":
        assert not should_execute, (
            f"Expected should_execute=False for consensus {decision.consensus_score:.1f}% < 15%, "
            f"but got should_execute=True"
        )
    
    # Verify: If action is skip, should_execute should always be False
    if decision.action == "skip":
        assert not should_execute, (
            f"Expected should_execute=False for skip action, but got should_execute=True"
        )


@given(votes=model_votes_strategy())
@settings(max_examples=100, deadline=None)
def test_property_model_weights_applied_correctly(votes):
    """
    **Validates: Requirements 3.1, 3.2**
    
    Property 10e: Model Weights Applied Correctly
    
    For any set of votes, verify that model weights are applied correctly:
    - LLM votes should have 40% weight
    - RL votes should have 25% weight
    - Historical votes should have 20% weight
    - Technical votes should have 15% weight
    """
    engine = EnsembleDecisionEngine(min_consensus=15.0)
    
    # Calculate ensemble decision
    decision = engine._calculate_ensemble(votes)
    
    # Manually calculate what the score should be for the winning action
    expected_score = 0.0
    total_weight = 0.0
    
    for model_name, vote in votes.items():
        if vote.action == decision.action:
            # Get model weight
            if model_name == "LLM":
                weight = 0.40
            elif model_name == "RL":
                weight = 0.25
            elif model_name == "Historical":
                weight = 0.20
            elif model_name == "Technical":
                weight = 0.15
            else:
                weight = 0.1
            
            # Weight by confidence
            confidence_weight = vote.confidence / 100.0
            expected_score += weight * confidence_weight
        
        # Add to total weight
        if model_name == "LLM":
            total_weight += 0.40
        elif model_name == "RL":
            total_weight += 0.25
        elif model_name == "Historical":
            total_weight += 0.20
        elif model_name == "Technical":
            total_weight += 0.15
    
    # Normalize
    if total_weight > 0:
        expected_score /= total_weight
    
    expected_consensus = expected_score * 100
    
    # Verify: Consensus should match expected (within 0.1% tolerance)
    assert abs(decision.consensus_score - expected_consensus) < 0.1, (
        f"Expected consensus {expected_consensus:.1f}%, got {decision.consensus_score:.1f}%"
    )


@given(
    llm_confidence=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    rl_confidence=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    historical_confidence=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    technical_confidence=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100, deadline=None)
def test_property_consensus_bounded_by_confidence(llm_confidence, rl_confidence, historical_confidence, technical_confidence):
    """
    **Validates: Requirements 3.1, 3.2**
    
    Property 10f: Consensus Score Bounded by Confidence
    
    The consensus score should never exceed the maximum confidence of any model voting for that action.
    The consensus score should be a weighted average, so it should be between the min and max confidences.
    """
    # Create votes where all models vote for the same action
    votes = {
        "LLM": ModelDecision("LLM", "buy_yes", llm_confidence, "LLM reasoning"),
        "RL": ModelDecision("RL", "buy_yes", rl_confidence, "RL reasoning"),
        "Historical": ModelDecision("Historical", "buy_yes", historical_confidence, "Historical reasoning"),
        "Technical": ModelDecision("Technical", "buy_yes", technical_confidence, "Technical reasoning")
    }
    
    engine = EnsembleDecisionEngine(min_consensus=15.0)
    decision = engine._calculate_ensemble(votes)
    
    # Get min and max confidence
    confidences = [llm_confidence, rl_confidence, historical_confidence, technical_confidence]
    min_confidence = min(confidences)
    max_confidence = max(confidences)
    
    # Verify: Consensus should be between min and max confidence (with some tolerance for weighting)
    # Since we're using weighted average, consensus should be within [min, max]
    # Allow 1% tolerance for floating point errors
    assert decision.consensus_score >= min_confidence - 1.0, (
        f"Consensus {decision.consensus_score:.1f}% should be >= min confidence {min_confidence:.1f}%"
    )
    assert decision.consensus_score <= max_confidence + 1.0, (
        f"Consensus {decision.consensus_score:.1f}% should be <= max confidence {max_confidence:.1f}%"
    )


@given(votes=model_votes_strategy())
@settings(max_examples=50, deadline=None)
def test_property_ensemble_decision_always_has_reasoning(votes):
    """
    **Validates: Requirements 3.1, 3.2**
    
    Property 10g: Ensemble Decision Always Has Reasoning
    
    Every ensemble decision should include reasoning that summarizes the model votes.
    """
    engine = EnsembleDecisionEngine(min_consensus=15.0)
    decision = engine._calculate_ensemble(votes)
    
    # Verify: Reasoning should not be empty
    assert decision.reasoning, "Ensemble decision should always have reasoning"
    
    # Verify: Reasoning should mention "Ensemble vote"
    assert "Ensemble vote" in decision.reasoning, (
        f"Reasoning should mention 'Ensemble vote', got: {decision.reasoning}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
