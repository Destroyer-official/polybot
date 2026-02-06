#!/usr/bin/env python3
"""
Withdraw funds from Polymarket to your wallet.
"""

import asyncio
import logging
from decimal import Decimal
from config.config import load_config
from src.fund_manager import FundManager
from web3 import Web3
from eth_account import Account

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Withdraw from Polymarket to wallet."""
    
    logger.info("=" * 70)
    logger.info("WITHDRAW FROM POLYMARKET TO WALLET")
    logger.info("=" * 70)
    logger.info("")
    
    # Load config
    config = load_config()
    
    # Setup Web3
    web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
    wallet = Account.from_key(config.private_key)
    
    logger.info(f"Wallet: {wallet.address}")
    logger.info("")
    
    # Create fund manager
    fund_manager = FundManager(
        web3=web3,
        wallet=wallet,
        usdc_address=config.usdc_address,
        ctf_exchange_address=config.ctf_exchange_address,
        min_balance=config.min_balance,
        target_balance=config.target_balance,
        withdraw_limit=config.withdraw_limit,
        dry_run=False  # Real withdrawal
    )
    
    # Check current balances
    logger.info("Checking current balances...")
    try:
        eoa_balance, polymarket_balance = await fund_manager.check_balance()
        
        logger.info(f"EOA Balance (Polygon): ${eoa_balance:.2f} USDC")
        logger.info(f"Polymarket Balance: ${polymarket_balance:.2f} USDC")
        logger.info("")
        
        if polymarket_balance <= 0:
            logger.error("No funds in Polymarket to withdraw!")
            logger.info("")
            logger.info("Possible reasons:")
            logger.info("1. Funds already withdrawn")
            logger.info("2. Balance check not working correctly")
            logger.info("3. Funds in open positions (not available cash)")
            logger.info("")
            logger.info("Check your Polymarket account at: https://polymarket.com/")
            return 1
        
        # Withdraw amount
        withdraw_amount = Decimal('10.0')
        
        if polymarket_balance < withdraw_amount:
            logger.warning(f"Polymarket balance (${polymarket_balance:.2f}) is less than $10")
            logger.info(f"Will withdraw available amount: ${polymarket_balance:.2f}")
            withdraw_amount = polymarket_balance
        
        logger.info("=" * 70)
        logger.info(f"WITHDRAWING ${withdraw_amount:.2f} FROM POLYMARKET")
        logger.info("=" * 70)
        logger.info("")
        logger.info("This will:")
        logger.info(f"1. Withdraw ${withdraw_amount:.2f} USDC from Polymarket")
        logger.info(f"2. Send it to your wallet: {wallet.address}")
        logger.info(f"3. You'll have ${eoa_balance + withdraw_amount:.2f} USDC in your wallet")
        logger.info("")
        
        # Confirm
        logger.warning("⚠️  This is a REAL transaction on Polygon blockchain")
        logger.warning("⚠️  Gas fees will be deducted from your MATIC balance")
        logger.info("")
        
        # Wait 3 seconds
        logger.info("Starting withdrawal in 3 seconds...")
        for i in range(3, 0, -1):
            logger.info(f"  {i}...")
            await asyncio.sleep(1)
        logger.info("")
        
        # Execute withdrawal
        logger.info("Executing withdrawal...")
        try:
            receipt = await fund_manager.auto_withdraw(withdraw_amount)
            
            if receipt:
                logger.info("")
                logger.info("=" * 70)
                logger.info("✅ WITHDRAWAL SUCCESSFUL!")
                logger.info("=" * 70)
                logger.info(f"Transaction Hash: {receipt['transactionHash'].hex()}")
                logger.info(f"Block Number: {receipt['blockNumber']}")
                logger.info(f"Gas Used: {receipt['gasUsed']}")
                logger.info("")
                
                # Check new balances
                logger.info("Checking new balances...")
                new_eoa_balance, new_polymarket_balance = await fund_manager.check_balance()
                
                logger.info(f"EOA Balance: ${eoa_balance:.2f} → ${new_eoa_balance:.2f}")
                logger.info(f"Polymarket Balance: ${polymarket_balance:.2f} → ${new_polymarket_balance:.2f}")
                logger.info("")
                logger.info(f"✓ Withdrew ${withdraw_amount:.2f} USDC to your wallet")
                logger.info("")
                
                return 0
            else:
                logger.error("Withdrawal failed - no receipt returned")
                return 1
                
        except Exception as e:
            logger.error(f"Withdrawal failed: {e}", exc_info=True)
            logger.info("")
            logger.info("TROUBLESHOOTING:")
            logger.info("1. Check if you have enough MATIC for gas")
            logger.info("2. Check if funds are locked in open positions")
            logger.info("3. Try withdrawing via Polymarket website")
            return 1
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
