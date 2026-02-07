"""
WebSocket Price Feed for Real-Time Polymarket Data.

Replaces 2-second polling with real-time WebSocket feeds for faster opportunity detection.
Provides <100ms latency compared to 2000ms polling.
"""

import asyncio
import logging
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Callable, Optional, List, Any
from dataclasses import dataclass, field
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


@dataclass
class OrderBookLevel:
    """Single level in the orderbook."""
    price: Decimal
    size: Decimal


@dataclass
class OrderBook:
    """Real-time orderbook state."""
    market_id: str
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)
    
    @property
    def best_bid(self) -> Optional[Decimal]:
        """Best bid price."""
        return self.bids[0].price if self.bids else None
    
    @property
    def best_ask(self) -> Optional[Decimal]:
        """Best ask price."""
        return self.asks[0].price if self.asks else None
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None
    
    @property
    def mid_price(self) -> Optional[Decimal]:
        """Mid price between bid and ask."""
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None


@dataclass
class PriceUpdate:
    """Real-time price update event."""
    market_id: str
    yes_price: Decimal
    no_price: Decimal
    spread: Decimal
    timestamp: datetime
    source: str = "websocket"


class WebSocketPriceFeed:
    """
    Real-time WebSocket price feed for Polymarket markets.
    
    Features:
    - Sub-100ms latency (vs 2000ms polling)
    - Automatic reconnection on disconnect
    - Local orderbook state management
    - Event-driven price updates
    - Heartbeat monitoring
    """
    
    # Polymarket WebSocket endpoints
    CLOB_WS_URL = "wss://clob.polymarket.com/ws"
    GAMMA_WS_URL = "wss://gamma-api.polymarket.com/ws"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        on_price_update: Optional[Callable[[PriceUpdate], None]] = None,
        reconnect_delay: float = 5.0,
        heartbeat_interval: float = 30.0
    ):
        """
        Initialize WebSocket Price Feed.
        
        Args:
            api_key: Optional API key for authenticated access
            on_price_update: Callback for price updates
            reconnect_delay: Delay before reconnection attempts
            heartbeat_interval: Interval for heartbeat checks
        """
        self.api_key = api_key
        self.on_price_update = on_price_update
        self.reconnect_delay = reconnect_delay
        self.heartbeat_interval = heartbeat_interval
        
        # Connection state
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._running = False
        self._subscribed_markets: List[str] = []
        
        # Local orderbook state
        self._orderbooks: Dict[str, OrderBook] = {}
        
        # Statistics
        self._messages_received = 0
        self._last_message_time: Optional[datetime] = None
        self._connection_errors = 0
        
        logger.info("WebSocket Price Feed initialized")
    
    async def connect(self) -> bool:
        """
        Establish WebSocket connection.
        
        Returns:
            True if connected successfully
        """
        try:
            # Build connection URL with auth if available
            url = self.CLOB_WS_URL
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self._ws = await websockets.connect(
                url,
                extra_headers=headers if headers else None,
                ping_interval=self.heartbeat_interval,
                ping_timeout=10.0
            )
            
            self._connected = True
            logger.info(f"WebSocket connected to {url}")
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self._connection_errors += 1
            return False
    
    async def disconnect(self):
        """Close WebSocket connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._connected = False
        logger.info("WebSocket disconnected")
    
    async def subscribe(self, market_ids: List[str]):
        """
        Subscribe to orderbook updates for markets.
        
        Args:
            market_ids: List of market IDs to subscribe to
        """
        if not self._connected or not self._ws:
            logger.warning("Cannot subscribe: not connected")
            return
        
        for market_id in market_ids:
            if market_id in self._subscribed_markets:
                continue
            
            # Send subscription message
            subscribe_msg = {
                "type": "subscribe",
                "channel": "orderbook",
                "market": market_id
            }
            
            try:
                await self._ws.send(json.dumps(subscribe_msg))
                self._subscribed_markets.append(market_id)
                
                # Initialize orderbook
                self._orderbooks[market_id] = OrderBook(market_id=market_id)
                
                logger.debug(f"Subscribed to market: {market_id}")
                
            except Exception as e:
                logger.error(f"Failed to subscribe to {market_id}: {e}")
    
    async def unsubscribe(self, market_ids: List[str]):
        """Unsubscribe from market updates."""
        if not self._connected or not self._ws:
            return
        
        for market_id in market_ids:
            if market_id not in self._subscribed_markets:
                continue
            
            unsubscribe_msg = {
                "type": "unsubscribe",
                "channel": "orderbook",
                "market": market_id
            }
            
            try:
                await self._ws.send(json.dumps(unsubscribe_msg))
                self._subscribed_markets.remove(market_id)
                
                if market_id in self._orderbooks:
                    del self._orderbooks[market_id]
                    
            except Exception as e:
                logger.error(f"Failed to unsubscribe from {market_id}: {e}")
    
    async def run(self):
        """
        Main event loop for receiving and processing messages.
        
        Handles:
        - Message receiving and parsing
        - Orderbook updates
        - Price change detection
        - Automatic reconnection
        """
        self._running = True
        
        while self._running:
            try:
                # Connect if not connected
                if not self._connected:
                    connected = await self.connect()
                    if not connected:
                        await asyncio.sleep(self.reconnect_delay)
                        continue
                    
                    # Resubscribe to markets
                    if self._subscribed_markets:
                        markets_to_resub = list(self._subscribed_markets)
                        self._subscribed_markets = []
                        await self.subscribe(markets_to_resub)
                
                # Receive message
                try:
                    message = await asyncio.wait_for(
                        self._ws.recv(),
                        timeout=self.heartbeat_interval * 2
                    )
                    
                    self._messages_received += 1
                    self._last_message_time = datetime.now()
                    
                    # Process message
                    await self._process_message(message)
                    
                except asyncio.TimeoutError:
                    # No message received, check connection health
                    logger.warning("WebSocket timeout, checking connection...")
                    continue
                    
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                self._connected = False
                await asyncio.sleep(self.reconnect_delay)
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self._connected = False
                await asyncio.sleep(self.reconnect_delay)
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")
            
            if msg_type == "orderbook_snapshot":
                await self._handle_orderbook_snapshot(data)
                
            elif msg_type == "orderbook_update":
                await self._handle_orderbook_update(data)
                
            elif msg_type == "trade":
                await self._handle_trade(data)
                
            elif msg_type == "heartbeat":
                logger.debug("Heartbeat received")
                
            elif msg_type == "error":
                logger.error(f"WebSocket error message: {data}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
    
    async def _handle_orderbook_snapshot(self, data: Dict):
        """Handle full orderbook snapshot."""
        market_id = data.get("market", "")
        if not market_id or market_id not in self._orderbooks:
            return
        
        orderbook = self._orderbooks[market_id]
        
        # Parse bids and asks
        orderbook.bids = [
            OrderBookLevel(
                price=Decimal(str(level["price"])),
                size=Decimal(str(level["size"]))
            )
            for level in data.get("bids", [])
        ]
        
        orderbook.asks = [
            OrderBookLevel(
                price=Decimal(str(level["price"])),
                size=Decimal(str(level["size"]))
            )
            for level in data.get("asks", [])
        ]
        
        orderbook.last_update = datetime.now()
        
        # Emit price update
        await self._emit_price_update(orderbook)
    
    async def _handle_orderbook_update(self, data: Dict):
        """Handle incremental orderbook update."""
        market_id = data.get("market", "")
        if not market_id or market_id not in self._orderbooks:
            return
        
        orderbook = self._orderbooks[market_id]
        
        # Apply updates
        for update in data.get("changes", []):
            side = update.get("side", "")
            price = Decimal(str(update.get("price", 0)))
            size = Decimal(str(update.get("size", 0)))
            
            levels = orderbook.bids if side == "bid" else orderbook.asks
            
            if size == 0:
                # Remove level
                levels[:] = [l for l in levels if l.price != price]
            else:
                # Update or add level
                found = False
                for level in levels:
                    if level.price == price:
                        level.size = size
                        found = True
                        break
                
                if not found:
                    levels.append(OrderBookLevel(price=price, size=size))
            
            # Re-sort
            orderbook.bids.sort(key=lambda x: x.price, reverse=True)
            orderbook.asks.sort(key=lambda x: x.price)
        
        orderbook.last_update = datetime.now()
        
        # Emit price update
        await self._emit_price_update(orderbook)
    
    async def _handle_trade(self, data: Dict):
        """Handle trade execution event."""
        logger.debug(f"Trade: {data}")
    
    async def _emit_price_update(self, orderbook: OrderBook):
        """Emit price update callback."""
        if not self.on_price_update or not orderbook.best_ask:
            return
        
        # For prediction markets, YES price is ask, NO price is 1 - ask
        yes_price = orderbook.best_ask
        no_price = Decimal('1.0') - yes_price
        
        update = PriceUpdate(
            market_id=orderbook.market_id,
            yes_price=yes_price,
            no_price=no_price,
            spread=orderbook.spread or Decimal('0'),
            timestamp=datetime.now()
        )
        
        try:
            if asyncio.iscoroutinefunction(self.on_price_update):
                await self.on_price_update(update)
            else:
                self.on_price_update(update)
        except Exception as e:
            logger.error(f"Price update callback error: {e}")
    
    def get_orderbook(self, market_id: str) -> Optional[OrderBook]:
        """Get current orderbook for a market."""
        return self._orderbooks.get(market_id)
    
    def get_price(self, market_id: str) -> Optional[Tuple[Decimal, Decimal]]:
        """Get current YES/NO prices for a market."""
        orderbook = self._orderbooks.get(market_id)
        if not orderbook or not orderbook.best_ask:
            return None
        
        yes_price = orderbook.best_ask
        no_price = Decimal('1.0') - yes_price
        return (yes_price, no_price)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get feed statistics."""
        return {
            "connected": self._connected,
            "subscribed_markets": len(self._subscribed_markets),
            "messages_received": self._messages_received,
            "last_message_time": self._last_message_time.isoformat() if self._last_message_time else None,
            "connection_errors": self._connection_errors
        }
