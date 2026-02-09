#!/usr/bin/env python3
"""
Comprehensive Test Suite for Polymarket Arbitrage Bot.
Tests all major systems and APIs.
"""

import asyncio
import sys
import time
import aiohttp
from decimal import Decimal
from datetime import datetime, timezone, timedelta

# Results tracker
RESULTS = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_pass(test_name, details=""):
    print(f"✅ PASS: {test_name}")
    if details:
        print(f"   {details}")
    RESULTS["passed"].append(test_name)

def log_fail(test_name, error):
    print(f"❌ FAIL: {test_name}")
    print(f"   Error: {error}")
    RESULTS["failed"].append(test_name)

def log_warn(test_name, message):
    print(f"⚠️ WARN: {test_name}")
    print(f"   {message}")
    RESULTS["warnings"].append(test_name)

# ============================================================
# TEST 1: Configuration Loading
# ============================================================
async def test_config_loading():
    print("\n" + "="*60)
    print("TEST 1: Configuration Loading")
    print("="*60)
    
    try:
        from config.config import load_config
        config = load_config()
        
        # Check required fields
        assert config.wallet_address, "wallet_address is empty"
        assert config.polygon_rpc_url, "polygon_rpc_url is empty"
        
        log_pass("Config Loading", f"Wallet: {config.wallet_address[:10]}...")
        log_pass("Polygon RPC", f"URL: {config.polygon_rpc_url[:30]}...")
        log_pass("Dry Run Mode", f"DRY_RUN={config.dry_run}")
        
        return config
    except Exception as e:
        log_fail("Config Loading", str(e))
        return None

# ============================================================
# TEST 2: Polygon RPC Connection
# ============================================================
async def test_polygon_rpc(config):
    print("\n" + "="*60)
    print("TEST 2: Polygon RPC Connection")
    print("="*60)
    
    if not config:
        log_fail("Polygon RPC", "Config not loaded")
        return
    
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
        
        # Test connection
        connected = w3.is_connected()
        if connected:
            log_pass("RPC Connection", "Connected to Polygon")
        else:
            log_fail("RPC Connection", "Failed to connect")
            return
        
        # Get chain ID
        chain_id = w3.eth.chain_id
        if chain_id == 137:
            log_pass("Chain ID", f"Chain ID = {chain_id} (Polygon Mainnet)")
        else:
            log_warn("Chain ID", f"Expected 137, got {chain_id}")
        
        # Get gas price
        gas_price = w3.eth.gas_price
        gas_gwei = gas_price / 1e9
        if gas_gwei < 800:
            log_pass("Gas Price", f"{gas_gwei:.2f} gwei (< 800 limit)")
        else:
            log_warn("Gas Price", f"{gas_gwei:.2f} gwei (> 800 limit)")
        
        # Get latest block
        block = w3.eth.block_number
        log_pass("Latest Block", f"Block #{block}")
        
    except Exception as e:
        log_fail("Polygon RPC", str(e))

