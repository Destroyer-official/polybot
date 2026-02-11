"""
Test script to verify the order placement fix using create_order with OrderArgs.
This tests the decimal precision fix for both buy and sell orders.
"""

import os
from decimal import Decimal
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY, SELL

load_dotenv()

# Initialize client
host = "https://clob.polymarket.com"
private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
chain_id = 137  # Polygon mainnet

client = ClobClient(host, key=private_key, chain_id=chain_id)

# Test token ID (ETH UP from current 15-min market)
# This is just for testing the order creation, not actual placement
test_token_id = "70228968863405128135082438146470327085176308688393085061507569980967815855264"

print("=" * 80)
print("TESTING ORDER CREATION WITH create_order + OrderArgs")
print("=" * 80)

# Test Case 1: Buy order with price that previously caused decimal errors
print("\nTest 1: Buy order @ $0.755 for 1.32 shares")
price_1 = 0.755
size_1 = 1.32
print(f"  Input: price={price_1}, size={size_1}")
print(f"  Total value: ${price_1 * size_1:.2f}")

try:
    order_args_1 = OrderArgs(
        token_id=test_token_id,
        price=price_1,
        size=size_1,
        side=BUY,
    )
    signed_order_1 = client.create_order(order_args_1)
    print(f"  ✅ Order created successfully!")
    print(f"  Maker amount: {signed_order_1.get('makerAmount', 'N/A')}")
    print(f"  Taker amount: {signed_order_1.get('takerAmount', 'N/A')}")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Test Case 2: Buy order @ $0.515 for 1.94 shares
print("\nTest 2: Buy order @ $0.515 for 1.94 shares")
price_2 = 0.515
size_2 = 1.94
print(f"  Input: price={price_2}, size={size_2}")
print(f"  Total value: ${price_2 * size_2:.2f}")

try:
    order_args_2 = OrderArgs(
        token_id=test_token_id,
        price=price_2,
        size=size_2,
        side=BUY,
    )
    signed_order_2 = client.create_order(order_args_2)
    print(f"  ✅ Order created successfully!")
    print(f"  Maker amount: {signed_order_2.get('makerAmount', 'N/A')}")
    print(f"  Taker amount: {signed_order_2.get('takerAmount', 'N/A')}")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Test Case 3: Sell order @ $0.175 for 5.71 shares (this one worked before)
print("\nTest 3: Sell order @ $0.175 for 5.71 shares")
price_3 = 0.175
size_3 = 5.71
print(f"  Input: price={price_3}, size={size_3}")
print(f"  Total value: ${price_3 * size_3:.2f}")

try:
    order_args_3 = OrderArgs(
        token_id=test_token_id,
        price=price_3,
        size=size_3,
        side=SELL,
    )
    signed_order_3 = client.create_order(order_args_3)
    print(f"  ✅ Order created successfully!")
    print(f"  Maker amount: {signed_order_3.get('makerAmount', 'N/A')}")
    print(f"  Taker amount: {signed_order_3.get('takerAmount', 'N/A')}")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Test Case 4: Buy order @ $0.22 for 4.55 shares
print("\nTest 4: Buy order @ $0.22 for 4.55 shares")
price_4 = 0.22
size_4 = 4.55
print(f"  Input: price={price_4}, size={size_4}")
print(f"  Total value: ${price_4 * size_4:.2f}")

try:
    order_args_4 = OrderArgs(
        token_id=test_token_id,
        price=price_4,
        size=size_4,
        side=BUY,
    )
    signed_order_4 = client.create_order(order_args_4)
    print(f"  ✅ Order created successfully!")
    print(f"  Maker amount: {signed_order_4.get('makerAmount', 'N/A')}")
    print(f"  Taker amount: {signed_order_4.get('takerAmount', 'N/A')}")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print("\nNOTE: Orders were created but NOT posted to the exchange.")
print("This test only validates that create_order handles decimal precision correctly.")
