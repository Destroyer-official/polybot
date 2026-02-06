#!/usr/bin/env python3
"""
Check Gamma API field names.
"""

import requests
import json

def main():
    """Check Gamma API fields."""
    
    print("=" * 80)
    print("GAMMA API FIELD NAMES")
    print("=" * 80)
    
    # Gamma API endpoint
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        'closed': 'false',
        'limit': 1
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        markets = response.json()
        
        if markets:
            print("\nFirst market structure:")
            print(json.dumps(markets[0], indent=2, default=str))
            
            print("\n" + "=" * 80)
            print("FIELD NAMES:")
            print("=" * 80)
            for key in markets[0].keys():
                print(f"  - {key}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
