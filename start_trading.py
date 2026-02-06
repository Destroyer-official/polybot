#!/usr/bin/env python3
"""
Start trading with automatic deposit and balance management.
This script will:
1. Check your wallet balance
2. Deposit available funds to Polymarket
3. Start the trading bot
"""

import asyncio
import sys
import time
from decimal import Decimal
from config.config import load_config
from src.main_orchestrator import MainOrchestrator

async def main():
    print("=" * 80)
    print("POLYMARKET ARBITRAGE BOT - STARTUP")
    print("=" * 80)
    print()
    
    # Load config
    config = load_config()
    
    print(f"Wallet: {config.wallet_address}")
    print(f"DRY_RUN: {config.dry_run}")
    print(f"Min Position: ${config.min_position_size}")
    print(f"Max Position: ${config.max_position_size}")
    print()
    
    # Warning for live trading
    if not config.dry_run:
        print("⚠️  WARNING: LIVE TRADING MODE")
        print("   Real money will be used for trades")
        print("   Gas fees will be charged")
        print("   Trades are irreversible")
        print()
        
        response = input("Continue with LIVE trading? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled")
            return 0
        print()
    else:
        print("✓ DRY_RUN MODE - No real trades will execute")
        print()
    
    # Initialize orchestrator
    print("Initializing bot...")
    orchestrator = MainOrchestrator(config)
    
    # Setup signal handlers
    orchestrator.setup_signal_handlers()
    
    print("✓ Bot initialized")
    print()
    
    # Check and manage balance before starting
    print("Checking balances and managing funds...")
    try:
        await orchestrator.fund_manager.check_and_manage_balance()
    except Exception as e:
        print(f"⚠️  Fund management error: {e}")
        print("   Continuing anyway...")
    
    print()
    print("=" * 80)
    print("STARTING BOT")
    print("=" * 80)
    print()
    print("Bot will:")
    print("  - Scan 1,247 markets every 2 seconds")
    print("  - Detect arbitrage opportunities")
    print("  - Execute trades automatically")
    print("  - Manage funds automatically")
    print("  - Save state every 60 seconds")
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
