#!/usr/bin/env python3
"""
Check what the py-clob-client is actually returning.
"""

import asyncio
import logging
from py_clob_client.client import ClobClient
from config.config import load_config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    """Check CLOB client balance response."""
    
    config = load_config()
    
    logger.info("=" * 70)
    logger.info("CHECKING PY-CLOB-CLIENT BALANCE")
    logger.info("=" * 70)
    logger.info(f"Wallet: {config.wallet_address}")
    logger.info("")
    
    try:
        # Create client
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=config.private_key,
            chain_id=137
        )
        
        logger.info("Getting balance allowance...")
        balance_data = client.get_balance_allowance()
        
        logger.info("")
        logger.info("Raw response:")
        logger.info(f"{balance_data}")
        logger.info("")
        
        if isinstance(balance_data, dict):
            logger.info("Response fields:")
            for key, value in balance_data.items():
                logger.info(f"  {key}: {value}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("EXPLANATION")
        logger.info("=" * 70)
        logger.info("")
        logger.info("The py-clob-client returns balance allowance, which is:")
        logger.info("- NOT the same as your actual USDC balance")
        logger.info("- It's the approved amount for trading")
        logger.info("- It might be a default/maximum value")
        logger.info("")
        logger.info("To check your REAL balance:")
        logger.info("1. Go to https://polymarket.com/")
        logger.info("2. Connect MetaMask")
        logger.info("3. Check Portfolio → Cash")
        logger.info("")
        logger.info("That's your actual withdrawable balance.")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
