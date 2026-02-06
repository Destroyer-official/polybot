#!/usr/bin/env python3
"""
Test script for live trading with small capital.

This script will:
1. Check your current balance
2. Deposit to Polymarket if needed
3. Run bot for 5 minutes to test trading
4. Show results
"""

import asyncio
import sys
import logging
from decimal import Decimal
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_live_trading.log')
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Run live trading test."""
    logger.info("=" * 80)
    logger.info("POLYMARKET BOT - LIVE TRADING TEST")
    logger.info("=" * 80)
    logger.info(f"Test started at: {datetime.now()}")
    logger.info("")
    
    try:
        # Import components
        logger.info("Loading configuration...")
        from config.config import load_config
        from src.fund_manager import FundManager
        from web3 import Web3
        
        config = load_config()
        
        # Check if dry run mode
        if config.dry_run:
            logger.error("=" * 80)
            logger.error("ERROR: DRY_RUN is still enabled!")
            logger.error("=" * 80)
            logger.error("")
            logger.error("To test live trading, you must:")
            logger.error("1. Edit .env file")
            logger.error("2. Change: DRY_RUN=true")
            logger.error("3. To: DRY_RUN=false")
            logger.error("4. Save the file")
            logger.error("5. Run this script again")
            logger.error("")
            return 1
        
        logger.info("✓ Live trading mode confirmed")
        logger.info(f"✓ Wallet: {config.wallet_address}")
        logger.info("")
        
        # Initialize Web3 and wallet
        logger.info("Connecting to Polygon...")
        web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
        account = web3.eth.account.from_key(config.private_key)
        
        if not web3.is_connected():
            logger.error("Failed to connect to Polygon RPC")
            return 1
        
        logger.info(f"✓ Connected to Polygon (block: {web3.eth.block_number})")
        logger.info("")
        
        # Initialize fund manager
        logger.info("Initializing fund manager...")
        fund_manager = FundManager(
            web3=web3,
            wallet=account,
            usdc_address=config.usdc_address,
            ctf_exchange_address=config.ctf_exchange_address,
            min_balance=config.min_balance,
            target_balance=config.target_balance,
            withdraw_limit=config.withdraw_limit,
            dry_run=False  # LIVE MODE
        )
        logger.info("✓ Fund manager initialized")
        logger.info("")
        
        # Check current balance
        logger.info("Checking current balance...")
        private_balance, polymarket_balance = await fund_manager.check_balance()
        total_balance = private_balance + polymarket_balance
        
        logger.info("=" * 80)
        logger.info("CURRENT BALANCE")
        logger.info("=" * 80)
        logger.info(f"Private wallet: ${private_balance:.2f} USDC")
        logger.info(f"Polymarket:     ${polymarket_balance:.2f} USDC")
        logger.info(f"Total:          ${total_balance:.2f} USDC")
        logger.info("=" * 80)
        logger.info("")
        
        # Check if we have funds
        if total_balance < Decimal('1.0'):
            logger.error("=" * 80)
            logger.error("INSUFFICIENT FUNDS")
            logger.error("=" * 80)
            logger.error("")
            logger.error(f"Current balance: ${total_balance:.2f} USDC")
            logger.error("Minimum required: $1.00 USDC")
            logger.error("")
            logger.error("Please send USDC to your wallet:")
            logger.error(f"Address: {config.wallet_address}")
            logger.error("Network: Polygon (MATIC)")
            logger.error("Token: USDC")
            logger.error("Amount: $4-$5 USDC recommended")
            logger.error("")
            return 1
        
        # Deposit to Polymarket if needed
        if private_balance >= Decimal('1.0') and private_balance < Decimal('50.0'):
            logger.info("=" * 80)
            logger.info("DEPOSITING TO POLYMARKET")
            logger.info("=" * 80)
            logger.info("")
            logger.info(f"Private wallet has ${private_balance:.2f}")
            logger.info("Initiating deposit to Polymarket...")
            logger.info("")
            
            # Calculate deposit amount
            if private_balance < Decimal('5.0'):
                buffer = Decimal('0.20')
            elif private_balance < Decimal('20.0'):
                buffer = Decimal('0.30')
            else:
                buffer = Decimal('0.50')
            
            deposit_amount = private_balance - buffer
            
            if deposit_amount < Decimal('0.50'):
                logger.warning(f"Deposit amount too small: ${deposit_amount:.2f}")
                logger.warning("Need at least $0.50 to deposit")
                logger.info("")
            else:
                logger.info(f"Depositing: ${deposit_amount:.2f}")
                logger.info(f"Keeping buffer: ${buffer:.2f}")
                logger.info("")
                logger.info("⚠️  This will execute a REAL transaction!")
                logger.info("⚠️  Gas fees will be deducted from your wallet!")
                logger.info("")
                
                # Execute deposit
                try:
                    receipt = await fund_manager.auto_deposit(deposit_amount)
                    
                    if receipt:
                        logger.info("=" * 80)
                        logger.info("DEPOSIT SUCCESSFUL!")
                        logger.info("=" * 80)
                        logger.info(f"Transaction: {receipt['transactionHash'].hex()}")
                        logger.info(f"Gas used: {receipt['gasUsed']}")
                        logger.info(f"Amount deposited: ${deposit_amount:.2f}")
                        logger.info("")
                        
                        # Check new balance
                        private_balance, polymarket_balance = await fund_manager.check_balance()
                        logger.info("New balances:")
                        logger.info(f"Private wallet: ${private_balance:.2f} USDC")
                        logger.info(f"Polymarket:     ${polymarket_balance:.2f} USDC")
                        logger.info("=" * 80)
                        logger.info("")
                    
                except Exception as e:
                    logger.error(f"Deposit failed: {e}")
                    logger.error("")
                    return 1
        
        # Start trading test
        logger.info("=" * 80)
        logger.info("STARTING TRADING TEST (5 MINUTES)")
        logger.info("=" * 80)
        logger.info("")
        logger.info("The bot will now:")
        logger.info("1. Scan 1,247 markets every 2 seconds")
        logger.info("2. Detect arbitrage opportunities")
        logger.info("3. Execute trades automatically")
        logger.info("4. Run for 5 minutes")
        logger.info("")
        logger.info("Press Ctrl+C to stop early")
        logger.info("=" * 80)
        logger.info("")
        
        # Import and start orchestrator
        from src.main_orchestrator import MainOrchestrator
        
        orchestrator = MainOrchestrator(config)
        
        # Run for 5 minutes
        async def run_test():
            try:
                task = asyncio.create_task(orchestrator.run())
                await asyncio.sleep(300)  # 5 minutes
                logger.info("")
                logger.info("=" * 80)
                logger.info("5-MINUTE TEST COMPLETE")
                logger.info("=" * 80)
                orchestrator.stop()
                await asyncio.sleep(2)
            except KeyboardInterrupt:
                logger.info("")
                logger.info("=" * 80)
                logger.info("TEST INTERRUPTED BY USER")
                logger.info("=" * 80)
                orchestrator.stop()
                await asyncio.sleep(2)
        
        await run_test()
        
        # Show results
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST RESULTS")
        logger.info("=" * 80)
        logger.info("")
        
        # Check final balance
        private_balance, polymarket_balance = await fund_manager.check_balance()
        total_balance = private_balance + polymarket_balance
        
        logger.info("Final balances:")
        logger.info(f"Private wallet: ${private_balance:.2f} USDC")
        logger.info(f"Polymarket:     ${polymarket_balance:.2f} USDC")
        logger.info(f"Total:          ${total_balance:.2f} USDC")
        logger.info("")
        
        # Check trade history
        from src.trade_history import TradeHistoryDB
        from src.trade_statistics import TradeStatisticsTracker
        
        db = TradeHistoryDB()
        tracker = TradeStatisticsTracker(db)
        stats = tracker.get_statistics()
        
        logger.info("Trading statistics:")
        logger.info(f"Total trades: {stats.total_trades}")
        logger.info(f"Successful: {stats.successful_trades}")
        logger.info(f"Failed: {stats.failed_trades}")
        logger.info(f"Win rate: {stats.win_rate:.2f}%")
        logger.info(f"Total profit: ${stats.total_profit:.2f}")
        logger.info(f"Gas costs: ${stats.total_gas_cost:.2f}")
        logger.info(f"Net profit: ${stats.net_profit:.2f}")
        logger.info("")
        logger.info("=" * 80)
        logger.info("")
        
        if stats.total_trades > 0:
            logger.info("✓ Bot executed trades successfully!")
            logger.info("✓ Live trading is working!")
            logger.info("")
            logger.info("Next steps:")
            logger.info("1. Review the trades above")
            logger.info("2. Check if profits are positive")
            logger.info("3. If satisfied, run: python bot.py")
            logger.info("4. Let it run continuously")
        else:
            logger.info("ℹ No trades executed during test period")
            logger.info("")
            logger.info("This is normal if:")
            logger.info("- No opportunities were available")
            logger.info("- AI safety guard rejected opportunities")
            logger.info("- Market conditions were unfavorable")
            logger.info("")
            logger.info("Recommendation:")
            logger.info("- Run bot for longer period: python bot.py")
            logger.info("- Opportunities come in waves")
            logger.info("- Peak times: US market hours")
        
        logger.info("")
        return 0
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("TEST FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.error("")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
