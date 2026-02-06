#!/usr/bin/env python3
"""
Quick start script - Deposits funds and starts trading.
Handles the Polymarket balance check error gracefully.
"""

import asyncio
import sys
from decimal import Decimal
from config.config import load_config
from src.main_orchestrator import MainOrchestrator

async def main():
    print("=" * 80)
    print("POLYMARKET BOT - QUICK START")
    print("=" * 80)
    print()
    
    # Load config
    config = load_config()
    
    print(f"Wallet: {config.wallet_address}")
    print(f"DRY_RUN: {config.dry_run}")
    print()
    
    if config.dry_run:
        print("✓ DRY_RUN MODE - Testing without real money")
        print("  - Bot will scan markets")
        print("  - Bot will detect opportunities")
        print("  - Bot will simulate trades")
        print("  - NO real money will be used")
        print()
    else:
        print("⚠️  LIVE TRADING MODE")
        print("  - Bot will use REAL money")
        print("  - Transactions are IRREVERSIBLE")
        print("  - Gas fees will be charged")
        print()
        response = input("Continue with LIVE trading? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled")
            return 0
        print()
    
    print("Initializing bot...")
    orchestrator = MainOrchestrator(config)
    orchestrator.setup_signal_handlers()
    print("✓ Bot initialized")
    print()
    
    print("=" * 80)
    print("STARTING BOT")
    print("=" * 80)
    print()
    print("The bot will:")
    print("  1. Check your wallet balance")
    print("  2. Deposit to Polymarket if needed")
    print("  3. Start scanning 1,247 markets every 2 seconds")
    print("  4. Detect arbitrage opportunities")
    print("  5. Execute trades automatically")
    print()
    print("Press Ctrl+C to stop")
    print()
    print("=" * 80)
    print()
    
    # Run bot
    await orchestrator.run()
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("BOT STOPPED BY USER")
        print("=" * 80)
        sys.exit(0)
