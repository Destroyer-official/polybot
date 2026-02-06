#!/usr/bin/env python3
"""
Test the fixed balance check.
"""

import asyncio
import logging
from config.config import load_config
from src.fund_manager import FundManager
from web3 import Web3
from eth_account import Account

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Test balance check."""
    
    logger.info("Testing balance check fix...")
    
    # Load config
    config = load_config()
    
    # Setup Web3
    web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
    wallet = Account.from_key(config.private_key)
    
    logger.info(f"Wallet: {wallet.address}")
    
    # Create fund manager
    fund_manager = FundManager(
        web3=web3,
        wallet=wallet,
        usdc_address=config.usdc_address,
        ctf_exchange_address=config.ctf_exchange_address,
        min_balance=config.min_balance,
        target_balance=config.target_balance,
        withdraw_limit=config.withdraw_limit,
        dry_run=config.dry_run
    )
    
    # Test balance check
    try:
        logger.info("Checking balances...")
        eoa_balance, polymarket_balance = await fund_manager.check_balance()
        
        logger.info("=" * 60)
        logger.info("BALANCE CHECK SUCCESSFUL!")
        logger.info("=" * 60)
        logger.info(f"EOA Balance (Polygon): ${eoa_balance:.2f} USDC")
        logger.info(f"Polymarket Balance: ${polymarket_balance:.2f} USDC")
        logger.info(f"Total Available: ${eoa_balance + polymarket_balance:.2f} USDC")
        logger.info("=" * 60)
        
        if polymarket_balance > 0:
            logger.info("")
            logger.info("✓ Polymarket balance detected!")
            logger.info("✓ Bot can start trading now!")
        else:
            logger.warning("")
            logger.warning("⚠ No Polymarket balance detected")
            logger.warning("Please deposit USDC to Polymarket via website")
        
        return 0
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error("BALANCE CHECK FAILED")
        logger.error("=" * 60)
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
