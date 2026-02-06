#!/usr/bin/env python3
"""
Check Polymarket balance and show deposit address.
"""

from web3 import Web3
from dotenv import load_dotenv
import os
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("POLYMARKET ACCOUNT INFO")
print("=" * 80)

# Your wallet info
wallet_address = os.getenv('WALLET_ADDRESS')
private_key = os.getenv('PRIVATE_KEY')
polygon_rpc = os.getenv('POLYGON_RPC_URL')
usdc_address = os.getenv('USDC_ADDRESS')
ctf_exchange = os.getenv('CTF_EXCHANGE_ADDRESS')

print(f"\n📍 YOUR WALLET ADDRESS:")
print(f"   {wallet_address}")

# Connect to Polygon
web3 = Web3(Web3.HTTPProvider(polygon_rpc))

# USDC ABI
usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
usdc_contract = web3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=usdc_abi)

print("\n💰 CURRENT BALANCES:")
print("-" * 80)

# Check private wallet balance (Polygon)
try:
    private_balance_raw = usdc_contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
    private_balance = Decimal(private_balance_raw) / Decimal(10**6)
    print(f"Private Wallet (Polygon): ${private_balance:.2f} USDC")
except Exception as e:
    print(f"Private Wallet: Error - {e}")
    private_balance = Decimal('0')

# Check Polymarket balance
try:
    polymarket_balance_raw = usdc_contract.functions.balanceOf(Web3.to_checksum_address(ctf_exchange)).call()
    polymarket_balance = Decimal(polymarket_balance_raw) / Decimal(10**6)
    print(f"Polymarket Balance: ${polymarket_balance:.2f} USDC")
except Exception as e:
    print(f"Polymarket Balance: Error - {e}")
    polymarket_balance = Decimal('0')

total = private_balance + polymarket_balance
print(f"\nTOTAL AVAILABLE: ${total:.2f} USDC")

print("\n" + "=" * 80)
print("HOW TO DEPOSIT TO POLYMARKET")
print("=" * 80)

print("\n🚀 OPTION 1: Deposit via Polymarket Website (RECOMMENDED)")
print("-" * 80)
print("1. Go to: https://polymarket.com")
print("2. Click 'Connect Wallet' (top right)")
print("3. Connect with your wallet:")
print(f"   {wallet_address}")
print("4. Click your profile → 'Deposit'")
print(f"5. Enter amount: $3.59 (or more)")
print("6. Select 'Wallet' as source")
print("7. Click 'Deposit' → Confirm in wallet")
print("\n⚡ INSTANT & FREE - No fees, takes 30 seconds!")

print("\n🔧 OPTION 2: Direct Transfer to Polymarket Proxy")
print("-" * 80)
print("Your Polymarket Proxy Address:")
print(f"   {ctf_exchange}")
print("\nSteps:")
print("1. Open your wallet (MetaMask)")
print("2. Send USDC to the address above")
print("3. Network: Polygon")
print("4. Amount: $3.59 or more")
print("5. Confirm transaction")
print("\n⚠️  Note: This requires approval transaction first")

print("\n" + "=" * 80)
print("MINIMUM DEPOSIT REQUIREMENT")
print("=" * 80)
print(f"\nPolymarket minimum: $3.00 USDC")
print(f"Your available: ${private_balance:.2f} USDC on Polygon")

if private_balance >= Decimal('3.0'):
    print(f"\n✅ You have enough! Deposit ${private_balance:.2f}")
else:
    needed = Decimal('3.0') - private_balance
    print(f"\n❌ You need ${needed:.2f} more USDC")
    print(f"\nOptions:")
    print(f"  1. Bridge more USDC from Ethereum to Polygon")
    print(f"  2. Buy USDC on Polygon (via exchange)")
    print(f"  3. Swap other tokens to USDC on Polygon")

print("\n" + "=" * 80)
print("AFTER DEPOSIT")
print("=" * 80)
print("\nThe bot will:")
print("  1. Detect your balance automatically")
print("  2. Start scanning for opportunities")
print("  3. Execute trades when profitable")
print("  4. Run 24/7 autonomously")
print("\nNo manual intervention needed!")
print("=" * 80)
