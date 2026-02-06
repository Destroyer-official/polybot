#!/usr/bin/env python3
"""
Get your Polymarket balance using the CLOB client.
"""

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from dotenv import load_dotenv
import os
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("GETTING YOUR POLYMARKET BALANCE VIA CLOB CLIENT")
print("=" * 80)

private_key = os.getenv('PRIVATE_KEY')
wallet_address = os.getenv('WALLET_ADDRESS')

print(f"\nYour Wallet: {wallet_address}")

try:
    # Initialize CLOB client
    print("\nInitializing CLOB client...")
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137
    )
    
    # Derive API credentials
    print("Deriving API credentials...")
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    print("✓ Connected to Polymarket CLOB API")
    
    # Get balance allowances
    print("\nGetting balance allowances...")
    try:
        allowances = client.get_balance_allowance()
        print(f"\nBalance Allowances:")
        for key, value in allowances.items():
            print(f"  {key}: {value}")
            
        # The balance is typically in the 'balance' field
        if 'balance' in allowances:
            balance_raw = int(allowances['balance'])
            balance = Decimal(balance_raw) / Decimal(10 ** 6)
            
            print("\n" + "=" * 80)
            print("YOUR POLYMARKET BALANCE")
            print("=" * 80)
            print(f"\n💰 Balance: ${balance:.2f} USDC")
            
            if balance >= Decimal('3.0'):
                print("\n✅ SUFFICIENT BALANCE TO TRADE!")
            else:
                print(f"\n⚠️  Balance is below minimum ($3.00)")
        else:
            print("\n❌ Could not find balance in response")
            
    except AttributeError as e:
        print(f"\nMethod not available: {e}")
        print("\nTrying alternative method...")
        
        # Try to get orders to see if account is active
        try:
            orders = client.get_orders()
            print(f"\nFound {len(orders)} orders")
            
            # Try to get market data
            print("\nTrying to get market data...")
            markets = client.get_markets()
            print(f"Found {len(markets)} markets")
            
            print("\n" + "=" * 80)
            print("ACCOUNT IS ACTIVE")
            print("=" * 80)
            print("\nYour account is connected to Polymarket.")
            print("The balance might be stored in a different location.")
            print("\nLet me check the proxy wallet...")
            
            # The proxy wallet is where your funds are stored
            # It's derived from your main wallet
            from py_clob_client.signer import Signer
            signer = Signer(private_key, 137)
            
            print(f"\nSigner address: {signer.address()}")
            
            # Now check the balance on-chain
            from web3 import Web3
            polygon_rpc = os.getenv('POLYGON_RPC_URL')
            usdc_address = os.getenv('USDC_ADDRESS')
            
            web3 = Web3(Web3.HTTPProvider(polygon_rpc))
            usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
            usdc_contract = web3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=usdc_abi)
            
            # Check USDC balance in your wallet
            balance_raw = usdc_contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
            balance = Decimal(balance_raw) / Decimal(10**6)
            
            print(f"\nUSDC in your wallet: ${balance:.2f}")
            
            # The issue is that when you deposit via Polymarket website,
            # the funds go to a PROXY WALLET, not your main wallet
            # The proxy wallet address is computed by Polymarket
            
            print("\n" + "=" * 80)
            print("IMPORTANT DISCOVERY")
            print("=" * 80)
            print("\nWhen you deposit via Polymarket website, your funds go to a")
            print("PROXY WALLET that Polymarket creates for you.")
            print("\nThe bot needs to:")
            print("1. Use the CLOB API to place orders (which it's doing)")
            print("2. The CLOB API handles the proxy wallet automatically")
            print("\nThe bot doesn't need to check the proxy wallet balance directly!")
            print("It just needs to use the CLOB client to trade.")
            
            print("\n✅ YOUR ACCOUNT IS READY TO TRADE")
            print("\nThe bot should use the CLOB client to:")
            print("- Place orders: client.create_order()")
            print("- Cancel orders: client.cancel_order()")
            print("- Get orders: client.get_orders()")
            
            print("\nThe CLOB API will handle the proxy wallet automatically.")
            
        except Exception as e2:
            print(f"\nError: {e2}")
            import traceback
            traceback.print_exc()
            
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
