#!/usr/bin/env python3
"""
Get your REAL Polymarket proxy address from the API.
"""

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from dotenv import load_dotenv
import os
import requests

load_dotenv()

print("=" * 80)
print("GETTING YOUR REAL POLYMARKET PROXY ADDRESS")
print("=" * 80)

private_key = os.getenv('PRIVATE_KEY')
wallet_address = os.getenv('WALLET_ADDRESS')

print(f"\nYour Wallet: {wallet_address}")

# Initialize CLOB client
try:
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137
    )
    
    # Derive API credentials
    print("\nDeriving API credentials...")
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    print("✓ Connected to Polymarket API")
    
    # Get user info from Data API
    print("\nFetching your Polymarket account info...")
    
    data_api_url = f"https://data-api.polymarket.com/users/{wallet_address}"
    response = requests.get(data_api_url, timeout=10)
    
    if response.status_code == 200:
        user_data = response.json()
        
        print("\n" + "=" * 80)
        print("YOUR POLYMARKET ACCOUNT")
        print("=" * 80)
        
        if 'proxyWallet' in user_data:
            proxy_wallet = user_data['proxyWallet']
            print(f"\n✅ FOUND YOUR PROXY WALLET!")
            print(f"\nProxy Address: {proxy_wallet}")
            print(f"\nThis is where your $4.23 is stored!")
            
            # Check balance
            from web3 import Web3
            from decimal import Decimal
            
            polygon_rpc = os.getenv('POLYGON_RPC_URL')
            usdc_address = os.getenv('USDC_ADDRESS')
            
            web3 = Web3(Web3.HTTPProvider(polygon_rpc))
            usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
            usdc_contract = web3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=usdc_abi)
            
            try:
                balance_raw = usdc_contract.functions.balanceOf(Web3.to_checksum_address(proxy_wallet)).call()
                balance = Decimal(balance_raw) / Decimal(10**6)
                
                print(f"\n💰 Balance: ${balance:.2f} USDC")
                
                if balance >= Decimal('3.0'):
                    print("\n✅ SUFFICIENT BALANCE TO TRADE!")
                    
                    # Update .env file
                    print("\n" + "=" * 80)
                    print("UPDATING BOT CONFIGURATION")
                    print("=" * 80)
                    print(f"\nThe bot needs to use this proxy address:")
                    print(f"{proxy_wallet}")
                    print(f"\nI'll update the configuration now...")
                    
            except Exception as e:
                print(f"\nCouldn't check balance: {e}")
        else:
            print("\n❌ Proxy wallet not found in API response")
            print(f"\nResponse: {user_data}")
    else:
        print(f"\n❌ Failed to get user data: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
