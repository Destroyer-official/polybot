#!/usr/bin/env python3
"""Check actual Polymarket balance using CLOB API."""

import os
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

load_dotenv()

private_key = os.getenv('PRIVATE_KEY')
wallet = os.getenv('WALLET_ADDRESS')

print("=" * 80)
print("CHECKING POLYMARKET BALANCE")
print("=" * 80)
print(f"Wallet: {wallet}")
print()

try:
    # Initialize CLOB client
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137
    )
    
    # Derive API credentials
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    
    # Get balance
    balance_response = client.get_balance_allowance()
    
    print("Polymarket Balance:")
    print(f"  Balance: ${float(balance_response.get('balance', 0)):.2f}")
    print(f"  Allowance: ${float(balance_response.get('allowance', 0)):.2f}")
    print()
    
    balance = float(balance_response.get('balance', 0))
    
    if balance > 0:
        print("[OK] You have funds in Polymarket!")
        print("[OK] Ready to start trading!")
        print()
        print("Run: python test_autonomous_bot.py")
    else:
        print("[!] No funds in Polymarket")
        print()
        print("Quick deposit options:")
        print("1. Use Polymarket website: https://polymarket.com → Deposit")
        print("2. Wait for bridge to complete (5-30 minutes)")
        
except Exception as e:
    print(f"Error: {e}")
    print()
    print("This might mean:")
    print("1. No funds deposited yet")
    print("2. Need to deposit via Polymarket website")

print("=" * 80)
