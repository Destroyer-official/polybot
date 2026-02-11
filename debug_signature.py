#!/usr/bin/env python3
"""
Debug script to test order signature generation
"""
import os
import sys
from decimal import Decimal
from types import SimpleNamespace

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY
from dotenv import load_dotenv

load_dotenv()

# Load environment variables
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")

print("=" * 80)
print("SIGNATURE DEBUG TEST")
print("=" * 80)
print(f"Private Key: {PRIVATE_KEY[:10]}...")
print(f"Funder: {FUNDER_ADDRESS}")
print()

# Initialize client with Gnosis Safe config
print("1. Initializing ClobClient...")
client = ClobClient(
    host="https://clob.polymarket.com",
    key=PRIVATE_KEY,
    chain_id=137,
    signature_type=2,  # GNOSIS_SAFE
    funder=FUNDER_ADDRESS
)

print("2. Deriving API credentials...")
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)
print(f"   API Key: {creds.api_key}")
print()

# Test token ID (XRP UP from current market - 10:00-10:15 UTC)
TOKEN_ID = "34182421546761093145036640605836029860289280460021779541370417147643830702599"  # From recent logs
PRICE = 0.51  # Rounded to 2 decimals like the bot does
SIZE = 1.96  # Rounded to 2 decimals

print("3. Creating test order...")
print(f"   Token ID: {TOKEN_ID}")
print(f"   Price: ${PRICE}")
print(f"   Size: {SIZE} shares")
print()

try:
    # Create order
    order = client.create_order(
        OrderArgs(
            token_id=TOKEN_ID,
            price=PRICE,
            size=SIZE,
            side=BUY,
        ),
        options=SimpleNamespace(
            tick_size="0.01",
            neg_risk=True,
        )
    )
    
    print("4. Order created successfully!")
    print(f"   Order object: {type(order)}")
    print()
    
    # Try to post order
    print("5. Posting order to Polymarket...")
    response = client.post_order(order, orderType="GTC")
    
    print("✅ ORDER POSTED SUCCESSFULLY!")
    print(f"   Response: {response}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    print()
    print("Full traceback:")
    import traceback
    traceback.print_exc()
    
print()
print("=" * 80)
