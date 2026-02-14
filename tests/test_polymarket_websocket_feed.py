"""
Unit tests for Polymarket WebSocket Price Feed.

Tests:
- Connection and disconnection
- Subscription management
- Price cache updates
- Auto-reconnect with exponential backoff
- Thread-safe cache access
"""

import asyncio
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from src.polymarket_websocket_feed import (
    PolymarketWebSocketFeed,
    TokenPrice
)


@pytest.fixture
def feed():
    """Create a WebSocket feed instance for testing."""
    return PolymarketWebSocketFeed(
        initial_reconnect_delay=0.1,
        max_reconnect_delay=1.0,
        heartbeat_interval=5.0
    )


@pytest.mark.asyncio
async def test_initialization():
    """Test feed initialization."""
    feed = PolymarketWebSocketFeed()
    
    assert feed.WS_URL == "wss://ws-subscriptions-clob.polymarket.com/ws/"
    assert not feed._connected
    assert not feed._running
    assert len(feed._subscribed_tokens) == 0
    assert len(feed._price_cache) == 0


@pytest.mark.asyncio
async def test_connect_success(feed):
    """Test successful WebSocket connection."""
    mock_ws = AsyncMock()
    mock_session = AsyncMock()
    mock_session.ws_connect = AsyncMock(return_value=mock_ws)
    
    feed._session = mock_session
    
    result = await feed.connect()
    
    assert result is True
    assert feed._connected is True
    assert feed._ws == mock_ws
    mock_session.ws_connect.assert_called_once()


@pytest.mark.asyncio
async def test_connect_failure(feed):
    """Test WebSocket connection failure."""
    mock_session = AsyncMock()
    mock_session.ws_connect = AsyncMock(side_effect=Exception("Connection failed"))
    
    feed._session = mock_session
    
    result = await feed.connect()
    
    assert result is False
    assert feed._connected is False
    assert feed._connection_errors == 1


@pytest.mark.asyncio
async def test_disconnect(feed):
    """Test WebSocket disconnection."""
    mock_ws = AsyncMock()
    mock_session = AsyncMock()
    
    feed._ws = mock_ws
    feed._session = mock_session
    feed._connected = True
    feed._running = True
    
    await feed.disconnect()
    
    assert feed._connected is False
    assert feed._running is False
    mock_ws.close.assert_called_once()
    mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_subscribe_tokens(feed):
    """Test subscribing to token price updates."""
    mock_ws = AsyncMock()
    feed._ws = mock_ws
    feed._connected = True
    
    token_ids = ["token1", "token2"]
    
    await feed.subscribe(token_ids)
    
    assert len(feed._subscribed_tokens) == 2
    assert "token1" in feed._subscribed_tokens
    assert "token2" in feed._subscribed_tokens
    assert mock_ws.send_json.call_count == 2


@pytest.mark.asyncio
async def test_subscribe_when_not_connected(feed):
    """Test subscribing when not connected."""
    feed._connected = False
    
    await feed.subscribe(["token1"])
    
    assert len(feed._subscribed_tokens) == 0


@pytest.mark.asyncio
async def test_subscribe_duplicate_tokens(feed):
    """Test subscribing to already subscribed tokens."""
    mock_ws = AsyncMock()
    feed._ws = mock_ws
    feed._connected = True
    feed._subscribed_tokens.add("token1")
    
    await feed.subscribe(["token1"])
    
    # Should not send duplicate subscription
    mock_ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_unsubscribe_tokens(feed):
    """Test unsubscribing from token updates."""
    mock_ws = AsyncMock()
    feed._ws = mock_ws
    feed._connected = True
    feed._subscribed_tokens = {"token1", "token2"}
    
    # Add to cache
    feed._price_cache["token1"] = TokenPrice(
        token_id="token1",
        price=Decimal("0.50"),
        timestamp=datetime.now()
    )
    
    await feed.unsubscribe(["token1"])
    
    assert "token1" not in feed._subscribed_tokens
    assert "token2" in feed._subscribed_tokens
    assert "token1" not in feed._price_cache
    mock_ws.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_update_price_cache(feed):
    """Test updating price cache."""
    token_id = "token1"
    price = Decimal("0.55")
    
    await feed._update_price_cache(token_id, price)
    
    cached_price = await feed.get_price(token_id)
    
    assert cached_price is not None
    assert cached_price.token_id == token_id
    assert cached_price.price == price
    assert cached_price.source == "polymarket_ws"


@pytest.mark.asyncio
async def test_get_price_not_found(feed):
    """Test getting price for non-existent token."""
    result = await feed.get_price("nonexistent")
    
    assert result is None


@pytest.mark.asyncio
async def test_get_all_prices(feed):
    """Test getting all cached prices."""
    # Add multiple prices
    await feed._update_price_cache("token1", Decimal("0.50"))
    await feed._update_price_cache("token2", Decimal("0.60"))
    
    all_prices = await feed.get_all_prices()
    
    assert len(all_prices) == 2
    assert "token1" in all_prices
    assert "token2" in all_prices
    assert all_prices["token1"].price == Decimal("0.50")
    assert all_prices["token2"].price == Decimal("0.60")


