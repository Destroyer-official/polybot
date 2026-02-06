#!/usr/bin/env python3
"""
Check wallet balance and simulate deposit to Polymarket.
This script helps verify the deposit process works correctly.
"""

import asyncio
import sys
from decimal import Decimal
from config.config import load_config
from src.fund_manager import FundManager
from web3 import Web3

async def main():
    print("=" * 80)
    print("WALLET BALANCE CHECK & DEPOSIT SIMULATION")
    print("=" * 80)
    print()
    
    # Load config
    config = load_config()
    
    # Initialize Web3
    web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
    account = web3.eth.account.from_key(config.private_key)
    
    print(f"Wallet: {account.address}")
    print(f"Network: Polygon (Chain ID: {config.chain_id})")
    print(f"DRY_RUN: {config.dry_run}")
    print()
    
    # Initialize fund manager
    fund_manager = FundManager(
        web3=web3,
        wallet=account,
        usdc_address=config.usdc_address,
        ctf_exchange_address=config.ctf_exchange_address,
        min_balance=config.min_balance,
        target_balance=config.target_balance,
        withdraw_limit=config.withdraw_limit,
        dry_run=config.dry_run
    )
    
    # Check balances
    print("Checking balances...")
    try:
        private_balance, polymarket_balance = await fund_manager.check_balance()
        
        print(f"✓ Private Wallet: ${private_balance:.2f} USDC")
        print(f"✓ Polymarket: ${polymarket_balance:.2f} USDC")
        print(f"✓ Total: ${private_balance + polymarket_balance:.2f} USDC")
        print()
        
        # Check if we have funds to deposit
        if private_balance >= Decimal('1.0'):
            print("=" * 80)
            print("FUNDS DETECTED - READY TO DEPOSIT")
            print("=" * 80)
            print()
            
            # Calculate deposit amount
            if private_balance < Decimal('5.0'):
                buffer = Decimal('0.20')
            elif private_balance < Decimal('20.0'):
                buffer = Decimal('0.30')
            else:
                buffer = Decimal('0.50')
            
            deposit_amount = private_balance - buffer
            
            if deposit_amount >= Decimal('0.50'):
                print(f"Private wallet balance: ${private_balance:.2f}")
                print(f"Gas buffer: ${buffer:.2f}")
                print(f"Deposit amount: ${deposit_amount:.2f}")
                print()
                
                if config.dry_run:
                    print("⚠️  DRY_RUN MODE - No actual deposit will occur")
                    print()
                    print("To make a REAL deposit:")
                    print("1. Edit .env file")
                    print("2. Change DRY_RUN=true to DRY_RUN=false")
                    print("3. Run this script again")
                    print()
                else:
                    print("🚀 INITIATING REAL DEPOSIT...")
                    print()
                    
                    # Confirm with user
                    response = input(f"Deposit ${deposit_amount:.2f} to Polymarket? (yes/no): ")
                    if response.lower() in ['yes', 'y']:
                        print()
                        print("Executing deposit...")
                        receipt = await fund_manager.auto_deposit(deposit_amount)
                        
                        if receipt:
                            print(f"✓ Deposit successful!")
                            print(f"✓ Transaction: {receipt['transactionHash'].hex()}")
                            print()
                            
                            # Check new balances
                            new_private, new_polymarket = await fund_manager.check_balance()
                            print("New balances:")
                            print(f"  Private Wallet: ${new_private:.2f} USDC")
                            print(f"  Polymarket: ${new_polymarket:.2f} USDC")
                            print()
                            print("✅ READY TO START TRADING!")
                        else:
                            print("⚠️  Deposit simulation completed (dry run)")
                    else:
                        print("Deposit cancelled")
            else:
                print(f"⚠️  Deposit amount too small: ${deposit_amount:.2f}")
                print(f"   Need at least $0.50 after gas buffer")
                print(f"   Please add more USDC to your wallet")
        else:
            print("=" * 80)
            print("NO FUNDS DETECTED")
            print("=" * 80)
            print()
            print(f"⚠️  Private wallet balance: ${private_balance:.2f}")
            print(f"   Minimum required: $1.00")
            print()
            print("📝 TO ADD FUNDS:")
            print(f"   1. Send USDC to: {account.address}")
            print(f"   2. Network: Polygon (NOT Ethereum!)")
            print(f"   3. Recommended: $4-$20 USDC")
            print()
            print("💡 WHERE TO GET USDC:")
            print("   - Coinbase: Buy USDC, withdraw to Polygon")
            print("   - Binance: Buy USDC, withdraw to Polygon")
            print("   - Bridge: Use Polygon Bridge from Ethereum")
            print()
        
    except Exception as e:
        print(f"❌ Error checking balance: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
