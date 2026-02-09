
import sys
import os
import asyncio
from unittest.mock import MagicMock
from decimal import Decimal

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# ----------------- MOCK SETUP -----------------
# Mock py_clob_client dependencies
sys.modules['py_clob_client'] = MagicMock()
sys.modules['py_clob_client.client'] = MagicMock()
sys.modules['py_clob_client.clob_types'] = MagicMock()
sys.modules['py_clob_client.order_builder'] = MagicMock()
sys.modules['py_clob_client.order_builder.constants'] = MagicMock()

# Define constants
BUY = "BUY"
SELL = "SELL"
OrderType = MagicMock()
OrderType.GTC = "GTC"
OrderArgs = MagicMock

# Apply
sys.modules['py_clob_client.order_builder.constants'].BUY = BUY
sys.modules['py_clob_client.clob_types'].OrderArgs = OrderArgs
sys.modules['py_clob_client.clob_types'].OrderType = OrderType

# Mock sibling modules
sys.modules['src.negrisk_arbitrage_engine'] = MagicMock()
sys.modules['src.main_orchestrator'] = MagicMock()

# Import strategies
from src.flash_crash_strategy import FlashCrashStrategy
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket

# ----------------- TESTS -----------------


async def test_flash_crash():
    print("\n[TEST] Flash Crash Strategy Fallback")
    mock_clob = MagicMock()
    mock_parser = MagicMock()
    
    strategy = FlashCrashStrategy(
        clob_client=mock_clob,
        market_parser=mock_parser,
        drop_threshold=Decimal("0.2"), 
        lookback_seconds=60,
        trade_size=Decimal("10"),
        dry_run=False
    )
    
    # 1. Setup mock to fail on primary call but CHECK options type
    def fail_primary(*args, **kwargs):
        # Verify options is NOT a dict
        if 'options' in kwargs:
            opts = kwargs['options']
            if isinstance(opts, dict):
                print("   ❌ FAIL: options is a dict!")
                raise ValueError("options should be an object, not a dict")
            try:
                _ = opts.tick_size
                print("   ✅ Verified options.tick_size exists")
            except AttributeError:
                print("   ❌ FAIL: options has no tick_size!")
                raise
        
        raise TypeError("unexpected keyword argument 'order_type'")
    mock_clob.create_and_post_order.side_effect = fail_primary
    
    # 2. Setup mock to succeed on fallback
    mock_clob.create_order.return_value = "mock_order"
    mock_clob.post_order.return_value = {"orderID": "success_id"}
    
    # 3. Dummy Market
    market = MagicMock()
    market.market_id = "mkt1"
    market.question = "Q1"
    
    # 4. Run async
    print("   Running enter_position...")
    result = await strategy.enter_position(market, "tok1", Decimal("0.50"), "YES")
    
    # 5. Check
    if result is True:
        print("   ✅ enter_position returned True")
    else:
        print("   ❌ enter_position returned False")
        
    # Check calls
    if mock_clob.create_order.called:
        print("   ✅ Fallback (create_order) was called")
        print("   TEST PASSED")
    else:
        print("   ❌ Fallback (create_order) was NOT called")
        print("   TEST FAILED")

async def test_15_min():
    print("\n[TEST] 15-Min Strategy Fallback")
    mock_clob = MagicMock()
    mock_parser = MagicMock()
    
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob,
        trade_size=Decimal("10"),
        dry_run=False
    )
    strategy.binance_feed = MagicMock()
    
    # 1. Setup mock to fail on primary call
    def fail_primary(*args, **kwargs):
        # Verify options is NOT a dict
        if 'options' in kwargs:
            opts = kwargs['options']
            if isinstance(opts, dict):
                print("   ❌ FAIL: options is a dict!")
                raise ValueError("options should be an object, not a dict")
            try:
                _ = opts.tick_size
                print("   ✅ Verified options.tick_size exists")
            except AttributeError:
                print("   ❌ FAIL: options has no tick_size!")
                raise

        raise TypeError("unexpected keyword argument from library")
    mock_clob.create_and_post_order.side_effect = fail_primary
    
    # 2. Setup mock to succeed on fallback
    mock_clob.create_order.return_value = "mock_order_15"
    mock_clob.post_order.return_value = {"orderID": "success_id_15"}
    
    # 3. Dummy Market
    market = CryptoMarket(
        market_id="mkt2", question="Q2", asset="ETH", 
        up_token_id="u", down_token_id="d",
        up_price=Decimal("0.5"), down_price=Decimal("0.5"),
        end_time=None, neg_risk=True
    )
    
    # 4. Run async
    print("   Running _place_order...")
    result = await strategy._place_order(market, "UP", Decimal("0.5"), 10.0)
    
    # 5. Check
    if result is True:
        print("   ✅ _place_order returned True")
    else:
        print("   ❌ _place_order returned False")
    
    if mock_clob.create_order.called:
        print("   ✅ Fallback (create_order) was called")
        print("   TEST PASSED")
    else:
        print("   ❌ Fallback (create_order) was NOT called")
        print("   TEST FAILED")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    async def run_all():
        await test_flash_crash()
        await test_15_min()
        
    asyncio.run(run_all())
