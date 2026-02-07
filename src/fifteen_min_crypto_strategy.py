"""
15-Minute Crypto Trading Strategy for Polymarket.

Implements the most profitable strategies used by top bots in 2026:
1. Binance Latency Arbitrage - Front-run Polymarket prices based on Binance moves
2. Sum-to-One Arbitrage - Buy YES+NO when total < $1.00 for guaranteed profit
3. Auto Sell on Profit - Exit positions when take-profit or stop-loss hit

Based on research from:
- gabagool222/Polymarket-Arbitrage-Trading-Bot
- Novus-Tech-LLC/Polymarket-Arbitrage-Bot
- discountry/polymarket-trading-bot
"""

import asyncio
import aiohttp
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from types import SimpleNamespace
from dataclasses import dataclass
from collections import deque

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

logger = logging.getLogger(__name__)


@dataclass
class CryptoMarket:
    """Represents a 15-minute crypto market."""
    market_id: str
    question: str
    asset: str  # BTC or ETH
    up_token_id: str
    down_token_id: str
    up_price: Decimal
    down_price: Decimal
    end_time: datetime
    neg_risk: bool = True


@dataclass
class Position:
    """Tracks an open position."""
    token_id: str
    side: str  # "UP" or "DOWN"
    entry_price: Decimal
    size: Decimal
    entry_time: datetime
    market_id: str
    asset: str


class BinancePriceFeed:
    """
    Real-time Binance price feed for latency arbitrage.
    
    Monitors BTC/USDT and ETH/USDT to detect large price moves
    before Polymarket reacts.
    """
    
    def __init__(self):
        self.prices: Dict[str, Decimal] = {"BTC": Decimal("0"), "ETH": Decimal("0")}
        self.price_history: Dict[str, deque] = {
            "BTC": deque(maxlen=60),  # 1 minute of prices
            "ETH": deque(maxlen=60),
        }
        self.is_running = False
        self._ws_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the Binance WebSocket feed."""
        if self.is_running:
            return
        
        self.is_running = True
        self._ws_task = asyncio.create_task(self._run_websocket())
        logger.info("🔗 Binance price feed started")
    
    async def stop(self):
        """Stop the Binance WebSocket feed."""
        self.is_running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        logger.info("🔗 Binance price feed stopped")
    
    async def _run_websocket(self):
        """Connect to Binance WebSocket for real-time prices."""
        urls = [
            "wss://stream.binance.com:9443/ws/btcusdt@trade/ethusdt@trade",
            "wss://stream.binance.us:9443/ws/btcusdt@trade/ethusdt@trade"
        ]
        
        current_url_index = 0
        
        while self.is_running:
            url = urls[current_url_index]
            try:
                logger.info(f"Connecting to Binance: {url.split('://')[1].split('/')[0]}...")
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url) as ws:
                        logger.info("✅ Connected to Binance WebSocket")
                        
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._process_message(msg.data)
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error(f"WebSocket error: {msg.data}")
                                break
                                
            except Exception as e:
                error_str = str(e)
                logger.error(f"Binance WebSocket error: {error_str}")
                
                # Check for 451 (Unavailable For Legal Reasons - Geo-blocking)
                if "451" in error_str or "status" in error_str.lower():
                    logger.warning("⚠️  Binance.com blocked (451). Switching to Binance.US...")
                    current_url_index = 1 - current_url_index  # Toggle between 0 and 1
                
                await asyncio.sleep(5)  # Reconnect after 5 seconds
    
    async def _process_message(self, data: str):
        """Process incoming Binance trade message."""
        import json
        try:
            trade = json.loads(data)
            symbol = trade.get("s", "")
            price = Decimal(trade.get("p", "0"))
            
            if symbol == "BTCUSDT":
                self._update_price("BTC", price)
            elif symbol == "ETHUSDT":
                self._update_price("ETH", price)
                
        except Exception as e:
            logger.debug(f"Error processing Binance message: {e}")
    
    def _update_price(self, asset: str, price: Decimal):
        """Update price and history."""
        self.prices[asset] = price
        self.price_history[asset].append((datetime.now(), price))
    
    def get_price_change(self, asset: str, seconds: int = 10) -> Optional[Decimal]:
        """
        Calculate price change over the last N seconds.
        
        Returns:
            Percentage change (0.01 = 1%), or None if insufficient data
        """
        history = self.price_history.get(asset, deque())
        if len(history) < 2:
            return None
        
        cutoff = datetime.now() - timedelta(seconds=seconds)
        old_prices = [(t, p) for t, p in history if t < cutoff]
        
        if not old_prices:
            return None
        
        old_price = old_prices[0][1]
        current_price = self.prices.get(asset, Decimal("0"))
        
        if old_price == 0:
            return None
        
        return (current_price - old_price) / old_price
    
    def is_bullish_signal(self, asset: str, threshold: Decimal = Decimal("0.001")) -> bool:
        """Check if there's a bullish (UP) signal from Binance."""
        change = self.get_price_change(asset, seconds=10)
        return change is not None and change > threshold
    
    def is_bearish_signal(self, asset: str, threshold: Decimal = Decimal("0.001")) -> bool:
        """Check if there's a bearish (DOWN) signal from Binance."""
        change = self.get_price_change(asset, seconds=10)
        return change is not None and change < -threshold


