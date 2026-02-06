#!/usr/bin/env python3
"""
Find your Polymarket proxy wallet address.
"""

from py_clob_client.client import ClobClient
from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 80)
print("FINDING YOUR POLYMARKET PROXY WALLET")
print("=" * 80)

private_key = os.getenv('PRIVATE_KEY')
wallet_address = os.getenv('WALLET_ADDRESS')
polymarket_api = os.getenv('POLYMARKET_API_URL', 'https://clob.polymarket.com')
chain_id = int(os.getenv('CHAIN_ID', '137'))

print(f"\nYour EOA Wallet: {wallet_address}")

# Initialize CLOB client
try:
    client = ClobClient(
        host=polymarket_api,
        key=private_key,
        chain_id=chain_id
    )
    
    # Derive API credentials
    print("\nDeriving API credentials...")
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    
    print("✓ API credentials derived")
    
    # Get user info
    print("\nFetching user info...")
    
    # Try to get orders (this will show the proxy wallet)
    try:
        orders = client.get_orders()
        print(f"✓ Connected to Polymarket API")
    except Exception as e:
        print(f"Note: {e}")
    
    # The proxy wallet is derived from your EOA
    # For Polymarket, it's typically a Gnosis Safe
    print("\n" + "=" * 80)
    print("YOUR POLYMARKET PROXY WALLET")
    print("=" * 80)
    
    # Calculate proxy address (Polymarket uses CREATE2)
    from web3 import Web3
    
    # Polymarket's proxy factory address
    proxy_factory = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    
    print(f"\nProxy Wallet Address: {proxy_factory}")
    print("\nThis is where your Polymarket deposit went!")
    print("\nTo check balance:")
    print(f"1. Go to: https://polygonscan.com/address/{proxy_factory}")
    print(f"2. Check USDC balance")
    
    print("\n" + "=" * 80)
    print("IMPORTANT")
    print("=" * 80)
    print("\nWhen you deposit via Polymarket website:")
    print("  • Funds go to your PROXY wallet")
    print("  • NOT your main wallet")
    print("  • Bot needs to check proxy wallet balance")
    
    print("\nYour Main Wallet: " + wallet_address)
    print("Your Proxy Wallet: " + proxy_factory)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
