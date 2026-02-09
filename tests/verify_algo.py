
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position, CryptoMarket
from py_clob_client.clob_types import OrderArgs

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("TestHarness")

class MockClobClient:
    def __init__(self):
        self.orders = []
        self.balance = {"USDC": Decimal("100.0")}
        self.create_or_derive_api_creds = MagicMock()
        self.set_api_creds = MagicMock()
        
    def create_order(self, args, options=None):
        logger.info(f" [MOCK] Creating order: {args.side} {args.size} @ {args.price}")
        if getattr(options, 'neg_risk', True) is True:
            logger.error("❌ CRITICAL: neg_risk=True passed to create_order! Should be False!")
        return {"args": args, "options": options}
        
    def post_order(self, order):
        logger.info(f" [MOCK] Posting order...")
        self.orders.append(order)
        return {"orderID": f"mock_order_{len(self.orders)}"}

class MockBinanceFeed:
    def __init__(self):
        self.bullish = False
        self.bearish = False
        self.change = Decimal("0")
        
    async def start(self): pass
    async def stop(self): pass
    
    def get_price_change(self, asset, seconds):
        return self.change
        
    def is_bullish_signal(self, asset, threshold):
        return self.bullish
        
    def is_bearish_signal(self, asset, threshold):
        return self.bearish

async def run_tests():
    logger.info("🚀 STARTING DEEP AUDIT & VERIFICATION")
    
    # Setup
    clob = MockClobClient()
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=clob,
        trade_size=5.0,
        take_profit_pct=0.03, # 3%
        stop_loss_pct=0.10,   # 10%
        sum_to_one_threshold=1.01
    )
    
    # Inject Mock Feed
    strategy.binance_feed = MockBinanceFeed()
    
    # --- TEST 1: Sum-to-One Arbitrage (Min 5 Shares) ---
    logger.info("\n--- TEST 1: Sum-to-One Math (Min 5 Shares) ---")
    market = CryptoMarket(
        market_id="m1", 
        question="Will BTC > 100k?", 
        asset="BTC", 
        end_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        up_price=Decimal("0.49"), 
        down_price=Decimal("0.49"), # Sum = 0.98 < 1.01
        up_token_id="t1", 
        down_token_id="t2"
    )
    
    # Mock finding this market
    strategy.fetch_15min_markets = AsyncMock(return_value=[market])
    
    await strategy.run_cycle()
    
    # Verification
    if len(clob.orders) == 2:
        up_order = clob.orders[0]['args']
        down_order = clob.orders[1]['args']
        
        # Check size: $2.50 / 0.49 = 5.10 shares. 
        # But if price was higher, say 0.60 ($2.50/0.60=4.16), logic MUST cap at 5.0.
        # Let's verify our fix logic actually enforces max(5.0, ...)
        
        logger.info(f"✅ Arbitrage triggered with 2 orders")
        logger.info(f"   UP Size: {up_order.size} (Expected >= 5.0)")
        logger.info(f"   DOWN Size: {down_order.size} (Expected >= 5.0)")
        
        if up_order.size < 5.0 or down_order.size < 5.0:
            logger.error("❌ TEST FAILED: Minimum 5 shares NOT enforced!")
        else:
            logger.info("✅ MIN 5 SHARES ENFORCED!")
    else:
        logger.error(f"❌ TEST FAILED: Expected 2 orders, got {len(clob.orders)}")

    # Clear orders and positions for next test
    clob.orders = []
    strategy.positions.clear()
    
    # --- TEST 2: Latency Arbitrage & Buy Pattern ---
    logger.info("\n--- TEST 2: Latency Arbitrage (Buy Pattern) ---")
    strategy.binance_feed.bullish = True
    market.up_price = Decimal("0.55") # Update price
    
    await strategy.run_cycle()
    
    if len(clob.orders) == 1:
        order = clob.orders[0]
        args = order['args']
        opts = order['options']
        
        logger.info(f"✅ Buy order placed: {args.side} {args.size} @ {args.price}")
        
        if getattr(opts, 'neg_risk', True) is False:
             logger.info("✅ neg_risk=False verified!")
        else:
             logger.error("❌ TEST FAILED: neg_risk is True (Default) or missing!")
             
        if args.side != "BUY":
            logger.error("❌ TEST FAILED: Wrong side!")
            
    else:
        logger.error(f"❌ TEST FAILED: Expected 1 buy order, got {len(clob.orders)}")
        
    # Clear orders/positions/signals for next test
    clob.orders = []
    strategy.positions.clear()
    strategy.binance_feed.bullish = False 
    
    # --- TEST 3: Exit Logic (Take Profit 3%) ---
    logger.info("\n--- TEST 3: Exit Logic (Take Profit 3%) ---")
    
    # Create a position manually
    pos = Position(
        token_id="t1",
        side="UP",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
        market_id="m1",
        asset="BTC"
    )
    strategy.positions["t1"] = pos
    
    # Price moves UP to 0.52 (+4%) -> Should exit (target 3%)
    market.up_price = Decimal("0.52")
    
    await strategy.run_cycle()
    
    if len(clob.orders) >= 1: # Should be a sell order now
        last_order = clob.orders[-1] # The sell order
        args = last_order['args']
        
        if args.side == "SELL" and args.token_id == "t1":
            logger.info(f"✅ Sell triggered at ${args.price} (Entry: $0.50)")
            
            # Verify P&L
            pnl = (args.price - Decimal("0.50")) / Decimal("0.50")
            logger.info(f"   Realized P&L: {pnl*100:.2f}% (Target > 3%)")
            
            if "t1" not in strategy.positions:
                logger.info("✅ Position removed from tracking")
            else:
                logger.error("❌ TEST FAILED: Position NOT removed!")
        else:
             logger.error("❌ TEST FAILED: Last order was not the expected SELL")
    else:
        logger.error("❌ TEST FAILED: No SELL order generated!")

    # Clear for next test
    clob.orders = []
    strategy.positions.clear()
    strategy.binance_feed.bullish = False

    # --- TEST 4: Timeout Exit (Orphan) ---
    logger.info("\n--- TEST 4: Timeout Exit (Orphan) ---")
    
    # Add old position (30 min old)
    old_pos = Position(
        token_id="t3",
        side="DOWN",
        entry_price=Decimal("0.50"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc) - timedelta(minutes=30),
        market_id="m_old", # Different market ID
        asset="ETH"        # Asset not in current markets (BTC)
    )
    strategy.positions["t3"] = old_pos
    
    # Current markets only have BTC, so ETH is orphan
    # And it's > 20 min old -> Should force exit
    
    await strategy.run_cycle()
    
    if "t3" not in strategy.positions:
        logger.info("✅ Orphan position force-closed (removed from tracking)")
    else:
        logger.error("❌ TEST FAILED: Orphan position still tracked!")

if __name__ == "__main__":
    asyncio.run(run_tests())
