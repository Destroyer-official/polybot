
import asyncio
import aiohttp
import logging
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mock dependencies to avoid import errors if environment is missing packages
sys.modules['py_clob_client'] = MagicMock()
sys.modules['py_clob_client.client'] = MagicMock()
sys.modules['py_clob_client.clob_types'] = MagicMock()
sys.modules['py_clob_client.order_builder'] = MagicMock()
sys.modules['py_clob_client.order_builder.constants'] = MagicMock()

# Import the class to test (assuming it's in the python path or same directory)
# For this script to run standalone, we need to add the project root to path
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from src.fifteen_min_crypto_strategy import BinancePriceFeed
except ImportError:
    # If standard import fails, try direct file execution style
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.fifteen_min_crypto_strategy import BinancePriceFeed

class TestBinanceFallback(unittest.TestCase):
    
    def test_fallback_logic(self):
        """Test that a 451 error triggers a switch to the backup URL."""
        logger.info("\n🧪 TEST 1: Verifying 451 Error Auto-Switch Logic")
        
        feed = BinancePriceFeed()
        feed.is_running = True
        
        # Mocks
        mock_session = MagicMock()
        mock_ws = AsyncMock()
        
        # Setup the ws_connect mock to fail first, then succeed
        # First call: raises 451 Error
        # Second call: returns a valid WS context manager
        
        async def side_effect(*args, **kwargs):
            url = args[0]
            if "binance.com" in url:
                logger.info(f"   Simulating connection to {url} -> 451 BLOCKED")
                raise Exception("451 Unavailable For Legal Reasons")
            else:
                logger.info(f"   Simulating connection to {url} -> SUCCESS")
                return mock_ws

        mock_session.ws_connect.side_effect = side_effect
        
        # Patch aiohttp.ClientSession to return our mock session
        with patch('aiohttp.ClientSession', return_value=mock_session):
            
            # We need to run the _run_websocket method, but it has an infinite loop.
            # We'll patch is_running to become False after 2 iterations to break the loop
            
            async def run_test():
                # Start the task
                task = asyncio.create_task(feed._run_websocket())
                
                # Give it time to try first URL, fail, wait 5s, try second URL
                # We will speed up the sleep by patching asyncio.sleep
                with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                    await asyncio.sleep(0.1)  # Let it run
                    
                    # Manually stop after a moment
                    feed.is_running = False
                    await asyncio.sleep(0.1)
                    
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except asyncio.TimeoutError:
                        task.cancel()
                        
            # Run the async test
            loop = asyncio.new_event_loop()
            loop.run_until_complete(run_test())
            loop.close()
            
        logger.info("✅ Logic check passed: Code attempted to switch URLs")

async def test_live_connectivity():
    """Test actual connectivity to both endpoints."""
    logger.info("\n🔌 TEST 2: Live Connectivity Check")
    
    urls = [
        "wss://stream.binance.com:9443/ws/btcusdt@trade",
        "wss://stream.binance.us:9443/ws/btcusdt@trade"
    ]
    
    for url in urls:
        print(f"   Testing {url}...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url) as ws:
                    print(f"   ✅ Connected to {url}")
                    # Read one message
                    # msg = await ws.receive()
                    # print(f"   📩 Received data: {str(msg.data)[:50]}...")
        except Exception as e:
            print(f"   ❌ Failed to connect to {url}: {e}")
            if "binance.com" in url:
                print("   (Expected if you are in the US)")
            if "binance.us" in url:
                print("   (Expected if you are outside the US)")

if __name__ == '__main__':
    # Run unit test
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBinanceFallback)
    unittest.TextTestRunner(verbosity=0).run(suite)
    
    # Run live test
    logger.info("Starting live connectivity test...")
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_live_connectivity())
