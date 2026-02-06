#!/usr/bin/env python3
"""Check both USDC tokens on Polygon."""

from web3 import Web3
from decimal import Decimal
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to Polygon
w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64'))
wallet = os.getenv('WALLET_ADDRESS')

# Both USDC addresses on Polygon
USDC_BRIDGED = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'  # USDC.e (bridged from Ethereum)
USDC_NATIVE = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'   # USDC (native)

# ABI for balanceOf
abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'

print("=" * 80)
print("CHECKING BOTH USDC TOKENS ON POLYGON")
print("=" * 80)
print(f"Wallet: {wallet}")
print()

# Check bridged USDC
bridged_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_BRIDGED), abi=abi)
bridged_bal = Decimal(bridged_contract.functions.balanceOf(wallet).call()) / Decimal(10**6)
print(f"USDC.e (Bridged - 0x2791...4174): ${bridged_bal:.2f}")

# Check native USDC
native_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_NATIVE), abi=abi)
native_bal = Decimal(native_contract.functions.balanceOf(wallet).call()) / Decimal(10**6)
print(f"USDC (Native - 0x3c49...3359):   ${native_bal:.2f}")

print()
print(f"Total USDC on Polygon: ${native_bal + bridged_bal:.2f}")
print("=" * 80)

if native_bal > 0:
    print()
    print("[!] You have NATIVE USDC!")
    print("[!] The bot uses BRIDGED USDC (USDC.e)")
    print("[!] You need to swap Native USDC → USDC.e on Uniswap or use Polymarket deposit")
    print()
    print("Option 1: Use Polymarket deposit feature (they handle the swap)")
    print("  Go to: https://polymarket.com")
    print("  Click: Deposit → Wallet → Select USDC → Continue")
    print()
    print("Option 2: Swap on Uniswap")
    print("  Go to: https://app.uniswap.org")
    print("  Swap: USDC → USDC.e")

if bridged_bal > 0:
    print()
    print("[OK] You have BRIDGED USDC (USDC.e) - Ready to trade!")
    print(f"[OK] Balance: ${bridged_bal:.2f}")
