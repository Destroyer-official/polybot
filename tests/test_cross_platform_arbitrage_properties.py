"""
Property-based tests for Cross-Platform Arbitrage Engine.

Tests universal properties that should hold across all valid executions.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock
import asyncio

from src.cross_platform_arbitrage_engine import CrossPlatformArbitrageEngine
from src.models import Market, Opportunity
from src.ai_safety_guard import AISafetyGuard
from src.kelly_position_sizer import KellyPositionSizer
from src.order_manager import OrderManager


# Strategy for generating valid prices (0.01 to 0.99)
price_strategy = st.decimals(
    min_value=Decimal('0.01'),
    max_value=Decimal('0.99'),
    places=2
)

# Strategy for generating market data
@st.composite
def market_strategy(draw, asset="BTC"):
    """Generate a valid Market object."""
    yes_price = draw(price_strategy)
    no_price = draw(price_strategy)
    
    # Ensure prices don't sum to exactly 1.0 to allow for arbitrage
    assume(abs((yes_price + no_price) - Decimal('1.0')) > Decimal('0.01'))
    
    market_id = f"market_{draw(st.integers(min_value=1000, max_value=9999))}"
    
    return Market(
        market_id=market_id,
        question=f"Will {asset} be above $95,000 in 15 minutes?",
        asset=asset,
        outcomes=["YES", "NO"],
        yes_price=yes_price,
        no_price=no_price,
        yes_token_id=f"token_yes_{market_id}",
        no_token_id=f"token_no_{market_id}",
        volume=Decimal('10000'),
        liquidity=Decimal('5000'),
        end_time=datetime.now() + timedelta(minutes=15),
        resolution_source="CEX"
    )


class TestCrossPlatformArbitrageDetection:
    """
    Property 7: Cross-Platform Arbitrage Detection
    
    **Validates: Requirements 3.2, 3.3**
    
    For any pair of equivalent markets on Polymarket and Kalshi,
    if (Polymarket_YES_price + fees) < (Kalshi_NO_price - fees) or vice versa,
    the system should identify a cross-platform arbitrage opportunity.
    """
    
    @given(
        pm_yes_price=price_strategy,
        kalshi_no_price=price_strategy,
        asset=st.sampled_from(["BTC", "ETH", "SOL", "XRP"])
    )
    @settings(max_examples=100, deadline=None)
    def test_cross_platform_arbitrage_detection_pm_yes_kalshi_no(
        self,
        pm_yes_price,
        kalshi_no_price,
        asset
    ):
        """
        Test that cross-platform arbitrage is detected when:
        Polymarket YES price + fees < Kalshi NO price - fees
        
        This validates that the engine correctly identifies profitable
        opportunities across platforms.
        """
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        ai_safety_guard = Mock(spec=AISafetyGuard)
        kelly_sizer = Mock(spec=KellyPositionSizer)
        
        # Create engine
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001'),  # 0.1% for testing
            withdrawal_fee_polymarket=Decimal('0.001'),
            withdrawal_fee_kalshi=Decimal('0.002')
        )
        
        # Create Polymarket market
        pm_market = Market(
            market_id="pm_market_1",
            question=f"Will {asset} be above $95,000 in 15 minutes?",
            asset=asset,
            outcomes=["YES", "NO"],
            yes_price=pm_yes_price,
            no_price=Decimal('1.0') - pm_yes_price,
            yes_token_id="pm_yes_token",
            no_token_id="pm_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        # Create Kalshi market with complementary pricing
        kalshi_market = Market(
            market_id="kalshi_market_1",
            question=f"Will {asset} be above $95,000 in 15 minutes?",
            asset=asset,
            outcomes=["YES", "NO"],
            yes_price=Decimal('1.0') - kalshi_no_price,
            no_price=kalshi_no_price,
            yes_token_id="kalshi_yes_token",
            no_token_id="kalshi_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        # Check for arbitrage opportunity
        opportunity = engine._check_arbitrage_opportunity(
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            pm_side="YES",
            kalshi_side="NO"
        )
        
        # Calculate expected profitability
        # PM YES cost = pm_yes_price * (1 + fee + withdrawal_fee)
        # Kalshi NO cost = kalshi_no_price * (1 + fee + withdrawal_fee)
        # Total cost = PM YES cost + Kalshi NO cost
        # Profit = $1.00 - total_cost
        
        # If there's a significant price discrepancy, we should find an opportunity
        price_sum = pm_yes_price + kalshi_no_price
        
        if price_sum < Decimal('0.95'):  # Significant arbitrage potential
            # Should detect opportunity
            assert opportunity is not None, (
                f"Failed to detect cross-platform arbitrage: "
                f"PM YES ${pm_yes_price} + Kalshi NO ${kalshi_no_price} = ${price_sum}"
            )
            
            # Verify opportunity properties
            assert opportunity.strategy == "cross_platform_arbitrage"
            assert opportunity.platform_a == "polymarket"
            assert opportunity.platform_b == "kalshi"
            assert opportunity.expected_profit > 0
            assert opportunity.profit_percentage >= engine.min_profit_threshold
            
        elif price_sum > Decimal('1.05'):  # No arbitrage possible
            # Should not detect opportunity (or detect reverse arbitrage)
            if opportunity is not None:
                # If opportunity found, profit should be minimal or negative
                assert opportunity.expected_profit <= Decimal('0.01')
    
    @given(
        pm_no_price=price_strategy,
        kalshi_yes_price=price_strategy,
        asset=st.sampled_from(["BTC", "ETH", "SOL", "XRP"])
    )
    @settings(max_examples=100, deadline=None)
    def test_cross_platform_arbitrage_detection_pm_no_kalshi_yes(
        self,
        pm_no_price,
        kalshi_yes_price,
        asset
    ):
        """
        Test that cross-platform arbitrage is detected when:
        Polymarket NO price + fees < Kalshi YES price - fees
        
        This validates the reverse direction of cross-platform arbitrage.
        """
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        ai_safety_guard = Mock(spec=AISafetyGuard)
        kelly_sizer = Mock(spec=KellyPositionSizer)
        
        # Create engine
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001'),  # 0.1% for testing
            withdrawal_fee_polymarket=Decimal('0.001'),
            withdrawal_fee_kalshi=Decimal('0.002')
        )
        
        # Create Polymarket market
        pm_market = Market(
            market_id="pm_market_2",
            question=f"Will {asset} be above $95,000 in 15 minutes?",
            asset=asset,
            outcomes=["YES", "NO"],
            yes_price=Decimal('1.0') - pm_no_price,
            no_price=pm_no_price,
            yes_token_id="pm_yes_token",
            no_token_id="pm_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        # Create Kalshi market
        kalshi_market = Market(
            market_id="kalshi_market_2",
            question=f"Will {asset} be above $95,000 in 15 minutes?",
            asset=asset,
            outcomes=["YES", "NO"],
            yes_price=kalshi_yes_price,
            no_price=Decimal('1.0') - kalshi_yes_price,
            yes_token_id="kalshi_yes_token",
            no_token_id="kalshi_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        # Check for arbitrage opportunity
        opportunity = engine._check_arbitrage_opportunity(
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            pm_side="NO",
            kalshi_side="YES"
        )
        
        # Calculate expected profitability
        price_sum = pm_no_price + kalshi_yes_price
        
        if price_sum < Decimal('0.95'):  # Significant arbitrage potential
            # Should detect opportunity
            assert opportunity is not None, (
                f"Failed to detect cross-platform arbitrage: "
                f"PM NO ${pm_no_price} + Kalshi YES ${kalshi_yes_price} = ${price_sum}"
            )
            
            # Verify opportunity properties
            assert opportunity.strategy == "cross_platform_arbitrage"
            assert opportunity.expected_profit > 0
            assert opportunity.profit_percentage >= engine.min_profit_threshold
    
    @given(
        pm_market=market_strategy(),
        kalshi_market=market_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_withdrawal_fees_accounted_in_profit(self, pm_market, kalshi_market):
        """
        Test that withdrawal fees are properly accounted for in profit calculations.
        
        **Validates: Requirement 3.6**
        
        For any cross-platform arbitrage calculation, the profit should account
        for all fees including trading fees, withdrawal fees, and settlement costs.
        """
        # Ensure markets have the same asset
        kalshi_market.asset = pm_market.asset
        kalshi_market.question = pm_market.question
        
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        ai_safety_guard = Mock(spec=AISafetyGuard)
        kelly_sizer = Mock(spec=KellyPositionSizer)
        
        # Create engine with known withdrawal fees
        withdrawal_fee_pm = Decimal('0.001')  # 0.1%
        withdrawal_fee_kalshi = Decimal('0.002')  # 0.2%
        
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001'),
            withdrawal_fee_polymarket=withdrawal_fee_pm,
            withdrawal_fee_kalshi=withdrawal_fee_kalshi
        )
        
        # Check for arbitrage opportunity
        opportunity = engine._check_arbitrage_opportunity(
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            pm_side="YES",
            kalshi_side="NO"
        )
        
        if opportunity is not None:
            # Verify that total_cost includes withdrawal fees
            # Total cost should be higher than just the sum of prices + trading fees
            
            pm_price = pm_market.yes_price
            kalshi_price = kalshi_market.no_price
            
            # Calculate minimum cost without withdrawal fees
            min_cost_without_withdrawal = pm_price + kalshi_price
            
            # Total cost should be higher (includes trading fees + withdrawal fees)
            assert opportunity.total_cost > min_cost_without_withdrawal, (
                f"Total cost ${opportunity.total_cost} should include withdrawal fees "
                f"and be greater than base prices ${min_cost_without_withdrawal}"
            )
            
            # Verify profit accounts for all fees
            expected_payout = Decimal('1.0')
            calculated_profit = expected_payout - opportunity.total_cost
            
            assert abs(opportunity.expected_profit - calculated_profit) < Decimal('0.0001'), (
                f"Profit calculation mismatch: "
                f"expected ${calculated_profit}, got ${opportunity.expected_profit}"
            )
    
    @given(
        pm_yes=price_strategy,
        kalshi_no=price_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_no_false_positives_when_unprofitable(self, pm_yes, kalshi_no):
        """
        Test that the engine does not detect arbitrage when it's not profitable.
        
        This ensures the system doesn't generate false positive opportunities
        that would result in losses.
        """
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        ai_safety_guard = Mock(spec=AISafetyGuard)
        kelly_sizer = Mock(spec=KellyPositionSizer)
        
        # Create engine
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.005'),  # 0.5%
            withdrawal_fee_polymarket=Decimal('0.001'),
            withdrawal_fee_kalshi=Decimal('0.002')
        )
        
        # Create markets where arbitrage is clearly unprofitable
        # Set prices such that sum is close to or above $1.00
        pm_market = Market(
            market_id="pm_market_3",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=pm_yes,
            no_price=Decimal('1.0') - pm_yes,
            yes_token_id="pm_yes_token",
            no_token_id="pm_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        kalshi_market = Market(
            market_id="kalshi_market_3",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('1.0') - kalshi_no,
            no_price=kalshi_no,
            yes_token_id="kalshi_yes_token",
            no_token_id="kalshi_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        # Check for arbitrage
        opportunity = engine._check_arbitrage_opportunity(
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            pm_side="YES",
            kalshi_side="NO"
        )
        
        # If prices sum to >= $1.00, there should be no opportunity
        price_sum = pm_yes + kalshi_no
        
        if price_sum >= Decimal('1.0'):
            # Should not detect opportunity
            if opportunity is not None:
                # If somehow detected, profit should be negative or below threshold
                assert (
                    opportunity.expected_profit <= 0 or
                    opportunity.profit_percentage < engine.min_profit_threshold
                ), (
                    f"False positive detected: prices sum to ${price_sum} >= $1.00, "
                    f"but opportunity shows profit ${opportunity.expected_profit}"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



class TestCrossPlatformAtomicExecution:
    """
    Property 8: Cross-Platform Atomic Execution
    
    **Validates: Requirements 3.4, 3.5**
    
    For any cross-platform arbitrage opportunity, if either platform's order
    fails to fill, the system should immediately cancel the other platform's
    order to maintain atomicity.
    """
    
    @given(
        pm_market=market_strategy(),
        kalshi_market=market_strategy(),
        bankroll=st.decimals(min_value=Decimal('100'), max_value=Decimal('1000'), places=2),
        pm_fills=st.booleans(),
        kalshi_fills=st.booleans()
    )
    @settings(max_examples=100, deadline=None)
    def test_atomic_execution_both_fill_or_neither(
        self,
        pm_market,
        kalshi_market,
        bankroll,
        pm_fills,
        kalshi_fills
    ):
        """
        Test that cross-platform orders execute atomically.
        
        Either both orders fill completely or neither fills, preventing
        unhedged positions across platforms.
        """
        # Ensure markets have the same asset
        kalshi_market.asset = pm_market.asset
        kalshi_market.question = pm_market.question
        
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        
        # Create mock order managers
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        
        # Mock order creation
        pm_order = Mock()
        pm_order.order_id = "pm_order_123"
        pm_order.fill_price = pm_market.yes_price
        pm_order.tx_hash = "0xpm123"
        
        kalshi_order = Mock()
        kalshi_order.order_id = "kalshi_order_456"
        kalshi_order.fill_price = kalshi_market.no_price
        kalshi_order.tx_hash = "0xkalshi456"
        
        pm_order_manager.create_fok_order.return_value = pm_order
        kalshi_order_manager.create_fok_order.return_value = kalshi_order
        
        # Mock order submission with specified fill results
        async def mock_pm_submit(order):
            return pm_fills
        
        async def mock_kalshi_submit(order):
            return kalshi_fills
        
        pm_order_manager.submit_order = AsyncMock(side_effect=mock_pm_submit)
        kalshi_order_manager.submit_order = AsyncMock(side_effect=mock_kalshi_submit)
        
        # Mock cancel_order
        pm_order_manager.cancel_order = AsyncMock(return_value=True)
        kalshi_order_manager.cancel_order = AsyncMock(return_value=True)
        
        # Create mock AI safety guard (always approves)
        ai_safety_guard = Mock(spec=AISafetyGuard)
        safety_decision = Mock()
        safety_decision.approved = True
        safety_decision.reason = "All checks passed"
        ai_safety_guard.validate_trade = AsyncMock(return_value=safety_decision)
        
        # Create mock Kelly sizer
        kelly_sizer = Mock(spec=KellyPositionSizer)
        kelly_sizer.calculate_position_size.return_value = Decimal('1.0')
        
        # Create engine
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001')
        )
        
        # Create opportunity
        opportunity = Opportunity(
            opportunity_id="test_opp_1",
            market_id=pm_market.market_id,
            strategy="cross_platform_arbitrage",
            timestamp=datetime.now(),
            yes_price=pm_market.yes_price,
            no_price=kalshi_market.no_price,
            yes_fee=Decimal('0.03'),
            no_fee=Decimal('0.03'),
            total_cost=pm_market.yes_price + kalshi_market.no_price,
            expected_profit=Decimal('0.05'),
            profit_percentage=Decimal('0.05'),
            position_size=Decimal('1.0'),
            gas_estimate=200000,
            platform_a="polymarket",
            platform_b="kalshi"
        )
        
        # Execute trade
        result = asyncio.run(engine.execute(
            opportunity=opportunity,
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            bankroll=bankroll
        ))
        
        # Verify atomicity (Requirement 3.4, 3.5)
        if pm_fills and kalshi_fills:
            # Both filled - trade should succeed
            assert result.status == "success", (
                "Trade should succeed when both orders fill"
            )
            assert result.yes_filled == True
            assert result.no_filled == True
            
            # Cancel should not be called
            pm_order_manager.cancel_order.assert_not_called()
            kalshi_order_manager.cancel_order.assert_not_called()
            
        elif pm_fills and not kalshi_fills:
            # Only PM filled - should cancel PM order (Requirement 3.5)
            assert result.status == "failed", (
                "Trade should fail when only one order fills"
            )
            assert result.yes_filled == True
            assert result.no_filled == False
            
            # PM order should be cancelled
            pm_order_manager.cancel_order.assert_called_once_with(pm_order.order_id)
            
        elif not pm_fills and kalshi_fills:
            # Only Kalshi filled - should cancel Kalshi order (Requirement 3.5)
            assert result.status == "failed", (
                "Trade should fail when only one order fills"
            )
            assert result.yes_filled == False
            assert result.no_filled == True
            
            # Kalshi order should be cancelled
            kalshi_order_manager.cancel_order.assert_called_once_with(kalshi_order.order_id)
            
        else:
            # Neither filled - trade should fail
            assert result.status == "failed", (
                "Trade should fail when neither order fills"
            )
            assert result.yes_filled == False
            assert result.no_filled == False
            
            # No cancellation needed since nothing filled
            pm_order_manager.cancel_order.assert_not_called()
            kalshi_order_manager.cancel_order.assert_not_called()
    
    @given(
        pm_market=market_strategy(),
        kalshi_market=market_strategy(),
        bankroll=st.decimals(min_value=Decimal('100'), max_value=Decimal('1000'), places=2)
    )
    @settings(max_examples=50, deadline=None)
    def test_no_partial_fills_allowed(self, pm_market, kalshi_market, bankroll):
        """
        Test that partial fills are not allowed in cross-platform arbitrage.
        
        This ensures that the system never holds unhedged positions that
        could result in losses.
        """
        # Ensure markets have the same asset
        kalshi_market.asset = pm_market.asset
        kalshi_market.question = pm_market.question
        
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        
        # Create mock order managers
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        
        # Mock order creation
        pm_order = Mock()
        pm_order.order_id = "pm_order_789"
        pm_order.fill_price = pm_market.yes_price
        pm_order.tx_hash = "0xpm789"
        
        kalshi_order = Mock()
        kalshi_order.order_id = "kalshi_order_012"
        kalshi_order.fill_price = kalshi_market.no_price
        kalshi_order.tx_hash = "0xkalshi012"
        
        pm_order_manager.create_fok_order.return_value = pm_order
        kalshi_order_manager.create_fok_order.return_value = kalshi_order
        
        # Simulate partial fill scenario: PM fills, Kalshi doesn't
        pm_order_manager.submit_order = AsyncMock(return_value=True)
        kalshi_order_manager.submit_order = AsyncMock(return_value=False)
        pm_order_manager.cancel_order = AsyncMock(return_value=True)
        kalshi_order_manager.cancel_order = AsyncMock(return_value=True)
        
        # Create mock AI safety guard
        ai_safety_guard = Mock(spec=AISafetyGuard)
        safety_decision = Mock()
        safety_decision.approved = True
        safety_decision.reason = "All checks passed"
        ai_safety_guard.validate_trade = AsyncMock(return_value=safety_decision)
        
        # Create mock Kelly sizer
        kelly_sizer = Mock(spec=KellyPositionSizer)
        kelly_sizer.calculate_position_size.return_value = Decimal('1.0')
        
        # Create engine
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001')
        )
        
        # Create opportunity
        opportunity = Opportunity(
            opportunity_id="test_opp_2",
            market_id=pm_market.market_id,
            strategy="cross_platform_arbitrage",
            timestamp=datetime.now(),
            yes_price=pm_market.yes_price,
            no_price=kalshi_market.no_price,
            yes_fee=Decimal('0.03'),
            no_fee=Decimal('0.03'),
            total_cost=pm_market.yes_price + kalshi_market.no_price,
            expected_profit=Decimal('0.05'),
            profit_percentage=Decimal('0.05'),
            position_size=Decimal('1.0'),
            gas_estimate=200000,
            platform_a="polymarket",
            platform_b="kalshi"
        )
        
        # Execute trade
        result = asyncio.run(engine.execute(
            opportunity=opportunity,
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            bankroll=bankroll
        ))
        
        # Verify no partial fills (Requirement 3.4, 3.5)
        assert result.status == "failed", (
            "Trade should fail when only one platform fills"
        )
        
        # Verify the filled order was cancelled
        pm_order_manager.cancel_order.assert_called_once_with(pm_order.order_id)
        
        # The result will show that PM filled and Kalshi didn't,
        # but the key is that the trade failed and PM order was cancelled
        # to prevent holding an unhedged position
        assert result.yes_filled == True, "PM order filled initially"
        assert result.no_filled == False, "Kalshi order did not fill"
        
        # The critical property: trade must fail to prevent unhedged position
        assert result.status == "failed", (
            "Trade must fail to prevent holding unhedged position"
        )
    
    @given(
        pm_market=market_strategy(),
        kalshi_market=market_strategy(),
        bankroll=st.decimals(min_value=Decimal('100'), max_value=Decimal('1000'), places=2)
    )
    @settings(max_examples=50, deadline=None)
    def test_exception_handling_maintains_atomicity(
        self,
        pm_market,
        kalshi_market,
        bankroll
    ):
        """
        Test that exceptions during order submission maintain atomicity.
        
        If an exception occurs on one platform, the other platform's order
        should be cancelled to prevent unhedged positions.
        """
        # Ensure markets have the same asset
        kalshi_market.asset = pm_market.asset
        kalshi_market.question = pm_market.question
        
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        
        # Create mock order managers
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        
        # Mock order creation
        pm_order = Mock()
        pm_order.order_id = "pm_order_exc"
        pm_order.fill_price = pm_market.yes_price
        pm_order.tx_hash = "0xpmexc"
        
        kalshi_order = Mock()
        kalshi_order.order_id = "kalshi_order_exc"
        kalshi_order.fill_price = kalshi_market.no_price
        kalshi_order.tx_hash = "0xkalshiexc"
        
        pm_order_manager.create_fok_order.return_value = pm_order
        kalshi_order_manager.create_fok_order.return_value = kalshi_order
        
        # Simulate exception on Kalshi, PM succeeds
        pm_order_manager.submit_order = AsyncMock(return_value=True)
        kalshi_order_manager.submit_order = AsyncMock(
            side_effect=Exception("Kalshi API error")
        )
        pm_order_manager.cancel_order = AsyncMock(return_value=True)
        
        # Create mock AI safety guard
        ai_safety_guard = Mock(spec=AISafetyGuard)
        safety_decision = Mock()
        safety_decision.approved = True
        safety_decision.reason = "All checks passed"
        ai_safety_guard.validate_trade = AsyncMock(return_value=safety_decision)
        
        # Create mock Kelly sizer
        kelly_sizer = Mock(spec=KellyPositionSizer)
        kelly_sizer.calculate_position_size.return_value = Decimal('1.0')
        
        # Create engine
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001')
        )
        
        # Create opportunity
        opportunity = Opportunity(
            opportunity_id="test_opp_exc",
            market_id=pm_market.market_id,
            strategy="cross_platform_arbitrage",
            timestamp=datetime.now(),
            yes_price=pm_market.yes_price,
            no_price=kalshi_market.no_price,
            yes_fee=Decimal('0.03'),
            no_fee=Decimal('0.03'),
            total_cost=pm_market.yes_price + kalshi_market.no_price,
            expected_profit=Decimal('0.05'),
            profit_percentage=Decimal('0.05'),
            position_size=Decimal('1.0'),
            gas_estimate=200000,
            platform_a="polymarket",
            platform_b="kalshi"
        )
        
        # Execute trade
        result = asyncio.run(engine.execute(
            opportunity=opportunity,
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            bankroll=bankroll
        ))
        
        # Verify atomicity is maintained despite exception
        assert result.status == "failed", (
            "Trade should fail when exception occurs"
        )
        
        # Verify PM order was cancelled (since Kalshi failed)
        pm_order_manager.cancel_order.assert_called_once_with(pm_order.order_id)



class TestCrossPlatformProfitAccounting:
    """
    Property 9: Cross-Platform Profit Accounting
    
    **Validates: Requirement 3.6**
    
    For any cross-platform arbitrage calculation, the profit should account
    for all fees including trading fees, withdrawal fees, and settlement costs
    on both platforms.
    """
    
    @given(
        pm_price=price_strategy,
        kalshi_price=price_strategy,
        withdrawal_fee_pm=st.decimals(min_value=Decimal('0.001'), max_value=Decimal('0.01'), places=3),
        withdrawal_fee_kalshi=st.decimals(min_value=Decimal('0.001'), max_value=Decimal('0.01'), places=3)
    )
    @settings(max_examples=100, deadline=None)
    def test_all_fees_included_in_profit_calculation(
        self,
        pm_price,
        kalshi_price,
        withdrawal_fee_pm,
        withdrawal_fee_kalshi
    ):
        """
        Test that all fees are included in profit calculations.
        
        This ensures that the system accounts for:
        - Trading fees on both platforms
        - Withdrawal fees on both platforms
        - Settlement costs
        """
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        ai_safety_guard = Mock(spec=AISafetyGuard)
        kelly_sizer = Mock(spec=KellyPositionSizer)
        
        # Create engine with specified withdrawal fees
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001'),
            withdrawal_fee_polymarket=withdrawal_fee_pm,
            withdrawal_fee_kalshi=withdrawal_fee_kalshi
        )
        
        # Create markets
        pm_market = Market(
            market_id="pm_market_fees",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=pm_price,
            no_price=Decimal('1.0') - pm_price,
            yes_token_id="pm_yes_token",
            no_token_id="pm_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        kalshi_market = Market(
            market_id="kalshi_market_fees",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('1.0') - kalshi_price,
            no_price=kalshi_price,
            yes_token_id="kalshi_yes_token",
            no_token_id="kalshi_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        # Check for arbitrage opportunity
        opportunity = engine._check_arbitrage_opportunity(
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            pm_side="YES",
            kalshi_side="NO"
        )
        
        if opportunity is not None:
            # Calculate expected costs manually
            pm_trading_fee = engine._calculate_fee(pm_price)
            kalshi_trading_fee = engine._calculate_fee(kalshi_price)
            
            # Total cost should include:
            # 1. Base prices
            # 2. Trading fees (price * fee_rate)
            # 3. Withdrawal fees (price * withdrawal_fee_rate)
            
            expected_pm_cost = pm_price * (Decimal('1') + pm_trading_fee)
            expected_kalshi_cost = kalshi_price * (Decimal('1') + kalshi_trading_fee)
            expected_pm_withdrawal = pm_price * withdrawal_fee_pm
            expected_kalshi_withdrawal = kalshi_price * withdrawal_fee_kalshi
            
            expected_total_cost = (
                expected_pm_cost + expected_kalshi_cost +
                expected_pm_withdrawal + expected_kalshi_withdrawal
            )
            
            # Verify total cost matches
            assert abs(opportunity.total_cost - expected_total_cost) < Decimal('0.0001'), (
                f"Total cost mismatch: expected ${expected_total_cost}, "
                f"got ${opportunity.total_cost}"
            )
            
            # Verify profit calculation
            expected_profit = Decimal('1.0') - expected_total_cost
            assert abs(opportunity.expected_profit - expected_profit) < Decimal('0.0001'), (
                f"Profit mismatch: expected ${expected_profit}, "
                f"got ${opportunity.expected_profit}"
            )
    
    @given(
        pm_market=market_strategy(),
        kalshi_market=market_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_profit_never_exceeds_one_dollar(self, pm_market, kalshi_market):
        """
        Test that calculated profit never exceeds $1.00.
        
        Since the maximum payout from arbitrage is $1.00 (one position pair),
        the profit after all fees should never exceed this amount.
        """
        # Ensure markets have the same asset
        kalshi_market.asset = pm_market.asset
        kalshi_market.question = pm_market.question
        
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        ai_safety_guard = Mock(spec=AISafetyGuard)
        kelly_sizer = Mock(spec=KellyPositionSizer)
        
        # Create engine
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001')
        )
        
        # Check for arbitrage opportunity
        opportunity = engine._check_arbitrage_opportunity(
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            pm_side="YES",
            kalshi_side="NO"
        )
        
        if opportunity is not None:
            # Profit should never exceed $1.00
            assert opportunity.expected_profit <= Decimal('1.0'), (
                f"Profit ${opportunity.expected_profit} exceeds maximum possible $1.00"
            )
            
            # Total cost should be at least $0.00
            assert opportunity.total_cost >= Decimal('0.0'), (
                f"Total cost ${opportunity.total_cost} is negative"
            )
            
            # Profit + total cost should equal $1.00 (the payout)
            assert abs((opportunity.expected_profit + opportunity.total_cost) - Decimal('1.0')) < Decimal('0.0001'), (
                f"Profit ${opportunity.expected_profit} + cost ${opportunity.total_cost} "
                f"should equal $1.00"
            )
    
    @given(
        pm_price=price_strategy,
        kalshi_price=price_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_higher_fees_reduce_profit(self, pm_price, kalshi_price):
        """
        Test that higher fees result in lower profits.
        
        This validates that fees are correctly subtracted from profit,
        not added to it.
        """
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        ai_safety_guard = Mock(spec=AISafetyGuard)
        kelly_sizer = Mock(spec=KellyPositionSizer)
        
        # Create engine with low fees
        engine_low_fees = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001'),
            withdrawal_fee_polymarket=Decimal('0.001'),  # 0.1%
            withdrawal_fee_kalshi=Decimal('0.001')  # 0.1%
        )
        
        # Create engine with high fees
        engine_high_fees = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001'),
            withdrawal_fee_polymarket=Decimal('0.01'),  # 1.0%
            withdrawal_fee_kalshi=Decimal('0.01')  # 1.0%
        )
        
        # Create markets
        pm_market = Market(
            market_id="pm_market_fee_test",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=pm_price,
            no_price=Decimal('1.0') - pm_price,
            yes_token_id="pm_yes_token",
            no_token_id="pm_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        kalshi_market = Market(
            market_id="kalshi_market_fee_test",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('1.0') - kalshi_price,
            no_price=kalshi_price,
            yes_token_id="kalshi_yes_token",
            no_token_id="kalshi_no_token",
            volume=Decimal('10000'),
            liquidity=Decimal('5000'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        # Check for arbitrage with both fee structures
        opp_low_fees = engine_low_fees._check_arbitrage_opportunity(
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            pm_side="YES",
            kalshi_side="NO"
        )
        
        opp_high_fees = engine_high_fees._check_arbitrage_opportunity(
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            pm_side="YES",
            kalshi_side="NO"
        )
        
        # If both opportunities exist, high fees should result in lower profit
        if opp_low_fees is not None and opp_high_fees is not None:
            assert opp_low_fees.expected_profit > opp_high_fees.expected_profit, (
                f"Higher fees should reduce profit: "
                f"low fees profit=${opp_low_fees.expected_profit}, "
                f"high fees profit=${opp_high_fees.expected_profit}"
            )
            
            # The difference should be approximately the difference in withdrawal fees
            # applied to both prices
            fee_difference = (
                (pm_price + kalshi_price) *
                (Decimal('0.01') - Decimal('0.001')) * Decimal('2')  # Both platforms
            )
            
            profit_difference = opp_low_fees.expected_profit - opp_high_fees.expected_profit
            
            # Allow some tolerance for rounding
            assert abs(profit_difference - fee_difference) < Decimal('0.01'), (
                f"Profit difference ${profit_difference} should approximately equal "
                f"fee difference ${fee_difference}"
            )
    
    @given(
        pm_market=market_strategy(),
        kalshi_market=market_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_settlement_time_accounted(self, pm_market, kalshi_market):
        """
        Test that settlement time is tracked in the opportunity.
        
        While settlement time doesn't directly affect profit calculation,
        it should be tracked for risk assessment.
        """
        # Ensure markets have the same asset
        kalshi_market.asset = pm_market.asset
        kalshi_market.question = pm_market.question
        
        # Create mock clients
        pm_client = Mock()
        kalshi_client = Mock()
        pm_order_manager = Mock(spec=OrderManager)
        kalshi_order_manager = Mock(spec=OrderManager)
        ai_safety_guard = Mock(spec=AISafetyGuard)
        kelly_sizer = Mock(spec=KellyPositionSizer)
        
        # Create engine with specified settlement time
        settlement_time = 24  # 24 hours
        engine = CrossPlatformArbitrageEngine(
            polymarket_client=pm_client,
            kalshi_client=kalshi_client,
            polymarket_order_manager=pm_order_manager,
            kalshi_order_manager=kalshi_order_manager,
            ai_safety_guard=ai_safety_guard,
            kelly_sizer=kelly_sizer,
            min_profit_threshold=Decimal('0.001'),
            settlement_time_hours=settlement_time
        )
        
        # Verify settlement time is stored
        assert engine.settlement_time_hours == settlement_time, (
            f"Settlement time should be {settlement_time} hours, "
            f"got {engine.settlement_time_hours}"
        )
        
        # Check for arbitrage opportunity
        opportunity = engine._check_arbitrage_opportunity(
            pm_market=pm_market,
            kalshi_market=kalshi_market,
            pm_side="YES",
            kalshi_side="NO"
        )
        
        # If opportunity exists, verify it's a cross-platform opportunity
        if opportunity is not None:
            assert opportunity.strategy == "cross_platform_arbitrage", (
                "Opportunity should be cross-platform arbitrage"
            )
            assert opportunity.platform_a == "polymarket"
            assert opportunity.platform_b == "kalshi"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
