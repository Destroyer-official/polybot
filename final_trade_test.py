#!/usr/bin/env python3
"""
FINAL TEST - Order with $2 value (above $1 minimum).

From previous error: "min size: $1" - our orders were being rejected
because the order VALUE was below $1, not signature issue!

Order value = size * price
To get $2 value at price $0.50: size = $2 / $0.50 = 4 shares
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY
from types import SimpleNamespace
import requests

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER_ADDRESS = "0x93e65c1419AB8147cbd16d440Bb7FC178b3b2F35"

def main():
    print("=" * 60)
    print("FINAL ORDER TEST - Meeting $1 minimum order value")
    print("=" * 60)
    
    from web3 import Web3
    eoa = Web3().eth.account.from_key(PRIVATE_KEY).address
    print(f"\nEOA: {eoa}")
    print(f"Funder: {FUNDER_ADDRESS}")
    print(f"Key: {PRIVATE_KEY[:5]}...{PRIVATE_KEY[-5:]}")
    print(f"Len: {len(PRIVATE_KEY)}")
    
    # Get market
    print("\n1. Getting market...")
    resp = requests.get("https://clob.polymarket.com/sampling-markets?limit=20", timeout=30)
    markets = resp.json().get('data', [])
    
    # Find good market
    target = None
    for m in markets:
        if m.get('active') and m.get('enable_order_book') and not m.get('neg_risk'):
            tokens = m.get('tokens', [])
            if tokens:
                target = m
                break
    
    if not target:
        print("No suitable market found!")
        return
    
    token_id = target['tokens'][0]['token_id']
    tick_size = str(target.get('minimum_tick_size', '0.01'))
    
    print(f"   Market: {target.get('question', '')[:50]}...")
    print(f"   Token: {token_id[:40]}...")
    print(f"   Tick: {tick_size}")
    
    # Try signature_type=2 (GNOSIS_SAFE) - for browser wallet proxies
    print("\n2. Creating client (sig_type=2, GNOSIS_SAFE)...")
    
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=PRIVATE_KEY,
        chain_id=137,
        signature_type=2,  # GNOSIS_SAFE for browser wallet proxy
        funder=FUNDER_ADDRESS
    )
    
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    print(f"   API Key: {creds.api_key}")
    
    # Get order book
    print("\n3. Getting order book...")
    try:
        book = client.get_order_book(token_id)
        if hasattr(book, 'asks') and book.asks:
            best_ask = float(book.asks[0].price)
            print(f"   Best Ask: ${best_ask}")
        else:
            best_ask = 0.50
    except Exception as e:
        print(f"   Order book error: {e}")
        best_ask = 0.50
    
    # Calculate size to meet $1 minimum value
    # Order value = size * price >= $1
    # size >= $1 / price
    min_size = max(2.0, 1.0 / best_ask + 0.5)  # At least $1 order value + margin
    
    print(f"\n4. Placing order:")
    print(f"   Price: ${best_ask}")
    print(f"   Size: {min_size} shares")
    print(f"   Order value: ${best_ask * min_size:.2f}")
    
    order_args = OrderArgs(
        token_id=token_id,
        price=best_ask,
        size=min_size,
        side=BUY
    )
    
    options = SimpleNamespace(tick_size=tick_size, neg_risk=False)
    
    try:
        response = client.create_and_post_order(order_args, options)
        print(f"\n   Response: {response}")
        
        resp_str = str(response).lower() if response else ""
        if 'invalid signature' in resp_str:
            print("\n❌ Invalid signature")
            # Try sig_type=0 and sig_type=1 as fallback
            return test_other_sig_types(token_id, tick_size, best_ask, min_size)
        elif 'insufficient' in resp_str:
            print("\n🎉 SIGNATURE WORKS! (insufficient balance = order was valid)")
            return True
        elif 'success' in resp_str or 'orderid' in resp_str or 'id' in resp_str.replace('invalid', ''):
            print("\n🎉 ORDER PLACED SUCCESSFULLY!")
            return True
        else:
            print(f"\n⚠️ Response: {response}")
            
    except Exception as e:
        error_str = str(e).lower()
        print(f"\n   Error: {e}")
        
        if 'invalid signature' in error_str:
            print("\n❌ Invalid signature with sig_type=2")
            return test_other_sig_types(token_id, tick_size, best_ask, min_size)
        elif 'insufficient' in error_str:
            print("\n🎉 SIGNATURE WORKS! (insufficient balance)")
            return True
        elif 'min size' in error_str or 'minimum' in error_str:
            print("\n⚠️ Still a size issue, need larger order")
            return False
    
    return False

def test_other_sig_types(token_id, tick_size, price, size):
    """Test remaining signature types."""
    for sig_type in [1, 0]:
        sig_name = {0: "EOA", 1: "POLY_PROXY"}[sig_type]
        print(f"\n--- Testing sig_type={sig_type} ({sig_name}) ---")
        
        try:
            client = ClobClient(
                host="https://clob.polymarket.com",
                key=PRIVATE_KEY,
                chain_id=137,
                signature_type=sig_type,
                funder=FUNDER_ADDRESS
            )
            
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=BUY
            )
            
            options = SimpleNamespace(tick_size=tick_size, neg_risk=False)
            response = client.create_and_post_order(order_args, options)
            
            resp_str = str(response).lower() if response else ""
            if 'invalid signature' not in resp_str:
                print(f"\n🎉 SUCCESS with sig_type={sig_type}!")
                return True
                
        except Exception as e:
            if 'insufficient' in str(e).lower():
                print(f"\n🎉 SIGNATURE WORKS with sig_type={sig_type}!")
                return True
            print(f"   Error: {e}")
    
    return False

if __name__ == "__main__":
    success = main()
    print("\n" + "=" * 60)
    if success:
        print("✅ SIGNATURE ISSUE RESOLVED!")
        print("The bot can now place orders successfully.")
    else:
        print("❌ Issue persists")
    print("=" * 60)
