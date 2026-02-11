#!/usr/bin/env python3
"""Test simple order placement using market order"""
import os
from decimal import Decimal
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER_ADDRESS = "0x93e65c1419AB8147cbd16d440Bb7FC178b3b2F35"

# Current ETH UP token from logs
TOKEN_ID = "104251913076115125885070298067690172382209181844742193788276609385854884954706"

print("=" * 80)
print("SIMPLE ORDER TEST")
print("=" * 80)

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

print(f"API Key: {creds.api_key}")
print(f"Funder: {FUNDER_ADDRESS}")
print()

# Try using create_market_order instead
print("Testing create_market_order...")
try:
    from py_clob_client.clob_types import MarketOrderArgs
    from py_clob_client.order_builder.constants import BUY
    
    order_args = MarketOrderArgs(
        token_id=TOKEN_ID,
        amount=1.0,  # $1 worth
        side=BUY,
    )
    
    response = client.create_market_order(order_args)
    print(f"✅ Market order created: {response}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
