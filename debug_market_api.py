#!/usr/bin/env python3
"""
Debug script to see actual market API response format.
"""

import json
from py_clob_client.client import ClobClient
from config.config import load_config

def main():
    """Fetch and display raw market data."""
    
    print("=" * 80)
    print("MARKET API DEBUG")
    print("=" * 80)
    
    # Load config
    config = load_config()
    
    # Initialize client
    print(f"\nConnecting to: {config.polymarket_api_url}")
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
        
        # Check response type
        print(f"\nResponse type: {type(response)}")
        
        # Get raw markets
        if isinstance(response, dict):
            raw_markets = response.get('data', [])
        else:
            raw_markets = response
        
        print(f"Total markets: {len(raw_markets)}")
        
        # Show first market in detail
        if raw_markets:
            print("\n" + "=" * 80)
            print("FIRST MARKET (RAW DATA)")
            print("=" * 80)
            first_market = raw_markets[0]
            print(json.dumps(first_market, indent=2, default=str))
            
            # Check for end_date_iso field
            print("\n" + "=" * 80)
            print("END DATE FIELD CHECK")
            print("=" * 80)
            print(f"Has 'end_date_iso': {'end_date_iso' in first_market}")
            if 'end_date_iso' in first_market:
                print(f"Value: {first_market['end_date_iso']}")
                print(f"Type: {type(first_market['end_date_iso'])}")
            
            # Check for alternative date fields
            print("\nAll date-related fields:")
            for key in first_market.keys():
                if 'date' in key.lower() or 'time' in key.lower() or 'end' in key.lower():
                    print(f"  {key}: {first_market[key]}")
        
    except Exception as e:
        print(f"[FAIL] Error fetching markets: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
