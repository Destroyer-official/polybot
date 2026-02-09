#!/usr/bin/env python3
"""Query the correct funder/proxy address from Polymarket CLOB API."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from web3 import Web3

PRIVATE_KEY = os.getenv("PRIVATE_KEY")

def main():
    print("=" * 60)
    print("POLYMARKET FUNDER ADDRESS QUERY")
    print("=" * 60)
    
    # Get EOA address
    w3 = Web3()
    account = w3.eth.account.from_key(PRIVATE_KEY)
    eoa_address = account.address
    print(f"\nEOA Address: {eoa_address}")
    
    # Try each signature type to find the right one
    for sig_type in [0, 1, 2]:
        print(f"\n--- Testing signature_type={sig_type} ---")
        try:
            client = ClobClient(
                host="https://clob.polymarket.com",
                key=PRIVATE_KEY,
                chain_id=137,
                signature_type=sig_type
            )
            
            # Derive API credentials
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            print(f"✅ API credentials derived successfully")
            
            # Get balance/allowance (might contain funder info)
            try:
                info = client.get_balance_allowance()
                print(f"Balance info: {info}")
            except Exception as e:
                print(f"Balance query error: {e}")
            
            # Check order book as simple test
            try:
                # Get a simple endpoint that works
                markets = client.get_markets()
                print(f"✅ Can access markets: {len(markets) if markets else 0} found")
            except Exception as e:
                print(f"Markets query: {e}")
                
        except Exception as e:
            print(f"❌ signature_type={sig_type} failed: {e}")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATION:")
    print("1. Go to polymarket.com and log in")
    print("2. Look at your profile URL - the address there is your PROXY ADDRESS")
    print("3. Update .env with: FUNDER_ADDRESS=<your_proxy_address>")
    print("=" * 60)

if __name__ == "__main__":
    main()
