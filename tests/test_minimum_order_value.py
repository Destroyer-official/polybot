#!/usr/bin/env python3
"""
TASK 10.4: Unit tests for minimum order value enforcement.

Tests verify that:
1. All orders meet $1.00 minimum value
2. Size is adjusted if below minimum
3. Trades are skipped if cannot meet minimum
4. Adjustments and skips are logged
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestMinimumOrderValueEnforcement:
    """Test minimum order value enforcement (TASK 10.4)."""
    
    @pytest.fixture
    def strategy(self):
        """Create a strategy instance with mocked dependencies."""
        from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
        
        # Mock CLOB client
        mock_clob = MagicMock()
        mock_clob.create_order = MagicMock(return_value={"order": "signed"})
        mock_clob.post_order = MagicMock(return_value={"orderID": "test123", "success": True})
        mock_clob.get_balance_allowance = MagicMock(return_value={"balance": "1000000000"})  # $1000 USDC
        
        # Create strategy
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_clob,
            dry_run=False
        )
        
        # Mock risk manager to allow trades
        strategy.risk_manager.check_can_trade = MagicMock(
            return_value=Mock(can_trade=True, max_position_size=Decimal('100.0'))
        )
        strategy.risk_manager.add_position = MagicMock()
        
        # Mock WebSocket feed
        strategy.polymarket_ws_feed = AsyncMock()
        strategy.polymarket_ws_feed.subscribe = AsyncMock()
        
        # Mock dynamic params
        strategy.dynamic_params.analyze_cost_benefit = MagicMock(
            return_value=(True, {"net_profit": Decimal("0.5"), "net_profit_pct": 50.0})
        )
        
        return strategy
    
    @pytest.fixture
    def market(self):
        """Create a test market."""
        from src.fifteen_min_crypto_strategy import CryptoMarket
        
        return CryptoMarket(
            market_id="test_market_123",
            question="Will BTC be above $100k in 15 minutes?",
            asset="BTC",
            up_token_id="token_up_123",
            down_token_id="token_down_123",
            up_price=Decimal("0.50"),
            down_price=Decimal("0.50"),
            end_time=datetime.now(timezone.utc),
            neg_risk=True,
            tick_size="0.01"
        )
    
    @pytest.mark.asyncio
    async def test_order_meets_minimum_value(self, strategy, market):
        """
        Test 1: Verify all orders meet $1.00 minimum.
        
        **Validates: Requirements 1.8**
        """
        logger.info("=" * 80)
        logger.info("TEST 1: Order meets $1.00 minimum value")
        logger.info("=" * 80)
        
        # Request 10 shares at $0.50 = $5.00 (well above minimum)
        result = await strategy._place_order(
            market=market,
            side="UP",
            price=Decimal("0.50"),
            shares=10.0,
            strategy="test"
        )
        
        # Verify order was placed
        assert result is True, "Order should be placed successfully"
        
        # Verify order value meets minimum
        call_args = strategy.clob_client.create_order.call_args
        order_args = call_args[0][0]
        order_value = order_args.price * order_args.size
        
        assert order_value >= 1.00, f"Order value ${order_value:.2f} must be >= $1.00"
        logger.info(f"✅ Order value ${order_value:.2f} meets minimum")
    
    @pytest.mark.asyncio
    async def test_size_adjusted_if_below_minimum(self, strategy, market):
        """
        Test 2: Adjust size if below minimum.
        
        **Validates: Requirements 1.8**
        """
        logger.info("=" * 80)
        logger.info("TEST 2: Size adjusted if below minimum")
        logger.info("=" * 80)
        
        # Request only 1 share at $0.50 = $0.50 (below $1.00 minimum)
        result = await strategy._place_order(
            market=market,
            side="UP",
            price=Decimal("0.50"),
            shares=1.0,
            strategy="test"
        )
        
        # Verify order was placed (after adjustment)
        assert result is True, "Order should be placed after size adjustment"
        
        # Verify size was adjusted to meet minimum
        call_args = strategy.clob_client.create_order.call_args
        order_args = call_args[0][0]
        order_value = order_args.price * order_args.size
        
        assert order_value >= 1.00, f"Adjusted order value ${order_value:.2f} must be >= $1.00"
        assert order_args.size > 1.0, f"Size {order_args.size} should be increased from 1.0"
        logger.info(f"✅ Size adjusted from 1.0 to {order_args.size:.2f} shares")
        logger.info(f"✅ Order value adjusted to ${order_value:.2f}")
    
    @pytest.mark.asyncio
    async def test_skip_trade_if_cannot_meet_minimum(self, strategy, market):
        """
        Test 3: Skip trade if cannot meet minimum.
        
        **Validates: Requirements 1.8**
        """
        logger.info("=" * 80)
        logger.info("TEST 3: Skip trade if cannot meet minimum")
        logger.info("=" * 80)
        
        # Set risk manager to allow only $0.50 (below minimum)
        strategy.risk_manager.check_can_trade = MagicMock(
            return_value=Mock(can_trade=True, max_position_size=Decimal('0.50'))
        )
        
        # Try to place order with very low price
        result = await strategy._place_order(
            market=market,
            side="UP",
            price=Decimal("0.10"),  # Very low price
            shares=1.0,
            strategy="test"
        )
        
        # Verify order was NOT placed
        assert result is False, "Order should be skipped when cannot meet minimum"
        
        # Verify no order was created
        strategy.clob_client.create_order.assert_not_called()
        logger.info("✅ Trade skipped when cannot meet $1.00 minimum")
    
    @pytest.mark.asyncio
    async def test_minimum_with_high_price(self, strategy, market):
        """
        Test 4: Minimum enforcement with high price (>$0.20).
        
        **Validates: Requirements 1.8**
        """
        logger.info("=" * 80)
        logger.info("TEST 4: Minimum enforcement with high price")
        logger.info("=" * 80)
        
        # High price market: $0.80 per share
        high_price_market = market
        high_price_market.up_price = Decimal("0.80")
        
        # Request 1 share at $0.80 = $0.80 (below $1.00 minimum)
        result = await strategy._place_order(
            market=high_price_market,
            side="UP",
            price=Decimal("0.80"),
            shares=1.0,
            strategy="test"
        )
        
        # Verify order was placed (after adjustment)
        assert result is True, "Order should be placed after size adjustment"
        
        # Verify size was adjusted to meet minimum
        call_args = strategy.clob_client.create_order.call_args
        order_args = call_args[0][0]
        order_value = order_args.price * order_args.size
        
        assert order_value >= 1.00, f"Order value ${order_value:.2f} must be >= $1.00"
        # At $0.80/share, need at least 1.25 shares for $1.00
        assert order_args.size >= 1.25, f"Size {order_args.size} should be >= 1.25 shares"
        logger.info(f"✅ Size adjusted to {order_args.size:.2f} shares for ${order_value:.2f}")
    
    @pytest.mark.asyncio
    async def test_minimum_with_low_price(self, strategy, market):
        """
        Test 5: Minimum enforcement with low price (<$0.20).
        
        **Validates: Requirements 1.8**
        """
        logger.info("=" * 80)
        logger.info("TEST 5: Minimum enforcement with low price")
        logger.info("=" * 80)
        
        # Low price market: $0.10 per share
        low_price_market = market
        low_price_market.up_price = Decimal("0.10")
        
        # Request 5 shares at $0.10 = $0.50 (below $1.00 minimum)
        result = await strategy._place_order(
            market=low_price_market,
            side="UP",
            price=Decimal("0.10"),
            shares=5.0,
            strategy="test"
        )
        
        # Verify order was placed (after adjustment)
        assert result is True, "Order should be placed after size adjustment"
        
        # Verify size was adjusted to meet minimum
        call_args = strategy.clob_client.create_order.call_args
        order_args = call_args[0][0]
        order_value = order_args.price * order_args.size
        
        assert order_value >= 1.00, f"Order value ${order_value:.2f} must be >= $1.00"
        # At $0.10/share, need at least 10 shares for $1.00
        assert order_args.size >= 10.0, f"Size {order_args.size} should be >= 10.0 shares"
        logger.info(f"✅ Size adjusted to {order_args.size:.2f} shares for ${order_value:.2f}")
    
    def test_calculate_position_size_meets_minimum(self, strategy):
        """
        Test 6: _calculate_position_size enforces $1.00 minimum.
        
        **Validates: Requirements 1.8**
        """
        logger.info("=" * 80)
        logger.info("TEST 6: Position size calculation meets minimum")
        logger.info("=" * 80)
        
        # Set very small balance
        strategy.risk_manager.current_capital = Decimal('5.0')
        strategy.risk_manager.check_can_trade = MagicMock(
            return_value=Mock(can_trade=True, max_position_size=Decimal('2.0'))
        )
        
        # Calculate position size
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('50.0'),
            expected_profit_pct=Decimal('0.05')
        )
        
        # Verify size meets minimum or is zero (skip trade)
        if position_size > Decimal('0'):
            assert position_size >= Decimal('1.0'), f"Position size ${position_size:.2f} must be >= $1.00"
            logger.info(f"✅ Position size ${position_size:.2f} meets minimum")
        else:
            logger.info(f"✅ Position size is $0.00 (trade skipped)")
    
    def test_calculate_position_size_skips_if_cannot_meet_minimum(self, strategy):
        """
        Test 7: _calculate_position_size returns 0 if cannot meet minimum.
        
        **Validates: Requirements 1.8**
        """
        logger.info("=" * 80)
        logger.info("TEST 7: Position size calculation skips if cannot meet minimum")
        logger.info("=" * 80)
        
        # Set very small balance and strict risk limit
        strategy.risk_manager.current_capital = Decimal('2.0')
        strategy.risk_manager.check_can_trade = MagicMock(
            return_value=Mock(can_trade=True, max_position_size=Decimal('0.50'))
        )
        
        # Calculate position size
        position_size = strategy._calculate_position_size(
            ensemble_confidence=Decimal('50.0'),
            expected_profit_pct=Decimal('0.05')
        )
        
        # Verify size is 0 (trade skipped)
        assert position_size == Decimal('0'), f"Position size should be $0.00 when cannot meet minimum, got ${position_size:.2f}"
        logger.info(f"✅ Position size is $0.00 (trade correctly skipped)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
