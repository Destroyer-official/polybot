#!/usr/bin/env python3
"""
Check if the withdrawal transaction went through.
"""

import asyncio
import logging
from web3 import Web3
from config.config import load_config

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def main():
    """Check transaction status."""
    
    config = load_config()
    web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
    
    tx_hash = "0x53176acf9ffcd33a36cb48b6b01eb077f8e1e563f92b1aa5ff726c148d471363"
    
    logger.info("=" * 70)
    logger.info("CHECKING WITHDRAWAL TRANSACTION")
    logger.info("=" * 70)
    logger.info(f"TX Hash: {tx_hash}")
    logger.info("")
    
    try:
        # Try to get transaction receipt
        logger.info("Checking transaction status...")
        receipt = web3.eth.get_transaction_receipt(tx_hash)
        
        if receipt:
            logger.info("")
            logger.info("✅ TRANSACTION FOUND!")
            logger.info("")
            logger.info(f"Status: {'SUCCESS' if receipt['status'] == 1 else 'FAILED'}")
            logger.info(f"Block: {receipt['blockNumber']}")
            logger.info(f"Gas Used: {receipt['gasUsed']}")
            logger.info("")
            
            if receipt['status'] == 1:
                logger.info("✅ Withdrawal was SUCCESSFUL!")
                logger.info("")
                logger.info("Checking new balance...")
                
                # Check USDC balance
                usdc_abi = [
                    {
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function"
                    }
                ]
                
                usdc_contract = web3.eth.contract(
                    address=Web3.to_checksum_address(config.usdc_address),
                    abi=usdc_abi
                )
                
                balance_raw = usdc_contract.functions.balanceOf(
                    Web3.to_checksum_address(config.wallet_address)
                ).call()
                balance = balance_raw / 10**6
                
                logger.info(f"Your wallet balance: ${balance:.2f} USDC")
                logger.info("")
                logger.info("Funds are now in your wallet!")
            else:
                logger.error("❌ Transaction FAILED!")
                logger.error("The withdrawal did not complete successfully")
        else:
            logger.warning("⏳ Transaction not found yet")
            logger.warning("It may still be pending...")
            logger.warning("")
            logger.warning("Wait a few minutes and check again")
            
    except Exception as e:
        logger.warning("⏳ Transaction not found in blockchain yet")
        logger.warning("")
        logger.warning("This could mean:")
        logger.warning("1. Transaction still pending (wait 2-5 minutes)")
        logger.warning("2. Transaction failed and was not included")
        logger.warning("3. Network congestion delaying confirmation")
        logger.warning("")
        logger.warning("Check on Polygonscan:")
        logger.warning(f"https://polygonscan.com/tx/{tx_hash}")
        logger.warning("")
        logger.warning("Or check your balance:")
        logger.warning("python BALANCE_DIAGNOSTIC.py")


if __name__ == "__main__":
    asyncio.run(main())
