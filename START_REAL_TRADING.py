#!/usr/bin/env python3
"""
START REAL TRADING - Run the bot with real money.

This script:
1. Checks your balances
2. Starts the trading bot
3. Scans for arbitrage opportunities
4. Executes profitable trades automatically

IMPORTANT: This uses REAL MONEY. Make sure you have:
- USDC in your Polymarket account (deposit via website is instant)
- Or USDC on Polygon (will auto-deposit to Polymarket)
"""

import asyncio
import sys
import logging
from decimal import Decimal
from config.config import load_config
from src.main_orchestrator import MainOrchestrator

# Setup logging
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
    """Start real trading."""
    
    logger.info("=" * 80)
    logger.info("POLYMARKET ARBITRAGE BOT - REAL TRADING MODE")
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
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Wallet: {config.wallet_address}")
    logger.info(f"  Network: Polygon (Chain ID: {config.chain_id})")
    logger.info(f"  DRY_RUN: {config.dry_run}")
    logger.info(f"  Min profit threshold: {config.min_profit_threshold * 100}%")
    logger.info(f"  Scan interval: {config.scan_interval_seconds}s")
    logger.info(f"  Max gas price: {config.max_gas_price_gwei} gwei")
    logger.info("")
    
    if config.dry_run:
        logger.warning("[TEST] DRY RUN MODE - No real transactions")
        logger.warning("Set DRY_RUN=false in .env for real trading")
        logger.warning("")
    else:
        logger.warning("=" * 80)
        logger.warning("LIVE TRADING MODE - REAL MONEY WILL BE USED")
        logger.warning("=" * 80)
        logger.warning("")
        logger.warning("The bot will:")
        logger.warning("  - Scan 77+ active markets every 2 seconds")
        logger.warning("  - Look for arbitrage opportunities (YES + NO != $1.00)")
        logger.warning("  - Execute profitable trades automatically")
        logger.warning("  - Use dynamic position sizing ($0.50 - $2.00 per trade)")
        logger.warning("")
        logger.warning("Press Ctrl+C at any time to stop")
        logger.warning("")
        
        # Give user 5 seconds to cancel
        logger.info("Starting in 5 seconds...")
        for i in range(5, 0, -1):
            logger.info(f"  {i}...")
            await asyncio.sleep(1)
        logger.info("")
    
    logger.info("=" * 80)
    logger.info("STARTING BOT")
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
