#!/usr/bin/env python3
"""
Debug script to test different API parameters.
"""

import json
from datetime import datetime, timezone
from py_clob_client.client import ClobClient
from config.config import load_config

def main():
    """Test different API parameters."""
    
    print("=" * 80)
    print("API PARAMETERS TEST")
    print("=" * 80)
    
    # Load config
    config = load_config()
    
    # Initialize client
    client = ClobClient(
        host=config.polymarket_api_url,
        key=config.private_key,
        chain_id=config.chain_id
    )
    
    # Derive API credentials
    try:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print("[OK] API credentials derived\n")
    except Exception as e:
        print(f"[!] Failed to derive API credentials: {e}\n")
    
    # Test 1: Default get_markets()
    print("TEST 1: Default get_markets()")
    print("-" * 80)
    try:
        response = client.get_markets()
        markets = response.get('data', []) if isinstance(response, dict) else response
        print(f"Total markets: {len(markets)}")
        
        # Count accepting orders
        accepting = sum(1 for m in markets if m.get('accepting_orders', False))
        print(f"Accepting orders: {accepting}")
        
        # Count not closed
        not_closed = sum(1 for m in markets if not m.get('closed', False))
        print(f"Not closed: {not_closed}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Try with next_cursor (pagination)
    print("\nTEST 2: Check if there's pagination")
    print("-" * 80)
    try:
        response = client.get_markets()
        if isinstance(response, dict):
            print(f"Response keys: {response.keys()}")
            if 'next_cursor' in response:
                print(f"Next cursor: {response['next_cursor']}")
            else:
                print("No next_cursor field - all markets returned")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: Check client methods
    print("\nTEST 3: Available client methods")
    print("-" * 80)
    methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
    print("Market-related methods:")
    for method in methods:
        if 'market' in method.lower() or 'order' in method.lower():
            print(f"  - {method}")
    
    # Test 4: Try to get orderbook for an accepting_orders market
    print("\nTEST 4: Check orderbook for active market")
    print("-" * 80)
    try:
        response = client.get_markets()
        markets = response.get('data', []) if isinstance(response, dict) else response
        
        # Find a market accepting orders
        active_market = None
        for m in markets:
            if m.get('accepting_orders', False) and not m.get('closed', False):
                active_market = m
                break
        
        if active_market:
            token_id = active_market['tokens'][0]['token_id']
            print(f"Found active market: {active_market['question'][:60]}...")
            print(f"Token ID: {token_id}")
            
            # Try to get orderbook
            try:
                orderbook = client.get_order_book(token_id)
                print(f"Orderbook retrieved successfully")
                print(f"Bids: {len(orderbook.get('bids', []))}")
                print(f"Asks: {len(orderbook.get('asks', []))}")
            except Exception as e:
                print(f"Failed to get orderbook: {e}")
        else:
            print("No active markets found")
            
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
