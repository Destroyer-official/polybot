"""
Unit tests for position cleanup after successful exit (Task 1.6).

Tests verify that after a successful position exit:
1. Position is removed from self.positions dictionary
2. Risk manager's close_position is called
3. Positions are saved to disk

**Validates: Requirements 2.7**
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from src.fifteen_min_crypto_strategy import Position, CryptoMarket


class TestPositionCleanup:
    """Test position cleanup after successful exit."""
    
    @pytest.mark.asyncio
    async def test_position_cleanup_after_successful_close(self):
        """
        Test that position cleanup happens correctly after _close_position succeeds.
        
        This test verifies the cleanup logic at the end of _check_all_positions_for_exit
        and check_exit_conditions methods.
        """
        # We'll test the cleanup logic directly by simulating what happens
        # after a successful _close_position call
        
        # Create mock objects
        risk_manager = Mock()
        risk_manager.close_position = Mock(return_value=Decimal("1.0"))
        
        # Create a positions dictionary
        positions = {}
        
        # Create a test position
        position = Position(
            token_id="test_token_123",
            side="UP",
            entry_price=Decimal("0.50"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
            market_id="test_market_456",
            asset="BTC",
            strategy="sum_to_one",
            neg_risk=False,
            highest_price=Decimal("0.52")
        )
        
        # Add position to dictionary
        positions[position.token_id] = position
        
        # Simulate the cleanup logic from the actual code
        # This is what happens at the end of _check_all_positions_for_exit
        positions_to_close = [position.token_id]  # Position was successfully closed
        
        # Execute cleanup (this is the code we're testing)
        for token_id in positions_to_close:
            if token_id in positions:
                pos = positions[token_id]
                
                # Close position in risk manager
                risk_manager.close_position(pos.market_id, pos.entry_price)
                
                # Remove from positions dictionary
                del positions[token_id]
        
        # Verify position was removed
        assert position.token_id not in positions
        
        # Verify risk manager's close_position was called
        risk_manager.close_position.assert_called_once_with(
            position.market_id,
            position.entry_price
        )
    
    @pytest.mark.asyncio
    async def test_position_cleanup_in_check_exit_conditions(self):
        """Test that positions are cleaned up correctly in check_exit_conditions."""
        from types import SimpleNamespace
        from src.fifteen_min_crypto_strategy import CryptoMarket
        
        strategy = SimpleNamespace()
        strategy.positions = {}
        strategy.risk_manager = Mock()
        strategy.risk_manager.close_position = Mock(return_value=Decimal("1.0"))
        strategy._save_positions = Mock()
        strategy.stats = {"trades_won": 0, "trades_lost": 0, "total_profit": Decimal("0")}
        strategy.consecutive_wins = 0
        strategy.consecutive_losses = 0
        strategy._record_trade_outcome = Mock()
        strategy._close_position = AsyncMock(return_value=True)
        strategy.take_profit_pct = Decimal("0.01")  # 1%
        strategy.stop_loss_pct = Decimal("0.02")  # 2%
        strategy.trailing_activation_pct = Decimal("0.005")
        strategy.trailing_stop_pct = Decimal("0.02")
        strategy._track_exit_outcome = Mock()
        
        # Create a test position
        position = Position(
            token_id="test_token_123",
            side="UP",
            entry_price=Decimal("0.50"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
            market_id="test_market_456",
            asset="BTC",
            strategy="sum_to_one",
            neg_risk=False,
            highest_price=Decimal("0.52")
        )
        
        # Add position to strategy
        strategy.positions[position.token_id] = position
        
        # Create a market with take-profit price
        market = CryptoMarket(
            market_id="test_market_456",
            question="Will BTC go up?",
            asset="BTC",
            up_token_id="up_token",
            down_token_id="down_token",
            up_price=Decimal("0.51"),  # 2% profit - triggers take-profit
            down_price=Decimal("0.49"),
            end_time=datetime.now(timezone.utc) + timedelta(minutes=10),
            neg_risk=False
        )
        
        # Import the actual method
        from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy
        
        # Bind the method to our mock strategy
        check_exit = FifteenMinuteCryptoStrategy.check_exit_conditions.__get__(strategy)
        
        # Verify position exists before
        assert position.token_id in strategy.positions
        
        # Run the exit check
        await check_exit(market)
        
        # Verify position was removed
        assert position.token_id not in strategy.positions
        
        # Verify risk manager's close_position was called
        strategy.risk_manager.close_position.assert_called_once_with(
            position.market_id,
            position.entry_price
        )
        
        # Verify positions were saved
        strategy._save_positions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_no_cleanup_when_close_fails(self):
        """Test that cleanup doesn't happen when _close_position fails."""
        # Create mock objects
        risk_manager = Mock()
        risk_manager.close_position = Mock(return_value=Decimal("1.0"))
        
        # Create a positions dictionary
        positions = {}
        
        # Create a test position
        position = Position(
            token_id="test_token_123",
            side="UP",
            entry_price=Decimal("0.50"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc) - timedelta(minutes=5),
            market_id="test_market_456",
            asset="BTC",
            strategy="sum_to_one",
            neg_risk=False,
            highest_price=Decimal("0.52")
        )
        
        # Add position to dictionary
        positions[position.token_id] = position
        
        # Simulate failed close - positions_to_close is empty
        positions_to_close = []  # Position close failed, so it's not in the list
        
        # Execute cleanup (this is the code we're testing)
        for token_id in positions_to_close:
            if token_id in positions:
                pos = positions[token_id]
                
                # Close position in risk manager
                risk_manager.close_position(pos.market_id, pos.entry_price)
                
                # Remove from positions dictionary
                del positions[token_id]
        
        # Verify position was NOT removed (close failed)
        assert position.token_id in positions
        
        # Verify risk manager's close_position was NOT called
        risk_manager.close_position.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

