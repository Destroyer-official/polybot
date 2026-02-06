#!/usr/bin/env python3
"""
Test the fully autonomous bot with automatic cross-chain bridging.

This script demonstrates the bot's ability to:
1. Detect USDC on Ethereum
2. Automatically bridge to Polygon
3. Start trading without human intervention
"""

import asyncio
import sys
import logging
from config.config import load_config
from src.main_orchestrator import MainOrchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('autonomous_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Run the fully autonomous bot."""
    
    logger.info("=" * 80)
    logger.info("FULLY AUTONOMOUS POLYMARKET BOT")
    logger.info("=" * 80)
    logger.info("")
    logger.info("This bot will:")
    logger.info("  1. Check for USDC on Ethereum and Polygon")
    logger.info("  2. Automatically bridge from Ethereum to Polygon if needed")
    logger.info("  3. Start trading autonomously")
    logger.info("  4. Manage funds automatically")
    logger.info("  5. Execute trades 24/7 without human intervention")
    logger.info("")
    logger.info("=" * 80)
    logger.info("")
    
    # Load configuration
    try:
        config = load_config()
        logger.info("[OK] Configuration loaded")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load configuration: {e}")
        return 1
    
    # Show configuration
    logger.info(f"Wallet: {config.wallet_address}")
    logger.info(f"Network: Polygon (Chain ID: {config.chain_id})")
    logger.info(f"DRY_RUN: {config.dry_run}")
    logger.info("")
    
    if config.dry_run:
        logger.warning("[!] DRY_RUN MODE ENABLED")
        logger.warning("No real transactions will be executed")
        logger.warning("This is safe for testing")
        logger.warning("")
    else:
        logger.warning("[LIVE] LIVE TRADING MODE")
        logger.warning("[!] REAL MONEY WILL BE USED")
        logger.warning("[!] REAL TRADES WILL BE EXECUTED")
        logger.warning("")
        
        # Countdown
        logger.info("Starting in 10 seconds... Press Ctrl+C to cancel")
        try:
            for i in range(10, 0, -1):
                logger.info(f"  {i}...")
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nCancelled by user")
            return 0
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("STARTING AUTONOMOUS BOT")
    logger.info("=" * 80)
    logger.info("")
    
    # Create and run orchestrator
    try:
        orchestrator = MainOrchestrator(config)
        orchestrator.setup_signal_handlers()
        
        await orchestrator.run()
        
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
