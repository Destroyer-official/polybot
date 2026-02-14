"""
Polymarket WebSocket Price Feed.

Real-time price updates for Polymarket tokens via WebSocket.
Replaces polling with sub-second latency price feeds.

WebSocket URL: wss://ws-subscriptions-clob.polymarket.com/ws/
"""

import asyncio
import inspect
import json
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, Set, Callable
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class TokenPrice:
    """Real-time token price data."""
    token_id: str
    price: Decimal
    timestamp: datetime
    source: str = "polymarket_ws"


class PolymarketWebSocketFeed:
    """
    Real-time WebSocket price feed for Polymarket tokens.
    
    Features:
    - Subscribe to token price updates
    - Maintain real-time price cache with timestamps
    - Auto-reconnect on disconnect with exponential backoff
    - Thread-safe access to price cache
    
    WebSocket URL: wss://ws-subscriptions-clob.polymarket.com/ws/
    """
    
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/"
    
    def __init__(
        self,
        on_price_update: Optional[Callable[[TokenPrice], None]] = None,
        initial_reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
        heartbeat_interval: float = 30.0
    ):
        """
        Initialize Polymarket WebSocket feed.
        
        Args:
            on_price_update: Optional callback for price updates
            initial_reconnect_delay: Initial delay before reconnection (seconds)
            max_reconnect_delay: Maximum delay before reconnection (seconds)
            heartbeat_interval: Interval for heartbeat checks (seconds)
        """
        self.on_price_update = on_price_update
        self.initial_reconnect_delay = initial_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.heartbeat_interval = heartbeat_interval
        
        # Connection state
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        self._running = False
        self._reconnect_delay = initial_reconnect_delay
        
        # Subscription state
        self._subscribed_tokens: Set[str] = set()
        
        # Price cache (thread-safe with asyncio)
        self._price_cache: Dict[str, TokenPrice] = {}
        self._cache_lock = asyncio.Lock()
        
        # Statistics
        self._messages_received = 0
        self._last_message_time: Optional[datetime] = None
        self._connection_errors = 0
        self._reconnect_count = 0
        
        logger.info("PolymarketWebSocketFeed initialized")
    
    async def connect(self) -> bool:
        """
        Establish WebSocket connection.
        
        Returns:
            True if connected successfully
        """
        try:
            if not self._session:
                self._session = aiohttp.ClientSession()
            
            logger.info(f"Connecting to Polymarket WebSocket: {self.WS_URL}")
            
            self._ws = await self._session.ws_connect(
                self.WS_URL,
                heartbeat=self.heartbeat_interval,
                timeout=aiohttp.ClientTimeout(total=30)
            )
            
            self._connected = True
            self._reconnect_delay = self.initial_reconnect_delay  # Reset backoff
            logger.info("✅ Connected to Polymarket WebSocket")
            
            return True
            
        except Exception as e:
            # Polymarket WebSocket endpoint sometimes returns 404
            # This is non-critical as bot uses REST API for all operations
            # WebSocket is only for optional real-time price updates
            if "404" in str(e) or "Invalid response status" in str(e):
                logger.debug(f"Polymarket WebSocket unavailable (404) - using REST API instead")
            else:
                logger.error(f"❌ WebSocket connection failed: {e}")
            self._connection_errors += 1
            return False
    
    async def disconnect(self):
        """Close WebSocket connection and cleanup."""
        logger.info("Disconnecting from Polymarket WebSocket")
        self._running = False
        self._connected = False
        
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        if self._session:
            await self._session.close()
            self._session = None
        
        logger.info("WebSocket disconnected")
    
    async def subscribe(self, token_ids: list[str]):
        """
        Subscribe to price updates for tokens.
        
        Args:
            token_ids: List of token IDs to subscribe to
        """
        if not self._connected or not self._ws:
            logger.warning("Cannot subscribe: not connected")
            return
        
        for token_id in token_ids:
            if token_id in self._subscribed_tokens:
                continue
            
            # Send subscription message
            subscribe_msg = {
                "type": "subscribe",
                "channel": "book",
                "market": token_id,
                "assets_ids": [token_id]
            }
            
            try:
                await self._ws.send_json(subscribe_msg)
                self._subscribed_tokens.add(token_id)
                
                logger.debug(f"Subscribed to token: {token_id}")
                
            except Exception as e:
                logger.error(f"Failed to subscribe to {token_id}: {e}")
    
    async def unsubscribe(self, token_ids: list[str]):
        """
        Unsubscribe from token price updates.
        
        Args:
            token_ids: List of token IDs to unsubscribe from
        """
        if not self._connected or not self._ws:
            return
        
        for token_id in token_ids:
            if token_id not in self._subscribed_tokens:
                continue
            
            unsubscribe_msg = {
                "type": "unsubscribe",
                "channel": "book",
                "market": token_id
            }
            
            try:
                await self._ws.send_json(unsubscribe_msg)
                self._subscribed_tokens.remove(token_id)
                
                # Remove from cache
                async with self._cache_lock:
                    if token_id in self._price_cache:
                        del self._price_cache[token_id]
                
                logger.debug(f"Unsubscribed from token: {token_id}")
                
            except Exception as e:
                logger.error(f"Failed to unsubscribe from {token_id}: {e}")
    
    async def run(self):
        """
        Main event loop for receiving and processing messages.
        
        Handles:
        - Message receiving and parsing
        - Price updates
        - Automatic reconnection with exponential backoff
        """
        self._running = True
        
        while self._running:
            try:
                # Connect if not connected
                if not self._connected:
                    connected = await self.connect()
                    if not connected:
                        # Exponential backoff (but don't spam logs for 404 errors)
                        if self._connection_errors <= 3:
                            logger.info(f"Reconnecting in {self._reconnect_delay:.1f}s...")
                        await asyncio.sleep(self._reconnect_delay)
                        self._reconnect_delay = min(
                            self._reconnect_delay * 2,
                            self.max_reconnect_delay
                        )
                        self._reconnect_count += 1
                        continue
                    
                    # Resubscribe to tokens
                    if self._subscribed_tokens:
                        tokens_to_resub = list(self._subscribed_tokens)
                        self._subscribed_tokens.clear()
                        await self.subscribe(tokens_to_resub)
                
                # Receive message
                try:
                    msg = await asyncio.wait_for(
                        self._ws.receive(),
                        timeout=self.heartbeat_interval * 2
                    )
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self._messages_received += 1
                        self._last_message_time = datetime.now()
                        await self._process_message(msg.data)
                        
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        logger.warning("WebSocket closed by server")
                        self._connected = False
                        
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket error: {msg.data}")
                        self._connected = False
                    
                except asyncio.TimeoutError:
                    # No message received, check connection health
                    logger.debug("WebSocket timeout, connection still alive")
                    continue
                    
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self._connected = False
                await asyncio.sleep(self._reconnect_delay)
    
    async def _process_message(self, message: str):
        """
        Process incoming WebSocket message.
        
        Args:
            message: JSON message from Polymarket
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")
            
            if msg_type == "book":
                # Orderbook update
                await self._handle_book_update(data)
                
            elif msg_type == "last_trade_price":
                # Last trade price update
                await self._handle_trade_price(data)
                
            elif msg_type == "error":
                logger.error(f"WebSocket error message: {data}")
                
            elif msg_type == "subscribed":
                logger.debug(f"Subscription confirmed: {data}")
                
            else:
                logger.debug(f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _handle_book_update(self, data: Dict):
        """
        Handle orderbook update message.
        
        Extracts best bid/ask prices and updates cache.
        """
        try:
            asset_id = data.get("asset_id", "")
            if not asset_id:
                return
            
            # Extract best bid and ask
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            
            if not asks:
                return
            
            # Best ask price (lowest sell price)
            best_ask = Decimal(str(asks[0]["price"])) if asks else None
            
            if best_ask:
                await self._update_price_cache(asset_id, best_ask)
                
        except Exception as e:
            logger.error(f"Error handling book update: {e}")
    
    async def _handle_trade_price(self, data: Dict):
        """
        Handle last trade price update.
        
        Updates cache with most recent trade price.
        """
        try:
            asset_id = data.get("asset_id", "")
            price_str = data.get("price", "")
            
            if not asset_id or not price_str:
                return
            
            price = Decimal(str(price_str))
            await self._update_price_cache(asset_id, price)
            
        except Exception as e:
            logger.error(f"Error handling trade price: {e}")
    
    async def _update_price_cache(self, token_id: str, price: Decimal):
        """
        Update price cache with new price.
        
        Args:
            token_id: Token ID
            price: New price
        """
        token_price = TokenPrice(
            token_id=token_id,
            price=price,
            timestamp=datetime.now()
        )
        
        async with self._cache_lock:
            self._price_cache[token_id] = token_price
        
        # Trigger callback if provided
        if self.on_price_update:
            try:
                if inspect.iscoroutinefunction(self.on_price_update):
                    await self.on_price_update(token_price)
                else:
                    self.on_price_update(token_price)
            except Exception as e:
                logger.error(f"Price update callback error: {e}")
    
    async def get_price(self, token_id: str) -> Optional[TokenPrice]:
        """
        Get current price for a token from cache.
        
        Args:
            token_id: Token ID
            
        Returns:
            TokenPrice or None if not available
        """
        async with self._cache_lock:
            return self._price_cache.get(token_id)
    
    async def get_all_prices(self) -> Dict[str, TokenPrice]:
        """
        Get all cached prices.
        
        Returns:
            Dictionary of token_id -> TokenPrice
        """
        async with self._cache_lock:
            return self._price_cache.copy()
    
    def get_statistics(self) -> Dict:
        """
        Get feed statistics.
        
        Returns:
            Dictionary with connection and performance stats
        """
        return {
            "connected": self._connected,
            "running": self._running,
            "subscribed_tokens": len(self._subscribed_tokens),
            "cached_prices": len(self._price_cache),
            "messages_received": self._messages_received,
            "last_message_time": self._last_message_time.isoformat() if self._last_message_time else None,
            "connection_errors": self._connection_errors,
            "reconnect_count": self._reconnect_count,
            "current_reconnect_delay": self._reconnect_delay
        }


# Example usage
async def main():
    """Example usage of Polymarket WebSocket feed."""
    
    async def on_price_update(token_price: TokenPrice):
        """Callback when price update received."""
        print(f"[{token_price.timestamp}] Token {token_price.token_id}: ${token_price.price}")
    
    # Create feed
    feed = PolymarketWebSocketFeed(on_price_update=on_price_update)
    
    # Start feed
    feed_task = asyncio.create_task(feed.run())
    
    # Wait for connection
    await asyncio.sleep(2)
    
    # Subscribe to some tokens (example token IDs)
    await feed.subscribe([
        "21742633143463906290569050155826241533067272736897614950488156847949938836455",
        "21742633143463906290569050155826241533067272736897614950488156847949938836456"
    ])
    
    # Run for 60 seconds
    await asyncio.sleep(60)
    
    # Print statistics
    stats = feed.get_statistics()
    print(f"\nStatistics: {stats}")
    
    # Cleanup
    await feed.disconnect()
    feed_task.cancel()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