class FifteenMinuteCryptoStrategy:
    """
    Complete 15-Minute Crypto Trading Strategy.
    
    Features:
    - Latency arbitrage using Binance price feed
    - Sum-to-one arbitrage (YES + NO < $1.00)
    - Automatic profit taking and stop-loss
    - Position sizing based on confidence
    """
    
    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    
    def __init__(
        self,
        clob_client: ClobClient,
        trade_size: float = 5.0,  # $5 per trade
        take_profit_pct: float = 0.10,  # 10% profit target
        stop_loss_pct: float = 0.05,  # 5% stop loss
        max_positions: int = 3,  # Max concurrent positions
        sum_to_one_threshold: float = 0.99,  # Buy both if YES+NO < $0.99
        dry_run: bool = False
    ):
        """
        Initialize the 15-minute crypto trading strategy.
        
        Args:
            clob_client: Authenticated CLOB client
            trade_size: USD amount per trade
            take_profit_pct: Take profit at this percentage gain
            stop_loss_pct: Stop loss at this percentage loss
            max_positions: Maximum concurrent positions
            sum_to_one_threshold: Threshold for sum-to-one arbitrage
            dry_run: If True, simulate trades without executing
        """
        self.clob_client = clob_client
        self.trade_size = Decimal(str(trade_size))
        self.take_profit_pct = Decimal(str(take_profit_pct))
        self.stop_loss_pct = Decimal(str(stop_loss_pct))
        self.max_positions = max_positions
        self.sum_to_one_threshold = Decimal(str(sum_to_one_threshold))
        self.dry_run = dry_run
        
        # Binance price feed for latency arbitrage
        self.binance_feed = BinancePriceFeed()
        
        # Active positions
        self.positions: Dict[str, Position] = {}
        
        # Trading stats
        self.stats = {
            "trades_placed": 0,
            "trades_won": 0,
            "trades_lost": 0,
            "total_profit": Decimal("0"),
            "arbitrage_opportunities": 0,
        }
        
        logger.info("=" * 80)
        logger.info("15-MINUTE CRYPTO TRADING STRATEGY INITIALIZED")
        logger.info("=" * 80)
        logger.info(f"Trade size: ${trade_size}")
        logger.info(f"Take profit: {take_profit_pct * 100}%")
        logger.info(f"Stop loss: {stop_loss_pct * 100}%")
        logger.info(f"Max positions: {max_positions}")
        logger.info(f"Sum-to-one threshold: ${sum_to_one_threshold}")
        logger.info(f"Dry run: {dry_run}")
        logger.info("=" * 80)
    
    async def start(self):
        """Start the strategy (including Binance feed)."""
        await self.binance_feed.start()
    
    async def stop(self):
        """Stop the strategy."""
        await self.binance_feed.stop()
    
    async def fetch_15min_markets(self) -> List[CryptoMarket]:
        """
        Fetch ONLY the CURRENT active 15-minute crypto markets from Polymarket.
        
        These markets use a specific slug pattern: {asset}-updown-15m-{timestamp}
        Only returns markets where current time is within the trading window.
        
        Returns:
            List of CURRENT active 15-minute crypto markets (max 4: BTC, ETH, SOL, XRP)
        """
        markets = []
        
        # Assets to search for
        assets = ["btc", "eth", "sol", "xrp"]
        
        # Calculate current 15-min interval
        import time
        from datetime import timezone
        now = int(time.time())
        now_dt = datetime.now(timezone.utc)
        
        # Round to 15-minute intervals (900 seconds)
        current_interval = (now // 900) * 900
        
        # ONLY try current interval (the one we're in now)
        # This ensures we only trade the live market
        timestamps = [current_interval]
        
        async with aiohttp.ClientSession() as session:
            for ts in timestamps:
                for asset in assets:
                    slug = f"{asset}-updown-15m-{ts}"
                    url = f"https://gamma-api.polymarket.com/events/slug/{slug}"
                    
                    try:
                        async with session.get(url, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                
                                event_markets = data.get("markets", [])
                                for m in event_markets:
                                    # Extract token IDs
                                    token_ids = m.get("clobTokenIds", [])
                                    if isinstance(token_ids, str):
                                        import json
                                        try:
                                            # Debug log for verification
                                            # logger.info(f"Parsing string token_ids: {token_ids[:50]}...")
                                            token_ids = json.loads(token_ids)
                                        except Exception as e:
                                            logger.error(f"Failed to parse token_ids: {e}")
                                            continue
                                        
                                    if len(token_ids) >= 2:
                                        up_token = token_ids[0]  # First is Up/Yes
                                        down_token = token_ids[1]  # Second is Down/No
                                    else:
                                        continue
                                    
                                    # Extract prices - handle JSON strings properly
                                    prices = m.get("outcomePrices", ["0.5", "0.5"])
                                    try:
                                        # Handle case where prices might be JSON string
                                        if isinstance(prices, str):
                                            import json
                                            prices = json.loads(prices)
                                        up_price = Decimal(str(prices[0]).strip('"'))
                                        down_price = Decimal(str(prices[1]).strip('"'))
                                    except:
                                        up_price = Decimal("0.5")
                                        down_price = Decimal("0.5")
                                    
                                    # Parse end time
                                    end_time_str = m.get("endDate", "")
                                    try:
                                        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                                    except:
                                        end_time = datetime.now(timezone.utc) + timedelta(minutes=15)
                                    
                                    # Check if market is CURRENTLY tradeable
                                    # (not closed AND end_time is in the future)
                                    is_closed = m.get("closed", False)
                                    is_active = m.get("active", True)
                                    is_trading = end_time > now_dt and is_active and not is_closed
                                    
                                    if is_trading:
                                        markets.append(CryptoMarket(
                                            market_id=m.get("conditionId", ""),
                                            question=m.get("question", data.get("title", "")),
                                            asset=asset.upper(),
                                            up_token_id=up_token,
                                            down_token_id=down_token,
                                            up_price=up_price,
                                            down_price=down_price,
                                            end_time=end_time,
                                            neg_risk=True
                                        ))
                                        
                                        logger.info(
                                            f"🎯 CURRENT {asset.upper()} market: "
                                            f"Up=${up_price:.2f}, Down=${down_price:.2f}, "
                                            f"Ends: {end_time.strftime('%H:%M:%S')} UTC"
                                        )
                            elif resp.status != 404:
                                logger.debug(f"Slug {slug}: Status {resp.status}")
                    except asyncio.TimeoutError:
                        logger.debug(f"Timeout fetching {slug}")
                    except Exception as e:
                        logger.debug(f"Error fetching {slug}: {e}")
        
        # Remove duplicates (same conditionId)
        seen_ids = set()
        unique_markets = []
        for m in markets:
            if m.market_id not in seen_ids:
                seen_ids.add(m.market_id)
                unique_markets.append(m)
        
        if unique_markets:
            logger.info(f"📊 Found {len(unique_markets)} CURRENT 15-minute markets (trading now!)")
        else:
            logger.debug("No active markets in current 15-min window")
        
        return unique_markets
    
    async def check_sum_to_one_arbitrage(self, market: CryptoMarket) -> bool:
        """
        Check for sum-to-one arbitrage opportunity.
        
        If UP_price + DOWN_price < $1.00, buy both for guaranteed profit.
        
        Returns:
            True if arbitrage executed, False otherwise
        """
        total = market.up_price + market.down_price
        
        if total < self.sum_to_one_threshold:
            spread = Decimal("1.0") - total
            logger.warning(f"🎯 SUM-TO-ONE ARBITRAGE FOUND!")
            logger.warning(f"   Market: {market.question[:50]}...")
            logger.warning(f"   UP: ${market.up_price} + DOWN: ${market.down_price} = ${total}")
            logger.warning(f"   Guaranteed profit: ${spread:.4f} per share pair!")
            
            self.stats["arbitrage_opportunities"] += 1
            
            if len(self.positions) < self.max_positions:
                # Buy both sides
                up_shares = float(self.trade_size / 2 / market.up_price)
                down_shares = float(self.trade_size / 2 / market.down_price)
                
                # Execute trades
                await self._place_order(market, "UP", market.up_price, up_shares)
                await self._place_order(market, "DOWN", market.down_price, down_shares)
                
                return True
        
        return False
    
    async def check_latency_arbitrage(self, market: CryptoMarket) -> bool:
        """
        Check for latency arbitrage opportunity using Binance signal.
        
        If Binance shows strong move, front-run Polymarket.
        
        Returns:
            True if trade executed, False otherwise
        """
        asset = market.asset
        
        # Check for bullish signal -> Buy UP
        if self.binance_feed.is_bullish_signal(asset, Decimal("0.002")):
            # Binance price rising > 0.2%, buy UP before Polymarket reacts
            logger.info(f"🚀 BINANCE BULLISH SIGNAL for {asset}!")
            logger.info(f"   Current UP price: ${market.up_price}")
            
            if len(self.positions) < self.max_positions:
                shares = float(self.trade_size / market.up_price)
                await self._place_order(market, "UP", market.up_price, shares)
                return True
        
        # Check for bearish signal -> Buy DOWN
        if self.binance_feed.is_bearish_signal(asset, Decimal("0.002")):
            # Binance price falling > 0.2%, buy DOWN before Polymarket reacts
            logger.info(f"📉 BINANCE BEARISH SIGNAL for {asset}!")
            logger.info(f"   Current DOWN price: ${market.down_price}")
            
            if len(self.positions) < self.max_positions:
                shares = float(self.trade_size / market.down_price)
                await self._place_order(market, "DOWN", market.down_price, shares)
                return True
        
        return False
    
    async def check_exit_conditions(self, market: CryptoMarket) -> None:
        """
        Check if any positions should be exited.
        
        Exit on take-profit or stop-loss.
        """
        positions_to_close = []
        
        for token_id, position in self.positions.items():
            if position.market_id != market.market_id:
                continue
            
            # Get current price
            if position.side == "UP":
                current_price = market.up_price
            else:
                current_price = market.down_price
            
            # Calculate P&L percentage
            pnl_pct = (current_price - position.entry_price) / position.entry_price
            
            # Take profit
            if pnl_pct >= self.take_profit_pct:
                logger.info(f"🎉 TAKE PROFIT on {position.asset} {position.side}!")
                logger.info(f"   Entry: ${position.entry_price} -> Current: ${current_price}")
                logger.info(f"   P&L: {pnl_pct * 100:.2f}%")
                
                await self._close_position(position, current_price)
                positions_to_close.append(token_id)
                
                self.stats["trades_won"] += 1
                self.stats["total_profit"] += (current_price - position.entry_price) * position.size
            
            # Stop loss
            elif pnl_pct <= -self.stop_loss_pct:
                logger.warning(f"❌ STOP LOSS on {position.asset} {position.side}!")
                logger.warning(f"   Entry: ${position.entry_price} -> Current: ${current_price}")
                logger.warning(f"   P&L: {pnl_pct * 100:.2f}%")
                
                await self._close_position(position, current_price)
                positions_to_close.append(token_id)
                
                self.stats["trades_lost"] += 1
                self.stats["total_profit"] += (current_price - position.entry_price) * position.size
        
        # Remove closed positions
        for token_id in positions_to_close:
            del self.positions[token_id]
    
    async def _place_order(
        self,
        market: CryptoMarket,
        side: str,  # "UP" or "DOWN"
        price: Decimal,
        shares: float
    ) -> bool:
        """
        Place a buy order.
        
        Args:
            market: Target market
            side: "UP" or "DOWN"
            price: Entry price
            shares: Number of shares to buy
            
        Returns:
            True if order placed successfully
        """
        token_id = market.up_token_id if side == "UP" else market.down_token_id
        
        logger.info("=" * 80)
        logger.info(f"📈 PLACING ORDER")
        logger.info(f"   Market: {market.question[:50]}...")
        logger.info(f"   Side: {side}")
        logger.info(f"   Price: ${price}")
        logger.info(f"   Shares: {shares:.2f}")
        logger.info(f"   Value: ${float(price) * shares:.2f}")
        logger.info("=" * 80)
        
        if self.dry_run:
            logger.info("DRY RUN: Order simulated (not placed)")
            # Track position for testing
            self.positions[token_id] = Position(
                token_id=token_id,
                side=side,
                entry_price=price,
                size=Decimal(str(shares)),
                entry_time=datetime.now(),
                market_id=market.market_id,
                asset=market.asset
            )
            self.stats["trades_placed"] += 1
            return True
        
        try:
            # Place order using correct API
            try:
                response = self.clob_client.create_and_post_order(
                    OrderArgs(
                        token_id=token_id,
                        price=float(price),
                        size=shares,
                        side=BUY,
                    ),
                    options=SimpleNamespace(
                        tick_size="0.01",
                        neg_risk=market.neg_risk,
                    )
                )
            except TypeError as e:
                logger.warning(f"First order attempt failed: {e}. Trying fallback...")
                # Fallback
                order = self.clob_client.create_order(
                    OrderArgs(
                        token_id=token_id,
                        price=float(price),
                        size=shares,
                        side=BUY,
                    ),
                    options=SimpleNamespace(
                        tick_size="0.01",
                        neg_risk=market.neg_risk,
                    )
                )
                response = self.clob_client.post_order(order)
            
            if response:
                order_id = "unknown"
                if isinstance(response, dict):
                    order_id = response.get("orderID") or response.get("order_id") or "unknown"
                
                logger.info(f"✅ ORDER PLACED: {order_id}")
                
                # Track position
                self.positions[token_id] = Position(
                    token_id=token_id,
                    side=side,
                    entry_price=price,
                    size=Decimal(str(shares)),
                    entry_time=datetime.now(),
                    market_id=market.market_id,
                    asset=market.asset
                )
                self.stats["trades_placed"] += 1
                return True
            else:
                logger.error("❌ ORDER FAILED: Empty response")
                return False
                
        except Exception as e:
            logger.error(f"Order error: {e}", exc_info=True)
            return False
    
    async def _close_position(self, position: Position, current_price: Decimal) -> bool:
        """
        Close a position by selling.
        
        Args:
            position: Position to close
            current_price: Current market price
            
        Returns:
            True if order placed successfully
        """
        logger.info("=" * 80)
        logger.info(f"📤 CLOSING POSITION")
        logger.info(f"   Side: {position.side}")
        logger.info(f"   Entry: ${position.entry_price} -> Exit: ${current_price}")
        logger.info(f"   Shares: {position.size}")
        logger.info("=" * 80)
        
        if self.dry_run:
            logger.info("DRY RUN: Exit simulated (not placed)")
            return True
        
        try:
            response = self.clob_client.create_and_post_order(
                OrderArgs(
                    token_id=position.token_id,
                    price=float(current_price),
                    size=float(position.size),
                    side=SELL,
                ),
                options={
                    "tick_size": "0.01",
                    "neg_risk": True,
                },
                order_type=OrderType.GTC
            )
            
            if response:
                logger.info(f"✅ EXIT ORDER PLACED")
                return True
            else:
                logger.error("❌ EXIT ORDER FAILED")
                return False
                
        except Exception as e:
            logger.error(f"Exit order error: {e}", exc_info=True)
            return False
    
    async def run_cycle(self) -> None:
        """
        Run one trading cycle.
        
        This should be called every few seconds in the main loop.
        """
        # Fetch current 15-minute markets
        markets = await self.fetch_15min_markets()
        
        if not markets:
            logger.debug("No active 15-minute markets found")
            return
        
        for market in markets:
            # Strategy 1: Sum-to-one arbitrage (guaranteed profit)
            await self.check_sum_to_one_arbitrage(market)
            
            # Strategy 2: Latency arbitrage (Binance signal)
            await self.check_latency_arbitrage(market)
            
            # Check exit conditions for existing positions
            await self.check_exit_conditions(market)
        
        # Log status
        if self.positions:
            logger.info(f"📊 Active positions: {len(self.positions)}")
            logger.info(f"   Stats: {self.stats['trades_won']} wins, {self.stats['trades_lost']} losses")
            logger.info(f"   Total P&L: ${self.stats['total_profit']:.2f}")
    
    async def run_forever(self, interval_seconds: int = 5):
        """
        Run the strategy continuously.
        
        Args:
            interval_seconds: Seconds between each cycle
        """
        await self.start()
        
        logger.info("🚀 Starting 15-minute crypto trading strategy...")
        logger.info(f"   Cycle interval: {interval_seconds} seconds")
        
        try:
            while True:
                await self.run_cycle()
                await asyncio.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.stop()
