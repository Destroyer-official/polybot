#!/usr/bin/env python3
"""
Integration test to verify all components work together.
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all critical imports work."""
    logger.info("Testing imports...")
    
    try:
        from config.config import load_config
        logger.info("✅ config.config imported")
    except Exception as e:
        logger.error(f"❌ Failed to import config.config: {e}")
        return False
    
    try:
        from src.wallet_type_detector import WalletTypeDetector
        logger.info("✅ WalletTypeDetector imported")
    except Exception as e:
        logger.error(f"❌ Failed to import WalletTypeDetector: {e}")
        return False
    
    try:
        from src.token_allowance_manager import TokenAllowanceManager
        logger.info("✅ TokenAllowanceManager imported")
    except Exception as e:
        logger.error(f"❌ Failed to import TokenAllowanceManager: {e}")
        return False
    
    try:
        from src.main_orchestrator import MainOrchestrator
        logger.info("✅ MainOrchestrator imported")
    except Exception as e:
        logger.error(f"❌ Failed to import MainOrchestrator: {e}")
        return False
    
    return True


def test_config_loading():
    """Test configuration loading."""
    logger.info("\nTesting configuration loading...")
    
    try:
        from config.config import load_config
        config = load_config()
        
        logger.info(f"✅ Configuration loaded")
        logger.info(f"   Wallet: {config.wallet_address}")
        logger.info(f"   Chain ID: {config.chain_id}")
        logger.info(f"   DRY RUN: {config.dry_run}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("=" * 80)
    logger.info("INTEGRATION TEST - POLYMARKET ARBITRAGE BOT")
    logger.info("=" * 80)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test config loading
    if not test_config_loading():
        all_passed = False
    
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 80)
        logger.info("\nYour bot is ready! To start:")
        logger.info("  1. Run setup: python setup_bot.py")
        logger.info("  2. Start bot: python bot.py")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED")
        logger.error("=" * 80)
        logger.error("\nPlease fix the errors above before running the bot.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
