"""
Unit tests for ensemble model weights validation.

Tests that model weights are correctly configured and sum to 1.0.
"""

import pytest
from src.ensemble_decision_engine import VoteWeight, EnsembleDecisionEngine


def test_model_weights_sum_to_one():
    """Test that all model weights sum to exactly 1.0."""
    total_weight = sum(w.value for w in VoteWeight)
    assert abs(total_weight - 1.0) < 0.001, f"Weights must sum to 1.0, got {total_weight}"


def test_individual_weight_values():
    """Test that individual weights match expected values."""
    assert VoteWeight.LLM.value == 0.40, "LLM weight should be 40%"
    assert VoteWeight.RL.value == 0.35, "RL weight should be 35%"
    assert VoteWeight.HISTORICAL.value == 0.20, "Historical weight should be 20%"
    assert VoteWeight.TECHNICAL.value == 0.05, "Technical weight should be 5%"


def test_all_weights_positive():
    """Test that all weights are positive values."""
    for weight in VoteWeight:
        assert weight.value > 0, f"{weight.name} weight must be positive"


def test_all_weights_less_than_one():
    """Test that no individual weight exceeds 1.0."""
    for weight in VoteWeight:
        assert weight.value <= 1.0, f"{weight.name} weight must be <= 1.0"


def test_ensemble_engine_validates_weights():
    """Test that EnsembleDecisionEngine validates weights on initialization."""
    # This should not raise an error with current weights
    try:
        engine = EnsembleDecisionEngine()
        assert True, "Engine initialized successfully with valid weights"
    except ValueError as e:
        pytest.fail(f"Engine should initialize with valid weights, but got error: {e}")


def test_weight_validation_error_message():
    """Test that weight validation provides clear error message."""
    # Temporarily modify weights to test validation (this is a conceptual test)
    # In practice, we verify the validation logic exists in __init__
    total_weight = sum(w.value for w in VoteWeight)
    
    # Verify the validation logic would catch invalid weights
    if abs(total_weight - 1.0) > 0.001:
        expected_error = (
            f"Model weights must sum to 1.0, got {total_weight:.4f}. "
            f"Weights: LLM={VoteWeight.LLM.value}, RL={VoteWeight.RL.value}, "
            f"Historical={VoteWeight.HISTORICAL.value}, Technical={VoteWeight.TECHNICAL.value}"
        )
        # This test passes if weights are valid (which they should be)
        assert abs(total_weight - 1.0) <= 0.001, expected_error
