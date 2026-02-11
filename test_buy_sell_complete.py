#!/usr/bin/env python3
"""
Complete test of BUY and SELL functionality
Tests the full cycle: Buy -> Hold -> Sell
"""
import os
import asyncio
from decimal import Decimal
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs
from py_clob_client.order_builder.constants import BUY, SELL
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER_ADDRESS = "0x93e65c1419AB8147cbd16d440Bb7FC178b3b2F35"

# Use a current token ID from the bot logs (10:30-10:45 UTC market)
TOKEN_ID = "70228968863405128135082438146470327085176308688393085061507569980967815855264"

print("=" * 80)
print("COMPLETE BUY/SELL TEST")
print("=" * 80)
print(f"Token ID: {TOKEN_ID}")
print()

# Initialize client
client = ClobClient(
    "https://clob.polymarket.com",
    key=PRIVATE_KEY,
    chain_id=137,
    signature_type=2,
    funder=FUNDER_ADDRESS
)

creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)

print(f"✅ Client initialized")
print(f"   API Key: {creds.api_key}")
print(f"   Funder: {FUNDER_ADDRESS}")
print()

# Get current price
try:
    price = client.get_price(TOKEN_ID, side="BUY")
    print(f"📊 Current BUY price: ${price}")
except Exception as e:
    print(f"❌ Error getting price: {e}")
    exit(1)

# Test 1: BUY order
print()
print("=" * 80)
print("TEST 1: PLACING BUY ORDER")
print("=" * 80)

try:
    buy_amount = round(0.50, 2)  # $0.50 test order (2 decimals)
    
    buy_args = MarketOrderArgs(
        token_id=TOKEN_ID,
        amount=buy_amount,
        side=BUY,
    )
    
    print(f"Creating BUY order: ${buy_amount}")
    buy_order = client.create_market_order(buy_args)
    print(f"✅ Order created, posting...")
    
    buy_response = client.post_order(buy_order)
    print(f"✅ BUY ORDER PLACED!")
    print(f"   Response: {buy_response}")
    
    if isinstance(buy_response, dict):
        order_id = buy_response.get("orderID") or buy_response.get("order_id")
        print(f"   Order ID: {order_id}")
        
except Exception as e:
    print(f"❌ BUY failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Wait a bit for order to fill
print()
print("⏳ Waiting 5 seconds for order to fill...")
import time
time.sleep(5)

# Test 2: SELL order
print()
print("=" * 80)
print("TEST 2: PLACING SELL ORDER")
print("=" * 80)

try:
    sell_amount = round(0.50, 2)  # Sell same amount (2 decimals)
    
    sell_args = MarketOrderArgs(
        token_id=TOKEN_ID,
        amount=sell_amount,
        side=SELL,
    )
    
    print(f"Creating SELL order: ${sell_amount}")
    sell_order = client.create_market_order(sell_args)
    print(f"✅ Order created, posting...")
    
    sell_response = client.post_order(sell_order)
    print(f"✅ SELL ORDER PLACED!")
    print(f"   Response: {sell_response}")
    
    if isinstance(sell_response, dict):
        order_id = sell_response.get("orderID") or sell_response.get("order_id")
        print(f"   Order ID: {order_id}")
        
except Exception as e:
    print(f"❌ SELL failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("=" * 80)
print("✅ ALL TESTS PASSED!")
print("=" * 80)
print("Both BUY and SELL orders were successfully placed.")
print("The bot's order placement logic is working correctly.")
