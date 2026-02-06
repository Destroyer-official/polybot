#!/usr/bin/env python3
"""Check Polymarket balance."""

from web3 import Web3
from dotenv import load_dotenv
import os

load_dotenv()

# Connect to Polygon
polygon_rpc = os.getenv('POLYGON_RPC_URL')
wallet_address = os.getenv('WALLET_ADDRESS')
usdc_address = os.getenv('USDC_ADDRESS')
ctf_exchange = os.getenv('CTF_EXCHANGE_ADDRESS')

web3 = Web3(Web3.HTTPProvider(polygon_rpc))

# USDC ABI
usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
usdc_contract = web3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=usdc_abi)

print("=" * 80)
print("POLYMARKET BALANCE CHECK")
print("=" * 80)

# Check private wallet (Polygon)
try:
    private_balance_raw = usdc_contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
    private_balance = private_balance_raw / 10**6
    print(f"\n✓ Private Wallet (Polygon): ${private_balance:.2f} USDC")
except Exception as e:
    print(f"\n✗ Private Wallet: Error - {e}")
    private_balance = 0

# Check Polymarket balance
try:
    polymarket_balance_raw = usdc_contract.functions.balanceOf(Web3.to_checksum_address(ctf_exchange)).call()
    polymarket_balance = polymarket_balance_raw / 10**6
    print(f"✓ Polymarket Balance: ${polymarket_balance:.2f} USDC")
except Exception as e:
    print(f"✗ Polymarket Balance: Error - {e}")
    polymarket_balance = 0

total = private_balance + polymarket_balance
print(f"\n💰 TOTAL AVAILABLE: ${total:.2f} USDC")

print("\n" + "=" * 80)
print("YOUR POLYMARKET ACCOUNT INFO")
print("=" * 80)
print(f"\nYour Wallet Address: {wallet_address}")
print(f"\nTo deposit manually:")
print(f"1. Go to: https://polymarket.com")
print(f"2. Click 'Connect Wallet' (top right)")
print(f"3. Connect with address: {wallet_address}")
print(f"4. Click your profile → 'Deposit'")
print(f"5. Deposit at least $3.00 USDC (Polymarket minimum)")
print(f"6. Select 'Wallet' as source (instant & free)")
print(f"7. Confirm transaction")
print("\n" + "=" * 80)

if polymarket_balance < 3.0:
    print("\n⚠️  WARNING: Polymarket balance < $3.00")
    print("   Minimum deposit: $3.00 USDC")
    print(f"   You need: ${max(3.0 - polymarket_balance, 0):.2f} more")
    print("\n   The $1.05 deposit may be rejected (below minimum)")
else:
    print("\n✅ Polymarket balance sufficient for trading!")
