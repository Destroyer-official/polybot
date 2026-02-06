#!/usr/bin/env python3
"""
Check Polymarket account status using py-clob-client.
"""

import asyncio
import logging
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from config.config import load_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Check Polymarket account."""
    
    config = load_config()
    
    logger.info("=" * 60)
    logger.info("CHECKING POLYMARKET ACCOUNT")
    logger.info("=" * 60)
    logger.info(f"Wallet: {config.wallet_address}")
    logger.info("")
    
    try:
        # Create CLOB client
        # For read-only operations, we don't need API credentials
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=config.private_key,
            chain_id=config.chain_id
        )
        
        logger.info("Checking account balance...")
        
        # Get balance allowance (this shows your trading balance)
        try:
            balance_allowance = client.get_balance_allowance()
            logger.info(f"Balance Allowance: {balance_allowance}")
        except Exception as e:
            logger.warning(f"Could not get balance allowance: {e}")
        
        # Get open orders
        try:
            logger.info("\nChecking open orders...")
            orders = client.get_orders()
            logger.info(f"Open orders: {len(orders) if orders else 0}")
            if orders:
                for order in orders[:5]:  # Show first 5
                    logger.info(f"  Order: {order}")
        except Exception as e:
            logger.warning(f"Could not get orders: {e}")
        
        # Get positions
        try:
            logger.info("\nChecking positions...")
            # This might require different method
            logger.info("(Position check not implemented)")
        except Exception as e:
            logger.warning(f"Could not get positions: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info("ACCOUNT CHECK COMPLETE")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error checking account: {e}", exc_info=True)
        
        logger.info("\n" + "=" * 60)
        logger.info("ALTERNATIVE: Check manually")
        logger.info("=" * 60)
        logger.info("1. Go to https://polymarket.com/")
        logger.info("2. Connect your MetaMask wallet")
        logger.info("3. Check your Portfolio balance")
        logger.info("")
        logger.info("If you see $4.23 there but bot shows $0.00:")
        logger.info("- The deposit might still be processing")
        logger.info("- Or funds are in a different format (shares vs USDC)")
        logger.info("- Or the bot needs to use a different API endpoint")


if __name__ == "__main__":
    asyncio.run(main())
