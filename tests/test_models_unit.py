"""
Unit tests for data models.

Tests specific examples and edge cases for Market, Opportunity, TradeResult,
SafetyDecision, and HealthStatus dataclasses.

Validates Requirements 17.4, 17.6.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import Market, Opportunity, TradeResult, SafetyDecision, HealthStatus


class TestMarketValidation:
    """Test Market dataclass validation and methods"""
    
    def test_is_crypto_15min_valid_btc_market(self):
        """Test that valid 15-minute BTC market is correctly identified"""
        market = Market(
            market_id="market_btc_15min",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('10000.0'),
            liquidity=Decimal('5000.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="Binance"
        )
        
        assert market.is_crypto_15min() is True
    
    def test_is_crypto_15min_valid_eth_market(self):
        """Test that valid 15-minute ETH market is correctly identified"""
        market = Market(
            market_id="market_eth_15min",
            question="ETH above $3,500?",
            asset="ETH",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.52'),
            no_price=Decimal('0.48'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('8000.0'),
            liquidity=Decimal('4000.0'),
            end_time=datetime.now() + timedelta(minutes=14.5),  # 14.5 minutes is valid
            resolution_source="Coinbase"
        )
        
        assert market.is_crypto_15min() is True
    
    def test_is_crypto_15min_valid_sol_market(self):
        """Test that valid 15-minute SOL market is correctly identified"""
        market = Market(
            market_id="market_sol_15min",
            question="SOL price above $180?",
            asset="SOL",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.55'),
            no_price=Decimal('0.45'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('5000.0'),
            liquidity=Decimal('2500.0'),
            end_time=datetime.now() + timedelta(minutes=15.5),  # 15.5 minutes is valid
            resolution_source="Kraken"
        )
        
        assert market.is_crypto_15min() is True
    
    def test_is_crypto_15min_valid_xrp_market(self):
        """Test that valid 15-minute XRP market is correctly identified"""
        market = Market(
            market_id="market_xrp_15min",
            question="Will XRP reach $2.50?",
            asset="XRP",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.30'),
            no_price=Decimal('0.70'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('3000.0'),
            liquidity=Decimal('1500.0'),
            end_time=datetime.now() + timedelta(minutes=14.5),  # 14.5 minutes is safely within bounds
            resolution_source="Binance"
        )
        
        assert market.is_crypto_15min() is True
    
    def test_is_crypto_15min_wrong_duration_too_short(self):
        """Test that market with duration < 14 minutes is rejected"""
        market = Market(
            market_id="market_short",
            question="BTC above $95,000?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=10),  # Too short
            resolution_source="CEX"
        )
        
        assert market.is_crypto_15min() is False
    
    def test_is_crypto_15min_wrong_duration_too_long(self):
        """Test that market with duration > 16 minutes is rejected"""
        market = Market(
            market_id="market_long",
            question="BTC above $95,000?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=60),  # Too long
            resolution_source="CEX"
        )
        
        assert market.is_crypto_15min() is False
    
    def test_is_crypto_15min_not_crypto_market(self):
        """Test that non-crypto market is rejected"""
        market = Market(
            market_id="market_weather",
            question="Will it rain tomorrow?",
            asset="WEATHER",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.60'),
            no_price=Decimal('0.40'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="Weather API"
        )
        
        assert market.is_crypto_15min() is False
    
    def test_is_crypto_15min_expired_market(self):
        """Test that expired market is rejected (Requirement 17.6)"""
        market = Market(
            market_id="market_expired",
            question="BTC above $95,000?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() - timedelta(minutes=5),  # Expired 5 minutes ago
            resolution_source="CEX"
        )
        
        assert market.is_crypto_15min() is False
    
    def test_parse_strike_price_with_dollar_sign_and_comma(self):
        """Test parsing strike price with $ and comma: '$95,000'"""
        market = Market(
            market_id="market_1",
            question="Will BTC be above $95,000?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        strike_price = market.parse_strike_price()
        assert strike_price == Decimal('95000')
    
    def test_parse_strike_price_without_dollar_sign(self):
        """Test parsing strike price without $: '3500'"""
        market = Market(
            market_id="market_2",
            question="ETH above 3500 in 15 minutes?",
            asset="ETH",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        strike_price = market.parse_strike_price()
        assert strike_price == Decimal('3500')
    
    def test_parse_strike_price_with_decimal(self):
        """Test parsing strike price with decimal: '$2.50'"""
        market = Market(
            market_id="market_3",
            question="XRP above $2.50?",
            asset="XRP",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        strike_price = market.parse_strike_price()
        assert strike_price == Decimal('2.50')
    
    def test_parse_strike_price_with_large_number(self):
        """Test parsing large strike price: '$100,000.99'"""
        market = Market(
            market_id="market_4",
            question="BTC reaches $100,000.99?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        strike_price = market.parse_strike_price()
        assert strike_price == Decimal('100000.99')
    
    def test_parse_strike_price_no_number_in_question(self):
        """Test parsing when no number exists in question"""
        market = Market(
            market_id="market_5",
            question="Will BTC go up?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        strike_price = market.parse_strike_price()
        assert strike_price is None
    
    def test_parse_strike_price_invalid_format(self):
        """Test parsing with invalid number format"""
        market = Market(
            market_id="market_6",
            question="BTC above $abc?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.50'),
            no_price=Decimal('0.50'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        strike_price = market.parse_strike_price()
        # Should return None since 'abc' is not a valid number
        assert strike_price is None


class TestOpportunityValidation:
    """Test Opportunity dataclass validation and methods"""
    
    def test_is_profitable_above_threshold(self):
        """Test opportunity is profitable when above threshold"""
        opportunity = Opportunity(
            opportunity_id="opp_1",
            market_id="market_1",
            strategy="internal",
            timestamp=datetime.now(),
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_fee=Decimal('0.028'),
            no_fee=Decimal('0.029'),
            total_cost=Decimal('0.9748'),
            expected_profit=Decimal('0.0252'),
            profit_percentage=Decimal('0.0258'),  # 2.58% > 0.5% threshold
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        assert opportunity.is_profitable() is True
    
    def test_is_profitable_at_threshold(self):
        """Test opportunity is profitable when exactly at threshold"""
        opportunity = Opportunity(
            opportunity_id="opp_2",
            market_id="market_2",
            strategy="internal",
            timestamp=datetime.now(),
            yes_price=Decimal('0.49'),
            no_price=Decimal('0.49'),
            yes_fee=Decimal('0.03'),
            no_fee=Decimal('0.03'),
            total_cost=Decimal('0.995'),
            expected_profit=Decimal('0.005'),
            profit_percentage=Decimal('0.005'),  # Exactly 0.5%
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        assert opportunity.is_profitable() is True
    
    def test_is_profitable_below_threshold(self):
        """Test opportunity is not profitable when below threshold"""
        opportunity = Opportunity(
            opportunity_id="opp_3",
            market_id="market_3",
            strategy="internal",
            timestamp=datetime.now(),
            yes_price=Decimal('0.495'),
            no_price=Decimal('0.495'),
            yes_fee=Decimal('0.03'),
            no_fee=Decimal('0.03'),
            total_cost=Decimal('0.9975'),
            expected_profit=Decimal('0.0025'),
            profit_percentage=Decimal('0.0025'),  # 0.25% < 0.5% threshold
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        assert opportunity.is_profitable() is False
    
    def test_is_profitable_custom_threshold(self):
        """Test opportunity profitability with custom threshold"""
        opportunity = Opportunity(
            opportunity_id="opp_4",
            market_id="market_4",
            strategy="resolution_farming",
            timestamp=datetime.now(),
            yes_price=Decimal('0.98'),
            no_price=Decimal('0.02'),
            yes_fee=Decimal('0.001'),
            no_fee=Decimal('0.001'),
            total_cost=Decimal('0.98098'),
            expected_profit=Decimal('0.01902'),
            profit_percentage=Decimal('0.0194'),  # 1.94%
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        # Should be profitable with 0.5% threshold
        assert opportunity.is_profitable(Decimal('0.005')) is True
        
        # Should not be profitable with 2% threshold
        assert opportunity.is_profitable(Decimal('0.02')) is False


class TestTradeResultValidation:
    """Test TradeResult dataclass validation and methods"""
    
    def test_was_successful_both_filled(self):
        """Test trade is successful when both orders filled"""
        opportunity = Opportunity(
            opportunity_id="opp_1",
            market_id="market_1",
            strategy="internal",
            timestamp=datetime.now(),
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_fee=Decimal('0.028'),
            no_fee=Decimal('0.029'),
            total_cost=Decimal('0.9748'),
            expected_profit=Decimal('0.0252'),
            profit_percentage=Decimal('0.0258'),
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        trade_result = TradeResult(
            trade_id="trade_1",
            opportunity=opportunity,
            timestamp=datetime.now(),
            status="success",
            yes_order_id="order_yes_1",
            no_order_id="order_no_1",
            yes_filled=True,
            no_filled=True,
            yes_fill_price=Decimal('0.48'),
            no_fill_price=Decimal('0.47'),
            actual_cost=Decimal('0.9748'),
            actual_profit=Decimal('0.0252'),
            gas_cost=Decimal('0.002'),
            net_profit=Decimal('0.0232'),
            yes_tx_hash="0xabc123",
            no_tx_hash="0xdef456",
            merge_tx_hash="0x789012"
        )
        
        assert trade_result.was_successful() is True
    
    def test_was_successful_only_yes_filled(self):
        """Test trade is not successful when only YES filled"""
        opportunity = Opportunity(
            opportunity_id="opp_2",
            market_id="market_2",
            strategy="internal",
            timestamp=datetime.now(),
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_fee=Decimal('0.028'),
            no_fee=Decimal('0.029'),
            total_cost=Decimal('0.9748'),
            expected_profit=Decimal('0.0252'),
            profit_percentage=Decimal('0.0258'),
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        trade_result = TradeResult(
            trade_id="trade_2",
            opportunity=opportunity,
            timestamp=datetime.now(),
            status="partial",
            yes_order_id="order_yes_2",
            no_order_id="order_no_2",
            yes_filled=True,
            no_filled=False,  # NO order failed
            yes_fill_price=Decimal('0.48'),
            no_fill_price=None,
            actual_cost=Decimal('0.48'),
            actual_profit=Decimal('0.0'),
            gas_cost=Decimal('0.001'),
            net_profit=Decimal('-0.001'),
            error_message="NO order failed to fill"
        )
        
        assert trade_result.was_successful() is False
    
    def test_was_successful_failed_status(self):
        """Test trade is not successful when status is failed"""
        opportunity = Opportunity(
            opportunity_id="opp_3",
            market_id="market_3",
            strategy="internal",
            timestamp=datetime.now(),
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_fee=Decimal('0.028'),
            no_fee=Decimal('0.029'),
            total_cost=Decimal('0.9748'),
            expected_profit=Decimal('0.0252'),
            profit_percentage=Decimal('0.0258'),
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        trade_result = TradeResult(
            trade_id="trade_3",
            opportunity=opportunity,
            timestamp=datetime.now(),
            status="failed",
            yes_order_id=None,
            no_order_id=None,
            yes_filled=False,
            no_filled=False,
            yes_fill_price=None,
            no_fill_price=None,
            actual_cost=Decimal('0.0'),
            actual_profit=Decimal('0.0'),
            gas_cost=Decimal('0.001'),
            net_profit=Decimal('-0.001'),
            error_message="Insufficient liquidity"
        )
        
        assert trade_result.was_successful() is False


class TestInvalidDataHandling:
    """Test handling of invalid data in data models"""
    
    def test_market_with_negative_price(self):
        """Test that Market can be created with negative price (validation happens elsewhere)"""
        # Note: Python dataclasses don't enforce validation by default
        # Validation should happen in parsing/creation logic
        market = Market(
            market_id="invalid_market",
            question="Test market",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('-0.1'),  # Invalid negative price
            no_price=Decimal('0.5'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        # Market object is created, but validation logic should reject it
        assert market.yes_price < 0
    
    def test_market_with_price_above_one(self):
        """Test that Market can be created with price > 1.0 (validation happens elsewhere)"""
        market = Market(
            market_id="invalid_market_2",
            question="Test market",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('1.5'),  # Invalid price > 1.0
            no_price=Decimal('0.5'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('1000.0'),
            liquidity=Decimal('500.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        # Market object is created, but validation logic should reject it
        assert market.yes_price > 1
    
    def test_opportunity_with_zero_profit(self):
        """Test opportunity with zero profit"""
        opportunity = Opportunity(
            opportunity_id="opp_zero",
            market_id="market_zero",
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
        
        assert opportunity.is_profitable() is False
    
    def test_opportunity_with_negative_profit(self):
        """Test opportunity with negative profit (loss)"""
        opportunity = Opportunity(
            opportunity_id="opp_loss",
            market_id="market_loss",
            strategy="internal",
            timestamp=datetime.now(),
            yes_price=Decimal('0.51'),
            no_price=Decimal('0.51'),
            yes_fee=Decimal('0.03'),
            no_fee=Decimal('0.03'),
            total_cost=Decimal('1.05'),
            expected_profit=Decimal('-0.05'),
            profit_percentage=Decimal('-0.0476'),
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        assert opportunity.is_profitable() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
