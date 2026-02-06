#!/usr/bin/env python3
"""
Quick check and start the bot.
"""

import asyncio
import os
from decimal import Decimal
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
POLYGON_RPC = os.getenv("POLYGON_RPC_URL")

async def quick_check():
    """Quick balance check before starting."""
    
    print("=" * 80)
    print("QUICK PRE-FLIGHT CHECK")
    print("=" * 80)
    print()
    
    # Connect to Polygon
    web3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    
    # USDC contract
    usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
    usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    
    usdc_contract = web3.eth.contract(
        address=Web3.to_checksum_address(usdc_address),
        abi=usdc_abi
    )
    
    # Check balance
    balance_wei = usdc_contract.functions.balanceOf(
        Web3.to_checksum_address(WALLET_ADDRESS)
    ).call()
    balance = Decimal(balance_wei) / Decimal(10**6)
    
    print(f"Wallet: {WALLET_ADDRESS}")
    print(f"Polygon USDC: ${balance:.2f}")
    print()
    
    if balance < Decimal("0.50"):
        print("⚠️  WARNING: Low balance on Polygon")
        print()
        print("You have 2 options:")
        print()
        print("1. DEPOSIT VIA POLYMARKET (RECOMMENDED - FREE & INSTANT):")
        print("   - Go to: https://polymarket.com")
        print("   - Click 'Deposit'")
        print("   - Deposit $3.59 USDC from Ethereum")
        print("   - FREE (Polymarket pays gas)")
        print("   - Takes 10-30 seconds")
        print()
        print("2. START BOT ANYWAY (will check Polymarket balance):")
        print("   - Bot will check if you have funds in Polymarket")
        print("   - If yes, starts trading immediately")
        print("   - If no, shows deposit instructions")
        print()
        
        response = input("Start bot anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("Cancelled. Deposit funds first, then run again.")
            return False
    else:
        print("✅ Sufficient balance - ready to start!")
        print()
    
    return True

if __name__ == "__main__":
    if asyncio.run(quick_check()):
        print("=" * 80)
        print("STARTING BOT...")
        print("=" * 80)
        print()
        
        # Import and run the bot
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        
        from config.config import load_config
        from src.main_orchestrator import MainOrchestrator
        
        async def run_bot():
            config = load_config()
            orchestrator = MainOrchestrator(config)
            orchestrator.setup_signal_handlers()
            await orchestrator.run()
        
        asyncio.run(run_bot())
