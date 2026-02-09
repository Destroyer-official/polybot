#!/usr/bin/env python3
"""Test with explicit funder and derive API key info."""

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
    print("FUNDER ADDRESS DIAGNOSTIC")
    print("=" * 60)
    
    # Get EOA address
    eoa = Web3().eth.account.from_key(PRIVATE_KEY).address
    print(f"\nEOA Address: {eoa}")
    
    # Try to derive API creds and see what address they're for
    for sig_type in [0, 1, 2]:
        print(f"\n--- signature_type={sig_type} ---")
        try:
            client = ClobClient(
                host="https://clob.polymarket.com",
                key=PRIVATE_KEY,
                chain_id=137,
                signature_type=sig_type,
                funder=eoa  # Explicitly set funder
            )
            
            creds = client.create_or_derive_api_creds()
            print(f"API Key: {getattr(creds, 'api_key', str(creds)[:50])}")
            
            # Check if creds have any address info
            if hasattr(creds, '__dict__'):
                print(f"Creds attrs: {creds.__dict__}")
            
            client.set_api_creds(creds)
            
            # Try to get balance - this might reveal the actual funder
            try:
                bal = client.get_balance_allowance()
                print(f"Balance response: {bal}")
            except Exception as e:
                print(f"Balance error: {e}")
            
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("IMPORTANT: If balance shows a different address,")
    print("that is your FUNDER/PROXY address!")
    print("=" * 60)

if __name__ == "__main__":
    main()
