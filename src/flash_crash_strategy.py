"""
Flash Crash Trading Strategy

Monitors markets for sudden price drops and buys the crashed side.
This is a DIRECTIONAL trading strategy (buys YES OR NO, not both).

Based on successful bots:
- Novus-Tech-LLC/Polymarket-Arbitrage-Bot
- discountry/polymarket-trading-bot
- gabagool222/Polymarket-Arbitrage-Trading-Bot
"""

import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from collections import deque

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

from src.models import Market
from src.market_parser import MarketParser

logger = logging.getLogger(__name__)


class FlashCrashStrategy:
    """
    Flash Crash Strategy
    
    Detects sudden price drops and buys the crashed side.
    
    Example:
    - YES price drops from $0.70 to $0.40 in 10 seconds (43% drop)
    - Strategy buys YES at $0.40
    - Exits at $0.50 (take profit) or $0.35 (stop loss)
    """
    
    def __init__(
        self,
        clob_client: ClobClient,
        market_parser: MarketParser,
        drop_threshold: float = 0.20,  # 20% drop
        lookback_seconds: int = 10,
        trade_size: float = 5.0,  # $5 per trade
        take_profit: float = 0.10,  # $0.10 profit
        stop_loss: float = 0.05,  # $0.05 loss
        dry_run: bool = False
    ):
        self.clob_client = clob_client
        self.market_parser = market_parser
        self.drop_threshold = Decimal(str(drop_threshold))
        self.lookback_seconds = lookback_seconds
        self.trade_size = Decimal(str(trade_size))
        self.take_profit = Decimal(str(take_profit))
        self.stop_loss = Decimal(str(stop_loss))
        self.dry_run = dry_run
        
        # Price history: {token_id: deque of (timestamp, price)}
        self.price_history: Dict[str, deque] = {}
        
        # Active positions: {token_id: {"entry_price": Decimal, "size": Decimal, "side": str}}
        self.positions: Dict[str, Dict] = {}
        
        logger.info("=" * 80)
        logger.info("FLASH CRASH STRATEGY INITIALIZED")
        logger.info("=" * 80)
        logger.info(f"Drop threshold: {drop_threshold * 100}%")
        logger.info(f"Lookback window: {lookback_seconds}s")
        logger.info(f"Trade size: ${trade_size}")
        logger.info(f"Take profit: ${take_profit}")
        logger.info(f"Stop loss: ${stop_loss}")
        logger.info(f"Dry run: {dry_run}")
        logger.info("=" * 80)
    
    def update_price_history(self, token_id: str, price: Decimal) -> None:
        """Update price history for a token."""
        if token_id not in self.price_history:
            self.price_history[token_id] = deque(maxlen=100)
        
        now = datetime.now()
        self.price_history[token_id].append((now, price))
        
        # Remove old prices outside lookback window
        cutoff = now - timedelta(seconds=self.lookback_seconds)
        while self.price_history[token_id] and self.price_history[token_id][0][0] < cutoff:
            self.price_history[token_id].popleft()
    
    def detect_flash_crash(self, token_id: str, current_price: Decimal) -> Optional[Decimal]:
        """
        Detect if there's a flash crash.
        
        Returns:
            Drop percentage if crash detected, None otherwise
        """
        if token_id not in self.price_history or len(self.price_history[token_id]) < 2:
            return None
        
        # Get highest price in lookback window
        highest_price = max(price for _, price in self.price_history[token_id])
        
        if highest_price == 0:
            return None
        
        # Calculate drop percentage
        drop = (highest_price - current_price) / highest_price
        
        if drop >= self.drop_threshold:
            return drop
        
        return None
    
    async def check_exit_conditions(self, token_id: str, current_price: Decimal) -> bool:
        """
        Check if we should exit a position.
        
        Returns:
            True if should exit, False otherwise
        """
        if token_id not in self.positions:
            return False
        
        position = self.positions[token_id]
        entry_price = position["entry_price"]
        size = position["size"]
        
        # Calculate P&L
        pnl = (current_price - entry_price) * size
        
        # Take profit
        if pnl >= self.take_profit:
            logger.info(f"✅ TAKE PROFIT: {token_id[:20]}... | Entry=${entry_price} Current=${current_price} | P&L=${pnl:.2f}")
            return True
        
        # Stop loss
        if pnl <= -self.stop_loss:
            logger.warning(f"❌ STOP LOSS: {token_id[:20]}... | Entry=${entry_price} Current=${current_price} | P&L=${pnl:.2f}")
            return True
        
        return False
    
    def _is_negrisk_market(self, market: Market) -> bool:
        """
        Check if market is a NegRisk (multi-outcome) market.
        
        BTC and ETH 15-minute markets are NegRisk markets and require
        special handling in the CLOB API.
        
        Returns:
            True if market is NegRisk, False otherwise
        """
        question_lower = market.question.lower()
        
        # BTC/Bitcoin markets
        if "btc" in question_lower or "bitcoin" in question_lower:
            return True
        
        # ETH/Ethereum markets  
        if "eth" in question_lower or "ethereum" in question_lower:
            return True
        
        # 15-minute markets are typically NegRisk
        if "15 minute" in question_lower or "15-minute" in question_lower:
            return True
        
        # Check market attributes if available
        if hasattr(market, 'neg_risk') and market.neg_risk:
            return True
        
        return False
    
    async def enter_position(self, market: Market, token_id: str, price: Decimal, side: str) -> bool:
        """
        Enter a position (buy YES or NO).
        
        Args:
            market: Market object
            token_id: Token ID to buy
            price: Current price
            side: "YES" or "NO"
            
        Returns:
            True if order placed successfully
        """
        try:
            # Calculate shares to buy
            shares = float(self.trade_size / price) if price > 0 else 0
            
            if shares < 0.01:
                logger.warning(f"Trade size too small: {shares} shares")
                return False
            
            logger.info("=" * 80)
            logger.info(f"🚀 ENTERING POSITION")
            logger.info(f"Market: {market.question[:50]}...")
            logger.info(f"Side: {side}")
            logger.info(f"Token ID: {token_id[:20]}...")
            logger.info(f"Price: ${price}")
            logger.info(f"Size: {shares:.2f} shares (${self.trade_size})")
            logger.info("=" * 80)
            
            if self.dry_run:
                logger.info("DRY RUN: Order not placed")
                # Still track position for testing
                self.positions[token_id] = {
                    "entry_price": price,
                    "size": Decimal(str(shares)),
                    "side": side,
                    "market_id": market.market_id
                }
                return True
            
            # Determine if this is a NegRisk market (BTC/ETH 15-min)
            is_negrisk = self._is_negrisk_market(market)
            
            # Place order using correct CLOB API format
            # CRITICAL: BTC/ETH markets require negRisk=True!
            try:
                response = self.clob_client.create_and_post_order(
                    OrderArgs(
                        token_id=token_id,
                        price=float(price),
                        size=shares,
                        side=BUY,
                    ),
                    options={
                        "tick_size": "0.01",
                        "neg_risk": is_negrisk,
                    },
                    order_type=OrderType.GTC
                )
            except TypeError:
                # Fallback for older py_clob_client versions
                order = self.clob_client.create_order(
                    token_id=token_id,
                    price=float(price),
                    size=shares,
                    side="BUY"
                )
                response = self.clob_client.post_order(order)
            
            if response:
                # Extract order ID from response
                order_id = "unknown"
                if isinstance(response, dict):
                    order_id = response.get("orderID") or response.get("order_id") or response.get("id", "unknown")
                elif hasattr(response, 'orderID'):
                    order_id = response.orderID
                
                logger.info(f"✅ ORDER PLACED: {order_id}")
                logger.info(f"   Response: {response}")
                
                # Track position
                self.positions[token_id] = {
                    "entry_price": price,
                    "size": Decimal(str(shares)),
                    "side": side,
                    "market_id": market.market_id,
                    "order_id": order_id,
                    "neg_risk": is_negrisk
                }
                return True
            else:
                logger.error(f"❌ ORDER FAILED: Empty response")
                return False
                
        except Exception as e:
            logger.error(f"Error entering position: {e}", exc_info=True)
            return False
    
    async def exit_position(self, token_id: str, current_price: Decimal) -> bool:
        """
        Exit a position (sell).
        
        Args:
            token_id: Token ID to sell
            current_price: Current price
            
        Returns:
            True if order placed successfully
        """
        try:
            if token_id not in self.positions:
                return False
            
            position = self.positions[token_id]
            shares = float(position["size"])
            entry_price = position["entry_price"]
            
            logger.info("=" * 80)
            logger.info(f"🔚 EXITING POSITION")
            logger.info(f"Token ID: {token_id[:20]}...")
            logger.info(f"Entry: ${entry_price} | Current: ${current_price}")
            logger.info(f"Size: {shares:.2f} shares")
            logger.info("=" * 80)
            
            if self.dry_run:
                logger.info("DRY RUN: Exit order not placed")
                del self.positions[token_id]
                return True
            
            # Get negRisk status from position (stored during entry)
            is_negrisk = position.get("neg_risk", True)  # Default True for safety
            
            # Place sell order using correct CLOB API format
            try:
                response = self.clob_client.create_and_post_order(
                    OrderArgs(
                        token_id=token_id,
                        price=float(current_price),
                        size=shares,
                        side=SELL,
                    ),
                    options={
                        "tick_size": "0.01",
                        "neg_risk": is_negrisk,
                    },
                    order_type=OrderType.GTC
                )
            except TypeError:
                # Fallback for older py_clob_client versions
                order = self.clob_client.create_order(
                    token_id=token_id,
                    price=float(current_price),
                    size=shares,
                    side="SELL"
                )
                response = self.clob_client.post_order(order)
            
            if response:
                # Extract order ID from response
                order_id = "unknown"
                if isinstance(response, dict):
                    order_id = response.get("orderID") or response.get("order_id") or response.get("id", "unknown")
                elif hasattr(response, 'orderID'):
                    order_id = response.orderID
                
                logger.info(f"✅ EXIT ORDER PLACED: {order_id}")
                del self.positions[token_id]
                return True
            else:
                logger.error(f"❌ EXIT ORDER FAILED: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error exiting position: {e}", exc_info=True)
            return False
    
    async def scan_market(self, market: Market) -> None:
        """
        Scan a single market for flash crash opportunities.
        
        Args:
            market: Market to scan
        """
        try:
            # Update price history
            self.update_price_history(market.yes_token_id, market.yes_price)
            self.update_price_history(market.no_token_id, market.no_price)
            
            # Check for flash crash on YES
            yes_drop = self.detect_flash_crash(market.yes_token_id, market.yes_price)
            if yes_drop and market.yes_token_id not in self.positions:
                logger.warning(f"🔥 FLASH CRASH DETECTED: YES dropped {yes_drop*100:.1f}% | {market.question[:50]}...")
                await self.enter_position(market, market.yes_token_id, market.yes_price, "YES")
            
            # Check for flash crash on NO
            no_drop = self.detect_flash_crash(market.no_token_id, market.no_price)
            if no_drop and market.no_token_id not in self.positions:
                logger.warning(f"🔥 FLASH CRASH DETECTED: NO dropped {no_drop*100:.1f}% | {market.question[:50]}...")
                await self.enter_position(market, market.no_token_id, market.no_price, "NO")
            
            # Check exit conditions for existing positions
            if market.yes_token_id in self.positions:
                if await self.check_exit_conditions(market.yes_token_id, market.yes_price):
                    await self.exit_position(market.yes_token_id, market.yes_price)
            
            if market.no_token_id in self.positions:
                if await self.check_exit_conditions(market.no_token_id, market.no_price):
                    await self.exit_position(market.no_token_id, market.no_price)
                    
        except Exception as e:
            logger.error(f"Error scanning market {market.market_id}: {e}")
    
    async def run(self, markets: List[Market]) -> None:
        """
        Run strategy on a list of markets.
        
        Args:
            markets: List of markets to monitor
        """
        for market in markets:
            await self.scan_market(market)
        
        # Log status
        if self.positions:
            logger.info(f"📊 Active positions: {len(self.positions)}")
