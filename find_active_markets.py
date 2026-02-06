#!/usr/bin/env python3
"""
Find active markets by checking Polymarket website directly.
"""

import json
from datetime import datetime, timezone
from py_clob_client.client import ClobClient
from config.config import load_config

def main():
    """Find active markets."""
    
    print("=" * 80)
    print("FINDING ACTIVE MARKETS")
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
    
    # Strategy: Fetch multiple pages and find ANY tradeable markets
    print("Fetching markets (checking multiple pages)...")
    print("-" * 80)
    
    all_markets = []
    next_cursor = None
    pages_checked = 0
    max_pages = 5  # Check first 5 pages (5000 markets)
    
    try:
        while pages_checked < max_pages:
            # Fetch page
            if next_cursor:
                # Note: py_clob_client might not support cursor parameter
                # Let's just use the default for now
                break
            else:
                response = client.get_markets()
            
            if isinstance(response, dict):
                markets = response.get('data', [])
                next_cursor = response.get('next_cursor')
            else:
                markets = response
                next_cursor = None
            
            all_markets.extend(markets)
            pages_checked += 1
            
            print(f"Page {pages_checked}: {len(markets)} markets")
            
            if not next_cursor:
                break
        
        print(f"\nTotal markets fetched: {len(all_markets)}")
        
        # Analyze all markets
        now = datetime.now(timezone.utc)
        
        tradeable_markets = []
        
        for market in all_markets:
            # Check if tradeable
            accepting_orders = market.get('accepting_orders', False)
            closed = market.get('closed', False)
            end_date_str = market.get('end_date_iso')
            
            # Must be accepting orders and not closed
            if not accepting_orders or closed:
                continue
            
            # Check if future (if end_date available)
            is_future = True
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    is_future = end_date > now
                except:
                    pass
            
            if is_future:
                tradeable_markets.append(market)
        
        print(f"\n" + "=" * 80)
        print(f"TRADEABLE MARKETS FOUND: {len(tradeable_markets)}")
        print("=" * 80)
        
        if tradeable_markets:
            print("\nShowing first 10 tradeable markets:")
            for i, market in enumerate(tradeable_markets[:10]):
                question = market.get('question', 'Unknown')
                end_date = market.get('end_date_iso', 'Unknown')
                tokens = market.get('tokens', [])
                
                print(f"\n{i+1}. {question[:70]}...")
                print(f"   End date: {end_date}")
                print(f"   Tokens: {len(tokens)}")
                
                if tokens:
                    for token in tokens[:2]:
                        outcome = token.get('outcome', 'Unknown')
                        price = token.get('price', 0)
                        print(f"     - {outcome}: ${price}")
        else:
            print("\n[!] NO TRADEABLE MARKETS FOUND IN FIRST 5 PAGES")
            print("\nPossible reasons:")
            print("1. Polymarket has very few active markets right now")
            print("2. API is returning old/cached data")
            print("3. Need to check Polymarket website directly")
            print("\nLet's check what markets are actually accepting orders:")
            
            accepting_any = [m for m in all_markets if m.get('accepting_orders', False)]
            print(f"\nMarkets accepting orders (any): {len(accepting_any)}")
            
            if accepting_any:
                print("\nSample markets accepting orders:")
                for i, market in enumerate(accepting_any[:5]):
                    question = market.get('question', 'Unknown')
                    end_date = market.get('end_date_iso', 'Unknown')
                    closed = market.get('closed', False)
                    
                    print(f"\n{i+1}. {question[:70]}...")
                    print(f"   End date: {end_date}")
                    print(f"   Closed: {closed}")
                    print(f"   Accepting orders: True")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
