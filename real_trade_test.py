#!/usr/bin/env python3
"""
Real trade test V11 - Try WITHOUT explicit funder (let SDK derive).

The issue might be that we're overriding the funder incorrectly.
The SDK may need to derive the correct funder based on signature type.
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

def test_with_funder(funder, sig_type, desc):
    """Test a specific signature_type and funder combination."""
    print(f"\n{'='*60}")
    print(f"Testing: {desc}")
    print(f"   signature_type={sig_type}, funder={'AUTO' if funder is None else funder[:20]+'...'}")
    print("=" * 60)
    
    try:
        # Build kwargs
        kwargs = {
            "host": "https://clob.polymarket.com",
            "key": PRIVATE_KEY,
            "chain_id": 137,
            "signature_type": sig_type,
        }
        if funder:
            kwargs["funder"] = funder
            
        client = ClobClient(**kwargs)
        
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print(f"   API Key: {creds.api_key}")
        
        # Get a simple active market
        resp = requests.get("https://clob.polymarket.com/sampling-markets?limit=10", timeout=30)
        markets = resp.json().get('data', [])
        
        target = None
        for m in markets:
            if m.get('active') and m.get('enable_order_book') and not m.get('neg_risk'):
                tokens = m.get('tokens', [])
                if tokens:
                    target = m
                    break
        
        if not target:
            print("   No suitable market")
            return False
        
        token_id = target['tokens'][0]['token_id']
        tick_size = str(target.get('minimum_tick_size', '0.01'))
        neg_risk = target.get('neg_risk', False)
        
        # Get price
        try:
            book = client.get_order_book(token_id)
            if hasattr(book, 'asks') and book.asks:
                price = float(book.asks[0].price)
            else:
                price = 0.50
        except:
            price = 0.50
            
        # Place order
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=1.0,
            side=BUY
        )
        
        options = SimpleNamespace(tick_size=tick_size, neg_risk=neg_risk)
        response = client.create_and_post_order(order_args, options)
        
        print(f"   Response: {response}")
        
        resp_str = str(response).lower() if response else ""
        if 'invalid signature' not in resp_str:
            print(f"\n🎉 SUCCESS!")
            return True
            
    except Exception as e:
        error_str = str(e).lower()
        print(f"   Error: {e}")
        if 'insufficient' in error_str:
            print(f"\n🎉 SIGNATURE WORKS! (balance error means order was valid)")
            return True
    
    return False

def main():
    print("=" * 60)
    print("REAL TRADE TEST V11 - Testing all funder combinations")
    print("=" * 60)
    
    from web3 import Web3
    eoa = Web3().eth.account.from_key(PRIVATE_KEY).address
    proxy = "0x93e65c1419AB8147cbd16d440Bb7FC178b3b2F35"
    
    print(f"\nEOA: {eoa}")
    print(f"PROXY: {proxy}")
    
    # Test combinations
    tests = [
        # (funder, sig_type, description)
        (None, 0, "EOA sig, no funder"),
        (None, 1, "POLY_PROXY sig, no funder"),
        (None, 2, "GNOSIS_SAFE sig, no funder"),
        (eoa, 0, "EOA sig, EOA funder"),
        (eoa, 1, "POLY_PROXY sig, EOA funder"),  
        (eoa, 2, "GNOSIS_SAFE sig, EOA funder"),
    ]
    
    for funder, sig_type, desc in tests:
        if test_with_funder(funder, sig_type, desc):
            print(f"\n{'='*60}")
            print(f"✅ WORKING CONFIG FOUND!")
            print(f"   signature_type={sig_type}")
            print(f"   funder={'None (auto)' if funder is None else funder}")
            print("=" * 60)
            return
    
    print("\n❌ All combinations failed")

if __name__ == "__main__":
    main()
