#!/usr/bin/env python3
"""
Polymarket Arbitrage Bot - Main Entry Point.

This is a simplified entry point that uses the main orchestrator.
For production use, run: python -m src.main_orchestrator
"""

import asyncio
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    try:
        # Load configuration
        from config.config import load_config
        config = load_config()
        
        logger.info("=" * 80)
        logger.info("POLYMARKET ARBITRAGE BOT")
        logger.info("=" * 80)
        logger.info(f"Wallet: {config.wallet_address}")
        logger.info(f"DRY RUN: {config.dry_run}")
        logger.info("=" * 80)
        
        # Import and run orchestrator
        from src.main_orchestrator import MainOrchestrator
        
        orchestrator = MainOrchestrator(config)
        orchestrator.setup_signal_handlers()
        
        await orchestrator.run()
        
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
