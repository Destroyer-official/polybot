#!/usr/bin/env python3
"""
Test the updated market parser.
"""

from py_clob_client.client import ClobClient
from config.config import load_config
from src.market_parser import MarketParser

def main():
    """Test updated parser."""
    
    print("=" * 80)
    print("TESTING UPDATED MARKET PARSER")
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
    
    # Parse markets
    print("Parsing markets with updated parser...")
    parser = MarketParser()
    markets = parser.parse_markets(response)
    
    print("\n" + "=" * 80)
    print("PARSING RESULTS")
    print("=" * 80)
    print(f"Total markets parsed: {len(markets)}")
    print(f"Markets skipped: {parser.markets_skipped}")
    print(f"\nSkip reasons:")
    for reason, count in sorted(parser.skip_reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count}")
    
    # Show sample parsed markets
    if markets:
        print("\n" + "=" * 80)
        print("SAMPLE PARSED MARKETS (first 10)")
        print("=" * 80)
        for i, market in enumerate(markets[:10]):
            print(f"\n{i+1}. {market.question[:70]}...")
            print(f"   Market ID: {market.market_id[:20]}...")
            print(f"   Asset: {market.asset}")
            print(f"   YES price: ${market.yes_price}")
            print(f"   NO price: ${market.no_price}")
            print(f"   Volume: ${market.volume}")
            print(f"   Liquidity: ${market.liquidity}")
            print(f"   End time: {market.end_time}")
    else:
        print("\n[!] NO MARKETS PARSED")
        print("\nThis means all markets were filtered out.")
        print("Check skip reasons above to see why.")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
