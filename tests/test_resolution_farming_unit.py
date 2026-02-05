"""
Unit tests for Resolution Farming Engine.

Tests specific examples and edge cases for resolution farming functionality.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import uuid

from src.resolution_farming_engine import ResolutionFarmingEngine
from src.ai_safety_guard import AISafetyGuard
from src.models import Market


class TestResolutionFarmingEngine:
    """Unit tests for ResolutionFarmingEngine class."""
    
    @pytest.fixture
    def mock_cex_feeds(self):
        """Create mock CEX feeds."""
        return {
            "BTC": Mock(get_latest_price=Mock(return_value=95000)),
            "ETH": Mock(get_latest_price=Mock(return_value=3500)),
            "SOL": Mock(get_latest_price=Mock(return_value=200)),
            "XRP": Mock(get_latest_price=Mock(return_value=2.5))
        }
    
    @pytest.fixture
    def ai_guard(self):
        """Create AI safety guard."""
        return AISafetyGuard(nvidia_api_key="test_key")
    
    @pytest.fixture
    def engine(self, mock_cex_feeds, ai_guard):
        """Create resolution farming engine."""
        return ResolutionFarmingEngine(
            cex_feeds=mock_cex_feeds,
            ai_safety_guard=ai_guard
        )
    
    def create_market(
        self,
        question: str,
        asset: str,
        yes_price: Decimal,
        closing_seconds: int
    ) -> Market:
        """Helper to create a market."""
        return Market(
            market_id=str(uuid.uuid4()),
            question=question,
            asset=asset,
            outcomes=["YES", "NO"],
            yes_price=yes_price,
            no_price=Decimal('1.00') - yes_price,
            yes_token_id=str(uuid.uuid4()),
            no_token_id=str(uuid.uuid4()),
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(seconds=closing_seconds),
            resolution_source="CEX"
        )
    
    @pytest.mark.asyncio
    async def test_scan_finds_opportunity_at_97_cents(self, engine):
        """Test that opportunities are found at minimum price (97¢)."""
        market = self.create_market(
            question="Will BTC be above $94000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.97'),
            closing_seconds=60
        )
        
        opportunities = await engine.scan_closing_markets([market])
        
        assert len(opportunities) == 1
        assert opportunities[0].total_cost == Decimal('0.97')
        assert opportunities[0].expected_profit == Decimal('0.03')
    
    @pytest.mark.asyncio
    async def test_scan_finds_opportunity_at_99_cents(self, engine):
        """Test that opportunities are found at maximum price (99¢)."""
        market = self.create_market(
            question="Will BTC be above $94000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.99'),
            closing_seconds=60
        )
        
        opportunities = await engine.scan_closing_markets([market])
        
        assert len(opportunities) == 1
        assert opportunities[0].total_cost == Decimal('0.99')
        assert opportunities[0].expected_profit == Decimal('0.01')
    
    @pytest.mark.asyncio
    async def test_scan_skips_price_below_97_cents(self, engine):
        """Test that prices below 97¢ are skipped."""
        market = self.create_market(
            question="Will BTC be above $94000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.96'),
            closing_seconds=60
        )
        
        opportunities = await engine.scan_closing_markets([market])
        
        assert len(opportunities) == 0
    
    @pytest.mark.asyncio
    async def test_scan_skips_price_above_99_cents(self, engine):
        """Test that prices above 99¢ are skipped."""
        market = self.create_market(
            question="Will BTC be above $94000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.995'),
            closing_seconds=60
        )
        
        opportunities = await engine.scan_closing_markets([market])
        
        assert len(opportunities) == 0
    
    @pytest.mark.asyncio
    async def test_scan_skips_expired_market(self, engine):
        """Test that expired markets are skipped."""
        market = self.create_market(
            question="Will BTC be above $94000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.98'),
            closing_seconds=-10  # Already closed
        )
        
        opportunities = await engine.scan_closing_markets([market])
        
        assert len(opportunities) == 0
    
    @pytest.mark.asyncio
    async def test_scan_skips_market_closing_too_late(self, engine):
        """Test that markets closing beyond 2 minutes are skipped."""
        market = self.create_market(
            question="Will BTC be above $94000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.98'),
            closing_seconds=150  # 2.5 minutes
        )
        
        opportunities = await engine.scan_closing_markets([market])
        
        assert len(opportunities) == 0
    
    def test_verify_outcome_btc_above_strike_yes(self, engine):
        """Test BTC above strike with 'above' question returns YES."""
        market = self.create_market(
            question="Will BTC be above $94000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.98'),
            closing_seconds=60
        )
        
        # CEX price is 95000, strike is 94000, so BTC is above
        outcome = engine.verify_outcome_certainty(market)
        
        assert outcome == "YES"
    
    def test_verify_outcome_btc_below_strike_no(self, engine):
        """Test BTC below strike with 'above' question returns NO."""
        market = self.create_market(
            question="Will BTC be above $96000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.98'),
            closing_seconds=60
        )
        
        # CEX price is 95000, strike is 96000, so BTC is below
        outcome = engine.verify_outcome_certainty(market)
        
        assert outcome == "NO"
    
    def test_verify_outcome_btc_below_strike_yes(self, engine):
        """Test BTC below strike with 'below' question returns YES."""
        market = self.create_market(
            question="Will BTC be below $96000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.98'),
            closing_seconds=60
        )
        
        # CEX price is 95000, strike is 96000, so BTC is below
        outcome = engine.verify_outcome_certainty(market)
        
        assert outcome == "YES"
    
    def test_verify_outcome_btc_above_strike_no_for_below(self, engine):
        """Test BTC above strike with 'below' question returns NO."""
        market = self.create_market(
            question="Will BTC be below $94000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.98'),
            closing_seconds=60
        )
        
        # CEX price is 95000, strike is 94000, so BTC is above
        outcome = engine.verify_outcome_certainty(market)
        
        assert outcome == "NO"
    
    def test_verify_outcome_no_cex_price(self, engine):
        """Test that None is returned when CEX price unavailable."""
        # Create market with asset not in CEX feeds
        market = self.create_market(
            question="Will DOGE be above $0.50 in 15 minutes?",
            asset="DOGE",
            yes_price=Decimal('0.98'),
            closing_seconds=60
        )
        
        outcome = engine.verify_outcome_certainty(market)
        
        assert outcome is None
    
    def test_verify_outcome_no_strike_price(self, engine):
        """Test that None is returned when strike price cannot be parsed."""
        market = self.create_market(
            question="Will BTC go up in 15 minutes?",  # No strike price
            asset="BTC",
            yes_price=Decimal('0.98'),
            closing_seconds=60
        )
        
        outcome = engine.verify_outcome_certainty(market)
        
        assert outcome is None
    
    def test_verify_outcome_unclear_direction(self, engine):
        """Test that None is returned when direction is unclear."""
        market = self.create_market(
            question="Will BTC be at $95000 in 15 minutes?",  # No above/below
            asset="BTC",
            yes_price=Decimal('0.98'),
            closing_seconds=60
        )
        
        outcome = engine.verify_outcome_certainty(market)
        
        assert outcome is None
    
    def test_calculate_position_size_2_percent(self, engine):
        """Test position size is exactly 2% of bankroll."""
        bankroll = Decimal('1000.00')
        
        position_size = engine.calculate_position_size(bankroll)
        
        assert position_size == Decimal('20.00')  # 2% of 1000
    
    def test_calculate_position_size_small_bankroll(self, engine):
        """Test position size for small bankroll."""
        bankroll = Decimal('100.00')
        
        position_size = engine.calculate_position_size(bankroll)
        
        assert position_size == Decimal('2.00')  # 2% of 100
    
    def test_calculate_position_size_large_bankroll(self, engine):
        """Test position size for large bankroll."""
        bankroll = Decimal('10000.00')
        
        position_size = engine.calculate_position_size(bankroll)
        
        assert position_size == Decimal('200.00')  # 2% of 10000
    
    @pytest.mark.asyncio
    async def test_multiple_markets_multiple_opportunities(self, engine):
        """Test scanning multiple markets finds multiple opportunities."""
        markets = [
            self.create_market(
                question="Will BTC be above $94000 in 15 minutes?",
                asset="BTC",
                yes_price=Decimal('0.98'),
                closing_seconds=60
            ),
            self.create_market(
                question="Will ETH be above $3400 in 15 minutes?",
                asset="ETH",
                yes_price=Decimal('0.97'),
                closing_seconds=90
            ),
            self.create_market(
                question="Will SOL be above $190 in 15 minutes?",
                asset="SOL",
                yes_price=Decimal('0.99'),
                closing_seconds=30
            )
        ]
        
        opportunities = await engine.scan_closing_markets(markets)
        
        assert len(opportunities) == 3
        assert all(opp.strategy == "resolution_farming" for opp in opportunities)
    
    @pytest.mark.asyncio
    async def test_profit_calculation_accuracy(self, engine):
        """Test that profit is calculated accurately."""
        market = self.create_market(
            question="Will BTC be above $94000 in 15 minutes?",
            asset="BTC",
            yes_price=Decimal('0.975'),
            closing_seconds=60
        )
        
        opportunities = await engine.scan_closing_markets([market])
        
        assert len(opportunities) == 1
        opp = opportunities[0]
        
        # Profit should be 1.00 - 0.975 = 0.025
        assert opp.expected_profit == Decimal('0.025')
        
        # Profit percentage should be 0.025 / 0.975 ≈ 0.02564
        expected_percentage = Decimal('0.025') / Decimal('0.975')
        assert abs(opp.profit_percentage - expected_percentage) < Decimal('0.00001')
