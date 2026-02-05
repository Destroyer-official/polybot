"""
Property-based tests for market data parsing and validation.

Tests market parsing, validation, and filtering using Hypothesis.
Validates Requirements 17.1, 17.2, 17.3, 17.4, 17.6.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.market_parser import MarketParser
from src.models import Market


# Strategy for generating valid market data
def valid_market_data_strategy():
    """Generate valid market data for testing."""
    return st.builds(
        lambda cid, q, t, v, l, rs: {
            'condition_id': cid,
            'question': q,
            'tokens': t,
            'end_date_iso': (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            'volume': v,
            'liquidity': l,
            'resolution_source': rs,
            'closed': False,
            'active': True,
        },
        cid=st.text(min_size=10, max_size=66, alphabet='0123456789abcdef'),
        q=st.sampled_from([
            'Will BTC be above $95,000 in 15 minutes?',
            'Will ETH be above $3,500 in 15 minutes?',
            'Will SOL be above $180 in 15 minutes?',
            'Will XRP be above $2.50 in 15 minutes?',
        ]),
        t=st.lists(
            st.fixed_dictionaries({
                'token_id': st.text(min_size=10, max_size=66, alphabet='0123456789abcdef'),
                'price': st.decimals(
                    min_value=Decimal('0.01'),
                    max_value=Decimal('0.99'),
                    places=4
                ).map(str),
            }),
            min_size=2,
            max_size=2
        ),
        v=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('100000'),
            places=2
        ).map(str),
        l=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('50000'),
            places=2
        ).map(str),
        rs=st.sampled_from(['CEX', 'Binance', 'Coinbase', 'Kraken']),
    )


@given(market_data=valid_market_data_strategy())
@settings(max_examples=100)
def test_market_data_parsing_and_validation(market_data):
    """
    **Validates: Requirements 17.1, 17.2**
    
    Feature: polymarket-arbitrage-bot, Property 47: Market Data Parsing and Validation
    
    For any valid market data from the CLOB API, the parser should successfully
    parse it into a Market object with all required fields validated and properly typed.
    """
    parser = MarketParser()
    
    # Parse the market
    market = parser.parse_single_market(market_data)
    
    # Should successfully parse valid data
    assert market is not None, \
        f"Parser should successfully parse valid market data"
    
    # Verify all required fields are present and correctly typed
    assert isinstance(market.market_id, str), \
        f"market_id should be string, got {type(market.market_id)}"
    assert market.market_id == market_data['condition_id'], \
        f"market_id should match condition_id"
    
    assert isinstance(market.question, str), \
        f"question should be string, got {type(market.question)}"
    assert market.question == market_data['question'], \
        f"question should match input"
    
    assert isinstance(market.asset, str), \
        f"asset should be string, got {type(market.asset)}"
    assert market.asset in ['BTC', 'ETH', 'SOL', 'XRP'], \
        f"asset should be valid crypto: {market.asset}"
    
    assert isinstance(market.outcomes, list), \
        f"outcomes should be list, got {type(market.outcomes)}"
    assert market.outcomes == ["YES", "NO"], \
        f"outcomes should be ['YES', 'NO']"
    
    # Verify prices are Decimal type (Requirement 17.5)
    assert isinstance(market.yes_price, Decimal), \
        f"yes_price should be Decimal, got {type(market.yes_price)}"
    assert isinstance(market.no_price, Decimal), \
        f"no_price should be Decimal, got {type(market.no_price)}"
    
    # Verify prices are in valid range
    assert Decimal('0') <= market.yes_price <= Decimal('1'), \
        f"yes_price should be between 0 and 1: {market.yes_price}"
    assert Decimal('0') <= market.no_price <= Decimal('1'), \
        f"no_price should be between 0 and 1: {market.no_price}"
    
    # Verify token IDs are present
    assert isinstance(market.yes_token_id, str), \
        f"yes_token_id should be string"
    assert isinstance(market.no_token_id, str), \
        f"no_token_id should be string"
    assert len(market.yes_token_id) > 0, \
        f"yes_token_id should not be empty"
    assert len(market.no_token_id) > 0, \
        f"no_token_id should not be empty"
    
    # Verify volume and liquidity are Decimal
    assert isinstance(market.volume, Decimal), \
        f"volume should be Decimal, got {type(market.volume)}"
    assert isinstance(market.liquidity, Decimal), \
        f"liquidity should be Decimal, got {type(market.liquidity)}"
    assert market.volume >= Decimal('0'), \
        f"volume should be non-negative"
    assert market.liquidity >= Decimal('0'), \
        f"liquidity should be non-negative"
    
    # Verify end_time is datetime
    assert isinstance(market.end_time, datetime), \
        f"end_time should be datetime, got {type(market.end_time)}"
    
    # Verify resolution source
    assert isinstance(market.resolution_source, str), \
        f"resolution_source should be string"
    
    # Verify market is not expired (Requirement 17.6)
    now = datetime.now(tz=market.end_time.tzinfo) if market.end_time.tzinfo else datetime.now()
    assert market.end_time > now, \
        f"Parsed market should not be expired"
    
    # Verify it's a crypto market (Requirement 17.4)
    assert market.asset in ['BTC', 'ETH', 'SOL', 'XRP'], \
        f"Parsed market should be a crypto market"
    
    # Verify time remaining is in expected range
    duration_minutes = (market.end_time - (datetime.now(tz=market.end_time.tzinfo) if market.end_time.tzinfo else datetime.now())).total_seconds() / 60
    assert 14 <= duration_minutes <= 16, \
        f"Market should have 14-16 minutes remaining, got {duration_minutes:.2f}"


@given(
    market_data=valid_market_data_strategy(),
    missing_field=st.sampled_from(['condition_id', 'question', 'tokens', 'end_date_iso'])
)
@settings(max_examples=100)
def test_invalid_market_handling(market_data, missing_field):
    """
    **Validates: Requirements 17.3**
    
    Feature: polymarket-arbitrage-bot, Property 48: Invalid Market Handling
    
    For any market data missing required fields, the parser should skip the market
    with a warning and return None, rather than raising an exception.
    """
    parser = MarketParser()
    
    # Remove a required field
    invalid_data = market_data.copy()
    del invalid_data[missing_field]
    
    # Parse should return None for invalid data
    market = parser.parse_single_market(invalid_data)
    
    assert market is None, \
        f"Parser should return None for market missing {missing_field}"
    
    # Verify the market was counted as skipped
    assert parser.markets_skipped > 0, \
        f"Parser should track skipped markets"
    
    # Verify the skip reason was recorded
    assert len(parser.skip_reasons) > 0, \
        f"Parser should record skip reasons"
    
    # Verify the specific reason includes the missing field
    skip_reasons_str = str(parser.skip_reasons)
    assert missing_field in skip_reasons_str or 'missing' in skip_reasons_str, \
        f"Skip reason should mention missing field: {parser.skip_reasons}"


@given(
    market_data=valid_market_data_strategy(),
    invalid_price=st.sampled_from(['invalid', 'NaN', 'Infinity', '', None, 'abc123'])
)
@settings(max_examples=100)
def test_invalid_price_handling(market_data, invalid_price):
    """
    **Validates: Requirements 17.3**
    
    Test that markets with invalid price data are skipped with warnings.
    """
    parser = MarketParser()
    
    # Set invalid price
    invalid_data = market_data.copy()
    invalid_data['tokens'][0]['price'] = invalid_price
    
    # Parse should return None for invalid price
    market = parser.parse_single_market(invalid_data)
    
    assert market is None, \
        f"Parser should return None for market with invalid price: {invalid_price}"
    
    # Verify skip was recorded
    assert parser.markets_skipped > 0, \
        f"Parser should track skipped markets with invalid prices"


@given(market_data=valid_market_data_strategy())
@settings(max_examples=100)
def test_crypto_market_filtering(market_data):
    """
    **Validates: Requirements 17.4, 17.6**
    
    Feature: polymarket-arbitrage-bot, Property 49: Crypto Market Filtering
    
    The parser should only accept markets that:
    1. Mention crypto assets (BTC, ETH, SOL, XRP) in the question
    2. Are 15-minute duration markets
    3. Are not expired
    
    Non-crypto markets or markets with different durations should be filtered out.
    """
    parser = MarketParser()
    
    # Test 1: Valid crypto market should parse
    market = parser.parse_single_market(market_data)
    if market is not None:
        # If parsed, must be crypto
        assert market.asset in ['BTC', 'ETH', 'SOL', 'XRP'], \
            f"Parsed market must be crypto asset"
        
        # Must be 15-minute market
        assert market.is_crypto_15min(), \
            f"Parsed market must be 15-minute crypto market"
        
        # Must not be expired
        now = datetime.now(tz=market.end_time.tzinfo) if market.end_time.tzinfo else datetime.now()
        assert market.end_time > now, \
            f"Parsed market must not be expired"
    
    # Test 2: Non-crypto market should be filtered
    non_crypto_data = market_data.copy()
    non_crypto_data['question'] = 'Will it rain tomorrow?'
    
    non_crypto_market = parser.parse_single_market(non_crypto_data)
    assert non_crypto_market is None, \
        f"Non-crypto market should be filtered out"
    
    # Test 3: Expired market should be filtered
    expired_data = market_data.copy()
    expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
    expired_data['end_date_iso'] = expired_time.isoformat()
    
    expired_market = parser.parse_single_market(expired_data)
    assert expired_market is None, \
        f"Expired market should be filtered out"
    
    # Test 4: Non-15-minute market should be filtered
    long_duration_data = market_data.copy()
    long_duration_time = datetime.now(timezone.utc) + timedelta(hours=1)
    long_duration_data['end_date_iso'] = long_duration_time.isoformat()
    
    long_duration_market = parser.parse_single_market(long_duration_data)
    assert long_duration_market is None, \
        f"Non-15-minute market should be filtered out"


@given(
    market_list=st.lists(
        valid_market_data_strategy(),
        min_size=1,
        max_size=20
    )
)
@settings(max_examples=50)
def test_batch_market_parsing(market_list):
    """
    Test that parsing multiple markets maintains consistency and tracks statistics.
    
    Validates: Requirements 17.1, 17.2, 17.3
    """
    parser = MarketParser()
    
    # Create API response format
    api_response = {'data': market_list}
    
    # Parse all markets
    parsed_markets = parser.parse_markets(api_response)
    
    # Verify result is a list
    assert isinstance(parsed_markets, list), \
        f"parse_markets should return a list"
    
    # Verify all parsed markets are Market objects
    for market in parsed_markets:
        assert isinstance(market, Market), \
            f"All parsed items should be Market objects"
    
    # Verify statistics are tracked
    stats = parser.get_stats()
    assert isinstance(stats, dict), \
        f"get_stats should return a dict"
    assert 'markets_parsed' in stats, \
        f"Stats should include markets_parsed"
    assert 'markets_skipped' in stats, \
        f"Stats should include markets_skipped"
    assert 'skip_reasons' in stats, \
        f"Stats should include skip_reasons"
    
    # Verify counts are consistent
    total_processed = stats['markets_parsed'] + stats['markets_skipped']
    assert total_processed == len(market_list), \
        f"Total processed should equal input count: {total_processed} != {len(market_list)}"
    
    # Verify parsed count matches returned list
    assert stats['markets_parsed'] == len(parsed_markets), \
        f"Parsed count should match returned list length"


@given(
    valid_data=valid_market_data_strategy(),
    num_invalid=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=50)
def test_mixed_valid_invalid_markets(valid_data, num_invalid):
    """
    Test that parser correctly handles a mix of valid and invalid markets.
    
    Validates: Requirements 17.3
    """
    parser = MarketParser()
    
    # Create a mix of valid and invalid markets
    market_list = [valid_data]
    
    # Add invalid markets (missing required fields)
    for i in range(num_invalid):
        invalid_data = {'condition_id': f'invalid_{i}'}
        market_list.append(invalid_data)
    
    api_response = {'data': market_list}
    
    # Parse all markets
    parsed_markets = parser.parse_markets(api_response)
    
    # Should have parsed at least the valid one (if it passes 15-min crypto filter)
    # Invalid ones should be skipped
    assert parser.markets_skipped >= num_invalid, \
        f"Should skip at least {num_invalid} invalid markets"
    
    # All returned markets should be valid Market objects
    for market in parsed_markets:
        assert isinstance(market, Market), \
            f"All returned items should be valid Market objects"


@given(market_data=valid_market_data_strategy())
@settings(max_examples=100)
def test_parser_statistics_reset(market_data):
    """
    Test that parser statistics can be reset.
    
    Validates: Requirements 17.1
    """
    parser = MarketParser()
    
    # Parse a market
    parser.parse_single_market(market_data)
    
    # Verify stats are non-zero
    stats_before = parser.get_stats()
    assert stats_before['markets_parsed'] > 0 or stats_before['markets_skipped'] > 0, \
        f"Stats should be non-zero after parsing"
    
    # Reset stats
    parser.reset_stats()
    
    # Verify stats are zero
    stats_after = parser.get_stats()
    assert stats_after['markets_parsed'] == 0, \
        f"markets_parsed should be 0 after reset"
    assert stats_after['markets_skipped'] == 0, \
        f"markets_skipped should be 0 after reset"
    assert len(stats_after['skip_reasons']) == 0, \
        f"skip_reasons should be empty after reset"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
