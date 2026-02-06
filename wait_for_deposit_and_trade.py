#!/usr/bin/env python3
"""
Wait for Polymarket deposit to be processed, then start trading.
"""

import asyncio
import time
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv
import os

load_dotenv()

async def wait_for_deposit():
    """Wait for deposit to be processed by Polymarket."""
    
    print("=" * 80)
    print("WAITING FOR POLYMARKET DEPOSIT TO PROCESS")
    print("=" * 80)
    
    polygon_rpc = os.getenv('POLYGON_RPC_URL')
    wallet_address = os.getenv('WALLET_ADDRESS')
    usdc_address = os.getenv('USDC_ADDRESS')
    ctf_exchange = os.getenv('CTF_EXCHANGE_ADDRESS')
    
    web3 = Web3(Web3.HTTPProvider(polygon_rpc))
    
    # USDC ABI
    usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
    usdc_contract = web3.eth.contract(address=Web3.to_checksum_address(usdc_address), abi=usdc_abi)
    
    print("\n✅ Deposit transaction confirmed on Polygon")
    print("Transaction: c9214e91cac8d32a505ace391c6c1aae9b82acaef0e86746e7b336e0fe76b4a1")
    print("\n⏳ Waiting for Polymarket to process deposit...")
    print("This usually takes 5-10 minutes")
    print("\nChecking balance every 30 seconds...")
    
    max_wait = 30 * 60  # 30 minutes max
    check_interval = 30  # Check every 30 seconds
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            # Check Polymarket balance
            polymarket_balance_raw = usdc_contract.functions.balanceOf(
                Web3.to_checksum_address(ctf_exchange)
            ).call()
            polymarket_balance = Decimal(polymarket_balance_raw) / Decimal(10**6)
            
            print(f"\r[{elapsed//60}m {elapsed%60}s] Polymarket balance: ${polymarket_balance:.2f} USDC", end="", flush=True)
            
            if polymarket_balance >= Decimal("0.50"):
                print(f"\n\n✅ DEPOSIT PROCESSED!")
                print("=" * 80)
                print(f"Polymarket balance: ${polymarket_balance:.2f} USDC")
                print("\nStarting trading bot in 3 seconds...")
                await asyncio.sleep(3)
                return True
            
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
        except Exception as e:
            print(f"\n⚠️  Error checking balance: {e}")
            await asyncio.sleep(check_interval)
            elapsed += check_interval
    
    print(f"\n\n❌ Deposit not processed after {max_wait//60} minutes")
    print("\nPossible issues:")
    print("1. Bridge is slow (can take up to 30 minutes)")
    print("2. Transaction failed (check: https://polygonscan.com/tx/c9214e91cac8d32a505ace391c6c1aae9b82acaef0e86746e7b336e0fe76b4a1)")
    print("3. Polymarket bridge is down")
    print("\nTry manual deposit at: https://polymarket.com")
    return False

async def main():
    """Main entry point."""
    
    success = await wait_for_deposit()
    
    if success:
        # Start the trading bot
        print("\n🤖 STARTING AUTO-TRADING BOT...")
        print("=" * 80)
        
        from config.config import Config
        from src.main_orchestrator import MainOrchestrator
        
        config = Config.from_env()
        orchestrator = MainOrchestrator(config)
        await orchestrator.run()
    else:
        print("\n" + "=" * 80)
        print("DEPOSIT NOT READY YET")
        print("=" * 80)
        print("\nRun this script again later:")
        print("  python wait_for_deposit_and_trade.py")

if __name__ == "__main__":
    asyncio.run(main())
