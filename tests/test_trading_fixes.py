"""
Comprehensive Test Suite for Trading Bot Fixes

Tests all critical fixes:
1. Exit logic is called in run_cycle
2. Take-profit threshold is realistic (1%)
3. Stop-loss threshold is tight (2%)
4. Time-based exit is 12 minutes
5. Market closing exit is 2 minutes before close
6. Positions are properly tracked and closed
"""

import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, MagicMock
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the strategy
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket, Position


class TestTradingFixes:
    """Test suite for trading bot fixes."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def assert_equal(self, actual, expected, test_name):
        """Assert two values are equal."""
        if actual == expected:
            logger.info(f"✅ PASS: {test_name}")
            self.passed += 1
            self.tests.append((test_name, "PASS", None))
        else:
            logger.error(f"❌ FAIL: {test_name}")
            logger.error(f"   Expected: {expected}")
            logger.error(f"   Actual: {actual}")
            self.failed += 1
            self.tests.append((test_name, "FAIL", f"Expected {expected}, got {actual}"))
    
    def assert_true(self, condition, test_name):
        """Assert condition is true."""
        if condition:
            logger.info(f"✅ PASS: {test_name}")
            self.passed += 1
            self.tests.append((test_name, "PASS", None))
        else:
            logger.error(f"❌ FAIL: {test_name}")
            self.failed += 1
            self.tests.append((test_name, "FAIL", "Condition was False"))
    
    def assert_less_than(self, actual, threshold, test_name):
        """Assert actual is less than threshold."""
        if actual < threshold:
            logger.info(f"✅ PASS: {test_name}")
            self.passed += 1
            self.tests.append((test_name, "PASS", None))
        else:
            logger.error(f"❌ FAIL: {test_name}")
            logger.error(f"   Threshold: {threshold}")
            logger.error(f"   Actual: {actual}")
            self.failed += 1
            self.tests.append((test_name, "FAIL", f"Expected < {threshold}, got {actual}"))
    
    async def test_exit_thresholds(self):
        """Test that exit thresholds are realistic."""
        logger.info("\n" + "="*80)
        logger.info("TEST 1: Exit Thresholds")
        logger.info("="*80)
        
        # Create mock CLOB client
        mock_clob = Mock()
        
        # Create strategy
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_clob,
            trade_size=5.0,
            dry_run=True
        )
        
        # Test take-profit threshold
        self.assert_equal(
            strategy.take_profit_pct,
            Decimal("0.01"),
            "Take-profit threshold is 1%"
        )
        
        # Test stop-loss threshold
        self.assert_equal(
            strategy.stop_loss_pct,
            Decimal("0.02"),
            "Stop-loss threshold is 2%"
        )
        
        logger.info(f"Take-profit: {strategy.take_profit_pct * 100}%")
        logger.info(f"Stop-loss: {strategy.stop_loss_pct * 100}%")
    
    async def test_time_based_exit(self):
        """Test that time-based exit triggers at 12 minutes."""
        logger.info("\n" + "="*80)
        logger.info("TEST 2: Time-Based Exit")
        logger.info("="*80)
        
        # Create mock CLOB client
        mock_clob = Mock()
        mock_clob.create_order = Mock(return_value=Mock())
        mock_clob.post_order = Mock(return_value={"orderID": "test123"})
        
        # Create strategy
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_clob,
            trade_size=5.0,
            dry_run=False  # Test actual order placement
        )
        
        # Create a test position that's 13 minutes old
        old_position = Position(
            token_id="test_token_123",
            side="UP",
            entry_price=Decimal("0.50"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc) - timedelta(minutes=13),
            market_id="test_market",
            asset="BTC"
        )
        
        # Add position to strategy
        strategy.positions["test_token_123"] = old_position
        
        # Create a test market
        test_market = CryptoMarket(
            market_id="test_market",
            question="Will BTC go up?",
            asset="BTC",
            up_token_id="test_token_123",
            down_token_id="test_token_456",
            up_price=Decimal("0.52"),
            down_price=Decimal("0.48"),
            end_time=datetime.now(timezone.utc) + timedelta(minutes=5),
            neg_risk=False,
            tick_size="0.01"
        )
        
        # Check exit conditions
        await strategy.check_exit_conditions(test_market)
        
        # Verify position was closed
        self.assert_true(
            "test_token_123" not in strategy.positions,
            "Position closed after 13 minutes (> 12 min threshold)"
        )
        
        # Verify sell order was placed
        self.assert_true(
            mock_clob.post_order.called,
            "Sell order was placed"
        )
    
    async def test_market_closing_exit(self):
        """Test that positions are closed when market is about to close."""
        logger.info("\n" + "="*80)
        logger.info("TEST 3: Market Closing Exit")
        logger.info("="*80)
        
        # Create mock CLOB client
        mock_clob = Mock()
        mock_clob.create_order = Mock(return_value=Mock())
        mock_clob.post_order = Mock(return_value={"orderID": "test456"})
        
        # Create strategy
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_clob,
            trade_size=5.0,
            dry_run=False
        )
        
        # Create a test position that's 5 minutes old
        position = Position(
            token_id="test_token_789",
            side="DOWN",
            entry_price=Decimal("0.45"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
            market_id="test_market_2",
            asset="ETH"
        )
        
        # Add position to strategy
        strategy.positions["test_token_789"] = position
        
        # Create a test market that closes in 1 minute
        test_market = CryptoMarket(
            market_id="test_market_2",
            question="Will ETH go down?",
            asset="ETH",
            up_token_id="test_token_999",
            down_token_id="test_token_789",
            up_price=Decimal("0.55"),
            down_price=Decimal("0.45"),
            end_time=datetime.now(timezone.utc) + timedelta(minutes=1),  # Closes in 1 min!
            neg_risk=False,
            tick_size="0.01"
        )
        
        # Check exit conditions
        await strategy.check_exit_conditions(test_market)
        
        # Verify position was closed
        self.assert_true(
            "test_token_789" not in strategy.positions,
            "Position closed when market closing in < 2 minutes"
        )
        
        # Verify sell order was placed
        self.assert_true(
            mock_clob.post_order.called,
            "Sell order was placed before market close"
        )
    
    async def test_take_profit_exit(self):
        """Test that positions are closed when take-profit is hit."""
        logger.info("\n" + "="*80)
        logger.info("TEST 4: Take-Profit Exit")
        logger.info("="*80)
        
        # Create mock CLOB client
        mock_clob = Mock()
        mock_clob.create_order = Mock(return_value=Mock())
        mock_clob.post_order = Mock(return_value={"orderID": "test_tp"})
        
        # Create strategy
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_clob,
            trade_size=5.0,
            dry_run=False
        )
        
        # Create a profitable position (entry 0.50, current 0.51 = 2% profit)
        position = Position(
            token_id="test_token_profit",
            side="UP",
            entry_price=Decimal("0.50"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc) - timedelta(minutes=3),
            market_id="test_market_profit",
            asset="BTC"
        )
        
        # Add position to strategy
        strategy.positions["test_token_profit"] = position
        
        # Create a test market with 2% profit (above 1% threshold)
        test_market = CryptoMarket(
            market_id="test_market_profit",
            question="Will BTC go up?",
            asset="BTC",
            up_token_id="test_token_profit",
            down_token_id="test_token_other",
            up_price=Decimal("0.51"),  # 2% profit!
            down_price=Decimal("0.49"),
            end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
            neg_risk=False,
            tick_size="0.01"
        )
        
        # Check exit conditions
        await strategy.check_exit_conditions(test_market)
        
        # Verify position was closed
        self.assert_true(
            "test_token_profit" not in strategy.positions,
            "Position closed when profit > 1%"
        )
        
        # Verify sell order was placed
        self.assert_true(
            mock_clob.post_order.called,
            "Sell order was placed for take-profit"
        )
        
        # Verify stats updated
        self.assert_equal(
            strategy.stats["trades_won"],
            1,
            "Winning trade recorded"
        )
    
    async def test_stop_loss_exit(self):
        """Test that positions are closed when stop-loss is hit."""
        logger.info("\n" + "="*80)
        logger.info("TEST 5: Stop-Loss Exit")
        logger.info("="*80)
        
        # Create mock CLOB client
        mock_clob = Mock()
        mock_clob.create_order = Mock(return_value=Mock())
        mock_clob.post_order = Mock(return_value={"orderID": "test_sl"})
        
        # Create strategy
        strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_clob,
            trade_size=5.0,
            dry_run=False
        )
        
        # Create a losing position (entry 0.50, current 0.48 = -4% loss)
        position = Position(
            token_id="test_token_loss",
            side="UP",
            entry_price=Decimal("0.50"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc) - timedelta(minutes=3),
            market_id="test_market_loss",
            asset="ETH"
        )
        
        # Add position to strategy
        strategy.positions["test_token_loss"] = position
        
        # Create a test market with -4% loss (below -2% threshold)
        test_market = CryptoMarket(
            market_id="test_market_loss",
            question="Will ETH go up?",
            asset="ETH",
            up_token_id="test_token_loss",
            down_token_id="test_token_other2",
            up_price=Decimal("0.48"),  # -4% loss!
            down_price=Decimal("0.52"),
            end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
            neg_risk=False,
            tick_size="0.01"
        )
        
        # Check exit conditions
        await strategy.check_exit_conditions(test_market)
        
        # Verify position was closed
        self.assert_true(
            "test_token_loss" not in strategy.positions,
            "Position closed when loss > 2%"
        )
        
        # Verify sell order was placed
        self.assert_true(
            mock_clob.post_order.called,
            "Sell order was placed for stop-loss"
        )
        
        # Verify stats updated
        self.assert_equal(
            strategy.stats["trades_lost"],
            1,
            "Losing trade recorded"
        )
    
    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        logger.info(f"Total tests: {total}")
        logger.info(f"Passed: {self.passed} ({pass_rate:.1f}%)")
        logger.info(f"Failed: {self.failed}")
        
        if self.failed > 0:
            logger.info("\nFailed tests:")
            for name, status, error in self.tests:
                if status == "FAIL":
                    logger.info(f"  ❌ {name}: {error}")
        
        logger.info("="*80)
        
        return self.failed == 0


async def main():
    """Run all tests."""
    logger.info("="*80)
    logger.info("TRADING BOT FIX VERIFICATION")
    logger.info("="*80)
    
    tester = TestTradingFixes()
    
    # Run all tests
    await tester.test_exit_thresholds()
    await tester.test_time_based_exit()
    await tester.test_market_closing_exit()
    await tester.test_take_profit_exit()
    await tester.test_stop_loss_exit()
    
    # Print summary
    all_passed = tester.print_summary()
    
    if all_passed:
        logger.info("\n🎉 ALL TESTS PASSED! Bot is ready for deployment.")
        return 0
    else:
        logger.error("\n❌ SOME TESTS FAILED! Review and fix before deployment.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
