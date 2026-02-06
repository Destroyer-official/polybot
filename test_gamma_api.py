#!/usr/bin/env python3
"""
Test Gamma API for active markets.
"""

import requests
from datetime import datetime, timezone

def main():
    """Test Gamma API."""
    
    print("=" * 80)
    print("TESTING GAMMA API")
    print("=" * 80)
    
    # Gamma API endpoint
    base_url = "https://gamma-api.polymarket.com"
    
    # Test 1: Get all active markets
    print("\nTEST 1: Get active markets (closed=false)")
    print("-" * 80)
    try:
        url = f"{base_url}/markets"
        params = {
            'closed': 'false',
            'limit': 100,
            'offset': 0
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        print(f"Status: {response.status_code}")
        print(f"Response keys: {data.keys() if isinstance(data, dict) else 'list'}")
        
        markets = data if isinstance(data, list) else data.get('data', [])
        print(f"Total markets: {len(markets)}")
        
        # Analyze markets
        now = datetime.now(timezone.utc)
        
        accepting_orders = 0
        not_closed = 0
        future_markets = 0
        has_prices = 0
        
        for market in markets:
            if market.get('accepting_orders', False):
                accepting_orders += 1
            if not market.get('closed', False):
                not_closed += 1
            
            # Check prices
            tokens = market.get('tokens', [])
            if tokens and any(float(t.get('price', 0)) > 0 for t in tokens):
                has_prices += 1
            
            # Check if future
            end_date_str = market.get('end_date_iso')
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    if end_date > now:
                        future_markets += 1
                except:
                    pass
        
        print(f"\nMarket statistics:")
        print(f"  Not closed: {not_closed}")
        print(f"  Accepting orders: {accepting_orders}")
        print(f"  Future markets: {future_markets}")
        print(f"  Has prices > 0: {has_prices}")
        
        # Show sample markets
        if markets:
            print("\n" + "=" * 80)
            print("SAMPLE ACTIVE MARKETS (first 5)")
            print("=" * 80)
            for i, market in enumerate(markets[:5]):
                question = market.get('question', 'Unknown')
                end_date = market.get('end_date_iso', 'No end date')
                closed = market.get('closed', False)
                accepting = market.get('accepting_orders', False)
                
                print(f"\n{i+1}. {question[:70]}...")
                print(f"   End date: {end_date}")
                print(f"   Closed: {closed}")
                print(f"   Accepting orders: {accepting}")
                
                # Show tokens
                tokens = market.get('tokens', [])
                if tokens:
                    for token in tokens[:2]:
                        outcome = token.get('outcome', 'Unknown')
                        price = token.get('price', 0)
                        print(f"     - {outcome}: ${price}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
