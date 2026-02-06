#!/usr/bin/env python3
"""
Check your REAL wallet balance on all networks.
"""

import os
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Your REAL wallet address
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

print("=" * 80)
print("CHECKING YOUR REAL WALLET BALANCE")
print("=" * 80)
print(f"Wallet: {WALLET_ADDRESS}")
print("=" * 80)
print()

# USDC ABI (balanceOf function)
USDC_ABI = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'

# Networks to check
networks = {
    "Ethereum": {
        "rpc": "https://eth-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64",
        "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "decimals": 6
    },
    "Polygon": {
        "rpc": "https://polygon-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64",
        "usdc": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "decimals": 6
    },
    "Polygon (USDC.E)": {
        "rpc": "https://polygon-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64",
        "usdc": "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",  # Bridged USDC
        "decimals": 6
    }
}

total_usdc = Decimal("0")

for network_name, config in networks.items():
    try:
        # Connect to network
        web3 = Web3(Web3.HTTPProvider(config["rpc"]))
        
        # Check ETH/MATIC balance
        eth_balance_wei = web3.eth.get_balance(WALLET_ADDRESS)
        eth_balance = Decimal(eth_balance_wei) / Decimal(10**18)
        
        # Check USDC balance
        usdc_contract = web3.eth.contract(
            address=Web3.to_checksum_address(config["usdc"]),
            abi=USDC_ABI
        )
        usdc_balance_wei = usdc_contract.functions.balanceOf(WALLET_ADDRESS).call()
        usdc_balance = Decimal(usdc_balance_wei) / Decimal(10**config["decimals"])
        
        # Display
        native_token = "ETH" if "Ethereum" in network_name else "MATIC"
        print(f"{network_name}:")
        print(f"  {native_token}: {eth_balance:.6f}")
        print(f"  USDC: ${usdc_balance:.2f}")
        print()
        
        total_usdc += usdc_balance
        
    except Exception as e:
        print(f"{network_name}: Error - {e}")
        print()

print("=" * 80)
print(f"TOTAL USDC ACROSS ALL NETWORKS: ${total_usdc:.2f}")
print("=" * 80)
print()

# Check Polymarket balance
print("Checking Polymarket balance...")
try:
    from py_clob_client.client import ClobClient
    
    clob_client = ClobClient(
        host="https://clob.polymarket.com",
        key=PRIVATE_KEY,
        chain_id=137
    )
    
    # Get balance
    balance_response = clob_client.get_balance_allowance()
    if isinstance(balance_response, dict):
        polymarket_balance = Decimal(balance_response.get('balance', '0')) / Decimal(10**6)
        print(f"Polymarket Balance: ${polymarket_balance:.2f}")
        print()
    else:
        print("Could not fetch Polymarket balance")
        print()
        
except Exception as e:
    print(f"Polymarket check failed: {e}")
    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total USDC (wallets): ${total_usdc:.2f}")
print()
print("Note: The $47.09B you saw is the NULL address (0x000000...00000000)")
print("That's not your wallet - it's a burn address with tokens sent by mistake.")
print("=" * 80)
