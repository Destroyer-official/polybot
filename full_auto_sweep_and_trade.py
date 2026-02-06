#!/usr/bin/env python3
"""
FULL AUTONOMOUS MODE:
1. Sweep ALL USDC from Ethereum to Polygon
2. Deposit to Polymarket
3. Start real trading

NO WAITING - IMMEDIATE ACTION!
"""

import asyncio
import sys
import logging
from decimal import Decimal
from web3 import Web3
from config.config import load_config
from src.main_orchestrator import MainOrchestrator
from src.auto_bridge_manager import AutoBridgeManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Full autonomous sweep and trade."""
    
    logger.info("=" * 80)
    logger.info("FULL AUTONOMOUS MODE - SWEEP + DEPOSIT + TRADE")
    logger.info("=" * 80)
    logger.info("")
    logger.info("This will:")
    logger.info("  1. Sweep ALL USDC from Ethereum to Polygon")
    logger.info("  2. Wait for bridge to complete")
    logger.info("  3. Deposit to Polymarket")
    logger.info("  4. Start real trading")
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
        logger.warning("[LIVE] LIVE TRADING MODE - REAL MONEY!")
        logger.warning("")
    
    # Step 1: Check balances
    logger.info("=" * 80)
    logger.info("STEP 1: CHECK BALANCES")
    logger.info("=" * 80)
    
    try:
        # Check Ethereum balance
        eth_web3 = Web3(Web3.HTTPProvider("https://eth-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64"))
        usdc_address = Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
        
        # USDC contract
        usdc_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            }
        ]
        usdc_contract = eth_web3.eth.contract(address=usdc_address, abi=usdc_abi)
        
        eth_usdc_balance_wei = usdc_contract.functions.balanceOf(config.wallet_address).call()
        eth_usdc_balance = Decimal(eth_usdc_balance_wei) / Decimal(10**6)
        
        eth_balance_wei = eth_web3.eth.get_balance(config.wallet_address)
        eth_balance = Decimal(eth_balance_wei) / Decimal(10**18)
        
        logger.info(f"Ethereum USDC: ${eth_usdc_balance:.2f}")
        logger.info(f"Ethereum ETH: {eth_balance:.6f} ETH")
        
        # Check Polygon balance
        polygon_web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
        polygon_usdc_address = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")
        polygon_usdc_contract = polygon_web3.eth.contract(address=polygon_usdc_address, abi=usdc_abi)
        
        polygon_usdc_balance_wei = polygon_usdc_contract.functions.balanceOf(config.wallet_address).call()
        polygon_usdc_balance = Decimal(polygon_usdc_balance_wei) / Decimal(10**6)
        
        logger.info(f"Polygon USDC: ${polygon_usdc_balance:.2f}")
        logger.info("")
        
        if eth_usdc_balance < Decimal("0.50"):
            logger.error("Not enough USDC on Ethereum to bridge (need at least $0.50)")
            logger.info("Starting bot with existing Polygon balance...")
        else:
            # Step 2: Bridge USDC
            logger.info("=" * 80)
            logger.info("STEP 2: BRIDGE USDC FROM ETHEREUM TO POLYGON")
            logger.info("=" * 80)
            logger.info(f"Bridging ${eth_usdc_balance:.2f} USDC...")
            logger.info("")
            
            bridge_manager = AutoBridgeManager(
                private_key=config.private_key,
                polygon_rpc=config.polygon_rpc_url,
                dry_run=config.dry_run
            )
            
            # Do full sweep - bridge ALL USDC
            success = await bridge_manager.bridge_if_needed(
                force_bridge=True,  # Force bridge even if we have some on Polygon
                min_bridge_amount=eth_usdc_balance  # Bridge everything
            )
            
            if success:
                logger.info("[OK] Bridge transaction sent!")
                logger.info("")
                logger.info("Waiting for bridge to complete (5-30 minutes)...")
                logger.info("Checking every 30 seconds...")
                logger.info("")
                
                # Wait for bridge with timeout
                import time
                max_wait = 30 * 60  # 30 minutes
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    # Check Polygon balance
                    new_balance_wei = polygon_usdc_contract.functions.balanceOf(config.wallet_address).call()
                    new_balance = Decimal(new_balance_wei) / Decimal(10**6)
                    
                    if new_balance > polygon_usdc_balance + Decimal("0.10"):
                        logger.info(f"[OK] Bridge complete! New Polygon balance: ${new_balance:.2f}")
                        polygon_usdc_balance = new_balance
                        break
                    
                    elapsed = int(time.time() - start_time)
                    logger.info(f"Still waiting... ({elapsed}s elapsed, balance: ${new_balance:.2f})")
                    await asyncio.sleep(30)
                else:
                    logger.warning("Bridge taking longer than expected, but continuing anyway...")
            else:
                logger.error("Bridge failed, but continuing with existing balance...")
        
    except Exception as e:
        logger.error(f"Error checking balances: {e}")
        logger.info("Continuing anyway...")
    
    # Step 3: Start trading bot
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 3: START TRADING BOT")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        orchestrator = MainOrchestrator(config)
        orchestrator.setup_signal_handlers()
        
        logger.info("[OK] Bot initialized")
        logger.info("Starting autonomous trading...")
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
