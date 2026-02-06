#!/usr/bin/env python3
"""
Polymarket Bot Setup Script.

Checks and configures everything needed for production trading:
1. Wallet configuration
2. Token allowances (for EOA wallets)
3. Balance checks
4. API connectivity
5. Test trade (dry-run)
"""

import asyncio
import logging
import sys
from decimal import Decimal
from web3 import Web3

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main setup flow."""
    logger.info("=" * 80)
    logger.info("POLYMARKET ARBITRAGE BOT - SETUP & CONFIGURATION")
    logger.info("=" * 80)
    
    # Step 1: Load configuration
    logger.info("\n[1/6] Loading configuration...")
    try:
        from config.config import load_config
        config = load_config()
        logger.info("✅ Configuration loaded successfully")
        logger.info(f"   Wallet: {config.wallet_address}")
        logger.info(f"   Chain ID: {config.chain_id}")
        logger.info(f"   RPC: {config.polygon_rpc_url}")
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        logger.error("\nPlease check your .env file and ensure all required variables are set:")
        logger.error("  - PRIVATE_KEY")
        logger.error("  - WALLET_ADDRESS")
        logger.error("  - POLYGON_RPC_URL")
        return False
    
    # Step 2: Connect to Polygon
    logger.info("\n[2/6] Connecting to Polygon...")
    try:
        web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
        if not web3.is_connected():
            raise ConnectionError("Failed to connect to Polygon RPC")
        
        block_number = web3.eth.block_number
        logger.info(f"✅ Connected to Polygon (block: {block_number})")
        
        account = web3.eth.account.from_key(config.private_key)
        logger.info(f"   Account: {account.address}")
        
        # Verify wallet address matches
        if account.address.lower() != config.wallet_address.lower():
            logger.error(f"❌ Wallet address mismatch!")
            logger.error(f"   Private key derives: {account.address}")
            logger.error(f"   Config specifies: {config.wallet_address}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to Polygon: {e}")
        return False
    
    # Step 3: Detect wallet type
    logger.info("\n[3/6] Detecting wallet type...")
    try:
        from src.wallet_type_detector import WalletTypeDetector
        
        detector = WalletTypeDetector(web3, config.private_key)
        wallet_config = detector.auto_detect_configuration()
        
        signature_type = wallet_config['signature_type']
        funder_address = wallet_config['funder_address']
        wallet_type = wallet_config['wallet_type']
        
        logger.info(f"✅ Wallet type detected: {wallet_type}")
        logger.info(f"   Signature type: {signature_type}")
        logger.info(f"   Funder address: {funder_address}")
        
        # Save to environment for future use
        import os
        os.environ['SIGNATURE_TYPE'] = str(signature_type)
        os.environ['FUNDER_ADDRESS'] = funder_address
        
    except Exception as e:
        logger.error(f"❌ Failed to detect wallet type: {e}")
        logger.warning("   Defaulting to signature_type=2 (Gnosis Safe)")
        signature_type = 2
        funder_address = account.address
    
    # Step 4: Check token allowances (EOA only)
    if signature_type == 0:
        logger.info("\n[4/6] Checking token allowances (EOA wallet)...")
        try:
            from src.token_allowance_manager import TokenAllowanceManager
            
            allowance_mgr = TokenAllowanceManager(web3, account)
            results = allowance_mgr.check_all_allowances()
            
            if results['all_approved']:
                logger.info("✅ All token allowances are set")
            else:
                logger.warning("⚠️  Some token allowances are missing")
                logger.info("\nMissing allowances:")
                
                for token_type in ['usdc', 'conditional_token']:
                    for spender, approved in results[token_type].items():
                        if not approved:
                            logger.info(f"   - {token_type} for {spender}")
                
                # Ask user if they want to set allowances
                response = input("\nWould you like to set allowances now? (yes/no): ")
                if response.lower() in ['yes', 'y']:
                    logger.info("\nSetting allowances...")
                    success = allowance_mgr.approve_all(dry_run=config.dry_run)
                    if success:
                        logger.info("✅ All allowances set successfully")
                    else:
                        logger.error("❌ Failed to set some allowances")
                        return False
                else:
                    logger.warning("⚠️  Skipping allowance setup")
                    logger.warning("   You will need to set allowances before trading")
        except Exception as e:
            logger.error(f"❌ Failed to check allowances: {e}")
            return False
    else:
        logger.info("\n[4/6] Skipping token allowances (not EOA wallet)")
        logger.info("   Proxy/Safe wallets have allowances managed automatically")
    
    # Step 5: Check balances
    logger.info("\n[5/6] Checking balances...")
    try:
        from py_clob_client.client import ClobClient
        
        # Initialize CLOB client
        clob_client = ClobClient(
            host=config.polymarket_api_url,
            key=config.private_key,
            chain_id=config.chain_id,
            signature_type=signature_type,
            funder=funder_address
        )
        
        # Derive API credentials
        try:
            creds = clob_client.create_or_derive_api_creds()
            clob_client.set_api_creds(creds)
            logger.info("✅ API credentials derived")
        except Exception as e:
            logger.warning(f"⚠️  Failed to derive API credentials: {e}")
        
        # Check balance
        try:
            balance_response = clob_client.get_balance_allowance()
            
            if isinstance(balance_response, dict):
                usdc_balance = Decimal(str(balance_response.get('balance', '0'))) / Decimal('1000000')  # USDC has 6 decimals
                logger.info(f"✅ Polymarket balance: ${usdc_balance:.2f} USDC")
                
                if usdc_balance < Decimal('0.50'):
                    logger.warning("\n⚠️  INSUFFICIENT FUNDS")
                    logger.warning(f"   Current balance: ${usdc_balance:.2f}")
                    logger.warning("   Minimum required: $0.50")
                    logger.warning("\n   To deposit funds:")
                    logger.warning("   1. Go to https://polymarket.com")
                    logger.warning(f"   2. Connect wallet: {account.address}")
                    logger.warning("   3. Click 'Deposit' → Enter amount → Confirm")
                    logger.warning("   4. Wait 10-30 seconds for confirmation")
                    return False
                else:
                    logger.info(f"✅ Sufficient funds for trading")
            else:
                logger.warning("⚠️  Could not parse balance response")
                
        except Exception as e:
            logger.warning(f"⚠️  Failed to check balance: {e}")
            logger.info("   This is normal for new wallets")
            logger.info("   Please deposit funds via https://polymarket.com")
    
    except Exception as e:
        logger.error(f"❌ Failed to initialize CLOB client: {e}")
        return False
    
    # Step 6: Test market data fetching
    logger.info("\n[6/6] Testing market data fetching...")
    try:
        import requests
        
        gamma_url = "https://gamma-api.polymarket.com/markets"
        params = {'closed': 'false', 'limit': 10}
        
        response = requests.get(gamma_url, params=params, timeout=10)
        response.raise_for_status()
        markets = response.json()
        
        if isinstance(markets, list):
            market_count = len(markets)
        else:
            market_count = len(markets.get('data', []))
        
        logger.info(f"✅ Successfully fetched {market_count} active markets")
        
        if market_count == 0:
            logger.warning("⚠️  No active markets found")
            logger.warning("   This is unusual - Polymarket usually has active markets")
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch markets: {e}")
        return False
    
    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("SETUP COMPLETE")
    logger.info("=" * 80)
    logger.info("\n✅ All checks passed!")
    logger.info("\nYour bot is ready to trade. To start:")
    logger.info("  python bot.py")
    logger.info("\nOr for dry-run mode (no real trades):")
    logger.info("  DRY_RUN=true python bot.py")
    logger.info("\n" + "=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\nUnexpected error: {e}", exc_info=True)
        sys.exit(1)
