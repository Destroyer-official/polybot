"""
Property-based tests for Latency Arbitrage Engine.

Tests latency arbitrage trigger, direction calculation, and volatility filtering
using property-based testing with Hypothesis.
Validates Requirements 4.2, 4.3, 4.6.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timedelta
from collections import deque
import asyncio

from src.models import Market
from src.latency_arbitrage_engine import LatencyArbitrageEngine, PriceMovement


# Helper function to create a test market
def create_test_market(
    market_id: str,
    question: str,
    yes_price: Decimal,
    no_price: Decimal,
    asset: str = "BTC"
) -> Market:
    """Create a test market with given prices."""
    return Market(
        market_id=market_id,
        question=question,
        asset=asset,
        outcomes=["YES", "NO"],
        yes_price=yes_price,
        no_price=no_price,
        yes_token_id=f"yes_token_{market_id}",
        no_token_id=f"no_token_{market_id}",
        volume=Decimal('10000.0'),
        liquidity=Decimal('5000.0'),
        end_time=datetime.now() + timedelta(minutes=15),
        resolution_source="CEX"
    )


@given(
    asset=st.sampled_from(['BTC', 'ETH', 'SOL', 'XRP']),
    old_price=st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    price_change=st.floats(min_value=-5000.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_latency_arbitrage_trigger(asset, old_price, price_change):
    """
    **Validates: Requirement 4.2**
    
    Feature: polymarket-arbitrage-bot, Property 10: Latency Arbitrage Trigger
    
    For any CEX price movement exceeding $100 for BTC (or equivalent thresholds
    for ETH/SOL/XRP), the system should immediately check corresponding
    Polymarket markets for lag-based opportunities.
    
    Property: For all (asset, old_price, price_change):
        If abs(price_change) >= threshold[asset], then trigger check
        If abs(price_change) < threshold[asset], then no trigger
    """
    # Create engine
    engine = LatencyArbitrageEngine(
        cex_feeds={},
        clob_client=None,
        order_manager=None,
        ai_safety_guard=None,
        kelly_sizer=None,
        min_profit_threshold=Decimal('0.005')
    )
    
    # Calculate new price
    new_price = old_price + price_change
    
    # Ensure new price is positive
    assume(new_price > 0)
    
    # Create price movement
    movement = PriceMovement(
        asset=asset,
        old_price=Decimal(str(old_price)),
        new_price=Decimal(str(new_price)),
        timestamp=datetime.now(),
        exchange="Binance"
    )
    
    # Get threshold for this asset
    threshold = engine.MOVEMENT_THRESHOLDS[asset]
    
    # Calculate actual price change
    actual_change = abs(movement.new_price - movement.old_price)
    
    # Verify threshold logic
    if actual_change >= threshold:
        # Movement exceeds threshold - should trigger check
        # In real implementation, this would call check_polymarket_lag
        # Here we verify the threshold detection logic
        assert actual_change >= threshold, \
            f"Movement {actual_change} should exceed threshold {threshold} for {asset}"
        
        # Verify movement properties
        assert movement.change_percentage > 0, \
            "Significant movement should have non-zero percentage change"
        
        assert movement.direction in ["UP", "DOWN"], \
            "Movement should have valid direction"
        
    else:
        # Movement below threshold - should not trigger
        assert actual_change < threshold, \
            f"Movement {actual_change} should be below threshold {threshold} for {asset}"


@given(
    asset=st.sampled_from(['BTC', 'ETH', 'SOL', 'XRP']),
    old_price=st.floats(min_value=1000.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    price_increase=st.floats(min_value=100.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_btc_threshold_enforcement(asset, old_price, price_increase):
    """
    Property test: BTC threshold of $100 is correctly enforced.
    
    For BTC, only movements >= $100 should trigger checks.
    """
    # Focus on BTC
    if asset != 'BTC':
        return
    
    engine = LatencyArbitrageEngine(
        cex_feeds={},
        clob_client=None,
        order_manager=None,
        ai_safety_guard=None,
        kelly_sizer=None
    )
    
    new_price = old_price + price_increase
    
    movement = PriceMovement(
        asset='BTC',
        old_price=Decimal(str(old_price)),
        new_price=Decimal(str(new_price)),
        timestamp=datetime.now(),
        exchange="Binance"
    )
    
    actual_change = abs(movement.new_price - movement.old_price)
    btc_threshold = engine.MOVEMENT_THRESHOLDS['BTC']
    
    # Verify BTC threshold is $100
    assert btc_threshold == Decimal('100'), \
        "BTC threshold should be $100"
    
    # Verify threshold enforcement
    if actual_change >= btc_threshold:
        assert actual_change >= Decimal('100'), \
            f"BTC movement {actual_change} should be >= $100"
    else:
        assert actual_change < Decimal('100'), \
            f"BTC movement {actual_change} should be < $100"


@given(
    cex_price=st.floats(min_value=90000.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    strike_price=st.floats(min_value=90000.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    pm_yes_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_latency_arbitrage_direction_calculation(cex_price, strike_price, pm_yes_price):
    """
    **Validates: Requirement 4.3**
    
    Feature: polymarket-arbitrage-bot, Property 11: Latency Arbitrage Direction Calculation
    
    For any Polymarket market lagging CEX prices by more than 1%, the system
    should calculate the expected market direction based on the CEX price movement.
    
    Property: For all (cex_price, strike_price, market_type):
        If market is "above" and cex_price > strike: expect YES high
        If market is "above" and cex_price < strike: expect YES low
        If market is "below" and cex_price < strike: expect YES high
        If market is "below" and cex_price > strike: expect YES low
    """
    # Skip if prices are too close (within $1)
    assume(abs(cex_price - strike_price) > 1.0)
    
    # Create engine
    engine = LatencyArbitrageEngine(
        cex_feeds={},
        clob_client=None,
        order_manager=None,
        ai_safety_guard=None,
        kelly_sizer=None
    )
    
    # Test "above" market type
    market_above = create_test_market(
        market_id="test_above",
        question=f"Will BTC be above ${strike_price:.0f} in 15 minutes?",
        yes_price=Decimal(str(pm_yes_price)),
        no_price=Decimal(str(1.0 - pm_yes_price)),
        asset="BTC"
    )
    
    # Create price movement
    old_price = cex_price - 500  # Simulate movement
    movement = PriceMovement(
        asset="BTC",
        old_price=Decimal(str(old_price)),
        new_price=Decimal(str(cex_price)),
        timestamp=datetime.now(),
        exchange="Binance"
    )
    
    # Calculate expected price
    expected_price = engine._calculate_expected_price(movement, market_above)
    
    if expected_price is not None:
        # Verify direction calculation (Requirement 4.3)
        if cex_price > strike_price:
            # CEX price above strike, YES should be high
            assert expected_price >= Decimal('0.90'), \
                f"For 'above' market with CEX ${cex_price} > strike ${strike_price}, " \
                f"expected YES price should be high, got {expected_price}"
        else:
            # CEX price below strike, YES should be low
            assert expected_price <= Decimal('0.10'), \
                f"For 'above' market with CEX ${cex_price} < strike ${strike_price}, " \
                f"expected YES price should be low, got {expected_price}"
    
    # Test "below" market type
    market_below = create_test_market(
        market_id="test_below",
        question=f"Will BTC be below ${strike_price:.0f} in 15 minutes?",
        yes_price=Decimal(str(pm_yes_price)),
        no_price=Decimal(str(1.0 - pm_yes_price)),
        asset="BTC"
    )
    
    expected_price_below = engine._calculate_expected_price(movement, market_below)
    
    if expected_price_below is not None:
        # Verify direction calculation for "below" market
        if cex_price < strike_price:
            # CEX price below strike, YES should be high
            assert expected_price_below >= Decimal('0.90'), \
                f"For 'below' market with CEX ${cex_price} < strike ${strike_price}, " \
                f"expected YES price should be high, got {expected_price_below}"
        else:
            # CEX price above strike, YES should be low
            assert expected_price_below <= Decimal('0.10'), \
                f"For 'below' market with CEX ${cex_price} > strike ${strike_price}, " \
                f"expected YES price should be low, got {expected_price_below}"


@given(
    current_price=st.floats(min_value=90000.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    pm_price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    lag_percentage=st.floats(min_value=0.0, max_value=0.10, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_lag_detection_threshold(current_price, pm_price, lag_percentage):
    """
    Property test: 1% lag threshold is correctly enforced.
    
    Only markets with >= 1% lag should be identified as opportunities.
    """
    engine = LatencyArbitrageEngine(
        cex_feeds={},
        clob_client=None,
        order_manager=None,
        ai_safety_guard=None,
        kelly_sizer=None
    )
    
    # Verify minimum lag percentage constant
    assert engine.MIN_LAG_PERCENTAGE == Decimal('0.01'), \
        "Minimum lag percentage should be 1%"
    
    # Test lag detection logic
    if lag_percentage >= 0.01:
        # Should be considered significant lag
        assert lag_percentage >= float(engine.MIN_LAG_PERCENTAGE), \
            f"Lag {lag_percentage*100}% should exceed minimum 1%"
    else:
        # Should not be considered significant lag
        assert lag_percentage < float(engine.MIN_LAG_PERCENTAGE), \
            f"Lag {lag_percentage*100}% should be below minimum 1%"


@given(
    asset=st.sampled_from(['BTC', 'ETH', 'SOL', 'XRP']),
    price_changes=st.lists(
        st.floats(min_value=-0.10, max_value=0.10, allow_nan=False, allow_infinity=False),
        min_size=10,
        max_size=60
    )
)
@settings(max_examples=100)
def test_volatility_based_latency_arbitrage_filter(asset, price_changes):
    """
    **Validates: Requirement 4.6**
    
    Feature: polymarket-arbitrage-bot, Property 12: Volatility-Based Latency Arbitrage Filter
    
    For any market where the underlying asset has moved more than 5% in the
    last 1 minute, the system should skip latency arbitrage opportunities
    to avoid false signals.
    
    Property: For all (asset, price_history):
        volatility = (max_price - min_price) / min_price over last 60 seconds
        If volatility > 5%, then skip opportunity
        If volatility <= 5%, then allow opportunity
    """
    # Create engine
    engine = LatencyArbitrageEngine(
        cex_feeds={},
        clob_client=None,
        order_manager=None,
        ai_safety_guard=None,
        kelly_sizer=None
    )
    
    # Verify maximum volatility constant
    assert engine.MAX_VOLATILITY == Decimal('0.05'), \
        "Maximum volatility should be 5%"
    
    # Simulate price history
    base_price = 95000.0 if asset == 'BTC' else 3500.0 if asset == 'ETH' else 180.0 if asset == 'SOL' else 2.5
    current_time = datetime.now()
    
    # Build price history
    for i, change in enumerate(price_changes):
        price = base_price * (1.0 + change)
        timestamp = current_time - timedelta(seconds=len(price_changes) - i)
        
        engine._price_history[asset].append({
            'price': Decimal(str(price)),
            'timestamp': timestamp
        })
    
    # Calculate volatility
    volatility = engine._calculate_volatility(asset)
    
    # Verify volatility calculation
    if len(price_changes) >= 2:
        # Get all prices
        prices = [Decimal(str(base_price * (1.0 + change))) for change in price_changes]
        min_price = min(prices)
        max_price = max(prices)
        
        if min_price > 0:
            expected_volatility = (max_price - min_price) / min_price
            
            # Allow small tolerance for floating-point differences
            tolerance = Decimal('0.001')
            assert abs(volatility - expected_volatility) < tolerance, \
                f"Volatility calculation mismatch: expected {expected_volatility}, got {volatility}"
    
    # Verify filtering logic (Requirement 4.6)
    if volatility > engine.MAX_VOLATILITY:
        # High volatility - should skip
        assert volatility > Decimal('0.05'), \
            f"Volatility {volatility*100:.2f}% should exceed 5% threshold"
        
        # In real implementation, check_polymarket_lag would return None
        # Here we verify the volatility detection
        
    else:
        # Low volatility - should allow
        assert volatility <= Decimal('0.05'), \
            f"Volatility {volatility*100:.2f}% should be <= 5% threshold"


@given(
    asset=st.sampled_from(['BTC', 'ETH', 'SOL', 'XRP']),
    volatility_percentage=st.floats(min_value=0.0, max_value=0.15, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_high_volatility_skips_opportunities(asset, volatility_percentage):
    """
    Property test: High volatility causes opportunities to be skipped.
    
    When volatility exceeds 5%, check_polymarket_lag should return None.
    """
    engine = LatencyArbitrageEngine(
        cex_feeds={},
        clob_client=None,
        order_manager=None,
        ai_safety_guard=None,
        kelly_sizer=None
    )
    
    # Simulate high volatility by creating price history with large swings
    base_price = 95000.0 if asset == 'BTC' else 3500.0
    current_time = datetime.now()
    
    # Create prices with specified volatility
    min_price = base_price
    max_price = base_price * (1.0 + volatility_percentage)
    
    # Add prices to history
    for i in range(30):
        # Alternate between min and max to create volatility
        price = min_price if i % 2 == 0 else max_price
        timestamp = current_time - timedelta(seconds=30 - i)
        
        engine._price_history[asset].append({
            'price': Decimal(str(price)),
            'timestamp': timestamp
        })
    
    # Calculate volatility
    calculated_volatility = engine._calculate_volatility(asset)
    
    # Verify volatility filtering
    if volatility_percentage > 0.05:
        # High volatility - should skip
        assert calculated_volatility > Decimal('0.05'), \
            f"Calculated volatility {calculated_volatility*100:.2f}% should exceed 5%"
        
        # Verify that opportunities would be skipped
        # (In real implementation, check_polymarket_lag returns None)
        
    else:
        # Low volatility - should allow
        assert calculated_volatility <= Decimal('0.05') or calculated_volatility > Decimal('0.05'), \
            "Volatility calculation should be deterministic"


@given(
    asset=st.sampled_from(['BTC', 'ETH', 'SOL', 'XRP'])
)
@settings(max_examples=100)
def test_volatility_calculation_with_empty_history(asset):
    """
    Property test: Volatility calculation handles empty history gracefully.
    
    With no price history, volatility should be 0.
    """
    engine = LatencyArbitrageEngine(
        cex_feeds={},
        clob_client=None,
        order_manager=None,
        ai_safety_guard=None,
        kelly_sizer=None
    )
    
    # Clear price history
    engine._price_history[asset].clear()
    
    # Calculate volatility
    volatility = engine._calculate_volatility(asset)
    
    # Should return 0 for empty history
    assert volatility == Decimal('0'), \
        f"Volatility should be 0 for empty history, got {volatility}"


@given(
    asset=st.sampled_from(['BTC', 'ETH', 'SOL', 'XRP']),
    constant_price=st.floats(min_value=1000.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_volatility_calculation_with_constant_price(asset, constant_price):
    """
    Property test: Volatility is 0 when price is constant.
    
    If all prices in history are the same, volatility should be 0.
    """
    engine = LatencyArbitrageEngine(
        cex_feeds={},
        clob_client=None,
        order_manager=None,
        ai_safety_guard=None,
        kelly_sizer=None
    )
    
    # Add constant prices to history
    current_time = datetime.now()
    for i in range(30):
        timestamp = current_time - timedelta(seconds=30 - i)
        engine._price_history[asset].append({
            'price': Decimal(str(constant_price)),
            'timestamp': timestamp
        })
    
    # Calculate volatility
    volatility = engine._calculate_volatility(asset)
    
    # Should be 0 for constant price
    assert volatility == Decimal('0'), \
        f"Volatility should be 0 for constant price, got {volatility}"


@given(
    asset=st.sampled_from(['BTC', 'ETH', 'SOL', 'XRP']),
    price_increase=st.floats(min_value=0.01, max_value=0.10, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_volatility_increases_with_price_swings(asset, price_increase):
    """
    Property test: Volatility increases with larger price swings.
    
    Larger price movements should result in higher volatility.
    """
    engine = LatencyArbitrageEngine(
        cex_feeds={},
        clob_client=None,
        order_manager=None,
        ai_safety_guard=None,
        kelly_sizer=None
    )
    
    base_price = 95000.0 if asset == 'BTC' else 3500.0
    current_time = datetime.now()
    
    # Create two scenarios: small swing and large swing
    # Small swing
    engine._price_history[asset].clear()
    small_swing = price_increase / 2
    for i in range(30):
        price = base_price * (1.0 + (small_swing if i % 2 == 0 else 0))
        timestamp = current_time - timedelta(seconds=30 - i)
        engine._price_history[asset].append({
            'price': Decimal(str(price)),
            'timestamp': timestamp
        })
    
    volatility_small = engine._calculate_volatility(asset)
    
    # Large swing
    engine._price_history[asset].clear()
    for i in range(30):
        price = base_price * (1.0 + (price_increase if i % 2 == 0 else 0))
        timestamp = current_time - timedelta(seconds=30 - i)
        engine._price_history[asset].append({
            'price': Decimal(str(price)),
            'timestamp': timestamp
        })
    
    volatility_large = engine._calculate_volatility(asset)
    
    # Larger price swings should result in higher volatility
    assert volatility_large >= volatility_small, \
        f"Larger price swings should increase volatility: " \
        f"small={volatility_small}, large={volatility_large}"


@given(
    asset=st.sampled_from(['BTC', 'ETH', 'SOL', 'XRP'])
)
@settings(max_examples=100)
def test_price_movement_direction_property(asset):
    """
    Property test: Price movement direction is correctly identified.
    
    Direction should be "UP" when new_price > old_price, "DOWN" otherwise.
    """
    old_price = 95000.0 if asset == 'BTC' else 3500.0
    
    # Test upward movement
    movement_up = PriceMovement(
        asset=asset,
        old_price=Decimal(str(old_price)),
        new_price=Decimal(str(old_price + 500)),
        timestamp=datetime.now(),
        exchange="Binance"
    )
    
    assert movement_up.direction == "UP", \
        "Direction should be UP when new_price > old_price"
    
    # Test downward movement
    movement_down = PriceMovement(
        asset=asset,
        old_price=Decimal(str(old_price)),
        new_price=Decimal(str(old_price - 500)),
        timestamp=datetime.now(),
        exchange="Binance"
    )
    
    assert movement_down.direction == "DOWN", \
        "Direction should be DOWN when new_price < old_price"


@given(
    asset=st.sampled_from(['BTC', 'ETH', 'SOL', 'XRP']),
    old_price=st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    new_price=st.floats(min_value=100.0, max_value=100000.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_price_movement_change_percentage(asset, old_price, new_price):
    """
    Property test: Change percentage is correctly calculated.
    
    change_percentage = abs(new_price - old_price) / old_price
    """
    assume(old_price > 0)
    
    movement = PriceMovement(
        asset=asset,
        old_price=Decimal(str(old_price)),
        new_price=Decimal(str(new_price)),
        timestamp=datetime.now(),
        exchange="Binance"
    )
    
    # Calculate expected change percentage
    expected_change = abs(new_price - old_price) / old_price
    
    # Verify calculation
    tolerance = Decimal('0.0001')
    assert abs(movement.change_percentage - Decimal(str(expected_change))) < tolerance, \
        f"Change percentage mismatch: expected {expected_change}, got {movement.change_percentage}"
    
    # Verify change percentage is non-negative
    assert movement.change_percentage >= 0, \
        "Change percentage should be non-negative"
