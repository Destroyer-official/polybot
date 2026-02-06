#!/usr/bin/env python3
"""
Quick test to see if bot can fetch and parse markets.
"""

import asyncio
import logging
from config.config import load_config
from src.main_orchestrator import MainOrchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Quick market fetch test."""
    
    logger.info("=" * 80)
    logger.info("QUICK MARKET FETCH TEST")
    logger.info("=" * 80)
    
    # Load configuration
    config = load_config()
    
    # Create orchestrator
    orchestrator = MainOrchestrator(config)
    
    # Run one scan
    logger.info("\nRunning one market scan...")
    try:
        await orchestrator._scan_and_execute()
    except Exception as e:
        logger.error(f"Error during scan: {e}", exc_info=True)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
