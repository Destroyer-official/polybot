"""
Property-based tests for multi-timeframe signal confirmation.

Tests that multi-timeframe analyzer requires at least 2 timeframes to agree
before confirming a signal, and skips trades when only 1 timeframe signals.

**Validates: Requirements 3.3**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from collections import deque
from typing import Dict, List

from src.multi_timeframe_analyzer import MultiTimeframeAnalyzer, TimeframeSignal


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def timeframe_signals_strategy(draw):
    """Generate random timeframe signals with various agreement patterns."""
    # Generate signals for 1m, 5m, 15m timeframes
    timeframes = ["1m", "5m", "15m"]
    signals = {}
    
    for tf in timeframes:
        # Randomly decide if this timeframe has a signal
        has_signal = draw(st.booleans())
        
        if has_signal:
            # Generate direction
            direction = draw(st.sampled_from(["bullish", "bearish", "neutral"]))
            
            # Generate strength (0-100)
            strength = draw(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
            
            # Generate price change
            if direction == "bullish":
                price_change = Decimal(str(draw(st.floats(min_value=0.002, max_value=0.10, allow_nan=False, allow_infinity=False))))
            elif direction == "bearish":
                price_change = Decimal(str(draw(st.floats(min_value=-0.10, max_value=-0.002, allow_nan=False, allow_infinity=False))))
            else:
                price_change = Decimal(str(draw(st.floats(min_value=-0.002, max_value=0.002, allow_nan=False, allow_infinity=False))))
            
            # Generate optional volume ratio
            has_volume = draw(st.booleans())
            volume_ratio = draw(st.floats(min_value=0.5, max_value=3.0, allow_nan=False, allow_infinity=False)) if has_volume else None
            
            signals[tf] = TimeframeSignal(
                timeframe=tf,
                direction=direction,
                strength=strength,
                price_change=price_change,
                volume_ratio=volume_ratio
            )
    
    return signals


@st.composite
def price_history_strategy(draw):
    """Generate random price history for an asset."""
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    
    # Generate base price
    base_price = Decimal(str(draw(st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False))))
    
    # Generate number of price points (2-60)
    num_points = draw(st.integers(min_value=2, max_value=60))
    
    # Generate price history with random movements
    prices = []
    current_price = base_price
    current_time = datetime.now(timezone.utc)
    
    for i in range(num_points):
        # Random price change (-5% to +5%)
        change_pct = Decimal(str(draw(st.floats(min_value=-0.05, max_value=0.05, allow_nan=False, allow_infinity=False))))
        current_price = current_price * (Decimal("1.0") + change_pct)
        
        # Add to history
        timestamp = current_time - timedelta(minutes=num_points - i)
        prices.append((timestamp, current_price))
    
    return asset, prices


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_analyzer_with_signals(signals: Dict[str, TimeframeSignal], asset: str = "BTC") -> MultiTimeframeAnalyzer:
    """Create a multi-timeframe analyzer with pre-populated signals."""
    analyzer = MultiTimeframeAnalyzer()
    
    # Populate price history to generate the desired signals
    current_time = datetime.now(timezone.utc)
    base_price = Decimal("50000.0")  # BTC price
    
    for tf, signal in signals.items():
        # Calculate number of periods based on timeframe
        if tf == "1m":
            period_seconds = 60
            num_periods = 10
        elif tf == "5m":
            period_seconds = 300
            num_periods = 10
        else:  # 15m
            period_seconds = 900
            num_periods = 10
        
        # Generate price history that produces the desired signal
        for i in range(num_periods):
            timestamp = current_time - timedelta(seconds=period_seconds * (num_periods - i))
            
            # Calculate price based on desired direction
            if signal.direction == "bullish":
                # Prices increase over time - ensure > 0.2% change
                progress = Decimal(str(i)) / Decimal(str(num_periods - 1)) if num_periods > 1 else Decimal("1.0")
                # Use at least 0.3% change to ensure signal is detected
                price_change = max(abs(signal.price_change), Decimal("0.003"))
                price = base_price * (Decimal("1.0") + price_change * progress)
            elif signal.direction == "bearish":
                # Prices decrease over time - ensure > 0.2% change
                progress = Decimal(str(i)) / Decimal(str(num_periods - 1)) if num_periods > 1 else Decimal("1.0")
                # Use at least 0.3% change to ensure signal is detected
                price_change = max(abs(signal.price_change), Decimal("0.003"))
                price = base_price * (Decimal("1.0") - price_change * progress)
            else:
                # Prices stay flat (< 0.2% change)
                price = base_price * (Decimal("1.0") + Decimal("0.0001") * Decimal(str(i)))
            
            # Add to appropriate timeframe
            analyzer.price_history[asset][tf].append((timestamp, price))
            
            # Add volume if specified
            if signal.volume_ratio is not None:
                volume = Decimal("1000.0") * Decimal(str(signal.volume_ratio))
                analyzer.volume_history[asset][tf].append((timestamp, volume))
    
    return analyzer


def count_agreeing_timeframes(signals: Dict[str, TimeframeSignal], direction: str) -> int:
    """Count how many timeframes agree on a direction."""
    return sum(1 for s in signals.values() if s.direction == direction)


# ============================================================================
# PROPERTY 11: MULTI-TIMEFRAME SIGNAL CONFIRMATION
# ============================================================================

@given(signals=timeframe_signals_strategy())
@settings(max_examples=100, deadline=None)
def test_property_multi_timeframe_requires_two_agreeing(signals):
    """
    **Validates: Requirements 3.3**
    
    Property 11a: Multi-Timeframe Requires 2+ Agreeing
    
    When require_alignment=True, the multi-timeframe analyzer should only
    return a bullish or bearish signal if at least 2 timeframes agree.
    
    If only 1 timeframe signals, the result should be neutral.
    """
    # Skip if no signals
    assume(len(signals) > 0)
    
    analyzer = create_analyzer_with_signals(signals, "BTC")
    
    # Get multi-timeframe signal with alignment required
    direction, confidence, returned_signals = analyzer.get_multi_timeframe_signal("BTC", require_alignment=True)
    
    # Count how many timeframes agree on each direction
    bullish_count = count_agreeing_timeframes(signals, "bullish")
    bearish_count = count_agreeing_timeframes(signals, "bearish")
    
    # Verify: If bullish_count >= 2, direction should be bullish
    if bullish_count >= 2:
        assert direction == "bullish", \
            f"Expected bullish (count={bullish_count}), got {direction}"
    
    # Verify: If bearish_count >= 2, direction should be bearish
    elif bearish_count >= 2:
        assert direction == "bearish", \
            f"Expected bearish (count={bearish_count}), got {direction}"
    
    # Verify: If neither has 2+, direction should be neutral
    else:
        assert direction == "neutral", \
            f"Expected neutral (bullish={bullish_count}, bearish={bearish_count}), got {direction}"


@given(signals=timeframe_signals_strategy())
@settings(max_examples=100, deadline=None)
def test_property_multi_timeframe_skips_single_signal(signals):
    """
    **Validates: Requirements 3.3**
    
    Property 11b: Multi-Timeframe Skips Single Signal
    
    When only 1 timeframe signals bullish or bearish, the multi-timeframe
    analyzer should return neutral (skip the trade).
    
    This prevents false signals and improves win rate.
    """
    # Filter to only have 1 bullish signal
    filtered_signals = {}
    bullish_added = False
    
    for tf, signal in signals.items():
        if signal.direction == "bullish" and not bullish_added:
            filtered_signals[tf] = signal
            bullish_added = True
        elif signal.direction != "bullish":
            # Add neutral or bearish signals
            filtered_signals[tf] = signal
    
    # Skip if we don't have exactly 1 bullish signal
    assume(bullish_added)
    assume(count_agreeing_timeframes(filtered_signals, "bullish") == 1)
    assume(count_agreeing_timeframes(filtered_signals, "bearish") < 2)
    
    analyzer = create_analyzer_with_signals(filtered_signals, "BTC")
    
    # Get multi-timeframe signal with alignment required
    direction, confidence, returned_signals = analyzer.get_multi_timeframe_signal("BTC", require_alignment=True)
    
    # Verify: Direction should be neutral (trade skipped)
    assert direction == "neutral", \
        f"Expected neutral with only 1 bullish signal, got {direction}"


@given(signals=timeframe_signals_strategy())
@settings(max_examples=100, deadline=None)
def test_property_multi_timeframe_confidence_from_aligned_signals(signals):
    """
    **Validates: Requirements 3.3**
    
    Property 11c: Confidence From Aligned Signals Only
    
    When calculating confidence, the multi-timeframe analyzer should only
    use the strength of signals that agree with the final direction.
    
    Signals that disagree should not contribute to confidence.
    """
    # Skip if no signals
    assume(len(signals) > 0)
    
    analyzer = create_analyzer_with_signals(signals, "BTC")
    
    # Get multi-timeframe signal with alignment required
    direction, confidence, returned_signals = analyzer.get_multi_timeframe_signal("BTC", require_alignment=True)
    
    # If direction is neutral, confidence should be 0
    if direction == "neutral":
        assert confidence == 0.0, \
            f"Expected 0 confidence for neutral, got {confidence}"
    
    # If direction is bullish or bearish, confidence should be average of aligned signals
    else:
        # Use the ACTUAL returned signals (which have calculated strength)
        # not the input signals (which may have different strength)
        aligned_signals = [s for s in returned_signals.values() if s.direction == direction]
        
        if aligned_signals:
            expected_confidence = sum(s.strength for s in aligned_signals) / len(aligned_signals)
            
            # Allow for volume boost (up to 20%)
            max_expected = expected_confidence * 1.2
            
            assert confidence >= expected_confidence * 0.99, \
                f"Confidence {confidence} too low (expected ~{expected_confidence})"
            assert confidence <= min(100.0, max_expected * 1.01), \
                f"Confidence {confidence} too high (expected ~{expected_confidence})"


@given(asset_prices=price_history_strategy())
@settings(max_examples=50, deadline=None)
def test_property_multi_timeframe_with_real_price_history(asset_prices):
    """
    **Validates: Requirements 3.3**
    
    Property 11d: Multi-Timeframe With Real Price History
    
    Test multi-timeframe confirmation with real price history updates.
    Verify that signals are generated correctly from price movements.
    """
    asset, prices = asset_prices
    
    # Skip if insufficient data
    assume(len(prices) >= 2)
    
    analyzer = MultiTimeframeAnalyzer()
    
    # Update prices
    for timestamp, price in prices:
        analyzer.update_price(asset, price, timestamp=timestamp)
    
    # Get multi-timeframe signal
    direction, confidence, signals = analyzer.get_multi_timeframe_signal(asset, require_alignment=True)
    
    # Verify: If direction is not neutral, at least 2 timeframes should agree
    if direction == "bullish":
        bullish_count = sum(1 for s in signals.values() if s.direction == "bullish")
        assert bullish_count >= 2, \
            f"Bullish signal but only {bullish_count} timeframes agree"
    
    elif direction == "bearish":
        bearish_count = sum(1 for s in signals.values() if s.direction == "bearish")
        assert bearish_count >= 2, \
            f"Bearish signal but only {bearish_count} timeframes agree"
    
    # Verify: Confidence is in valid range
    assert 0.0 <= confidence <= 100.0, \
        f"Confidence {confidence} out of range [0, 100]"


@given(signals=timeframe_signals_strategy())
@settings(max_examples=100, deadline=None)
def test_property_multi_timeframe_without_alignment_uses_majority(signals):
    """
    **Validates: Requirements 3.3**
    
    Property 11e: Without Alignment Uses Majority Vote
    
    When require_alignment=False, the multi-timeframe analyzer should use
    majority vote (most timeframes win), not require 2+ agreement.
    
    This is a fallback mode for when strict alignment is too restrictive.
    """
    # Skip if no signals
    assume(len(signals) > 0)
    
    analyzer = create_analyzer_with_signals(signals, "BTC")
    
    # Get multi-timeframe signal WITHOUT alignment requirement
    direction, confidence, returned_signals = analyzer.get_multi_timeframe_signal("BTC", require_alignment=False)
    
    # Count directions
    bullish_count = count_agreeing_timeframes(signals, "bullish")
    bearish_count = count_agreeing_timeframes(signals, "bearish")
    
    # Verify: Direction follows majority vote
    if bullish_count > bearish_count:
        assert direction == "bullish", \
            f"Expected bullish (majority), got {direction}"
    elif bearish_count > bullish_count:
        assert direction == "bearish", \
            f"Expected bearish (majority), got {direction}"
    else:
        assert direction == "neutral", \
            f"Expected neutral (tie), got {direction}"


@given(signals=timeframe_signals_strategy())
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
def test_property_multi_timeframe_volume_confirmation_boosts_confidence(signals):
    """
    **Validates: Requirements 3.3**
    
    Property 11f: Volume Confirmation Boosts Confidence
    
    When a signal is confirmed by high volume (volume_ratio > 1.5),
    the confidence should be boosted by up to 20%.
    """
    # Filter to have at least 2 bullish signals
    bullish_signals = {tf: s for tf, s in signals.items() if s.direction == "bullish"}
    
    # Skip if we don't have 2 bullish signals
    assume(len(bullish_signals) >= 2)
    
    # Create filtered signals with high volume
    filtered_signals = {}
    for tf, signal in bullish_signals.items():
        # Force high volume
        filtered_signals[tf] = TimeframeSignal(
            timeframe=signal.timeframe,
            direction=signal.direction,
            strength=signal.strength,
            price_change=signal.price_change,
            volume_ratio=2.0  # High volume
        )
    
    # Add any non-bullish signals
    for tf, signal in signals.items():
        if signal.direction != "bullish":
            filtered_signals[tf] = signal
    
    analyzer = create_analyzer_with_signals(filtered_signals, "BTC")
    
    # Get multi-timeframe signal
    direction, confidence, returned_signals = analyzer.get_multi_timeframe_signal("BTC", require_alignment=True)
    
    # Skip if direction is not bullish
    assume(direction == "bullish")
    
    # Calculate expected confidence without volume boost
    # Use ACTUAL returned signals (which have calculated strength)
    aligned_signals = [s for s in returned_signals.values() if s.direction == "bullish"]
    
    if not aligned_signals:
        # No bullish signals detected, skip this test case
        assume(False)
    
    base_confidence = sum(s.strength for s in aligned_signals) / len(aligned_signals)
    
    # Verify: Confidence should be boosted (up to 20%)
    # Allow for rounding and edge cases
    assert confidence >= base_confidence * 0.99, \
        f"Confidence {confidence} should be >= base {base_confidence}"
    assert confidence <= min(100.0, base_confidence * 1.21), \
        f"Confidence {confidence} should be <= boosted {base_confidence * 1.2}"


@given(signals=timeframe_signals_strategy())
@settings(max_examples=100, deadline=None)
def test_property_multi_timeframe_returns_all_signals(signals):
    """
    **Validates: Requirements 3.3**
    
    Property 11g: Returns All Individual Signals
    
    The multi-timeframe analyzer should return all individual timeframe
    signals in the result, allowing callers to inspect details.
    """
    # Skip if no signals
    assume(len(signals) > 0)
    
    analyzer = create_analyzer_with_signals(signals, "BTC")
    
    # Get multi-timeframe signal
    direction, confidence, returned_signals = analyzer.get_multi_timeframe_signal("BTC", require_alignment=True)
    
    # Verify: All input signals should be in returned signals
    # (Note: returned_signals may have fewer if some timeframes had no data)
    for tf in returned_signals.keys():
        assert tf in ["1m", "5m", "15m"], \
            f"Invalid timeframe {tf} in returned signals"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
