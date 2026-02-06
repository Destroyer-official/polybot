#!/usr/bin/env python3
"""
Debug script to test simplified markets API.
"""

import json
from datetime import datetime, timezone
from py_clob_client.client import ClobClient
from config.config import load_config

def main():
    """Test simplified markets API."""
    
    print("=" * 80)
    print("SIMPLIFIED MARKETS TEST")
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
    
    # Test get_simplified_markets
    print("TEST: get_simplified_markets()")
    print("-" * 80)
    try:
        response = client.get_simplified_markets()
        
        print(f"Response type: {type(response)}")
        
        if isinstance(response, dict):
            print(f"Response keys: {response.keys()}")
            markets = response.get('data', [])
        else:
            markets = response
        
        print(f"Total markets: {len(markets)}")
        
        # Analyze markets
        now = datetime.now(timezone.utc)
        
        accepting_orders = 0
        not_closed = 0
        future_markets = 0
        tradeable = 0
        
        tradeable_markets = []
        
        for market in markets:
            if market.get('accepting_orders', False):
                accepting_orders += 1
            if not market.get('closed', False):
                not_closed += 1
            
            # Check if future
            end_date_str = market.get('end_date_iso')
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    if end_date > now:
                        future_markets += 1
                        
                        # Check if tradeable
                        if market.get('accepting_orders', False) and not market.get('closed', False):
                            tradeable += 1
                            tradeable_markets.append(market)
                except:
                    pass
        
        print(f"\nAccepting orders: {accepting_orders}")
        print(f"Not closed: {not_closed}")
        print(f"Future markets: {future_markets}")
        print(f"Tradeable (accepting_orders + not closed + future): {tradeable}")
        
        # Show sample tradeable markets
        if tradeable_markets:
            print("\n" + "=" * 80)
            print("SAMPLE TRADEABLE MARKETS (first 5)")
            print("=" * 80)
            for i, market in enumerate(tradeable_markets[:5]):
                print(f"\n{i+1}. {market.get('question', 'Unknown')[:70]}...")
                print(f"   Market ID: {market.get('condition_id', 'Unknown')[:20]}...")
                print(f"   End date: {market.get('end_date_iso', 'Unknown')}")
                print(f"   Accepting orders: {market.get('accepting_orders', False)}")
                print(f"   Closed: {market.get('closed', False)}")
                
                # Show tokens
                tokens = market.get('tokens', [])
                if tokens:
                    print(f"   Tokens: {len(tokens)}")
                    for token in tokens[:2]:
                        outcome = token.get('outcome', 'Unknown')
                        price = token.get('price', 0)
                        print(f"     - {outcome}: ${price}")
        else:
            print("\n[!] NO TRADEABLE MARKETS FOUND")
        
        # Show first market structure
        if markets:
            print("\n" + "=" * 80)
            print("FIRST MARKET STRUCTURE")
            print("=" * 80)
            print(json.dumps(markets[0], indent=2, default=str))
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
