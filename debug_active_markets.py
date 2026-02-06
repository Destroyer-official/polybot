#!/usr/bin/env python3
"""
Debug script to find active markets.
"""

import json
from datetime import datetime, timezone
from py_clob_client.client import ClobClient
from config.config import load_config

def main():
    """Fetch and analyze market status."""
    
    print("=" * 80)
    print("ACTIVE MARKETS ANALYSIS")
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
        print("[OK] API credentials derived")
    except Exception as e:
        print(f"[!] Failed to derive API credentials: {e}")
    
    # Fetch markets
    print("\nFetching markets...")
    try:
        response = client.get_markets()
        
        # Get raw markets
        if isinstance(response, dict):
            raw_markets = response.get('data', [])
        else:
            raw_markets = response
        
        print(f"Total markets: {len(raw_markets)}")
        
        # Analyze market status
        now = datetime.now(timezone.utc)
        
        active_count = 0
        closed_count = 0
        expired_count = 0
        future_count = 0
        accepting_orders_count = 0
        
        active_markets = []
        
        for market in raw_markets:
            is_active = market.get('active', False)
            is_closed = market.get('closed', False)
            accepting_orders = market.get('accepting_orders', False)
            end_date_str = market.get('end_date_iso')
            
            if is_active:
                active_count += 1
            if is_closed:
                closed_count += 1
            if accepting_orders:
                accepting_orders_count += 1
            
            # Check if expired
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    if end_date < now:
                        expired_count += 1
                    else:
                        future_count += 1
                        
                        # This is a future market
                        if accepting_orders and not is_closed:
                            active_markets.append({
                                'question': market.get('question', 'Unknown'),
                                'end_date': end_date_str,
                                'accepting_orders': accepting_orders,
                                'active': is_active,
                                'closed': is_closed
                            })
                except:
                    pass
        
        print("\n" + "=" * 80)
        print("MARKET STATUS SUMMARY")
        print("=" * 80)
        print(f"Total markets: {len(raw_markets)}")
        print(f"Active flag=true: {active_count}")
        print(f"Closed flag=true: {closed_count}")
        print(f"Accepting orders: {accepting_orders_count}")
        print(f"Expired (end_date < now): {expired_count}")
        print(f"Future (end_date > now): {future_count}")
        print(f"\nTradeable markets (accepting_orders=true, closed=false, future): {len(active_markets)}")
        
        # Show some active markets
        if active_markets:
            print("\n" + "=" * 80)
            print("SAMPLE ACTIVE MARKETS (first 10)")
            print("=" * 80)
            for i, market in enumerate(active_markets[:10]):
                print(f"\n{i+1}. {market['question']}")
                print(f"   End date: {market['end_date']}")
                print(f"   Accepting orders: {market['accepting_orders']}")
                print(f"   Active: {market['active']}")
                print(f"   Closed: {market['closed']}")
        else:
            print("\n[!] NO ACTIVE MARKETS FOUND")
            print("\nThis could mean:")
            print("1. All markets are closed/expired")
            print("2. API is returning old data")
            print("3. Need to use different API endpoint")
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
