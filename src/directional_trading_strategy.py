"""
Directional Trading Strategy - Like Successful Polymarket Bots

This strategy:
1. Monitors 15-minute crypto markets (BTC/ETH Up/Down)
2. Uses external price signals (Binance) to predict direction
3. Buys YES or NO based on price movement
4. This is SPECULATION, not arbitrage - you can lose money!

Based on successful bots:
- discountry/polymarket-trading-bot
- gabagool222/Polymarket-Arbitrage-Trading-Bot
- FrondEnt/PolymarketBTC15mAssistant
"""

import asyncio
import logging
from decimal import Decimal
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import requests

from src.models import Market, Opportunity
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

logger = logging.getLogger(__name__)


class DirectionalTradingStrategy:
    """
    Directional trading strategy for Polymarket 15-minute crypto markets.
    
    Strategy:
    - Monitor BTC/ETH/SOL 15-minute Up/Down markets
    - Get current price from Binance
    - If price is going UP → Buy "Up" token
    - If price is going DOWN → Buy "Down" token
    - Exit after 5-10 minutes or at profit target
    """
    
    def __init__(
        self,
        clob_client: ClobClient,
        min_confidence: Decimal = Decimal("0.6"),  # 60% confidence to trade
        position_size: Decimal = Decimal("1.0"),   # $1 per trade
        max_price: Decimal = Decimal("0.80"),      # Don't buy if price > 80%
    ):
        self.clob_client = clob_client
        self.min_confidence = min_confidence
        self.position_size = position_size
        self.max_price = max_price
        
        # Track active positions
        self.active_positions: Dict[str, Dict] = {}
        
        logger.info(f"Directional Trading Strategy initialized")
        logger.info(f"  Min confidence: {min_confidence*100}%")
        logger.info(f"  Position size: ${position_size}")
        logger.info(f"  Max price: {max_price*100}%")
    
    async def scan_opportunities(self, markets: List[Market]) -> List[Opportunity]:
        """
        Scan for directional trading opportunities.
        
        Returns opportunities where we have high confidence in direction.
        """
        opportunities = []
        
        logger.info(f"🎯 SCANNING {len(markets)} markets for DIRECTIONAL trades...")
        
        for market in markets:
            try:
                # Only trade 15-minute crypto markets
                if not self._is_15min_crypto_market(market):
                    continue
                
                # Get price signal from Binance
                signal = await self._get_price_signal(market)
                
                if signal is None:
                    continue
                
                direction = signal["direction"]  # "UP" or "DOWN"
                confidence = signal["confidence"]  # 0.0 to 1.0
                
                # Check if we have enough confidence
                if confidence < float(self.min_confidence):
                    logger.debug(f"  Low confidence: {confidence:.2%} < {self.min_confidence:.2%}")
                    continue
                
                # Determine which token to buy
                if direction == "UP":
                    token_id = market.yes_token_id
                    price = market.yes_price
                    side = "YES"
                else:
                    token_id = market.no_token_id
                    price = market.no_price
                    side = "NO"
                
                # Don't buy if price is too high (low expected return)
                if price > self.max_price:
                    logger.debug(f"  Price too high: {price} > {self.max_price}")
                    continue
                
                # Calculate expected profit
                # If we buy at 0.60 and win, we get $1.00 → profit = $0.40
                expected_profit = Decimal("1.0") - price
                profit_percentage = expected_profit / price if price > 0 else Decimal("0")
                
                # Create opportunity
                opportunity = Opportunity(
                    opportunity_id=f"directional_{market.market_id[:12]}",
                    market_id=market.market_id,
                    strategy="directional_trading",
                    timestamp=datetime.now(),
                    yes_price=market.yes_price,
                    no_price=market.no_price,
                    yes_fee=Decimal("0.03"),  # Approximate
                    no_fee=Decimal("0.03"),
                    total_cost=price * self.position_size,
                    expected_profit=expected_profit * self.position_size,
                    profit_percentage=profit_percentage,
                    position_size=self.position_size,
                    gas_estimate=0  # Gasless with proxy wallet
                )
                
                # Add metadata
                opportunity.metadata = {
                    "direction": direction,
                    "confidence": confidence,
                    "token_id": token_id,
                    "side": side,
                    "signal": signal
                }
                
                opportunities.append(opportunity)
                
                logger.info(
                    f"✅ FOUND TRADE: {market.question[:50]}... | "
                    f"Direction={direction} ({side}) | "
                    f"Confidence={confidence:.1%} | "
                    f"Price=${price} | "
                    f"Expected profit=${expected_profit * self.position_size:.2f}"
                )
                
            except Exception as e:
                logger.error(f"Error scanning market {market.market_id}: {e}")
                continue
        
        if len(opportunities) == 0:
            logger.info(f"⚠️  No high-confidence trades found")
        else:
            logger.info(f"✅ Found {len(opportunities)} trading opportunities!")
        
        return opportunities
    
    def _is_15min_crypto_market(self, market: Market) -> bool:
        """Check if this is a 15-minute crypto Up/Down market."""
        # Check if question mentions crypto and Up/Down
        question_upper = market.question.upper()
        
        has_crypto = any(coin in question_upper for coin in ["BTC", "ETH", "SOL", "XRP", "BITCOIN", "ETHEREUM"])
        has_direction = "UP" in question_upper or "DOWN" in question_upper
        has_15min = "15" in question_upper or "FIFTEEN" in question_upper
        
        if not (has_crypto and has_direction):
            return False
        
        # Check if market closes within 20 minutes
        now = datetime.now(tz=market.end_time.tzinfo) if market.end_time.tzinfo else datetime.now()
        time_to_close = (market.end_time - now).total_seconds() / 60
        
        # Accept markets closing in 5-20 minutes
        if not (5 <= time_to_close <= 20):
            return False
        
        return True
    
    async def _get_price_signal(self, market: Market) -> Optional[Dict]:
        """
        Get price signal from Binance to predict direction.
        
        Returns:
            {
                "direction": "UP" or "DOWN",
                "confidence": 0.0 to 1.0,
                "price_change": percentage change,
                "current_price": current price
            }
        """
        try:
            # Determine which coin
            question_upper = market.question.upper()
            
            if "BTC" in question_upper or "BITCOIN" in question_upper:
                symbol = "BTCUSDT"
            elif "ETH" in question_upper or "ETHEREUM" in question_upper:
                symbol = "ETHUSDT"
            elif "SOL" in question_upper or "SOLANA" in question_upper:
                symbol = "SOLUSDT"
            elif "XRP" in question_upper or "RIPPLE" in question_upper:
                symbol = "XRPUSDT"
            else:
                return None
            
            # Get recent price data from Binance
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": "1m",  # 1-minute candles
                "limit": 15  # Last 15 minutes
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            klines = response.json()
            
            if len(klines) < 10:
                return None
            
            # Calculate price change over last 5 minutes
            price_5min_ago = float(klines[-6][4])  # Close price 5 minutes ago
            current_price = float(klines[-1][4])   # Current close price
            
            price_change = (current_price - price_5min_ago) / price_5min_ago
            
            # Determine direction and confidence
            if price_change > 0.001:  # 0.1% up
                direction = "UP"
                confidence = min(abs(price_change) * 100, 0.95)  # Scale to confidence
            elif price_change < -0.001:  # 0.1% down
                direction = "DOWN"
                confidence = min(abs(price_change) * 100, 0.95)
            else:
                # No clear direction
                return None
            
            return {
                "direction": direction,
                "confidence": confidence,
                "price_change": price_change,
                "current_price": current_price,
                "symbol": symbol
            }
            
        except Exception as e:
            logger.debug(f"Failed to get Binance signal: {e}")
            return None
    
    async def execute(
        self,
        opportunity: Opportunity,
        market: Market,
        **kwargs
    ) -> Dict:
        """
        Execute a directional trade.
        
        Places a market order to buy the predicted direction.
        """
        try:
            token_id = opportunity.metadata["token_id"]
            side = opportunity.metadata["side"]
            direction = opportunity.metadata["direction"]
            confidence = opportunity.metadata["confidence"]
            
            logger.info(f"🎯 EXECUTING DIRECTIONAL TRADE:")
            logger.info(f"   Market: {market.question[:60]}...")
            logger.info(f"   Direction: {direction} ({side})")
            logger.info(f"   Confidence: {confidence:.1%}")
            logger.info(f"   Size: ${self.position_size}")
            
            # Get current price
            if side == "YES":
                price = market.yes_price
            else:
                price = market.no_price
            
            # Calculate shares to buy
            shares = float(self.position_size / price)
            
            # Place market order (buy at current best price)
            logger.info(f"   Buying {shares:.2f} shares at ${price}")
            
            # Use py-clob-client to place order
            try:
                # Import BUY constant
                try:
                    from py_clob_client.order_builder.constants import BUY
                except:
                    from py_clob_client.constants import BUY
                
                order_args = OrderArgs(
                    token_id=token_id,
                    price=float(price),
                    size=shares,
                    side=BUY,
                    fee_rate_bps=0,  # Will be calculated by API
                    nonce=0  # Will be set by API
                )
                
                order_result = self.clob_client.create_order(order_args)
                
                if order_result and "orderID" in order_result:
                    logger.info(f"✅ ORDER PLACED: {order_result['orderID']}")
                    
                    # Track position
                    self.active_positions[opportunity.opportunity_id] = {
                        "market_id": market.market_id,
                        "token_id": token_id,
                        "side": side,
                        "entry_price": price,
                        "shares": shares,
                        "entry_time": datetime.now(),
                        "order_id": order_result["orderID"]
                    }
                    
                    return {
                        "success": True,
                        "opportunity_id": opportunity.opportunity_id,
                        "order_id": order_result["orderID"],
                        "message": f"Bought {shares:.2f} {side} shares at ${price}"
                    }
                else:
                    logger.error(f"❌ ORDER FAILED: {order_result}")
                    return {
                        "success": False,
                        "error": f"Order placement failed: {order_result}"
                    }
                    
            except Exception as order_error:
                logger.error(f"❌ ORDER ERROR: {order_error}")
                return {
                    "success": False,
                    "error": str(order_error)
                }
                
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
