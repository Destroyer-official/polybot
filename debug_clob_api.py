#!/usr/bin/env python3
"""
Debug CLOB API balance response.
"""

import asyncio
import aiohttp
import logging
from config.config import load_config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    """Check CLOB API response."""
    
    config = load_config()
    wallet = config.wallet_address
    
    logger.info(f"Checking CLOB API for wallet: {wallet}")
    
    # Try different API endpoints
    endpoints = [
        f"https://clob.polymarket.com/balances/{wallet}",
        f"https://clob.polymarket.com/balance/{wallet}",
        f"https://clob.polymarket.com/user/{wallet}/balance",
        f"https://clob.polymarket.com/user/{wallet}/balances",
    ]
    
    async with aiohttp.ClientSession() as session:
        for url in endpoints:
            logger.info(f"\nTrying: {url}")
            try:
                async with session.get(url, timeout=10) as response:
                    logger.info(f"Status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Response: {data}")
                    else:
                        text = await response.text()
                        logger.info(f"Response: {text[:200]}")
                        
            except Exception as e:
                logger.error(f"Error: {e}")
    
    # Also check if there's a proxy wallet
    logger.info("\n" + "=" * 60)
    logger.info("Checking for Polymarket proxy wallet...")
    logger.info("=" * 60)
    
    # The proxy wallet address from your deposit
    proxy_address = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    
    logger.info(f"\nYour EOA: {wallet}")
    logger.info(f"Your Proxy: {proxy_address}")
    
    # Check USDC balance of proxy wallet directly
    from web3 import Web3
    web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
    
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
    
    # Check EOA balance
    eoa_balance_raw = usdc_contract.functions.balanceOf(
        Web3.to_checksum_address(wallet)
    ).call()
    eoa_balance = eoa_balance_raw / 10**6
    
    # Check proxy balance
    proxy_balance_raw = usdc_contract.functions.balanceOf(
        Web3.to_checksum_address(proxy_address)
    ).call()
    proxy_balance = proxy_balance_raw / 10**6
    
    logger.info(f"\nDirect USDC balance check:")
    logger.info(f"  EOA: ${eoa_balance:.2f} USDC")
    logger.info(f"  Proxy: ${proxy_balance:.2f} USDC")
    logger.info(f"  Total: ${eoa_balance + proxy_balance:.2f} USDC")


if __name__ == "__main__":
    asyncio.run(main())
