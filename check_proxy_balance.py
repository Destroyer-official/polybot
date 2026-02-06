#!/usr/bin/env python3
"""Check proxy wallet balance."""

from web3 import Web3
from dotenv import load_dotenv
import os
from decimal import Decimal

load_dotenv()

polygon_rpc = os.getenv('POLYGON_RPC_URL')
usdc_address = os.getenv('USDC_ADDRESS')
proxy_wallet = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

web3 = Web3(Web3.HTTPProvider(polygon_rpc))

usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
usdc_contract = web3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=usdc_abi)

print("=" * 80)
print("CHECKING PROXY WALLET BALANCE")
print("=" * 80)

print(f"\nProxy Wallet: {proxy_wallet}")

try:
    balance_raw = usdc_contract.functions.balanceOf(Web3.to_checksum_address(proxy_wallet)).call()
    balance = Decimal(balance_raw) / Decimal(10**6)
    
    print(f"\n💰 Balance: ${balance:.2f} USDC")
    
    if balance >= Decimal('3.0'):
        print("\n✅ SUFFICIENT BALANCE!")
        print("Bot should start trading now!")
    elif balance > Decimal('0'):
        print(f"\n⚠️  Balance found but below $3 minimum")
        print(f"Need ${Decimal('3.0') - balance:.2f} more")
    else:
        print("\n❌ No balance found")
        print("Deposit may still be processing...")
        
except Exception as e:
    print(f"\n✗ Error: {e}")

print("\n" + "=" * 80)
