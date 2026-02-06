#!/usr/bin/env python3
"""
Find markets with actual trading activity.
"""

import requests
from datetime import datetime, timezone

def main():
    """Find tradeable markets."""
    
    print("=" * 80)
    print("FINDING TRADEABLE MARKETS")
    print("=" * 80)
    
    # Gamma API endpoint
    base_url = "https://gamma-api.polymarket.com"
    
    # Fetch multiple pages to find active markets
    print("\nFetching markets...")
    all_markets = []
    
    for page in range(10):  # Check first 10 pages (1000 markets)
        try:
            url = f"{base_url}/markets"
            params = {
                'closed': 'false',
                'limit': 100,
                'offset': page * 100
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            markets = response.json()
            
            if not markets:
                break
            
            all_markets.extend(markets)
            print(f"Page {page + 1}: {len(markets)} markets")
            
        except Exception as e:
            print(f"Error on page {page + 1}: {e}")
            break
    
    print(f"\nTotal markets fetched: {len(all_markets)}")
    
    # Find markets with prices
    tradeable_markets = []
    
    for market in all_markets:
        tokens = market.get('tokens', [])
        if not tokens:
            continue
        
        # Check if any token has a price > 0
        has_price = any(float(t.get('price', 0)) > 0 for t in tokens)
        if has_price:
            tradeable_markets.append(market)
    
    print(f"\n" + "=" * 80)
    print(f"TRADEABLE MARKETS (with prices): {len(tradeable_markets)}")
    print("=" * 80)
    
    if tradeable_markets:
        print("\nShowing first 20 tradeable markets:")
        for i, market in enumerate(tradeable_markets[:20]):
            question = market.get('question', 'Unknown')
            end_date = market.get('end_date_iso', 'No end date')
            tokens = market.get('tokens', [])
            
            print(f"\n{i+1}. {question[:70]}...")
            print(f"   End date: {end_date}")
            
            if tokens:
                for token in tokens[:2]:
                    outcome = token.get('outcome', 'Unknown')
                    price = token.get('price', 0)
                    print(f"     - {outcome}: ${price}")
    else:
        print("\n[!] NO TRADEABLE MARKETS FOUND")
        print("\nThis could mean:")
        print("1. All active markets are newly created with no trading yet")
        print("2. Need to check a different API endpoint")
        print("3. Need to use CLOB API orderbook to get real-time prices")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
