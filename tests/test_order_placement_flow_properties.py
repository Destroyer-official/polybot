"""
Property-based tests for order placement flow correctness.

Tests that the CLOB API order flow is correct: create_order() must be called
before post_order(), and both must complete successfully.

**Validates: Requirements 1.4**
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from unittest.mock import MagicMock, Mock, call, AsyncMock
import asyncio

from src.order_manager import OrderManager
from src.transaction_manager import TransactionManager


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_mock_tx_manager():
    """Create a mock transaction manager."""
    mock = Mock(spec=TransactionManager)
    mock.get_pending_count = Mock(return_value=0)
    return mock


# ============================================================================
# STRATEGY GENERATORS
# ============================================================================

@st.composite
def order_scenario_strategy(draw):
    """Generate random order scenarios for testing."""
    market_id = f"token_{draw(st.integers(min_value=1, max_value=100000))}"
    side = draw(st.sampled_from(["YES", "NO"]))
    price = Decimal(str(draw(st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False))))
    size = Decimal(str(draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False, allow_infinity=False))))
    neg_risk = draw(st.booleans())
    tick_size = draw(st.sampled_from(["0.01", "0.001"]))
    
    return {
        "market_id": market_id,
        "side": side,
        "price": price,
        "size": size,
        "neg_risk": neg_risk,
        "tick_size": tick_size
    }


# ============================================================================
# PROPERTY 5: ORDER PLACEMENT FLOW CORRECTNESS
# ============================================================================

@given(scenario=order_scenario_strategy())
@settings(max_examples=100, deadline=None)
@pytest.mark.asyncio
async def test_property_5_order_placement_flow_correctness(scenario):
    """
    Property 5: Order Placement Flow Correctness
    
    **Validates: Requirements 1.4**
    
    Tests that:
    1. create_order() is called before post_order()
    2. Both methods complete successfully
    3. The order flow is correct for all random order scenarios
    """
    # Create mock CLOB client
    mock_clob = MagicMock()
    
    # Track method call order
    call_sequence = []
    
    def track_create_order(*args, **kwargs):
        call_sequence.append("create_order")
        return {"signed": "order_data"}
    
    def track_post_order(*args, **kwargs):
        call_sequence.append("post_order")
        return {"orderID": "test_order_123", "success": True}
    
    mock_clob.create_order = MagicMock(side_effect=track_create_order)
    mock_clob.post_order = MagicMock(side_effect=track_post_order)
    
    # Create mock transaction manager
    mock_tx_manager = create_mock_tx_manager()
    
    # Create OrderManager
    order_manager = OrderManager(
        clob_client=mock_clob,
        tx_manager=mock_tx_manager,
        dry_run=False
    )
    
    # Create and submit order
    order = order_manager.create_fok_order(
        market_id=scenario["market_id"],
        side=scenario["side"],
        price=scenario["price"],
        size=scenario["size"],
        neg_risk=scenario["neg_risk"],
        tick_size=scenario["tick_size"]
    )
    
    # Submit the order (this should call create_order then post_order)
    result = await order_manager._submit_order(order)
    
    # PROPERTY 5.1: create_order must be called before post_order
    assert len(call_sequence) == 2, \
        f"Expected 2 calls (create_order, post_order), got {len(call_sequence)}: {call_sequence}"
    
    assert call_sequence[0] == "create_order", \
        f"First call must be create_order, got {call_sequence[0]}"
    
    assert call_sequence[1] == "post_order", \
        f"Second call must be post_order, got {call_sequence[1]}"
    
    # PROPERTY 5.2: Both methods must complete successfully
    assert mock_clob.create_order.called, "create_order was not called"
    assert mock_clob.post_order.called, "post_order was not called"
    
    # PROPERTY 5.3: Result indicates successful execution
    assert result is not None, "Order submission returned None"
    assert result.get("filled") is True, f"Order not filled: {result}"


@given(scenarios=st.lists(order_scenario_strategy(), min_size=2, max_size=5))
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_5_multiple_orders_flow_correctness(scenarios):
    """
    Property 5: Order Placement Flow Correctness (Multiple Orders)
    
    **Validates: Requirements 1.4**
    
    Tests that the correct order flow is maintained across multiple
    sequential order submissions.
    """
    # Create mock CLOB client
    mock_clob = MagicMock()
    
    # Track all method calls
    call_sequence = []
    
    def track_create_order(*args, **kwargs):
        call_sequence.append("create_order")
        return {"signed": "order_data"}
    
    def track_post_order(*args, **kwargs):
        call_sequence.append("post_order")
        return {"orderID": f"order_{len(call_sequence)}", "success": True}
    
    mock_clob.create_order = MagicMock(side_effect=track_create_order)
    mock_clob.post_order = MagicMock(side_effect=track_post_order)
    
    # Create mock transaction manager
    mock_tx_manager = create_mock_tx_manager()
    
    # Create OrderManager
    order_manager = OrderManager(
        clob_client=mock_clob,
        tx_manager=mock_tx_manager,
        dry_run=False
    )
    
    # Submit multiple orders
    for scenario in scenarios:
        order = order_manager.create_fok_order(
            market_id=scenario["market_id"],
            side=scenario["side"],
            price=scenario["price"],
            size=scenario["size"],
            neg_risk=scenario["neg_risk"],
            tick_size=scenario["tick_size"]
        )
        
        result = await order_manager._submit_order(order)
        assert result.get("filled") is True, f"Order not filled: {result}"
    
    # PROPERTY 5.1: For N orders, we should have 2*N calls
    expected_calls = len(scenarios) * 2
    assert len(call_sequence) == expected_calls, \
        f"Expected {expected_calls} calls for {len(scenarios)} orders, got {len(call_sequence)}"
    
    # PROPERTY 5.2: Calls must alternate: create_order, post_order, create_order, post_order, ...
    for i in range(0, len(call_sequence), 2):
        assert call_sequence[i] == "create_order", \
            f"Call {i} should be create_order, got {call_sequence[i]}"
        assert call_sequence[i + 1] == "post_order", \
            f"Call {i+1} should be post_order, got {call_sequence[i + 1]}"


@given(scenario=order_scenario_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_5_create_order_parameters_passed_correctly(scenario):
    """
    Property 5: Order Placement Flow Correctness (Parameter Passing)
    
    **Validates: Requirements 1.4**
    
    Tests that parameters are correctly passed to create_order and post_order.
    """
    # Create mock CLOB client
    mock_clob = MagicMock()
    
    # Track calls
    create_order_called = False
    post_order_called = False
    
    def track_create_order(*args, **kwargs):
        nonlocal create_order_called
        create_order_called = True
        # Verify we received OrderArgs
        assert len(args) >= 1, "create_order should receive at least 1 positional arg"
        order_args = args[0]
        assert hasattr(order_args, "token_id"), "First arg should have token_id attribute"
        assert order_args.token_id == scenario["market_id"], \
            f"token_id mismatch: expected {scenario['market_id']}, got {order_args.token_id}"
        return {"signed": "order_data"}
    
    def track_post_order(*args, **kwargs):
        nonlocal post_order_called
        post_order_called = True
        # Verify we received the signed order
        assert len(args) >= 1, "post_order should receive at least 1 positional arg"
        signed_order = args[0]
        assert signed_order.get("signed") == "order_data", \
            "post_order did not receive the signed order from create_order"
        return {"orderID": "test_order_123", "success": True}
    
    mock_clob.create_order = MagicMock(side_effect=track_create_order)
    mock_clob.post_order = MagicMock(side_effect=track_post_order)
    
    # Create mock transaction manager
    mock_tx_manager = create_mock_tx_manager()
    
    # Create OrderManager
    order_manager = OrderManager(
        clob_client=mock_clob,
        tx_manager=mock_tx_manager,
        dry_run=False
    )
    
    # Create and submit order
    order = order_manager.create_fok_order(
        market_id=scenario["market_id"],
        side=scenario["side"],
        price=scenario["price"],
        size=scenario["size"],
        neg_risk=scenario["neg_risk"],
        tick_size=scenario["tick_size"]
    )
    
    result = await order_manager._submit_order(order)
    
    # PROPERTY 5.3: Both methods were called
    assert create_order_called, "create_order was not called"
    assert post_order_called, "post_order was not called"
    
    # PROPERTY 5.4: Result indicates successful execution
    assert result is not None, "Order submission returned None"
    assert result.get("filled") is True, f"Order not filled: {result}"


@given(scenario=order_scenario_strategy())
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property_5_order_flow_failure_handling(scenario):
    """
    Property 5: Order Placement Flow Correctness (Failure Handling)
    
    **Validates: Requirements 1.4**
    
    Tests that if create_order fails, post_order is never called.
    """
    # Create mock CLOB client
    mock_clob = MagicMock()
    
    # Make create_order fail
    mock_clob.create_order = MagicMock(side_effect=Exception("create_order failed"))
    mock_clob.post_order = MagicMock(return_value={"orderID": "should_not_be_called"})
    
    # Create mock transaction manager
    mock_tx_manager = create_mock_tx_manager()
    
    # Create OrderManager
    order_manager = OrderManager(
        clob_client=mock_clob,
        tx_manager=mock_tx_manager,
        dry_run=False
    )
    
    # Create order
    order = order_manager.create_fok_order(
        market_id=scenario["market_id"],
        side=scenario["side"],
        price=scenario["price"],
        size=scenario["size"],
        neg_risk=scenario["neg_risk"],
        tick_size=scenario["tick_size"]
    )
    
    # Try to submit order (should fail)
    with pytest.raises(Exception):
        await order_manager._submit_order(order)
    
    # PROPERTY 5.6: If create_order fails, post_order must not be called
    assert mock_clob.create_order.called, "create_order should have been called"
    assert not mock_clob.post_order.called, \
        "post_order should NOT be called if create_order fails"
