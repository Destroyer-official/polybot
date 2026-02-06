#!/usr/bin/env python3
"""
REAL TRADING TEST - $4 DEPOSIT
This script will:
1. Check wallet and Polymarket balances
2. Verify all connections (RPC, CLOB API, NVIDIA AI)
3. Run the bot in REAL mode (DRY_RUN=false)
4. Monitor trades and report results
"""

import asyncio
import sys
import time
from decimal import Decimal
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('real_trading_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import bot components
from config.config import Config
from src.main_orchestrator import MainOrchestrator

async def check_prerequisites():
    """Check all prerequisites before starting real trading."""
    logger.info("=" * 80)
    logger.info("REAL TRADING TEST - PRE-FLIGHT CHECKS")
    logger.info("=" * 80)
    
    # Load config
    config = Config.from_env()
    
    # Check 1: DRY_RUN must be false
    if config.dry_run:
        logger.error("❌ DRY_RUN is still TRUE! Set DRY_RUN=false in .env file")
        return False
    logger.info("✅ DRY_RUN is FALSE - Real trading enabled")
    
    # Check 2: Verify wallet address
    from web3 import Web3
    web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
    account = web3.eth.account.from_key(config.private_key)
    
    if account.address.lower() != config.wallet_address.lower():
        logger.error(f"❌ Wallet mismatch! Private key: {account.address}, Config: {config.wallet_address}")
        return False
    logger.info(f"✅ Wallet verified: {account.address}")
    
    # Check 3: Check balances
    usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
    usdc_contract = web3.eth.contract(address=config.usdc_address, abi=usdc_abi)
    
    wallet_balance_raw = usdc_contract.functions.balanceOf(account.address).call()
    wallet_balance = Decimal(wallet_balance_raw) / Decimal(10**6)
    
    logger.info(f"💰 Private Wallet Balance: ${wallet_balance:.2f} USDC")
    
    if wallet_balance < Decimal("1.0"):
        logger.error(f"❌ Insufficient balance! Need at least $1.00, have ${wallet_balance:.2f}")
        return False
    logger.info("✅ Sufficient balance for trading")
    
    # Check 4: RPC connection
    try:
        block_number = web3.eth.block_number
        logger.info(f"✅ RPC connected - Block: {block_number}")
    except Exception as e:
        logger.error(f"❌ RPC connection failed: {e}")
        return False
    
    # Check 5: Gas price
    try:
        gas_price_wei = web3.eth.gas_price
        gas_price_gwei = gas_price_wei // 10**9
        logger.info(f"⛽ Current gas price: {gas_price_gwei} gwei")
        
        if gas_price_gwei > config.max_gas_price_gwei:
            logger.warning(f"⚠️  Gas price high ({gas_price_gwei} gwei > {config.max_gas_price_gwei} gwei)")
            logger.warning("Bot will wait for gas to normalize before trading")
    except Exception as e:
        logger.error(f"❌ Gas price check failed: {e}")
        return False
    
    # Check 6: CLOB API
    try:
        from py_clob_client.client import ClobClient
        clob_client = ClobClient(
            host=config.polymarket_api_url,
            key=config.private_key,
            chain_id=config.chain_id
        )
        
        # Try to derive credentials
        creds = clob_client.create_or_derive_api_creds()
        clob_client.set_api_creds(creds)
        
        # Test API call
        markets = clob_client.get_markets()
        market_count = len(markets.get('data', []) if isinstance(markets, dict) else markets)
        logger.info(f"✅ CLOB API connected - {market_count} markets available")
    except Exception as e:
        logger.error(f"❌ CLOB API connection failed: {e}")
        return False
    
    # Check 7: NVIDIA AI (optional)
    if config.nvidia_api_key:
        try:
            from openai import OpenAI
            ai_client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=config.nvidia_api_key
            )
            
            # Test API call
            response = ai_client.chat.completions.create(
                model="deepseek-ai/deepseek-v3.2",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            logger.info("✅ NVIDIA AI connected")
        except Exception as e:
            logger.warning(f"⚠️  NVIDIA AI not available: {e}")
            logger.warning("Bot will continue without AI safety guard")
    else:
        logger.warning("⚠️  NVIDIA API key not set - AI safety guard disabled")
    
    logger.info("=" * 80)
    logger.info("✅ ALL PRE-FLIGHT CHECKS PASSED")
    logger.info("=" * 80)
    
    return True

async def run_real_trading_test():
    """Run the bot in real trading mode."""
    
    # Pre-flight checks
    if not await check_prerequisites():
        logger.error("Pre-flight checks failed. Aborting.")
        return
    
    # Confirm with user
    logger.info("")
    logger.info("⚠️  WARNING: REAL TRADING MODE ⚠️")
    logger.info("This will execute REAL trades with REAL money on Polymarket")
    logger.info("Starting in 10 seconds... Press Ctrl+C to cancel")
    logger.info("")
    
    try:
        for i in range(10, 0, -1):
            logger.info(f"Starting in {i}...")
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Cancelled by user")
        return
    
    # Load config and start bot
    logger.info("")
    logger.info("=" * 80)
    logger.info("STARTING REAL TRADING BOT")
    logger.info("=" * 80)
    
    config = Config.from_env()
    orchestrator = MainOrchestrator(config)
    
    # Run bot
    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await orchestrator.shutdown()

if __name__ == "__main__":
    asyncio.run(run_real_trading_test())
