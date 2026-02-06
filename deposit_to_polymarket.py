#!/usr/bin/env python3
"""Deposit USDC from Polygon to Polymarket."""

import os
from dotenv import load_dotenv
from web3 import Web3
from decimal import Decimal

load_dotenv()

# Configuration
POLYGON_RPC = "https://polygon-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
WALLET = os.getenv('WALLET_ADDRESS')

# Polygon addresses
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC.e
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # Polymarket exchange

# Connect to Polygon
w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
account = w3.eth.account.from_key(PRIVATE_KEY)

print("=" * 80)
print("DEPOSIT USDC TO POLYMARKET")
print("=" * 80)
print(f"Wallet: {WALLET}")
print()

# Check USDC balance
usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"}]'

usdc_contract = w3.eth.contract(
    address=Web3.to_checksum_address(USDC_ADDRESS),
    abi=usdc_abi
)

balance_wei = usdc_contract.functions.balanceOf(WALLET).call()
balance = Decimal(balance_wei) / Decimal(10**6)

print(f"USDC Balance on Polygon: ${balance:.2f}")
print()

if balance == 0:
    print("[!] No USDC on Polygon")
    print()
    print("You need to:")
    print("1. Bridge USDC from Ethereum (wait 5-30 min)")
    print("2. OR buy USDC on Polygon")
    print("3. OR use Polymarket deposit feature")
    print()
    print("=" * 80)
    exit(0)

# Ask for deposit amount
print(f"Available: ${balance:.2f}")
deposit_amount = input(f"Enter amount to deposit (max ${balance:.2f}): $")

try:
    deposit_amount = Decimal(deposit_amount)
    if deposit_amount <= 0 or deposit_amount > balance:
        print("[!] Invalid amount")
        exit(1)
except:
    print("[!] Invalid amount")
    exit(1)

print()
print(f"Depositing ${deposit_amount:.2f} to Polymarket...")
print()

# Step 1: Approve USDC
print("Step 1: Approving USDC...")
amount_wei = int(deposit_amount * Decimal(10**6))

approve_tx = usdc_contract.functions.approve(
    Web3.to_checksum_address(CTF_EXCHANGE),
    amount_wei
).build_transaction({
    'from': WALLET,
    'nonce': w3.eth.get_transaction_count(WALLET),
    'gas': 100000,
    'gasPrice': w3.eth.gas_price
})

signed_approve = w3.eth.account.sign_transaction(approve_tx, PRIVATE_KEY)
approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)

print(f"Approval TX: {approve_hash.hex()}")
print("Waiting for confirmation...")

approve_receipt = w3.eth.wait_for_transaction_receipt(approve_hash, timeout=120)

if approve_receipt['status'] != 1:
    print("[FAIL] Approval failed")
    exit(1)

print("[OK] Approval confirmed")
print()

# Step 2: Deposit to Polymarket
print("Step 2: Depositing to Polymarket...")

# CTF Exchange deposit function
exchange_abi = '[{"inputs":[{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"deposit","outputs":[],"stateMutability":"nonpayable","type":"function"}]'

exchange_contract = w3.eth.contract(
    address=Web3.to_checksum_address(CTF_EXCHANGE),
    abi=exchange_abi
)

deposit_tx = exchange_contract.functions.deposit(amount_wei).build_transaction({
    'from': WALLET,
    'nonce': w3.eth.get_transaction_count(WALLET),
    'gas': 200000,
    'gasPrice': w3.eth.gas_price
})

signed_deposit = w3.eth.account.sign_transaction(deposit_tx, PRIVATE_KEY)
deposit_hash = w3.eth.send_raw_transaction(signed_deposit.raw_transaction)

print(f"Deposit TX: {deposit_hash.hex()}")
print("Waiting for confirmation...")

deposit_receipt = w3.eth.wait_for_transaction_receipt(deposit_hash, timeout=120)

if deposit_receipt['status'] != 1:
    print("[FAIL] Deposit failed")
    exit(1)

print("[OK] Deposit confirmed!")
print()
print("=" * 80)
print("SUCCESS!")
print("=" * 80)
print(f"Deposited: ${deposit_amount:.2f}")
print()
print("Now run the bot:")
print("  python test_autonomous_bot.py")
print()
print("The bot will:")
print("  - Scan 1000+ markets every 2 seconds")
print("  - Execute trades with dynamic sizing ($0.50-$2.00)")
print("  - Trade 24/7 autonomously")
print("=" * 80)
