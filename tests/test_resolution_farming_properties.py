"""
Property-based tests for Resolution Farming Engine.

Tests correctness properties for:
- Resolution farming opportunity detection (Property 13)
- Outcome verification (Property 14)
- Position size limit (Property 15)
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import uuid

from src.resolution_farming_engine import ResolutionFarmingEngine
from src.ai_safety_guard import AISafetyGuard
from src.models import Market, Opportunity


# Helper strategies
@st.composite
def market_strategy(draw, closing_in_seconds=None, price_range=None):
    """Generate a Market for testing."""
    asset = draw(st.sampled_from(["BTC", "ETH", "SOL", "XRP"]))
    
    # Generate strike price
    if asset == "BTC":
        strike = draw(st.integers(min_value=80000, max_value=100000))
    elif asset == "ETH":
        strike = draw(st.integers(min_value=3000, max_value=4000))
    elif asset == "SOL":
        strike = draw(st.integers(min_value=150, max_value=250))
    else:  # XRP
        strike = draw(st.decimals(min_value=Decimal('2.0'), max_value=Decimal('3.0'), places=2))
    
    # Generate question with direction
    direction = draw(st.sampled_from(["above", "below"]))
    question = f"Will {asset} be {direction} ${strike} in 15 minutes?"
    
    # Generate prices
    if price_range:
        yes_price = draw(st.decimals(
            min_value=price_range[0],
            max_value=price_range[1],
            places=2
        ))
    else:
        yes_price = draw(st.decimals(min_value=Decimal('0.01'), max_value=Decimal('0.99'), places=2))
    
    no_price = Decimal('1.00') - yes_price
    
    # Generate end time
    now = datetime.now()
    if closing_in_seconds is not None:
        end_time = now + timedelta(seconds=closing_in_seconds)
    else:
        end_time = now + timedelta(seconds=draw(st.integers(min_value=1, max_value=300)))
    
    return Market(
        market_id=str(uuid.uuid4()),
        question=question,
        asset=asset,
        outcomes=["YES", "NO"],
        yes_price=yes_price,
        no_price=no_price,
        yes_token_id=str(uuid.uuid4()),
        no_token_id=str(uuid.uuid4()),
        volume=draw(st.decimals(min_value=Decimal('1000'), max_value=Decimal('100000'), places=2)),
        liquidity=draw(st.decimals(min_value=Decimal('500'), max_value=Decimal('50000'), places=2)),
        end_time=end_time,
        resolution_source="CEX"
    )


# Property 13: Resolution Farming Opportunity Detection
@given(
    closing_seconds=st.integers(min_value=1, max_value=119),  # Within 2 minutes
    position_price=st.decimals(min_value=Decimal('0.97'), max_value=Decimal('0.99'), places=2)
)
@settings(max_examples=100)
def test_resolution_farming_opportunity_detection(closing_seconds, position_price):
    """
    **Validates: Requirements 5.1, 5.2**
    
    Property 13: Resolution Farming Opportunity Detection
    
    For any market closing within 2 minutes where a position is priced at 97-99¢
    and the outcome is verifiable from CEX data, the system should identify it as
    a resolution farming opportunity.
    
    This property verifies that:
    1. Markets closing within 2 minutes are considered
    2. Positions priced at 97-99¢ are identified
    3. Outcome must be verifiable from CEX data
    4. Opportunities are correctly created with expected profit calculation
    """
    # Create mock CEX feeds
    cex_feeds = {
        "BTC": Mock(get_latest_price=Mock(return_value=95000)),
        "ETH": Mock(get_latest_price=Mock(return_value=3500)),
        "SOL": Mock(get_latest_price=Mock(return_value=200)),
        "XRP": Mock(get_latest_price=Mock(return_value=2.5))
    }
    
    # Create AI safety guard
    ai_guard = AISafetyGuard(nvidia_api_key="test_key")
    
    # Create engine
    engine = ResolutionFarmingEngine(
        cex_feeds=cex_feeds,
        ai_safety_guard=ai_guard
    )
    
    # Generate market closing within window with price in range
    market = Market(
        market_id=str(uuid.uuid4()),
        question="Will BTC be above $94000 in 15 minutes?",
        asset="BTC",
        outcomes=["YES", "NO"],
        yes_price=position_price,
        no_price=Decimal('1.00') - position_price,
        yes_token_id=str(uuid.uuid4()),
        no_token_id=str(uuid.uuid4()),
        volume=Decimal('10000'),
        liquidity=Decimal('5000'),
        end_time=datetime.now() + timedelta(seconds=closing_seconds),
        resolution_source="CEX"
    )
    
    # Scan for opportunities
    import asyncio
    opportunities = asyncio.run(engine.scan_closing_markets([market]))
    
    # Verify opportunity was detected
    assert len(opportunities) == 1, (
        f"Expected 1 opportunity for market closing in {closing_seconds}s "
        f"with price ${position_price}, got {len(opportunities)}"
    )
    
    opp = opportunities[0]
    
    # Verify opportunity properties
    assert opp.market_id == market.market_id
    assert opp.strategy == "resolution_farming"
    assert opp.total_cost == position_price
    
    # Verify profit calculation
    expected_profit = Decimal('1.00') - position_price
    assert opp.expected_profit == expected_profit, (
        f"Expected profit ${expected_profit}, got ${opp.expected_profit}"
    )
    
    # Verify profit percentage
    expected_percentage = expected_profit / position_price
    assert abs(opp.profit_percentage - expected_percentage) < Decimal('0.0001'), (
        f"Expected profit percentage {expected_percentage}, got {opp.profit_percentage}"
    )


# Property 14: Resolution Farming Outcome Verification
@given(
    asset=st.sampled_from(["BTC", "ETH", "SOL", "XRP"]),
    direction=st.sampled_from(["above", "below"]),
    price_above_strike=st.booleans()
)
@settings(max_examples=100)
def test_resolution_farming_outcome_verification(asset, direction, price_above_strike):
    """
    **Validates: Requirements 5.3**
    
    Property 14: Resolution Farming Outcome Verification
    
    For any resolution farming trade, the purchased outcome should match the
    current CEX price direction, ensuring the position is on the correct side.
    
    This property verifies that:
    1. When CEX price is above strike and market asks "above", YES is certain
    2. When CEX price is below strike and market asks "above", NO is certain
    3. When CEX price is below strike and market asks "below", YES is certain
    4. When CEX price is above strike and market asks "below", NO is certain
    """
    # Define strike prices and CEX prices
    strike_prices = {
        "BTC": Decimal('95000'),
        "ETH": Decimal('3500'),
        "SOL": Decimal('200'),
        "XRP": Decimal('2.5')
    }
    
    strike = strike_prices[asset]
    
    # Set CEX price based on test parameter
    if price_above_strike:
        cex_price = strike + Decimal('100')
    else:
        cex_price = strike - Decimal('100')
    
    # Create mock CEX feeds
    cex_feeds = {
        asset: Mock(get_latest_price=Mock(return_value=float(cex_price)))
    }
    
    # Create AI safety guard
    ai_guard = AISafetyGuard(nvidia_api_key="test_key")
    
    # Create engine
    engine = ResolutionFarmingEngine(
        cex_feeds=cex_feeds,
        ai_safety_guard=ai_guard
    )
    
    # Create market
    question = f"Will {asset} be {direction} ${strike} in 15 minutes?"
    market = Market(
        market_id=str(uuid.uuid4()),
        question=question,
        asset=asset,
        outcomes=["YES", "NO"],
        yes_price=Decimal('0.98'),
        no_price=Decimal('0.02'),
        yes_token_id=str(uuid.uuid4()),
        no_token_id=str(uuid.uuid4()),
        volume=Decimal('10000'),
        liquidity=Decimal('5000'),
        end_time=datetime.now() + timedelta(seconds=60),
        resolution_source="CEX"
    )
    
    # Verify outcome certainty
    certain_outcome = engine.verify_outcome_certainty(market)
    
    # Determine expected outcome
    if direction == "above":
        # Market asks if price will be above strike
        if price_above_strike:
            expected_outcome = "YES"  # Price is above, YES wins
        else:
            expected_outcome = "NO"  # Price is below, NO wins
    else:  # direction == "below"
        # Market asks if price will be below strike
        if price_above_strike:
            expected_outcome = "NO"  # Price is above, NO wins
        else:
            expected_outcome = "YES"  # Price is below, YES wins
    
    assert certain_outcome == expected_outcome, (
        f"For {asset} with CEX price ${cex_price} and strike ${strike}, "
        f"direction '{direction}', expected outcome {expected_outcome}, "
        f"got {certain_outcome}"
    )


# Property 15: Resolution Farming Position Size Limit
@given(
    bankroll=st.decimals(min_value=Decimal('100'), max_value=Decimal('10000'), places=2)
)
@settings(max_examples=100)
def test_resolution_farming_position_size_limit(bankroll):
    """
    **Validates: Requirements 5.5**
    
    Property 15: Resolution Farming Position Size Limit
    
    For any resolution farming opportunity, the position size should not exceed
    2% of the total bankroll, limiting risk exposure.
    
    This property verifies that:
    1. Position size is calculated as 2% of bankroll
    2. Position size never exceeds 2% regardless of bankroll amount
    3. Calculation is consistent across different bankroll sizes
    """
    # Create mock CEX feeds
    cex_feeds = {
        "BTC": Mock(get_latest_price=Mock(return_value=95000))
    }
    
    # Create AI safety guard
    ai_guard = AISafetyGuard(nvidia_api_key="test_key")
    
    # Create engine with default 2% max position
    engine = ResolutionFarmingEngine(
        cex_feeds=cex_feeds,
        ai_safety_guard=ai_guard,
        max_position_percentage=Decimal('0.02')
    )
    
    # Calculate position size
    position_size = engine.calculate_position_size(bankroll)
    
    # Verify position size is exactly 2% of bankroll
    expected_size = bankroll * Decimal('0.02')
    assert position_size == expected_size, (
        f"For bankroll ${bankroll}, expected position size ${expected_size}, "
        f"got ${position_size}"
    )
    
    # Verify position size does not exceed 2%
    max_allowed = bankroll * Decimal('0.02')
    assert position_size <= max_allowed, (
        f"Position size ${position_size} exceeds 2% of bankroll ${bankroll} "
        f"(max: ${max_allowed})"
    )
    
    # Verify position size is positive
    assert position_size > 0, f"Position size must be positive, got ${position_size}"


# Additional test: Markets outside closing window should be skipped
@given(
    closing_seconds=st.integers(min_value=121, max_value=900)  # Outside 2-minute window
)
@settings(max_examples=50)
def test_markets_outside_closing_window_skipped(closing_seconds):
    """
    Verify that markets closing outside the 2-minute window are not identified
    as resolution farming opportunities.
    """
    # Create mock CEX feeds
    cex_feeds = {
        "BTC": Mock(get_latest_price=Mock(return_value=95000))
    }
    
    # Create AI safety guard
    ai_guard = AISafetyGuard(nvidia_api_key="test_key")
    
    # Create engine
    engine = ResolutionFarmingEngine(
        cex_feeds=cex_feeds,
        ai_safety_guard=ai_guard
    )
    
    # Generate market closing outside window
    market = Market(
        market_id=str(uuid.uuid4()),
        question="Will BTC be above $94000 in 15 minutes?",
        asset="BTC",
        outcomes=["YES", "NO"],
        yes_price=Decimal('0.98'),
        no_price=Decimal('0.02'),
        yes_token_id=str(uuid.uuid4()),
        no_token_id=str(uuid.uuid4()),
        volume=Decimal('10000'),
        liquidity=Decimal('5000'),
        end_time=datetime.now() + timedelta(seconds=closing_seconds),
        resolution_source="CEX"
    )
    
    # Scan for opportunities
    import asyncio
    opportunities = asyncio.run(engine.scan_closing_markets([market]))
    
    # Verify no opportunities detected
    assert len(opportunities) == 0, (
        f"Expected 0 opportunities for market closing in {closing_seconds}s "
        f"(outside 2-minute window), got {len(opportunities)}"
    )


# Additional test: Ambiguous markets should be skipped
@given(
    ambiguous_keyword=st.sampled_from([
        "approximately", "around", "roughly", "about", "near",
        "close to", "almost", "nearly", "circa"
    ])
)
@settings(max_examples=50)
def test_ambiguous_markets_skipped(ambiguous_keyword):
    """
    Verify that markets with ambiguous resolution criteria are skipped.
    
    Validates Requirement 5.4: Skip markets with ambiguous resolution criteria
    """
    # Create mock CEX feeds
    cex_feeds = {
        "BTC": Mock(get_latest_price=Mock(return_value=95000))
    }
    
    # Create AI safety guard
    ai_guard = AISafetyGuard(nvidia_api_key="test_key")
    
    # Create engine
    engine = ResolutionFarmingEngine(
        cex_feeds=cex_feeds,
        ai_safety_guard=ai_guard
    )
    
    # Generate market with ambiguous keyword
    question = f"Will BTC be {ambiguous_keyword} $95000 in 15 minutes?"
    market = Market(
        market_id=str(uuid.uuid4()),
        question=question,
        asset="BTC",
        outcomes=["YES", "NO"],
        yes_price=Decimal('0.98'),
        no_price=Decimal('0.02'),
        yes_token_id=str(uuid.uuid4()),
        no_token_id=str(uuid.uuid4()),
        volume=Decimal('10000'),
        liquidity=Decimal('5000'),
        end_time=datetime.now() + timedelta(seconds=60),
        resolution_source="CEX"
    )
    
    # Scan for opportunities
    import asyncio
    opportunities = asyncio.run(engine.scan_closing_markets([market]))
    
    # Verify no opportunities detected
    assert len(opportunities) == 0, (
        f"Expected 0 opportunities for ambiguous market with keyword '{ambiguous_keyword}', "
        f"got {len(opportunities)}"
    )
