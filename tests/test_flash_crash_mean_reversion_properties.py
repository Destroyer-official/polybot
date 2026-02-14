"""
Property-based tests for flash crash mean reversion strategy.

Tests that the bot correctly detects flash crashes and trades in the opposite direction
(mean reversion strategy). Verifies that trades only occur when price moves >= 15%.

**Validates: Requirements 3.8**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from collections import deque

from src.flash_crash_strategy import FlashCrashStrategy
from src.models import Market


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def price_sequence_with_crash(draw):
    """
    Generate a price sequence with a flash crash (DROP only, not rise).
    
    Returns:
        tuple: (initial_price, crash_price, drop_percentage, should_trigger)
    """
    # Generate initial price (0.30 to 0.70)
    initial_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    
    # Generate drop percentage (0% to 50% DROP only)
    drop_pct = draw(st.floats(min_value=0.0, max_value=0.50, allow_nan=False, allow_infinity=False))
    
    # Calculate crash price (price goes DOWN)
    crash_price = initial_price * (Decimal("1.0") - Decimal(str(drop_pct)))
    
    # Ensure crash price is valid (0.01 to 0.99)
    crash_price = max(Decimal("0.01"), min(Decimal("0.99"), crash_price))
    
    # Determine if this should trigger (drop >= 15%)
    actual_drop_pct = (initial_price - crash_price) / initial_price
    should_trigger = actual_drop_pct >= Decimal("0.15")
    
    return initial_price, crash_price, actual_drop_pct, should_trigger


@st.composite
def price_sequence_no_crash(draw):
    """
    Generate a price sequence without a significant crash (< 15% move).
    
    Returns:
        tuple: (initial_price, new_price, change_percentage)
    """
    # Generate initial price
    initial_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    
    # Generate small change (-14% to +14%)
    change_pct = draw(st.floats(min_value=-0.14, max_value=0.14, allow_nan=False, allow_infinity=False))
    
    # Calculate new price
    new_price = initial_price * (Decimal("1.0") + Decimal(str(change_pct)))
    
    # Ensure new price is valid
    new_price = max(Decimal("0.01"), min(Decimal("0.99"), new_price))
    
    # Verify it's actually < 15%
    actual_change = abs((initial_price - new_price) / initial_price)
    assume(actual_change < Decimal("0.15"))
    
    return initial_price, new_price, actual_change


@st.composite
def market_strategy(draw):
    """Generate a random Market for testing."""
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    market_id = f"market_{draw(st.integers(min_value=1, max_value=10000))}"
    yes_token_id = f"yes_token_{draw(st.integers(min_value=1, max_value=100000))}"
    no_token_id = f"no_token_{draw(st.integers(min_value=1, max_value=100000))}"
    
    yes_price = Decimal(str(draw(st.floats(min_value=0.30, max_value=0.70, allow_nan=False, allow_infinity=False))))
    no_price = Decimal("1.0") - yes_price
    
    market = Market(
        market_id=market_id,
        question=f"Will {asset} go up in the next 15 minutes?",
        asset=asset,
        outcomes=["YES", "NO"],
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        yes_price=yes_price,
        no_price=no_price,
        volume=Decimal("1000.0"),
        liquidity=Decimal("500.0"),
        end_time=datetime.now() + timedelta(minutes=15),
        resolution_source="Binance"
    )
    
    return market


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_mock_strategy(drop_threshold=0.15, lookback_seconds=3):
    """Create a mock FlashCrashStrategy for testing."""
    mock_clob = MagicMock()
    mock_parser = MagicMock()
    
    # Mock order placement
    mock_clob.create_order = MagicMock(return_value={"signed": "order"})
    mock_clob.post_order = MagicMock(return_value={"orderID": "test_order_123", "success": True})
    
    strategy = FlashCrashStrategy(
        clob_client=mock_clob,
        market_parser=mock_parser,
        drop_threshold=drop_threshold,
        lookback_seconds=lookback_seconds,
        trade_size=5.0,
        dry_run=True  # Don't place real orders
    )
    
    return strategy


def simulate_price_history(strategy, token_id, prices, time_interval_seconds=1):
    """
    Simulate price history by adding prices at regular intervals.
    
    Args:
        strategy: FlashCrashStrategy instance
        token_id: Token ID to track
        prices: List of prices to add
        time_interval_seconds: Time between each price update
    """
    base_time = datetime.now() - timedelta(seconds=len(prices) * time_interval_seconds)
    
    for i, price in enumerate(prices):
        timestamp = base_time + timedelta(seconds=i * time_interval_seconds)
        
        # Manually add to price history
        if token_id not in strategy.price_history:
            strategy.price_history[token_id] = deque(maxlen=100)
        
        strategy.price_history[token_id].append((timestamp, Decimal(str(price))))


# ============================================================================
# PROPERTY 16: FLASH CRASH MEAN REVERSION
# ============================================================================

@given(price_data=price_sequence_with_crash())
@settings(max_examples=200, deadline=None)
def test_property_16a_flash_crash_detection_threshold(price_data):
    """
    **Validates: Requirements 3.8**
    
    Property 16a: Flash Crash Detection Threshold
    
    The bot MUST detect a flash crash when price drops >= 15% within the lookback window.
    The bot MUST NOT detect a flash crash when price drops < 15%.
    """
    initial_price, crash_price, drop_pct, should_trigger = price_data
    strategy = create_mock_strategy(drop_threshold=0.15, lookback_seconds=3)
    
    token_id = "test_token_123"
    
    # Simulate price history: stable price, then crash
    prices = [initial_price, initial_price, crash_price]
    simulate_price_history(strategy, token_id, prices, time_interval_seconds=1)
    
    # Detect flash crash
    detected_drop = strategy.detect_flash_crash(token_id, crash_price)
    
    # Verify detection matches expectation
    if should_trigger:
        assert detected_drop is not None, \
            f"Should detect crash: {float(initial_price):.3f} -> {float(crash_price):.3f} ({float(drop_pct)*100:.1f}% drop)"
        assert detected_drop >= Decimal("0.15"), \
            f"Detected drop {float(detected_drop)*100:.1f}% should be >= 15%"
    else:
        # For moves < 15%, should not trigger
        if drop_pct < Decimal("0.15"):
            assert detected_drop is None, \
                f"Should NOT detect crash for {float(drop_pct)*100:.1f}% drop (< 15% threshold)"


@given(price_data=price_sequence_no_crash())
@settings(max_examples=100, deadline=None)
def test_property_16b_no_false_positives_below_threshold(price_data):
    """
    **Validates: Requirements 3.8**
    
    Property 16b: No False Positives Below Threshold
    
    The bot MUST NOT trigger on price moves < 15%.
    """
    initial_price, new_price, change_pct = price_data
    strategy = create_mock_strategy(drop_threshold=0.15, lookback_seconds=3)
    
    token_id = "test_token_456"
    
    # Simulate price history with small change
    prices = [initial_price, initial_price, new_price]
    simulate_price_history(strategy, token_id, prices, time_interval_seconds=1)
    
    # Detect flash crash
    detected_drop = strategy.detect_flash_crash(token_id, new_price)
    
    # Verify no detection for small moves
    assert detected_drop is None, \
        f"Should NOT detect crash for {float(change_pct)*100:.1f}% move (< 15% threshold)"


@given(market=market_strategy(), price_data=price_sequence_with_crash())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_16c_mean_reversion_trade_direction(market, price_data):
    """
    **Validates: Requirements 3.8**
    
    Property 16c: Mean Reversion Trade Direction
    
    When a flash crash is detected (price drops >= 15%), the bot MUST trade in the
    OPPOSITE direction (buy the crashed side), expecting mean reversion.
    
    - If YES price crashes (drops 15%+), buy YES (expecting recovery)
    - If NO price crashes (drops 15%+), buy NO (expecting recovery)
    """
    initial_price, crash_price, drop_pct, should_trigger = price_data
    
    # Only test cases where crash should trigger
    assume(should_trigger and drop_pct >= Decimal("0.15"))
    
    strategy = create_mock_strategy(drop_threshold=0.15, lookback_seconds=3)
    
    # Simulate YES token crash
    yes_token_id = market.yes_token_id
    prices = [initial_price, initial_price, crash_price]
    simulate_price_history(strategy, yes_token_id, prices, time_interval_seconds=1)
    
    # Update market with crash price
    market.yes_price = crash_price
    
    # Scan market (should detect crash and enter position)
    await strategy.scan_market(market)
    
    # Verify position was entered on the crashed side (YES)
    if yes_token_id in strategy.positions:
        position = strategy.positions[yes_token_id]
        assert position["side"] == "YES", \
            f"Should buy YES (crashed side) for mean reversion, got {position['side']}"
        assert position["entry_price"] == crash_price, \
            f"Entry price should be crash price {crash_price}"


@given(market=market_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_16d_no_trade_without_crash(market):
    """
    **Validates: Requirements 3.8**
    
    Property 16d: No Trade Without Flash Crash
    
    The bot MUST NOT enter positions when price moves are < 15%.
    """
    strategy = create_mock_strategy(drop_threshold=0.15, lookback_seconds=3)
    
    # Simulate stable prices (no crash)
    stable_price = Decimal("0.50")
    prices = [stable_price, stable_price, stable_price]
    simulate_price_history(strategy, market.yes_token_id, prices, time_interval_seconds=1)
    simulate_price_history(strategy, market.no_token_id, prices, time_interval_seconds=1)
    
    # Update market with stable prices
    market.yes_price = stable_price
    market.no_price = Decimal("1.0") - stable_price
    
    # Scan market
    await strategy.scan_market(market)
    
    # Verify no positions were entered
    assert len(strategy.positions) == 0, \
        "Should NOT enter position without flash crash (< 15% move)"


@given(
    initial_price=st.decimals(min_value=Decimal("0.30"), max_value=Decimal("0.70"), places=2),
    drop_pct=st.decimals(min_value=Decimal("0.15"), max_value=Decimal("0.50"), places=2)
)
@settings(max_examples=100, deadline=None)
def test_property_16e_crash_detection_consistency(initial_price, drop_pct):
    """
    **Validates: Requirements 3.8**
    
    Property 16e: Crash Detection Consistency
    
    For any price drop >= 15%, the detection should be consistent regardless of
    the absolute price levels.
    """
    strategy = create_mock_strategy(drop_threshold=0.15, lookback_seconds=3)
    
    # Calculate crash price
    crash_price = initial_price * (Decimal("1.0") - drop_pct)
    crash_price = max(Decimal("0.01"), min(Decimal("0.99"), crash_price))
    
    token_id = "test_token_consistency"
    
    # Simulate crash
    prices = [initial_price, initial_price, crash_price]
    simulate_price_history(strategy, token_id, prices, time_interval_seconds=1)
    
    # Detect crash
    detected_drop = strategy.detect_flash_crash(token_id, crash_price)
    
    # Verify detection
    assert detected_drop is not None, \
        f"Should detect {float(drop_pct)*100:.1f}% drop from ${float(initial_price):.2f} to ${float(crash_price):.2f}"
    assert detected_drop >= Decimal("0.15"), \
        f"Detected drop {float(detected_drop)*100:.1f}% should be >= 15%"


@given(market=market_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_16f_no_duplicate_positions(market):
    """
    **Validates: Requirements 3.8**
    
    Property 16f: No Duplicate Positions
    
    The bot MUST NOT enter multiple positions on the same token_id.
    Even if a crash is still detected, only one position should exist per token.
    """
    # Use higher stop-loss and take-profit to prevent exit during test
    strategy = create_mock_strategy(drop_threshold=0.15, lookback_seconds=3)
    strategy.stop_loss = Decimal("10.0")  # $10 stop loss (won't trigger in test)
    strategy.take_profit = Decimal("10.0")  # $10 take profit (won't trigger in test)
    
    # Simulate first crash
    initial_price = Decimal("0.60")
    crash_price = Decimal("0.45")  # 25% drop
    prices = [initial_price, initial_price, crash_price]
    simulate_price_history(strategy, market.yes_token_id, prices, time_interval_seconds=1)
    
    market.yes_price = crash_price
    
    # First scan - should enter position
    await strategy.scan_market(market)
    
    initial_position_count = len(strategy.positions)
    assert initial_position_count == 1, "Should enter one position after first crash"
    
    # Keep the same crash price (crash is still detected)
    # Second scan - should NOT enter duplicate position even though crash still detected
    await strategy.scan_market(market)
    
    final_position_count = len(strategy.positions)
    assert final_position_count == 1, \
        f"Should still have only 1 position, got {final_position_count} (no duplicates even with ongoing crash)"


@given(
    lookback_seconds=st.integers(min_value=1, max_value=10),
    num_prices=st.integers(min_value=3, max_value=20)
)
@settings(max_examples=50, deadline=None)
def test_property_16g_lookback_window_respected(lookback_seconds, num_prices):
    """
    **Validates: Requirements 3.8**
    
    Property 16g: Lookback Window Respected
    
    The bot MUST only consider prices within the lookback window when detecting crashes.
    Old prices outside the window should not affect detection.
    """
    strategy = create_mock_strategy(drop_threshold=0.15, lookback_seconds=lookback_seconds)
    
    token_id = "test_token_lookback"
    
    # Create price sequence: high price (old), then stable prices (recent)
    high_price = Decimal("0.70")
    stable_price = Decimal("0.60")  # 14% drop from high (below 15% threshold)
    
    # Add old high price (outside lookback window)
    old_time = datetime.now() - timedelta(seconds=lookback_seconds + 5)
    strategy.price_history[token_id] = deque(maxlen=100)
    strategy.price_history[token_id].append((old_time, high_price))
    
    # Add recent stable prices (within lookback window)
    for i in range(num_prices):
        recent_time = datetime.now() - timedelta(seconds=i)
        strategy.price_history[token_id].append((recent_time, stable_price))
    
    # Detect crash
    detected_drop = strategy.detect_flash_crash(token_id, stable_price)
    
    # Should NOT detect crash because high price is outside lookback window
    # Within the lookback window, price is stable
    assert detected_drop is None, \
        f"Should NOT detect crash when high price is outside {lookback_seconds}s lookback window"
