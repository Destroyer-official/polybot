#!/usr/bin/env python3
"""
FULLY AUTONOMOUS BOT STARTUP

This script starts the bot in fully autonomous mode:
- Automatically detects USDC on any network
- Automatically bridges to Polygon if needed
- Automatically starts trading
- NO human intervention required

Just run this and let it work!
"""

import asyncio
import sys
import logging
from pathlib import Path

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
    """Start the bot in fully autonomous mode."""
    
    print("=" * 80)
    print("POLYMARKET ARBITRAGE BOT - FULLY AUTONOMOUS MODE")
    print("=" * 80)
    print()
    print("🤖 This bot operates 100% autonomously:")
    print("   ✓ Detects USDC on any network")
    print("   ✓ Automatically bridges to Polygon")
    print("   ✓ Automatically deposits to Polymarket")
    print("   ✓ Automatically executes trades")
    print("   ✓ Automatically manages funds")
    print("   ✓ NO human intervention needed")
    print()
    print("=" * 80)
    print()
    
    # Import here to show loading progress
    logger.info("Loading configuration...")
    from config.config import Config
    config = Config.from_env()
    
    logger.info("Initializing bot components...")
    from src.main_orchestrator import MainOrchestrator
    
    # Create orchestrator
    orchestrator = MainOrchestrator(config)
    
    # Setup signal handlers for graceful shutdown
    orchestrator.setup_signal_handlers()
    
    logger.info("=" * 80)
    logger.info("🚀 STARTING AUTONOMOUS OPERATION")
    logger.info("=" * 80)
    logger.info("")
    logger.info("The bot will now:")
    logger.info("1. Check for USDC on Ethereum and Polygon")
    logger.info("2. Automatically bridge if needed")
    logger.info("3. Start scanning markets")
    logger.info("4. Execute profitable trades")
    logger.info("5. Manage funds automatically")
    logger.info("")
    logger.info("Press Ctrl+C to stop the bot gracefully")
    logger.info("=" * 80)
    logger.info("")
    
    # Run the bot
    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutdown requested by user")
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
