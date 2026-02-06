#!/usr/bin/env python3
"""
Check your REAL Polymarket balance.
"""

import asyncio
import os
from decimal import Decimal
from dotenv import load_dotenv
from web3 import Web3
from py_clob_client.client import ClobClient

load_dotenv()

# Your real wallet address from .env
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
POLYGON_RPC = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")

# USDC addresses on Polygon
USDC_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # Native USDC
USDC_E_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC.e (bridged)

# Polymarket proxy address (where your trading balance is)
POLYMARKET_PROXY = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"


async def check_balance():
    """Check all your balances."""
    
    print("=" * 80)
    print("YOUR REAL BALANCE CHECK")
    print("=" * 80)
    print()
    
    # Connect to Polygon
    web3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    
    if not web3.is_connected():
        print("ERROR: Cannot connect to Polygon RPC")
        return
    
    print(f"Your Wallet Address: {WALLET_ADDRESS}")
    print()
    
    # USDC ABI (balanceOf function)
    usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
    
    # Check USDC balance on Polygon (your private wallet)
    try:
        usdc_contract = web3.eth.contract(
            address=Web3.to_checksum_address(USDC_POLYGON),
            abi=usdc_abi
        )
        
        balance_wei = usdc_contract.functions.balanceOf(
            Web3.to_checksum_address(WALLET_ADDRESS)
        ).call()
        
        balance = Decimal(balance_wei) / Decimal(10**6)  # USDC has 6 decimals
        print(f"Private Wallet (Polygon): ${balance:.2f} USDC")
        
    except Exception as e:
        print(f"ERROR checking private wallet: {e}")
        balance = Decimal("0")
    
    # Check Polymarket balance (proxy contract)
    try:
        # Initialize CLOB client
        clob_client = ClobClient(
            host="https://clob.polymarket.com",
            key=PRIVATE_KEY,
            chain_id=137
        )
        
        # Derive API credentials
        try:
            creds = clob_client.create_or_derive_api_creds()
            clob_client.set_api_creds(creds)
        except:
            pass
        
        # Get balance from Polymarket
        # The proxy contract holds your trading balance
        proxy_balance_wei = usdc_contract.functions.balanceOf(
            Web3.to_checksum_address(POLYMARKET_PROXY)
        ).call()
        
        proxy_balance = Decimal(proxy_balance_wei) / Decimal(10**6)
        
        # Note: This shows the TOTAL in the proxy, not just yours
        # To get YOUR balance, we need to query the Polymarket API
        print(f"Polymarket Proxy (Total): ${proxy_balance:.2f} USDC")
        print()
        print("NOTE: The proxy holds funds for ALL users.")
        print("To see YOUR Polymarket balance, check the website:")
        print("https://polymarket.com")
        
    except Exception as e:
        print(f"ERROR checking Polymarket: {e}")
        proxy_balance = Decimal("0")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Your Private Wallet: ${balance:.2f} USDC")
    print()
    print("To check your Polymarket balance:")
    print("1. Go to: https://polymarket.com")
    print("2. Connect your wallet")
    print("3. Look at top right corner")
    print()
    print("The $47.09 BILLION you saw is the NULL ADDRESS (0x000...000)")
    print("That's NOT your wallet!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(check_balance())
