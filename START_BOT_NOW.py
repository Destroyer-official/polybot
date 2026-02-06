#!/usr/bin/env python3
"""
Start the bot immediately - NO BRIDGE WAIT!

This script skips the slow bridge and starts trading right away
if you have any USDC in Polymarket.
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
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Run the bot immediately without bridge wait."""
    
    logger.info("=" * 80)
    logger.info("POLYMARKET ARBITRAGE BOT - INSTANT START")
    logger.info("=" * 80)
    logger.info("")
    logger.info("This version skips the slow bridge and starts trading immediately")
    logger.info("if you have USDC in Polymarket.")
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
    
    if not config.dry_run:
        logger.warning("[LIVE] LIVE TRADING MODE")
        logger.warning("[!] REAL MONEY WILL BE USED")
        logger.warning("[!] REAL TRADES WILL BE EXECUTED")
        logger.warning("")
    
    logger.info("=" * 80)
    logger.info("STARTING BOT")
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
