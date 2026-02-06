#!/usr/bin/env python3
"""
Comprehensive balance diagnostic.
"""

import asyncio
import logging
from web3 import Web3
from eth_account import Account
from config.config import load_config

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def main():
    """Run comprehensive balance check."""
    
    config = load_config()
    web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
    wallet = Account.from_key(config.private_key)
    
    logger.info("=" * 70)
    logger.info("POLYMARKET BALANCE DIAGNOSTIC")
    logger.info("=" * 70)
    logger.info("")
    
    # 1. Check EOA USDC balance
    logger.info("1. Checking EOA USDC balance on Polygon...")
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
    
    eoa_balance_raw = usdc_contract.functions.balanceOf(
        Web3.to_checksum_address(wallet.address)
    ).call()
    eoa_balance = eoa_balance_raw / 10**6
    
    logger.info(f"   EOA Address: {wallet.address}")
    logger.info(f"   USDC Balance: ${eoa_balance:.6f}")
    logger.info("")
    
    # 2. Check proxy wallet USDC balance
    logger.info("2. Checking Polymarket Proxy wallet...")
    proxy_address = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    
    proxy_balance_raw = usdc_contract.functions.balanceOf(
        Web3.to_checksum_address(proxy_address)
    ).call()
    proxy_balance = proxy_balance_raw / 10**6
    
    logger.info(f"   Proxy Address: {proxy_address}")
    logger.info(f"   USDC Balance: ${proxy_balance:.6f}")
    logger.info("")
    
    # 3. Check MATIC balance (for gas)
    logger.info("3. Checking MATIC balance (for gas)...")
    matic_balance_raw = web3.eth.get_balance(wallet.address)
    matic_balance = matic_balance_raw / 10**18
    
    logger.info(f"   MATIC Balance: {matic_balance:.6f} MATIC")
    logger.info("")
    
    # 4. Summary
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    
    total_usdc = eoa_balance + proxy_balance
    
    if total_usdc > 0:
        logger.info(f"✓ Total USDC found: ${total_usdc:.2f}")
        logger.info(f"  - In EOA: ${eoa_balance:.2f}")
        logger.info(f"  - In Proxy: ${proxy_balance:.2f}")
        logger.info("")
        logger.info("Bot can start trading!")
    else:
        logger.info("✗ No USDC found on Polygon")
        logger.info("")
        logger.info("POSSIBLE REASONS:")
        logger.info("1. Deposit still processing (check Polymarket website)")
        logger.info("2. Funds deposited to different wallet")
        logger.info("3. Funds in shares/positions (not cash)")
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info("1. Go to https://polymarket.com/")
        logger.info("2. Connect MetaMask with this wallet:")
        logger.info(f"   {wallet.address}")
        logger.info("3. Check Portfolio → Cash balance")
        logger.info("4. If you see $4.23 there:")
        logger.info("   - Wait 5-10 minutes for deposit to complete")
        logger.info("   - Or check if funds are in open positions")
        logger.info("5. If you don't see any balance:")
        logger.info("   - You may have deposited to a different wallet")
        logger.info("   - Check which wallet is connected in MetaMask")
    
    logger.info("")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
