#!/usr/bin/env python3
"""Check USDC balance on both Polygon USDC contracts."""

from web3 import Web3
from decimal import Decimal

# Connect to Polygon
web3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64'))

# USDC ABI (minimal)
usdc_abi = '''[{
    "constant": true,
    "inputs": [{"name": "_owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "type": "function"
}]'''

# Two USDC contracts on Polygon
USDC_NATIVE = '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359'  # Native USDC (new)
USDC_BRIDGED = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'  # Bridged USDC.e (old)

# Your wallet
wallet = '0x1A821E4488732156cC9B3580efe3984F9B6C0116'

print("=" * 80)
print("CHECKING USDC BALANCE ON POLYGON")
print("=" * 80)
print()

# Check Native USDC
usdc_native_contract = web3.eth.contract(
    address=Web3.to_checksum_address(USDC_NATIVE),
    abi=usdc_abi
)
balance_native_raw = usdc_native_contract.functions.balanceOf(wallet).call()
balance_native = Decimal(balance_native_raw) / Decimal(10 ** 6)

print(f"USDC (Native) - 0x3c49...3359")
print(f"  Balance: ${balance_native:.6f}")
print()

# Check Bridged USDC.e
usdc_bridged_contract = web3.eth.contract(
    address=Web3.to_checksum_address(USDC_BRIDGED),
    abi=usdc_abi
)
balance_bridged_raw = usdc_bridged_contract.functions.balanceOf(wallet).call()
balance_bridged = Decimal(balance_bridged_raw) / Decimal(10 ** 6)

print(f"USDC.e (Bridged) - 0x2791...4174")
print(f"  Balance: ${balance_bridged:.6f}")
print()

# Total
total = balance_native + balance_bridged
print("=" * 80)
print(f"TOTAL USDC ON POLYGON: ${total:.6f}")
print("=" * 80)
print()

# Diagnosis
if total == 0:
    print("[ISSUE] No USDC found on Polygon network")
    print()
    print("POSSIBLE REASONS:")
    print("1. USDC is on a different network (Ethereum, Arbitrum, etc.)")
    print("2. USDC hasn't been transferred to Polygon yet")
    print()
    print("SOLUTION:")
    print("1. Check MetaMask - switch to Polygon network")
    print("2. If USDC is on another network, use Polygon Bridge:")
    print("   https://wallet.polygon.technology/polygon/bridge")
    print("3. Or send USDC directly to Polygon from exchange")
elif balance_native > 0:
    print("[OK] Found USDC on Native contract (correct)")
    print("Bot is configured correctly!")
elif balance_bridged > 0:
    print("[ISSUE] Found USDC on Bridged contract (old)")
    print()
    print("SOLUTION:")
    print("The bot is using the old USDC.e contract address.")
    print("You have two options:")
    print()
    print("Option 1: Update .env to use USDC.e address:")
    print(f"  USDC_ADDRESS={USDC_BRIDGED}")
    print()
    print("Option 2: Swap USDC.e to native USDC:")
    print("  1. Go to https://app.uniswap.org/")
    print("  2. Connect wallet on Polygon")
    print("  3. Swap USDC.e to USDC (1:1, minimal fee)")
