#!/usr/bin/env python3
"""
Check your REAL Polymarket balance using the CTF Exchange contract.
"""

from web3 import Web3
from dotenv import load_dotenv
import os
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("CHECKING YOUR REAL POLYMARKET BALANCE")
print("=" * 80)

wallet_address = os.getenv('WALLET_ADDRESS')
polygon_rpc = os.getenv('POLYGON_RPC_URL')
ctf_exchange_address = os.getenv('CTF_EXCHANGE_ADDRESS')

print(f"\nYour Wallet: {wallet_address}")
print(f"CTF Exchange: {ctf_exchange_address}")

# Connect to Polygon
web3 = Web3(Web3.HTTPProvider(polygon_rpc))

if not web3.is_connected():
    print("\n❌ Failed to connect to Polygon RPC")
    exit(1)

print("\n✓ Connected to Polygon")

# CTF Exchange ABI - getCollateralBalance function
ctf_abi = [
    {
        "constant": True,
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getCollateralBalance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

# Create contract instance
ctf_contract = web3.eth.contract(
    address=Web3.to_checksum_address(ctf_exchange_address),
    abi=ctf_abi
)

print("\nChecking balance...")

try:
    # Get collateral balance (this is your Polymarket balance)
    balance_raw = ctf_contract.functions.getCollateralBalance(
        Web3.to_checksum_address(wallet_address)
    ).call()
    
    balance = Decimal(balance_raw) / Decimal(10 ** 6)  # USDC has 6 decimals
    
    print("\n" + "=" * 80)
    print("YOUR POLYMARKET BALANCE")
    print("=" * 80)
    print(f"\n💰 Balance: ${balance:.2f} USDC")
    
    if balance >= Decimal('3.0'):
        print("\n✅ SUFFICIENT BALANCE TO TRADE!")
        print("\nThe bot should be able to see this balance and start trading.")
        print("If the bot is not trading, check the logs for errors.")
    elif balance > Decimal('0'):
        print(f"\n⚠️  Balance is below minimum ($3.00)")
        print("Please deposit more USDC to start trading.")
    else:
        print("\n❌ NO BALANCE FOUND")
        print("\nPossible reasons:")
        print("1. You haven't deposited to Polymarket yet")
        print("2. The deposit is still processing")
        print("3. The funds are in a different wallet")
        
except Exception as e:
    print(f"\n❌ Error checking balance: {e}")
    print("\nThis might mean:")
    print("1. The CTF Exchange address is incorrect")
    print("2. The RPC connection is not working")
    print("3. The contract ABI is incorrect")

print("\n" + "=" * 80)