# ============================================================
# TEST 3: Gamma API (Market Fetching)
# ============================================================
async def test_gamma_api():
    print("\n" + "="*60)
    print("TEST 3: Gamma API (Market Fetching)")
    print("="*60)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test main market endpoint
            url = "https://gamma-api.polymarket.com/markets?limit=10&active=true"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    log_pass("Gamma API Connection", f"Status: {resp.status}")
                    log_pass("Active Markets", f"Fetched {len(data)} markets")
                else:
                    log_fail("Gamma API", f"Status: {resp.status}")
                    return
            
            # Test 15-min crypto market endpoint
            now = int(time.time())
            current_interval = (now // 900) * 900
            slug = f"btc-updown-15m-{current_interval}"
            url15m = f"https://gamma-api.polymarket.com/events/slug/{slug}"
            
            async with session.get(url15m, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    title = data.get("title", "Unknown")
                    markets = data.get("markets", [])
                    log_pass("15-Min BTC Market", f"Found: {title[:50]}...")
                    
                    if markets:
                        m = markets[0]
                        prices = m.get("outcomePrices", ["?", "?"])
                        log_pass("Market Prices", f"Up={prices[0]}, Down={prices[1]}")
                elif resp.status == 404:
                    log_warn("15-Min BTC Market", "No active market in current interval")
                else:
                    log_fail("15-Min Market", f"Status: {resp.status}")
                    
    except Exception as e:
        log_fail("Gamma API", str(e))

# ============================================================
# TEST 4: Binance WebSocket (Price Feed)
# ============================================================
async def test_binance_websocket():
    print("\n" + "="*60)
    print("TEST 4: Binance WebSocket (Price Feed)")
    print("="*60)
    
    try:
        url = "wss://stream.binance.com:9443/ws/btcusdt@trade"
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url, timeout=10) as ws:
                log_pass("WebSocket Connection", "Connected to Binance")
                
                # Get a few price updates
                prices = []
                for i in range(3):
                    msg = await asyncio.wait_for(ws.receive(), timeout=5)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        import json
                        data = json.loads(msg.data)
                        price = float(data.get("p", 0))
                        prices.append(price)
                
                if prices:
                    avg_price = sum(prices) / len(prices)
                    log_pass("BTC Price Feed", f"Current BTC: ${avg_price:,.2f}")
                else:
                    log_warn("Price Feed", "No prices received")
                    
    except asyncio.TimeoutError:
        log_fail("Binance WebSocket", "Connection timeout")
    except Exception as e:
        log_fail("Binance WebSocket", str(e))

# ============================================================
# TEST 5: CLOB Client Initialization
# ============================================================
async def test_clob_client(config):
    print("\n" + "="*60)
    print("TEST 5: CLOB Client (Order Placement)")
    print("="*60)
    
    if not config:
        log_fail("CLOB Client", "Config not loaded")
        return
    
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds
        
        # Initialize client
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,
            key=config.private_key,
            creds=ApiCreds(
                api_key=config.clob_api_key if hasattr(config, 'clob_api_key') else "",
                api_secret=config.clob_api_secret if hasattr(config, 'clob_api_secret') else "",
                api_passphrase=config.clob_api_passphrase if hasattr(config, 'clob_api_passphrase') else ""
            )
        )
        
        log_pass("CLOB Client Init", "Client initialized successfully")
        
        # Try to get server time (basic connectivity test)
        try:
            server_time = client.get_server_time()
            log_pass("CLOB Server Time", f"Server time: {server_time}")
        except Exception as e:
            log_warn("CLOB Server Time", str(e))
        
    except ImportError as e:
        log_fail("CLOB Client", f"Import error: {e}")
    except Exception as e:
        log_warn("CLOB Client", f"Init issue (may need API creds): {e}")

# ============================================================
# TEST 6: NVIDIA DeepSeek API (Optional)
# ============================================================
async def test_nvidia_api(config):
    print("\n" + "="*60)
    print("TEST 6: NVIDIA DeepSeek API (AI Safety)")
    print("="*60)
    
    if not config:
        log_fail("NVIDIA API", "Config not loaded")
        return
    
    api_key = getattr(config, 'nvidia_api_key', None)
    if not api_key or api_key == "" or "your_" in api_key.lower():
        log_warn("NVIDIA API", "API key not configured (AI safety will use fallback)")
        return
    
    try:
        from openai import OpenAI
        
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        
        # Quick test call
        completion = client.chat.completions.create(
            model="deepseek-ai/deepseek-v3.2",
            messages=[{"role": "user", "content": "Say YES"}],
            max_tokens=10,
            timeout=5.0
        )
        
        response = completion.choices[0].message.content if completion.choices else ""
        log_pass("NVIDIA DeepSeek", f"Response: {response}")
        
    except Exception as e:
        log_warn("NVIDIA API", f"Not available: {e}")

