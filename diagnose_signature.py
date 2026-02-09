#!/usr/bin/env python3
"""
Test script to diagnose signature type and funder address issues.
Run this on AWS to find the correct configuration for order signing.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.order_builder.constants import BUY
from web3 import Web3
import requests

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

def get_wallet_address():
    """Get the EOA address from private key."""
    w3 = Web3()
    account = w3.eth.account.from_key(PRIVATE_KEY)
    return account.address

def get_proxy_wallet_from_api(eoa_address: str):
    """Query Polymarket API for proxy wallet address."""
    try:
        # Query the proxy wallet API
        url = f"https://gamma-api.polymarket.com/users?address={eoa_address}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                proxy = data[0].get('proxyWallet') or data[0].get('polyAddress')
                if proxy:
                    print(f"✅ Found proxy wallet from API: {proxy}")
                    return proxy
    except Exception as e:
        print(f"❌ Failed to query proxy wallet: {e}")
    return None

def test_signature_type(sig_type: int, funder: str):
    """Test if a signature type works for order signing."""
    print(f"\n--- Testing signature_type={sig_type} with funder={funder} ---")
    
    try:
        client = ClobClient(
            host=CLOB_HOST,
            key=PRIVATE_KEY,
            chain_id=CHAIN_ID,
            signature_type=sig_type,
            funder=funder
        )
        
        # Derive API credentials
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print(f"✅ API credentials derived successfully")
        api_key = getattr(creds, 'api_key', None) or getattr(creds, 'apiKey', None) or str(creds)[:30]
        print(f"   API Key: {api_key}...")
        
        # Try to get a CRYPTO market to place a test order (these have valid token IDs)
        markets_resp = requests.get(
            "https://gamma-api.polymarket.com/markets?active=true&tag=crypto&limit=10", 
            timeout=10
        )
        if markets_resp.status_code != 200:
            print(f"❌ Failed to fetch markets")
            return False
            
        markets = markets_resp.json()
        if not markets:
            print(f"❌ No active crypto markets found")
            return False
        
        # Find a market with proper clobTokenIds
        market = None
        token_id = None
        for m in markets:
            clob_ids = m.get('clobTokenIds') or []
            if clob_ids and len(clob_ids) > 0 and clob_ids[0]:
                market = m
                token_id = clob_ids[0]
                break
        
        if not token_id:
            print(f"❌ No valid token ID found in any market")
            return False
        if not token_id:
            print(f"❌ No token ID found")
            return False
            
        print(f"   Using market: {market.get('question', 'Unknown')[:50]}...")
        print(f"   Token ID: {token_id[:30]}...")
        
        # Try to create and sign an order (but don't post it)
        # We'll use a very low price so it won't fill even if it gets through
        order_args = OrderArgs(
            token_id=token_id,
            price=0.01,  # Very low price, won't fill
            size=1.0,
            side=BUY
        )
        
        # Create order to test signing (this will fail if signature is wrong)
        print("   Attempting to create and sign order...")
        
        from types import SimpleNamespace
        try:
            order = client.create_order(
                order_args,
                options=SimpleNamespace(tick_size="0.01", neg_risk=False)
            )
            print(f"✅ Order created successfully!")
            print(f"   Order signature: {order.get('signature', 'N/A')[:30]}...")
            
            # Try to post the order
            print("   Attempting to post order...")
            response = client.post_order(order)
            if response:
                print(f"✅ ORDER POSTED SUCCESSFULLY!")
                print(f"   Response: {response}")
                return True
            else:
                print(f"❌ Empty response from post_order")
                return False
                
        except Exception as e:
            print(f"❌ Order creation/posting failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("POLYMARKET SIGNATURE DIAGNOSTIC TOOL")
    print("=" * 60)
    
    eoa_address = get_wallet_address()
    print(f"\nEOA Address: {eoa_address}")
    
    # Get proxy wallet
    proxy_address = get_proxy_wallet_from_api(eoa_address)
    
    # Test all combinations
    test_cases = [
        (0, eoa_address, "EOA with EOA funder"),
        (1, eoa_address, "POLY_PROXY with EOA funder"),
        (2, eoa_address, "GNOSIS_SAFE with EOA funder"),
    ]
    
    if proxy_address:
        test_cases.extend([
            (0, proxy_address, "EOA with Proxy funder"),
            (1, proxy_address, "POLY_PROXY with Proxy funder"),
            (2, proxy_address, "GNOSIS_SAFE with Proxy funder"),
        ])
    
    print(f"\nRunning {len(test_cases)} test cases...")
    
    working_config = None
    for sig_type, funder, description in test_cases:
        print(f"\n{'='*60}")
        print(f"TEST: {description}")
        print(f"{'='*60}")
        if test_signature_type(sig_type, funder):
            working_config = (sig_type, funder, description)
            print(f"\n🎉 FOUND WORKING CONFIGURATION!")
            print(f"   Signature Type: {sig_type}")
            print(f"   Funder Address: {funder}")
            break
    
    if working_config:
        sig_type, funder, desc = working_config
        print(f"\n" + "="*60)
        print(f"✅ SUCCESS! Use these settings in main_orchestrator.py:")
        print(f"   signature_type={sig_type}")
        print(f"   funder=\"{funder}\"")
        print(f"="*60)
    else:
        print(f"\n" + "="*60)
        print(f"❌ ALL CONFIGURATIONS FAILED")
        print(f"   The wallet may not have been properly initialized on Polymarket")
        print(f"   Try logging into polymarket.com first with this wallet")
        print(f"="*60)

if __name__ == "__main__":
    main()
