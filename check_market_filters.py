#!/usr/bin/env python3
"""
Check what filters are blocking markets.
"""

from datetime import datetime, timezone
from py_clob_client.client import ClobClient
from config.config import load_config

def main():
    """Check market filters."""
    
    print("=" * 80)
    print("MARKET FILTER ANALYSIS")
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
    
    # Fetch markets
    print("Fetching markets...")
    response = client.get_markets()
    raw_markets = response.get('data', []) if isinstance(response, dict) else response
    print(f"Total raw markets: {len(raw_markets)}\n")
    
    # Analyze filters
    now = datetime.now(timezone.utc)
    
    stats = {
        'total': len(raw_markets),
        'has_end_date': 0,
        'no_end_date': 0,
        'expired': 0,
        'future': 0,
        'closed': 0,
        'not_closed': 0,
        'accepting_orders': 0,
        'not_accepting_orders': 0,
        'pass_all_filters': 0
    }
    
    passing_markets = []
    
    for market in raw_markets:
        # Check end_date
        end_date_str = market.get('end_date_iso')
        if end_date_str:
            stats['has_end_date'] += 1
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                if end_date < now:
                    stats['expired'] += 1
                else:
                    stats['future'] += 1
            except:
                pass
        else:
            stats['no_end_date'] += 1
        
        # Check closed
        if market.get('closed', False):
            stats['closed'] += 1
        else:
            stats['not_closed'] += 1
        
        # Check accepting_orders
        if market.get('accepting_orders', False):
            stats['accepting_orders'] += 1
        else:
            stats['not_accepting_orders'] += 1
        
        # Check if passes all filters
        is_expired = False
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                is_expired = end_date < now
            except:
                pass
        
        is_closed = market.get('closed', False)
        is_accepting = market.get('accepting_orders', True)  # Default to True if not specified
        
        # Pass if: not expired AND not closed AND accepting orders
        if not is_expired and not is_closed and is_accepting:
            stats['pass_all_filters'] += 1
            passing_markets.append(market)
    
    print("=" * 80)
    print("FILTER STATISTICS")
    print("=" * 80)
    print(f"Total markets: {stats['total']}")
    print(f"\nEnd date:")
    print(f"  Has end_date_iso: {stats['has_end_date']}")
    print(f"  No end_date_iso: {stats['no_end_date']}")
    print(f"  Expired: {stats['expired']}")
    print(f"  Future: {stats['future']}")
    print(f"\nClosed status:")
    print(f"  Closed: {stats['closed']}")
    print(f"  Not closed: {stats['not_closed']}")
    print(f"\nAccepting orders:")
    print(f"  Accepting: {stats['accepting_orders']}")
    print(f"  Not accepting: {stats['not_accepting_orders']}")
    print(f"\n" + "=" * 80)
    print(f"MARKETS PASSING ALL FILTERS: {stats['pass_all_filters']}")
    print("=" * 80)
    
    if passing_markets:
        print("\nSample passing markets:")
        for i, market in enumerate(passing_markets[:10]):
            question = market.get('question', 'Unknown')
            end_date = market.get('end_date_iso', 'No end date')
            print(f"\n{i+1}. {question[:70]}...")
            print(f"   End date: {end_date}")
            print(f"   Closed: {market.get('closed', False)}")
            print(f"   Accepting orders: {market.get('accepting_orders', False)}")
    else:
        print("\n[!] NO MARKETS PASS ALL FILTERS")
        print("\nLet's relax filters and see what we get:")
        print("\nMarkets that are NOT closed:")
        not_closed = [m for m in raw_markets if not m.get('closed', False)]
        print(f"  Count: {len(not_closed)}")
        if not_closed:
            for i, market in enumerate(not_closed[:5]):
                question = market.get('question', 'Unknown')
                end_date = market.get('end_date_iso', 'No end date')
                accepting = market.get('accepting_orders', False)
                print(f"\n  {i+1}. {question[:60]}...")
                print(f"     End date: {end_date}")
                print(f"     Accepting orders: {accepting}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
