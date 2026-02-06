#!/usr/bin/env python3
"""
FULL AUTONOMOUS START - Does everything automatically:
1. Bridge ALL USDC from Ethereum to Polygon
2. Deposit to Polymarket
3. Start trading bot

This is for REAL TRADING with REAL MONEY.
"""

import asyncio
import sys
import logging
from decimal import Decimal
from web3 import Web3
from config.config import load_config
from src.main_orchestrator import MainOrchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('full_auto_start.log')
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Full autonomous start."""
    
    logger.info("=" * 80)
    logger.info("FULL AUTONOMOUS START - REAL TRADING")
    logger.info("=" * 80)
    logger.info("")
    logger.info("This will:")
    logger.info("  1. Bridge ALL USDC from Ethereum to Polygon")
    logger.info("  2. Wait for bridge to complete")
    logger.info("  3. Deposit to Polymarket")
    logger.info("  4. Start trading bot")
    logger.info("")
    logger.info("=" * 80)
    logger.info("")
    
    # Load configuration
    try:
        config = load_config()
        logger.info("[OK] Configuration loaded")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load configuration: {e}")
        return 1
    
    logger.info(f"Wallet: {config.wallet_address}")
    logger.info(f"DRY_RUN: {config.dry_run}")
    logger.info("")
    
    if not config.dry_run:
        logger.warning("[LIVE] LIVE TRADING MODE - REAL MONEY WILL BE USED")
        logger.warning("")
    
    # Step 1: Bridge USDC from Ethereum to Polygon
    logger.info("=" * 80)
    logger.info("STEP 1: BRIDGE USDC FROM ETHEREUM TO POLYGON")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        from src.auto_bridge_manager import AutoBridgeManager
        
        bridge_manager = AutoBridgeManager(
            private_key=config.private_key,
            polygon_rpc=config.polygon_rpc_url,
            dry_run=config.dry_run
        )
        
        # Check Ethereum balance
        eth_web3 = Web3(Web3.HTTPProvider("https://eth-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64"))
        account = eth_web3.eth.account.from_key(config.private_key)
        
        # USDC contract on Ethereum
        usdc_address = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        usdc_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]
        
        usdc_contract = eth_web3.eth.contract(address=usdc_address, abi=usdc_abi)
        usdc_balance_wei = usdc_contract.functions.balanceOf(account.address).call()
        usdc_balance = Decimal(usdc_balance_wei) / Decimal(10**6)
        
        eth_balance_wei = eth_web3.eth.get_balance(account.address)
        eth_balance = Decimal(eth_balance_wei) / Decimal(10**18)
        
        logger.info(f"Ethereum Wallet Balance:")
        logger.info(f"  USDC: ${usdc_balance:.2f}")
        logger.info(f"  ETH: {eth_balance:.6f} ETH")
        logger.info("")
        
        if usdc_balance < Decimal("0.50"):
            logger.error("Insufficient USDC on Ethereum to bridge (need at least $0.50)")
            logger.info("Skipping bridge, checking Polygon balance...")
        else:
            # Bridge ALL USDC
            logger.info(f"Bridging ${usdc_balance:.2f} USDC from Ethereum to Polygon...")
            logger.info("This will take 5-30 minutes...")
            logger.info("")
            
            success = await bridge_manager.bridge_if_needed()
            
            if success:
                logger.info("[OK] Bridge completed successfully!")
            else:
                logger.warning("[!] Bridge may have failed or is still pending")
                logger.info("Continuing anyway - will check Polygon balance...")
        
    except Exception as e:
        logger.error(f"Bridge error: {e}")
        logger.info("Continuing anyway - will check Polygon balance...")
    
    logger.info("")
    
    # Step 2: Check Polygon balance and deposit to Polymarket
    logger.info("=" * 80)
    logger.info("STEP 2: CHECK POLYGON BALANCE")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        polygon_web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
        account = polygon_web3.eth.account.from_key(config.private_key)
        
        # USDC contract on Polygon
        polygon_usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        polygon_usdc_contract = polygon_web3.eth.contract(address=polygon_usdc_address, abi=usdc_abi)
        polygon_usdc_balance_wei = polygon_usdc_contract.functions.balanceOf(account.address).call()
        polygon_usdc_balance = Decimal(polygon_usdc_balance_wei) / Decimal(10**6)
        
        logger.info(f"Polygon Wallet Balance:")
        logger.info(f"  USDC: ${polygon_usdc_balance:.2f}")
        logger.info("")
        
        if polygon_usdc_balance < Decimal("0.50"):
            logger.error("=" * 80)
            logger.error("INSUFFICIENT FUNDS ON POLYGON")
            logger.error("=" * 80)
            logger.error(f"Polygon USDC balance: ${polygon_usdc_balance:.2f}")
            logger.error("Minimum required: $0.50")
            logger.error("")
            logger.error("Options:")
            logger.error("1. Wait for bridge to complete (if you just bridged)")
            logger.error("2. Use Polymarket website to deposit (instant, free)")
            logger.error("3. Send USDC directly to Polygon")
            logger.error("")
            return 1
        
    except Exception as e:
        logger.error(f"Failed to check Polygon balance: {e}")
        logger.info("Continuing anyway...")
    
    logger.info("")
    
    # Step 3: Start trading bot
    logger.info("=" * 80)
    logger.info("STEP 3: START TRADING BOT")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        orchestrator = MainOrchestrator(config)
        orchestrator.setup_signal_handlers()
        
        logger.info("[OK] Bot initialized successfully")
        logger.info("")
        logger.info("Starting autonomous trading...")
        logger.info("Press Ctrl+C to stop")
        logger.info("")
        
        await orchestrator.run()
        
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
