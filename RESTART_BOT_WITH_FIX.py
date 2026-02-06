#!/usr/bin/env python3
"""
Restart the bot with the fixed balance check.

This script:
1. Stops the old bot (Process ID 17)
2. Starts the new bot with fixed balance checking
3. Bot will now properly detect your Polymarket balance
"""

import asyncio
import sys
import logging
import subprocess
from config.config import load_config
from src.main_orchestrator import MainOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('real_trading.log')
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Restart bot with fixes."""
    
    logger.info("=" * 80)
    logger.info("RESTARTING BOT WITH BALANCE FIX")
    logger.info("=" * 80)
    logger.info("")
    
    # Stop old bot
    logger.info("Stopping old bot (Process ID 17)...")
    try:
        # On Windows, use taskkill
        subprocess.run(
            ["taskkill", "/F", "/PID", "17"],
            capture_output=True,
            text=True
        )
        logger.info("[OK] Old bot stopped")
    except Exception as e:
        logger.warning(f"Could not stop old bot: {e}")
        logger.warning("It may have already stopped")
    
    logger.info("")
    await asyncio.sleep(2)
    
    # Load configuration
    try:
        config = load_config()
        logger.info("[OK] Configuration loaded")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load configuration: {e}")
        return 1
    
    # Show configuration
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Wallet: {config.wallet_address}")
    logger.info(f"  Network: Polygon (Chain ID: {config.chain_id})")
    logger.info(f"  DRY_RUN: {config.dry_run}")
    logger.info(f"  Min profit threshold: {config.min_profit_threshold * 100}%")
    logger.info(f"  Scan interval: {config.scan_interval_seconds}s")
    logger.info("")
    
    if not config.dry_run:
        logger.warning("=" * 80)
        logger.warning("LIVE TRADING MODE - REAL MONEY WILL BE USED")
        logger.warning("=" * 80)
        logger.warning("")
        logger.warning("The bot will:")
        logger.warning("  - Scan 77+ active markets every 2 seconds")
        logger.warning("  - Look for arbitrage opportunities")
        logger.warning("  - Execute profitable trades automatically")
        logger.warning("  - Use dynamic position sizing ($0.50 - $2.00 per trade)")
        logger.warning("")
        logger.warning("Press Ctrl+C at any time to stop")
        logger.warning("")
        
        # Give user 3 seconds to cancel
        logger.info("Starting in 3 seconds...")
        for i in range(3, 0, -1):
            logger.info(f"  {i}...")
            await asyncio.sleep(1)
        logger.info("")
    
    logger.info("=" * 80)
    logger.info("STARTING BOT WITH FIXED BALANCE CHECK")
    logger.info("=" * 80)
    logger.info("")
    
    # Create and run orchestrator
    try:
        orchestrator = MainOrchestrator(config)
        orchestrator.setup_signal_handlers()
        
        logger.info("[OK] Bot initialized successfully")
        logger.info("")
        logger.info("Bot is now running...")
        logger.info("Scanning markets for opportunities...")
        logger.info("")
        
        await orchestrator.run()
        
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 80)
        logger.info("SHUTDOWN REQUESTED BY USER")
        logger.info("=" * 80)
        logger.info("")
    except Exception as e:
        logger.error("=" * 80)
        logger.error("FATAL ERROR")
        logger.error("=" * 80)
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    
    logger.info("Bot stopped")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
