"""
Property-based tests for data models.

Tests Decimal price precision and data model validation using Hypothesis.
Validates Requirements 17.5, 17.4, 17.6.
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal, getcontext
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import Market, Opportunity, TradeResult, SafetyDecision, HealthStatus


# Strategy for generating Decimal prices with proper precision
def decimal_price_strategy():
    """Generate Decimal prices between 0.0 and 1.0 with up to 18 decimal places."""
    return st.decimals(
        min_value=Decimal('0.0'),
        max_value=Decimal('1.0'),
        allow_nan=False,
        allow_infinity=False,
        places=18  # Maximum precision for financial calculations
    )


@given(
    yes_price=decimal_price_strategy(),
    no_price=decimal_price_strategy()
)
@settings(max_examples=100)
def test_decimal_price_precision(yes_price, no_price):
    """
    **Validates: Requirements 17.5**
    
    Feature: polymarket-arbitrage-bot, Property 50: Decimal Price Precision
    
    For any price data parsed from market responses, the system should represent
    it as a Decimal type to avoid floating-point precision errors.
    """
    # Create a Market with Decimal prices
    market = Market(
        market_id="test_market",
        question="BTC above $95,000 in 15 minutes?",
        asset="BTC",
        outcomes=["YES", "NO"],
        yes_price=yes_price,
        no_price=no_price,
        yes_token_id="token_yes",
        no_token_id="token_no",
        volume=Decimal('1000.0'),
        liquidity=Decimal('500.0'),
        end_time=datetime.now() + timedelta(minutes=15),
        resolution_source="CEX"
    )
    
    # Verify prices are stored as Decimal type
    assert isinstance(market.yes_price, Decimal), \
        f"YES price should be Decimal, got {type(market.yes_price)}"
    assert isinstance(market.no_price, Decimal), \
        f"NO price should be Decimal, got {type(market.no_price)}"
    
    # Verify exact precision is maintained (no floating-point errors)
    assert market.yes_price == yes_price, \
        f"YES price precision lost: {market.yes_price} != {yes_price}"
    assert market.no_price == no_price, \
        f"NO price precision lost: {market.no_price} != {no_price}"
    
    # Test arithmetic operations maintain precision
    total = market.yes_price + market.no_price
    assert isinstance(total, Decimal), \
        f"Arithmetic result should be Decimal, got {type(total)}"
    
    # Verify no precision loss in calculations
    expected_total = yes_price + no_price
    assert total == expected_total, \
        f"Arithmetic precision lost: {total} != {expected_total}"
    
    # Test that Decimal arithmetic is exact (unlike float)
    # This would fail with floats due to precision errors
    if yes_price > 0 and no_price > 0:
        ratio = market.yes_price / market.no_price
        reconstructed = ratio * market.no_price
        # Allow tiny difference due to division, but should be very close
        difference = abs(reconstructed - market.yes_price)
        # Decimal maintains much better precision than float
        assert difference < Decimal('1e-15'), \
            f"Division precision error too large: {difference}"


@given(
    yes_price=decimal_price_strategy(),
    no_price=decimal_price_strategy(),
    yes_fee=decimal_price_strategy(),
    no_fee=decimal_price_strategy()
)
@settings(max_examples=100)
def test_opportunity_decimal_precision(yes_price, no_price, yes_fee, no_fee):
    """
    Test that Opportunity dataclass maintains Decimal precision for all financial fields.
    
    Validates: Requirements 17.5
    """
    # Calculate total cost and profit using Decimal arithmetic
    yes_cost = yes_price + (yes_price * yes_fee)
    no_cost = no_price + (no_price * no_fee)
    total_cost = yes_cost + no_cost
    expected_profit = Decimal('1.0') - total_cost
    profit_percentage = expected_profit / total_cost if total_cost > 0 else Decimal('0')
    
    opportunity = Opportunity(
        opportunity_id="opp_123",
        market_id="market_456",
        strategy="internal",
        timestamp=datetime.now(),
        yes_price=yes_price,
        no_price=no_price,
        yes_fee=yes_fee,
        no_fee=no_fee,
        total_cost=total_cost,
        expected_profit=expected_profit,
        profit_percentage=profit_percentage,
        position_size=Decimal('1.0'),
        gas_estimate=100000
    )
    
    # Verify all financial fields are Decimal
    assert isinstance(opportunity.yes_price, Decimal)
    assert isinstance(opportunity.no_price, Decimal)
    assert isinstance(opportunity.yes_fee, Decimal)
    assert isinstance(opportunity.no_fee, Decimal)
    assert isinstance(opportunity.total_cost, Decimal)
    assert isinstance(opportunity.expected_profit, Decimal)
    assert isinstance(opportunity.profit_percentage, Decimal)
    assert isinstance(opportunity.position_size, Decimal)
    
    # Verify precision is maintained
    assert opportunity.yes_price == yes_price
    assert opportunity.no_price == no_price
    assert opportunity.total_cost == total_cost
    assert opportunity.expected_profit == expected_profit


@given(
    actual_cost=decimal_price_strategy(),
    actual_profit=decimal_price_strategy(),
    gas_cost=st.decimals(min_value=Decimal('0.0'), max_value=Decimal('0.1'), places=18)
)
@settings(max_examples=100)
def test_trade_result_decimal_precision(actual_cost, actual_profit, gas_cost):
    """
    Test that TradeResult maintains Decimal precision for financial results.
    
    Validates: Requirements 17.5
    """
    net_profit = actual_profit - gas_cost
    
    # Create minimal Opportunity for TradeResult
    opportunity = Opportunity(
        opportunity_id="opp_123",
        market_id="market_456",
        strategy="internal",
        timestamp=datetime.now(),
        yes_price=Decimal('0.5'),
        no_price=Decimal('0.5'),
        yes_fee=Decimal('0.03'),
        no_fee=Decimal('0.03'),
        total_cost=Decimal('1.0'),
        expected_profit=Decimal('0.0'),
        profit_percentage=Decimal('0.0'),
        position_size=Decimal('1.0'),
        gas_estimate=100000
    )
    
    trade_result = TradeResult(
        trade_id="trade_789",
        opportunity=opportunity,
        timestamp=datetime.now(),
        status="success",
        yes_order_id="order_yes",
        no_order_id="order_no",
        yes_filled=True,
        no_filled=True,
        yes_fill_price=Decimal('0.48'),
        no_fill_price=Decimal('0.47'),
        actual_cost=actual_cost,
        actual_profit=actual_profit,
        gas_cost=gas_cost,
        net_profit=net_profit
    )
    
    # Verify all financial fields are Decimal
    assert isinstance(trade_result.actual_cost, Decimal)
    assert isinstance(trade_result.actual_profit, Decimal)
    assert isinstance(trade_result.gas_cost, Decimal)
    assert isinstance(trade_result.net_profit, Decimal)
    
    # Verify precision is maintained
    assert trade_result.actual_cost == actual_cost
    assert trade_result.actual_profit == actual_profit
    assert trade_result.gas_cost == gas_cost
    assert trade_result.net_profit == net_profit
    
    # Verify calculation is exact
    calculated_net = trade_result.actual_profit - trade_result.gas_cost
    assert calculated_net == trade_result.net_profit


@given(
    eoa_balance=st.decimals(min_value=Decimal('0.0'), max_value=Decimal('10000.0'), places=6),
    proxy_balance=st.decimals(min_value=Decimal('0.0'), max_value=Decimal('1000.0'), places=6),
    total_profit=st.decimals(min_value=Decimal('-100.0'), max_value=Decimal('1000.0'), places=6),
    total_gas_cost=st.decimals(min_value=Decimal('0.0'), max_value=Decimal('100.0'), places=6)
)
@settings(max_examples=100)
def test_health_status_decimal_precision(eoa_balance, proxy_balance, total_profit, total_gas_cost):
    """
    Test that HealthStatus maintains Decimal precision for balance and performance metrics.
    
    Validates: Requirements 17.5
    """
    total_balance = eoa_balance + proxy_balance
    net_profit = total_profit - total_gas_cost
    total_trades = 100
    avg_profit = total_profit / Decimal(str(total_trades)) if total_trades > 0 else Decimal('0')
    win_rate = Decimal('99.5')
    
    health_status = HealthStatus(
        timestamp=datetime.now(),
        is_healthy=True,
        eoa_balance=eoa_balance,
        proxy_balance=proxy_balance,
        total_balance=total_balance,
        balance_ok=True,
        gas_ok=True,
        gas_price_gwei=50,
        pending_tx_ok=True,
        pending_tx_count=2,
        api_connectivity_ok=True,
        rpc_latency_ms=100.0,
        block_number=12345678,
        total_trades=total_trades,
        win_rate=win_rate,
        total_profit=total_profit,
        avg_profit_per_trade=avg_profit,
        total_gas_cost=total_gas_cost,
        net_profit=net_profit,
        circuit_breaker_open=False,
        consecutive_failures=0,
        ai_safety_active=True
    )
    
    # Verify all financial fields are Decimal
    assert isinstance(health_status.eoa_balance, Decimal)
    assert isinstance(health_status.proxy_balance, Decimal)
    assert isinstance(health_status.total_balance, Decimal)
    assert isinstance(health_status.win_rate, Decimal)
    assert isinstance(health_status.total_profit, Decimal)
    assert isinstance(health_status.avg_profit_per_trade, Decimal)
    assert isinstance(health_status.total_gas_cost, Decimal)
    assert isinstance(health_status.net_profit, Decimal)
    
    # Verify precision is maintained
    assert health_status.eoa_balance == eoa_balance
    assert health_status.proxy_balance == proxy_balance
    assert health_status.total_balance == total_balance
    assert health_status.total_profit == total_profit
    assert health_status.net_profit == net_profit


@given(
    price_str=st.text(
        alphabet=st.characters(whitelist_categories=('Nd',), max_codepoint=127),
        min_size=1,
        max_size=10
    ).filter(lambda s: s.isdigit() and len(s) > 0)
)
@settings(max_examples=100)
def test_decimal_string_conversion_precision(price_str):
    """
    Test that converting string prices to Decimal maintains precision.
    
    This simulates parsing price data from API responses.
    Validates: Requirements 17.5
    """
    # Add decimal point to make it a valid price
    if len(price_str) > 1:
        price_str = "0." + price_str
    else:
        price_str = "0.0" + price_str
    
    # Convert string to Decimal (as would happen when parsing API response)
    price_decimal = Decimal(price_str)
    
    # Create market with this price
    market = Market(
        market_id="test",
        question="BTC above $95,000?",
        asset="BTC",
        outcomes=["YES", "NO"],
        yes_price=price_decimal,
        no_price=Decimal('0.5'),
        yes_token_id="token_yes",
        no_token_id="token_no",
        volume=Decimal('1000.0'),
        liquidity=Decimal('500.0'),
        end_time=datetime.now() + timedelta(minutes=15),
        resolution_source="CEX"
    )
    
    # Verify exact string representation is preserved
    assert str(market.yes_price) == price_str, \
        f"String precision lost: {str(market.yes_price)} != {price_str}"
    
    # Verify type is Decimal
    assert isinstance(market.yes_price, Decimal)


@given(
    price1=decimal_price_strategy(),
    price2=decimal_price_strategy(),
    price3=decimal_price_strategy()
)
@settings(max_examples=100)
def test_decimal_associativity(price1, price2, price3):
    """
    Test that Decimal arithmetic is associative (unlike float).
    
    This property is critical for financial calculations.
    Validates: Requirements 17.5
    """
    # Test addition associativity: (a + b) + c == a + (b + c)
    left_assoc = (price1 + price2) + price3
    right_assoc = price1 + (price2 + price3)
    
    assert left_assoc == right_assoc, \
        f"Addition not associative: ({price1} + {price2}) + {price3} != {price1} + ({price2} + {price3})"
    
    # This would often fail with floats due to precision errors
    # Decimal maintains exact precision


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