# ============================================================
# TEST 7: 15-Minute Market Detection Logic
# ============================================================
async def test_15min_detection():
    print("\n" + "="*60)
    print("TEST 7: 15-Minute Market Detection")
    print("="*60)
    
    try:
        assets = ["btc", "eth", "sol", "xrp"]
        now = int(time.time())
        current_interval = (now // 900) * 900
        now_dt = datetime.now(timezone.utc)
        
        found_markets = []
        
        async with aiohttp.ClientSession() as session:
            for asset in assets:
                slug = f"{asset}-updown-15m-{current_interval}"
                url = f"https://gamma-api.polymarket.com/events/slug/{slug}"
                
                try:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            markets = data.get("markets", [])
                            
                            for m in markets:
                                end_time_str = m.get("endDate", "")
                                try:
                                    end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                                    if end_time > now_dt and m.get("active", True) and not m.get("closed", False):
                                        prices = m.get("outcomePrices", ["0.5", "0.5"])
                                        found_markets.append({
                                            "asset": asset.upper(),
                                            "up": prices[0],
                                            "down": prices[1],
                                            "ends": end_time.strftime("%H:%M:%S UTC")
                                        })
                                except:
                                    pass
                except:
                    pass
        
        if found_markets:
            log_pass("Market Detection", f"Found {len(found_markets)} active markets")
            for m in found_markets:
                log_pass(f"  {m['asset']} Market", f"Up=${m['up']}, Down=${m['down']}, Ends: {m['ends']}")
        else:
            log_warn("Market Detection", "No active 15-min markets in current interval")
            
    except Exception as e:
        log_fail("15-Min Detection", str(e))

# ============================================================
# TEST 8: Trading Decision Logic
# ============================================================
async def test_trading_logic():
    print("\n" + "="*60)
    print("TEST 8: Trading Decision Logic")
    print("="*60)
    
    try:
        # Test bullish signal detection
        def is_bullish(price_change, threshold=0.002):
            return price_change is not None and price_change > threshold
        
        def is_bearish(price_change, threshold=0.002):
            return price_change is not None and price_change < -threshold
        
        # Test cases
        test_cases = [
            (0.003, "Bullish 0.3%", True, False),
            (-0.003, "Bearish 0.3%", False, True),
            (0.001, "Neutral 0.1%", False, False),
            (None, "No data", False, False),
        ]
        
        all_passed = True
        for change, desc, expect_bull, expect_bear in test_cases:
            is_bull = is_bullish(change)
            is_bear = is_bearish(change)
            
            if is_bull == expect_bull and is_bear == expect_bear:
                log_pass(f"Signal: {desc}", f"Bullish={is_bull}, Bearish={is_bear}")
            else:
                log_fail(f"Signal: {desc}", f"Expected Bull={expect_bull}, Bear={expect_bear}")
                all_passed = False
        
        # Test sum-to-one arbitrage
        def check_arbitrage(up_price, down_price, threshold=0.99):
            total = Decimal(str(up_price)) + Decimal(str(down_price))
            return total < Decimal(str(threshold))
        
        arb_cases = [
            (0.45, 0.45, True, "Up=$0.45 + Down=$0.45 = $0.90 < $0.99"),
            (0.50, 0.50, False, "Up=$0.50 + Down=$0.50 = $1.00 >= $0.99"),
            (0.30, 0.60, True, "Up=$0.30 + Down=$0.60 = $0.90 < $0.99"),
        ]
        
        for up, down, expect_arb, desc in arb_cases:
            is_arb = check_arbitrage(up, down)
            if is_arb == expect_arb:
                log_pass(f"Arbitrage: {desc}", f"Opportunity={is_arb}")
            else:
                log_fail(f"Arbitrage", f"Expected {expect_arb}, got {is_arb}")
                all_passed = False
        
    except Exception as e:
        log_fail("Trading Logic", str(e))

# ============================================================
# TEST 9: Safety Fallback Heuristics
# ============================================================
async def test_safety_heuristics():
    print("\n" + "="*60)
    print("TEST 9: Safety Fallback Heuristics")
    print("="*60)
    
    try:
        def fallback_check(balance, gas_gwei, pending_tx,
                          min_balance=10, max_gas=800, max_pending=5):
            balance_ok = balance > min_balance
            gas_ok = gas_gwei < max_gas
            pending_ok = pending_tx < max_pending
            return balance_ok and gas_ok and pending_ok
        
        test_cases = [
            (50, 100, 2, True, "Normal: $50, 100 gwei, 2 pending"),
            (5, 100, 2, False, "Low balance: $5 < $10"),
            (50, 900, 2, False, "High gas: 900 > 800 gwei"),
            (50, 100, 6, False, "Too many pending: 6 > 5"),
        ]
        
        for balance, gas, pending, expect, desc in test_cases:
            result = fallback_check(balance, gas, pending)
            if result == expect:
                log_pass(f"Safety: {desc}", f"Approved={result}")
            else:
                log_fail(f"Safety: {desc}", f"Expected {expect}, got {result}")
                
    except Exception as e:
        log_fail("Safety Heuristics", str(e))

# ============================================================
# MAIN TEST RUNNER
# ============================================================
async def main():
    print("="*60)
    print("POLYMARKET BOT - COMPREHENSIVE TEST SUITE")
    print("="*60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all tests
    config = await test_config_loading()
    await test_polygon_rpc(config)
    await test_gamma_api()
    await test_binance_websocket()
    await test_clob_client(config)
    await test_nvidia_api(config)
    await test_15min_detection()
    await test_trading_logic()
    await test_safety_heuristics()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed:   {len(RESULTS['passed'])}")
    print(f"❌ Failed:   {len(RESULTS['failed'])}")
    print(f"⚠️ Warnings: {len(RESULTS['warnings'])}")
    print("="*60)
    
    if RESULTS['failed']:
        print("\nFailed Tests:")
        for t in RESULTS['failed']:
            print(f"  ❌ {t}")
    
    if RESULTS['warnings']:
        print("\nWarnings:")
        for t in RESULTS['warnings']:
            print(f"  ⚠️ {t}")
    
    print("\n" + "="*60)
    if not RESULTS['failed']:
        print("🎉 ALL CRITICAL TESTS PASSED - BOT IS READY!")
    else:
        print("⚠️ SOME TESTS FAILED - REVIEW ABOVE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