@pytest.mark.asyncio
async def test_handle_book_update(feed):
    """Test handling orderbook update message."""
    data = {
        "type": "book",
        "asset_id": "token1",
        "bids": [
            {"price": "0.48", "size": "100"}
        ],
        "asks": [
            {"price": "0.52", "size": "100"}
        ]
    }
    
    await feed._handle_book_update(data)
    
    cached_price = await feed.get_price("token1")
    
    assert cached_price is not None
    assert cached_price.price == Decimal("0.52")  # Best ask


@pytest.mark.asyncio
async def test_handle_trade_price(feed):
    """Test handling trade price update."""
    data = {
        "type": "last_trade_price",
        "asset_id": "token1",
        "price": "0.55"
    }
    
    await feed._handle_trade_price(data)
    
    cached_price = await feed.get_price("token1")
    
    assert cached_price is not None
    assert cached_price.price == Decimal("0.55")


@pytest.mark.asyncio
async def test_price_update_callback(feed):
    """Test price update callback is triggered."""
    callback_called = False
    received_price = None
    
    async def callback(token_price: TokenPrice):
        nonlocal callback_called, received_price
        callback_called = True
        received_price = token_price
    
    feed.on_price_update = callback
    
    await feed._update_price_cache("token1", Decimal("0.50"))
    
    assert callback_called is True
    assert received_price is not None
    assert received_price.token_id == "token1"
    assert received_price.price == Decimal("0.50")


@pytest.mark.asyncio
async def test_exponential_backoff():
    """Test exponential backoff on reconnection."""
    feed = PolymarketWebSocketFeed(
        initial_reconnect_delay=1.0,
        max_reconnect_delay=16.0
    )
    
    # Simulate failed connections
    assert feed._reconnect_delay == 1.0
    
    # First failure
    feed._reconnect_delay = min(feed._reconnect_delay * 2, feed.max_reconnect_delay)
    assert feed._reconnect_delay == 2.0
    
    # Second failure
    feed._reconnect_delay = min(feed._reconnect_delay * 2, feed.max_reconnect_delay)
    assert feed._reconnect_delay == 4.0
    
    # Third failure
    feed._reconnect_delay = min(feed._reconnect_delay * 2, feed.max_reconnect_delay)
    assert feed._reconnect_delay == 8.0
    
    # Fourth failure
    feed._reconnect_delay = min(feed._reconnect_delay * 2, feed.max_reconnect_delay)
    assert feed._reconnect_delay == 16.0
    
    # Fifth failure (should cap at max)
    feed._reconnect_delay = min(feed._reconnect_delay * 2, feed.max_reconnect_delay)
    assert feed._reconnect_delay == 16.0


@pytest.mark.asyncio
async def test_statistics(feed):
    """Test getting feed statistics."""
    feed._connected = True
    feed._running = True
    feed._subscribed_tokens = {"token1", "token2"}
    feed._messages_received = 100
    feed._connection_errors = 2
    feed._reconnect_count = 3
    
    await feed._update_price_cache("token1", Decimal("0.50"))
    
    stats = feed.get_statistics()
    
    assert stats["connected"] is True
    assert stats["running"] is True
    assert stats["subscribed_tokens"] == 2
    assert stats["cached_prices"] == 1
    assert stats["messages_received"] == 100
    assert stats["connection_errors"] == 2
    assert stats["reconnect_count"] == 3


@pytest.mark.asyncio
async def test_thread_safe_cache_access(feed):
    """Test thread-safe concurrent cache access."""
    # Simulate concurrent updates
    tasks = []
    for i in range(10):
        task = feed._update_price_cache(f"token{i}", Decimal(f"0.{i}"))
        tasks.append(task)
    
    await asyncio.gather(*tasks)
    
    # Verify all prices were cached
    all_prices = await feed.get_all_prices()
    assert len(all_prices) == 10
    
    # Verify concurrent reads
    read_tasks = [feed.get_price(f"token{i}") for i in range(10)]
    results = await asyncio.gather(*read_tasks)
    
    assert len(results) == 10
    assert all(r is not None for r in results)


@pytest.mark.asyncio
async def test_process_message_invalid_json(feed):
    """Test handling invalid JSON message."""
    # Should not raise exception
    await feed._process_message("invalid json {")
    
    # Cache should be empty
    all_prices = await feed.get_all_prices()
    assert len(all_prices) == 0


@pytest.mark.asyncio
async def test_process_message_unknown_type(feed):
    """Test handling unknown message type."""
    message = '{"type": "unknown", "data": "test"}'
    
    # Should not raise exception
    await feed._process_message(message)
    
    # Cache should be empty
    all_prices = await feed.get_all_prices()
    assert len(all_prices) == 0


@pytest.mark.asyncio
async def test_resubscribe_after_reconnect(feed):
    """Test resubscribing to tokens after reconnection."""
    mock_ws = AsyncMock()
    mock_session = AsyncMock()
    mock_session.ws_connect = AsyncMock(return_value=mock_ws)
    
    feed._session = mock_session
    feed._subscribed_tokens = {"token1", "token2"}
    
    # Simulate reconnection
    await feed.connect()
    
    # Should be ready to resubscribe
    assert feed._connected is True
    
    # Resubscribe
    tokens_to_resub = list(feed._subscribed_tokens)
    feed._subscribed_tokens.clear()
    await feed.subscribe(tokens_to_resub)
    
    assert len(feed._subscribed_tokens) == 2
    assert mock_ws.send_json.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
