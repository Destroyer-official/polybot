#!/usr/bin/env python3
"""
Check balance and guide user to deposit, then start auto-trading.
"""

import asyncio
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv
import os

load_dotenv()

async def main():
    """Check balance and guide deposit."""
    
    print("=" * 80)
    print("POLYMARKET AUTO-TRADING BOT - BALANCE CHECK")
    print("=" * 80)
    
    # Connect to Polygon
    polygon_rpc = os.getenv('POLYGON_RPC_URL')
    private_key = os.getenv('PRIVATE_KEY')
    wallet_address = os.getenv('WALLET_ADDRESS')
    usdc_address = os.getenv('USDC_ADDRESS')
    ctf_exchange = os.getenv('CTF_EXCHANGE_ADDRESS')
    
    web3 = Web3(Web3.HTTPProvider(polygon_rpc))
    
    # USDC ABI (balanceOf only)
    usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
    
    usdc_contract = web3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=usdc_abi)
    
    # Check balances
    print("\n[1] CHECKING YOUR BALANCES...")
    print("-" * 80)
    
    # Private wallet balance (Polygon)
    try:
        private_balance_raw = usdc_contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
        private_balance = Decimal(private_balance_raw) / Decimal(10**6)
        print(f"✓ Private Wallet (Polygon): ${private_balance:.2f} USDC")
    except Exception as e:
        print(f"✗ Private Wallet: Error - {e}")
        private_balance = Decimal('0')
    
    # Polymarket balance (CTF Exchange proxy)
    try:
        polymarket_balance_raw = usdc_contract.functions.balanceOf(Web3.to_checksum_address(ctf_exchange)).call()
        polymarket_balance = Decimal(polymarket_balance_raw) / Decimal(10**6)
        print(f"✓ Polymarket Balance: ${polymarket_balance:.2f} USDC")
    except Exception as e:
        print(f"✗ Polymarket Balance: Error - {e}")
        polymarket_balance = Decimal('0')
    
    total_balance = private_balance + polymarket_balance
    print(f"\n💰 TOTAL AVAILABLE: ${total_balance:.2f} USDC")
    
    # Check if ready to trade
    print("\n" + "=" * 80)
    
    if polymarket_balance >= Decimal("0.50"):
        print("✅ READY TO TRADE!")
        print("=" * 80)
        print(f"You have ${polymarket_balance:.2f} USDC in Polymarket")
        print("\nStarting bot in 3 seconds...")
        await asyncio.sleep(3)
        
        # Start the bot
        print("\n🤖 STARTING AUTO-TRADING BOT...")
        print("=" * 80)
        
        from config.config import Config
        from src.main_orchestrator import MainOrchestrator
        
        config = Config.from_env()
        orchestrator = MainOrchestrator(config)
        await orchestrator.run()
        
    else:
        print("❌ NOT ENOUGH FUNDS IN POLYMARKET")
        print("=" * 80)
        print(f"Current Polymarket balance: ${polymarket_balance:.2f} USDC")
        print(f"Minimum needed: $0.50 USDC")
        print(f"You need to deposit: ${max(Decimal('0.50') - polymarket_balance, Decimal('0')):.2f} USDC")
        
        print("\n" + "=" * 80)
        print("🚀 DEPOSIT NOW (TAKES 30 SECONDS):")
        print("=" * 80)
        print("\n1. Open: https://polymarket.com")
        print("2. Click 'Connect Wallet' (top right)")
        print("3. Connect your wallet")
        print("4. Click your profile → 'Deposit'")
        
        if private_balance >= Decimal("0.50"):
            print(f"5. Enter amount: ${private_balance:.2f} (use all your Polygon USDC)")
        else:
            print(f"5. Enter amount: $3.59 (or any amount ≥ $0.50)")
        
        print("6. Select 'Wallet' as source")
        print("7. Click 'Deposit' → Confirm in wallet")
        print("\n⚡ INSTANT & FREE - No bridge needed!")
        
        print("\n" + "=" * 80)
        print("After deposit, run this script again:")
        print("  python DEPOSIT_NOW_THEN_AUTO_TRADE.py")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
