"""
Test order flow validation for Task 10.1.

Validates:
- create_order() is called before post_order()
- Logging for order creation and posting
- Error handling for order failures
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from decimal import Decimal
from datetime import datetime, timezone
import logging

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket, Position


@pytest.fixture
def mock_clob_client():
    """Create a mock CLOB client."""
    client = MagicMock()
    client.create_order = MagicMock(return_value={"signed": "order"})
    client.post_order = MagicMock(return_value={"orderID": "test123", "success": True})
    client.get_balance_allowance = MagicMock(return_value={"balance": "1000000000"})  # $1000 USDC
    return client


@pytest.fixture
def strategy(mock_clob_client):
    """Create a strategy instance with mocked dependencies."""
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob_client,
        trade_size=5.0,
        dry_run=False,
        enable_adaptive_learning=False  # Disable to avoid file I/O
    )
    
    # Mock risk manager to allow trades
    strategy.risk_manager.check_can_trade = Mock(return_value=Mock(
        can_trade=True,
        max_position_size=Decimal("100"),
        reason=""
    ))
    
    # Mock dynamic params
    strategy.dynamic_params.analyze_cost_benefit = Mock(return_value=(True, {"net_profit": 1.0}))
    
    return strategy


@pytest.fixture
def test_market():
    """Create a test market."""
    return CryptoMarket(
        market_id="test_market_123",
        question="Will BTC be up in 15 minutes?",
        asset="BTC",
        up_token_id="up_token_123",
        down_token_id="down_token_123",
        up_price=Decimal("0.50"),
        down_price=Decimal("0.50"),
        end_time=datetime.now(timezone.utc),
        neg_risk=True
    )


@pytest.mark.asyncio
async def test_buy_order_flow_validation(strategy, test_market, mock_clob_client, caplog):
    """
    Test that buy orders follow correct CLOB API flow:
    1. create_order() is called first
    2. post_order() is called second
    3. Both steps are logged
    """
    caplog.set_level(logging.INFO)
    
    # Place order
    result = await strategy._place_order(
        market=test_market,
        side="UP",
        price=Decimal("0.50"),
        shares=10.0,
        strategy="test"
    )
    
    # Verify order was placed successfully
    assert result is True, "Order should be placed successfully"
    
    # Verify create_order was called
    assert mock_clob_client.create_order.called, "create_order should be called"
    
    # Verify post_order was called
    assert mock_clob_client.post_order.called, "post_order should be called"
    
    # Verify create_order was called BEFORE post_order
    call_order = mock_clob_client.method_calls
    create_call_index = next(i for i, c in enumerate(call_order) if c[0] == 'create_order')
    post_call_index = next(i for i, c in enumerate(call_order) if c[0] == 'post_order')
    assert create_call_index < post_call_index, "create_order must be called before post_order"
    
    # Verify logging
    log_messages = [record.message for record in caplog.records]
    
    # Check for Step 1 logging
    assert any("CLOB API Flow - Step 1: Creating order" in msg for msg in log_messages), \
        "Should log Step 1: create_order"
    assert any("Order created and signed successfully" in msg for msg in log_messages), \
        "Should log successful order creation"
    
    # Check for Step 2 logging
    assert any("CLOB API Flow - Step 2: Posting order" in msg for msg in log_messages), \
        "Should log Step 2: post_order"
    assert any("Order posted to exchange successfully" in msg for msg in log_messages), \
        "Should log successful order posting"


@pytest.mark.asyncio
async def test_buy_order_create_error_handling(strategy, test_market, mock_clob_client, caplog):
    """
    Test error handling when create_order() fails.
    """
    caplog.set_level(logging.ERROR)
    
    # Make create_order fail
    mock_clob_client.create_order.side_effect = Exception("API error: Invalid token")
    
    # Place order
    result = await strategy._place_order(
        market=test_market,
        side="UP",
        price=Decimal("0.50"),
        shares=10.0,
        strategy="test"
    )
    
    # Verify order was NOT placed
    assert result is False, "Order should fail when create_order fails"
    
    # Verify post_order was NOT called (since create failed)
    assert not mock_clob_client.post_order.called, "post_order should NOT be called when create_order fails"
    
    # Verify error logging
    log_messages = [record.message for record in caplog.records]
    assert any("CLOB API Flow - Step 1 FAILED" in msg for msg in log_messages), \
        "Should log create_order failure"
    assert any("Order was NOT created" in msg for msg in log_messages), \
        "Should log that order was not created"


@pytest.mark.asyncio
async def test_buy_order_post_error_handling(strategy, test_market, mock_clob_client, caplog):
    """
    Test error handling when post_order() fails.
    """
    caplog.set_level(logging.ERROR)
    
    # Make post_order fail
    mock_clob_client.post_order.side_effect = Exception("API error: Rate limit exceeded")
    
    # Place order
    result = await strategy._place_order(
        market=test_market,
        side="UP",
        price=Decimal("0.50"),
        shares=10.0,
        strategy="test"
    )
    
    # Verify order was NOT placed
    assert result is False, "Order should fail when post_order fails"
    
    # Verify create_order WAS called (but post failed)
    assert mock_clob_client.create_order.called, "create_order should be called"
    
    # Verify error logging
    log_messages = [record.message for record in caplog.records]
    assert any("CLOB API Flow - Step 2 FAILED" in msg for msg in log_messages), \
        "Should log post_order failure"
    assert any("Order was created but NOT posted" in msg for msg in log_messages), \
        "Should log that order was created but not posted"


@pytest.mark.asyncio
async def test_sell_order_flow_validation(strategy, mock_clob_client, caplog):
    """
    Test that sell orders follow correct CLOB API flow:
    1. create_order() is called first
    2. post_order() is called second
    3. Both steps are logged
    """
    caplog.set_level(logging.INFO)
    
    # Create a position to close
    position = Position(
        token_id="test_token_123",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market_123",
        asset="BTC",
        strategy="test",
        neg_risk=True,
        highest_price=Decimal("0.50")
    )
    
    # Mock _get_actual_token_balance to return None (use tracked size)
    async def mock_get_balance(token_id):
        return None
    strategy._get_actual_token_balance = mock_get_balance
    
    # Close position
    result = await strategy._close_position(
        position=position,
        current_price=Decimal("0.52"),
        exit_reason="take_profit"
    )
    
    # Verify position was closed successfully
    assert result is True, "Position should be closed successfully"
    
    # Verify create_order was called
    assert mock_clob_client.create_order.called, "create_order should be called"
    
    # Verify post_order was called
    assert mock_clob_client.post_order.called, "post_order should be called"
    
    # Verify create_order was called BEFORE post_order
    call_order = mock_clob_client.method_calls
    create_call_index = next(i for i, c in enumerate(call_order) if c[0] == 'create_order')
    post_call_index = next(i for i, c in enumerate(call_order) if c[0] == 'post_order')
    assert create_call_index < post_call_index, "create_order must be called before post_order"
    
    # Verify logging
    log_messages = [record.message for record in caplog.records]
    
    # Check for Step 1 logging
    assert any("CLOB API Flow - Step 1: Creating SELL order" in msg for msg in log_messages), \
        "Should log Step 1: create_order for SELL"
    assert any("SELL order created and signed successfully" in msg for msg in log_messages), \
        "Should log successful SELL order creation"
    
    # Check for Step 2 logging
    assert any("CLOB API Flow - Step 2: Posting SELL order" in msg for msg in log_messages), \
        "Should log Step 2: post_order for SELL"


@pytest.mark.asyncio
async def test_sell_order_create_error_handling(strategy, mock_clob_client, caplog):
    """
    Test error handling when create_order() fails for sell orders.
    """
    caplog.set_level(logging.ERROR)
    
    # Create a position to close
    position = Position(
        token_id="test_token_123",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        market_id="test_market_123",
        asset="BTC",
        strategy="test",
        neg_risk=True,
        highest_price=Decimal("0.50")
    )
    
    # Mock _get_actual_token_balance
    async def mock_get_balance(token_id):
        return None
    strategy._get_actual_token_balance = mock_get_balance
    
    # Make create_order fail
    mock_clob_client.create_order.side_effect = Exception("API error: Invalid parameters")
    
    # Close position
    result = await strategy._close_position(
        position=position,
        current_price=Decimal("0.52"),
        exit_reason="take_profit"
    )
    
    # Verify position was NOT closed
    assert result is False, "Position should fail to close when create_order fails"
    
    # Verify post_order was NOT called
    assert not mock_clob_client.post_order.called, "post_order should NOT be called when create_order fails"
    
    # Verify error logging
    log_messages = [record.message for record in caplog.records]
    assert any("CLOB API Flow - Step 1 FAILED" in msg for msg in log_messages), \
        "Should log create_order failure"
    assert any("SELL order was NOT created" in msg for msg in log_messages), \
        "Should log that SELL order was not created"


@pytest.mark.asyncio
async def test_order_response_validation_and_diagnostics(strategy, test_market, mock_clob_client, caplog):
    """
    Test enhanced response validation and diagnostic hints.
    """
    caplog.set_level(logging.ERROR)
    
    # Make post_order return error response
    mock_clob_client.post_order.return_value = {
        "success": False,
        "errorMsg": "Insufficient balance to place order"
    }
    
    # Place order
    result = await strategy._place_order(
        market=test_market,
        side="UP",
        price=Decimal("0.50"),
        shares=10.0,
        strategy="test"
    )
    
    # Verify order was NOT placed
    assert result is False, "Order should fail when exchange rejects it"
    
    # Verify error logging with diagnostics
    log_messages = [record.message for record in caplog.records]
    assert any("ORDER FAILED: Exchange rejected order" in msg for msg in log_messages), \
        "Should log order rejection"
    assert any("Insufficient balance" in msg for msg in log_messages), \
        "Should log rejection reason"
    assert any("Hint: Insufficient balance or allowance" in msg for msg in log_messages), \
        "Should provide diagnostic hint"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
