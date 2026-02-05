"""
Main Orchestrator for Polymarket Arbitrage Bot.

Coordinates all system components, manages the main event loop, and handles lifecycle management.
Implements Requirements 9.1, 9.6, 6.6, 9.3.
"""

import asyncio
import signal
import time
import json
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pathlib import Path
import logging

from web3 import Web3
from py_clob_client.client import ClobClient

from config.config import Config
from src.models import HealthStatus, Opportunity, TradeResult
from src.internal_arbitrage_engine import InternalArbitrageEngine
from src.cross_platform_arbitrage_engine import CrossPlatformArbitrageEngine
from src.latency_arbitrage_engine import LatencyArbitrageEngine
from src.resolution_farming_engine import ResolutionFarmingEngine
from src.order_manager import OrderManager
from src.position_merger import PositionMerger
from src.transaction_manager import TransactionManager
from src.ai_safety_guard import AISafetyGuard
from src.fund_manager import FundManager
from src.monitoring_system import MonitoringSystem
from src.status_dashboard import StatusDashboard
from src.market_parser import MarketParser
from src.trade_history import TradeHistoryDB
from src.trade_statistics import TradeStatistics
from src.error_recovery import CircuitBreaker

logger = logging.getLogger(__name__)


class MainOrchestrator:
    """
    Main orchestrator that coordinates all system components.
    
    Responsibilities:
    - Initialize all components with configuration
    - Run main event loop scanning markets every 1-5 seconds
    - Perform heartbeat checks every 60 seconds
    - Handle graceful shutdown on SIGTERM/SIGINT
    - Coordinate strategy engines, safety checks, fund management
    - Monitor gas prices and halt trading when necessary
    - Persist state to disk and restore on restart
    
    Validates Requirements:
    - 9.1: 24/7 autonomous operation with systemd service
    - 9.6: Heartbeat check every 60 seconds
    - 6.6: Gas price monitoring and trading halt
    - 9.3: State persistence across restarts
    """
    
    def __init__(self, config: Config):
        """
        Initialize all components with configuration.
        
        Args:
            config: Validated system configuration
        """
        self.config = config
        self.running = False
        self.shutdown_requested = False
        
        # State file path
        self.state_file = Path("state.json")
        
        # Initialize Web3
        logger.info(f"Connecting to Polygon RPC: {config.polygon_rpc_url}")
        self.web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
        self.account = self.web3.eth.account.from_key(config.private_key)
        
        # Verify wallet address matches (Requirement 14.4)
        from src.wallet_verifier import WalletVerifier
        if not WalletVerifier.verify_wallet_address(config.private_key, config.wallet_address):
            raise ValueError(
                f"SECURITY ERROR: Private key does not match wallet address. "
                f"Expected: {config.wallet_address}, Got: {self.account.address}"
            )
        
        logger.info(f"✓ Wallet address verified: {self.account.address}")
        
        # Initialize CLOB client
        logger.info("Initializing Polymarket CLOB client...")
        self.clob_client = ClobClient(
            host=config.polymarket_api_url,
            key=config.private_key,
            chain_id=config.chain_id
        )
        
        # Derive API credentials
        try:
            creds = self.clob_client.create_or_derive_api_creds()
            self.clob_client.set_api_creds(creds)
            logger.info("API credentials derived successfully")
        except Exception as e:
            logger.warning(f"Failed to derive API credentials: {e}")
        
        # Initialize core components
        logger.info("Initializing core components...")
        
        self.transaction_manager = TransactionManager(self.web3, self.account)
        self.position_merger = PositionMerger(
            self.web3,
            config.conditional_token_address
        )
        self.order_manager = OrderManager(
            self.clob_client,
            self.transaction_manager
        )
        
        # Initialize safety and risk management
        self.ai_safety_guard = AISafetyGuard(
            nvidia_api_key=config.nvidia_api_key,
            max_volatility=Decimal("0.05"),  # 5%
            timeout_seconds=2.0
        )
        
        self.circuit_breaker = CircuitBreaker(
            threshold=config.circuit_breaker_threshold
        )
        
        # Initialize fund manager
        self.fund_manager = FundManager(
            web3=self.web3,
            clob_client=self.clob_client,
            account=self.account,
            usdc_address=config.usdc_address,
            ctf_exchange_address=config.ctf_exchange_address,
            min_balance=config.min_balance,
            target_balance=config.target_balance,
            withdraw_limit=config.withdraw_limit
        )
        
        # Initialize strategy engines
        logger.info("Initializing strategy engines...")
        
        self.internal_arbitrage = InternalArbitrageEngine(
            clob_client=self.clob_client,
            order_manager=self.order_manager,
            position_merger=self.position_merger,
            ai_safety_guard=self.ai_safety_guard,
            min_profit_threshold=config.min_profit_threshold
        )
        
        # Cross-platform arbitrage (if Kalshi API key provided)
        self.cross_platform_arbitrage = None
        if config.kalshi_api_key:
            self.cross_platform_arbitrage = CrossPlatformArbitrageEngine(
                polymarket_client=self.clob_client,
                kalshi_api_key=config.kalshi_api_key,
                order_manager=self.order_manager,
                ai_safety_guard=self.ai_safety_guard
            )
            logger.info("Cross-platform arbitrage enabled")
        
        # Latency arbitrage
        self.latency_arbitrage = LatencyArbitrageEngine(
            clob_client=self.clob_client,
            order_manager=self.order_manager,
            ai_safety_guard=self.ai_safety_guard
        )
        
        # Resolution farming
        self.resolution_farming = ResolutionFarmingEngine(
            clob_client=self.clob_client,
            order_manager=self.order_manager,
            ai_safety_guard=self.ai_safety_guard,
            max_position_pct=Decimal("0.02")  # 2% of bankroll
        )
        
        # Initialize monitoring and reporting
        logger.info("Initializing monitoring system...")
        
        self.monitoring = MonitoringSystem(
            prometheus_port=config.prometheus_port,
            cloudwatch_log_group=config.cloudwatch_log_group,
            sns_topic_arn=config.sns_alert_topic
        )
        
        self.trade_history = TradeHistoryDB()
        self.trade_statistics = TradeStatistics()
        
        # Initialize status dashboard
        self.dashboard = StatusDashboard(
            monitoring=self.monitoring,
            trade_statistics=self.trade_statistics
        )
        
        # Initialize market parser
        self.market_parser = MarketParser()
        
        # Timing trackers
        self.last_heartbeat = time.time()
        self.last_fund_check = time.time()
        self.last_state_save = time.time()
        self.scan_count = 0
        
        # Gas price monitoring
        self.gas_price_halted = False
        
        # Load persisted state
        self._load_state()
        
        logger.info("MainOrchestrator initialized successfully")
    
    def _load_state(self) -> None:
        """
        Load persisted state from disk.
        
        Validates Requirement 9.3: State persistence across restarts
        """
        if not self.state_file.exists():
            logger.info("No persisted state found, starting fresh")
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # Restore trade statistics
            if 'trade_statistics' in state:
                stats = state['trade_statistics']
                self.trade_statistics.total_trades = stats.get('total_trades', 0)
                self.trade_statistics.successful_trades = stats.get('successful_trades', 0)
                self.trade_statistics.failed_trades = stats.get('failed_trades', 0)
                self.trade_statistics.total_profit = Decimal(str(stats.get('total_profit', '0')))
                self.trade_statistics.total_gas_cost = Decimal(str(stats.get('total_gas_cost', '0')))
            
            # Restore circuit breaker state
            if 'circuit_breaker' in state:
                cb = state['circuit_breaker']
                self.circuit_breaker.consecutive_failures = cb.get('consecutive_failures', 0)
                self.circuit_breaker.is_open = cb.get('is_open', False)
            
            logger.info(f"State restored from {self.state_file}")
            logger.info(f"Total trades: {self.trade_statistics.total_trades}")
            logger.info(f"Circuit breaker: {'OPEN' if self.circuit_breaker.is_open else 'CLOSED'}")
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            logger.info("Starting with fresh state")
    
    def _save_state(self) -> None:
        """
        Save current state to disk.
        
        Validates Requirement 9.3: State persistence across restarts
        """
        try:
            state = {
                'timestamp': datetime.now().isoformat(),
                'trade_statistics': {
                    'total_trades': self.trade_statistics.total_trades,
                    'successful_trades': self.trade_statistics.successful_trades,
                    'failed_trades': self.trade_statistics.failed_trades,
                    'total_profit': str(self.trade_statistics.total_profit),
                    'total_gas_cost': str(self.trade_statistics.total_gas_cost),
                },
                'circuit_breaker': {
                    'consecutive_failures': self.circuit_breaker.consecutive_failures,
                    'is_open': self.circuit_breaker.is_open,
                }
            }
            
            # Write atomically
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            temp_file.replace(self.state_file)
            
            logger.debug(f"State saved to {self.state_file}")
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    async def heartbeat_check(self) -> HealthStatus:
        """
        Perform comprehensive health check.
        
        Validates Requirement 9.6: Heartbeat check every 60 seconds
        
        Checks:
        - Balance > $10
        - Gas < 800 gwei
        - Pending TX < 5
        - API connectivity
        - RPC latency
        
        Returns:
            HealthStatus: Current system health status
        """
        logger.debug("Performing heartbeat check...")
        
        issues = []
        
        # Check balances
        try:
            eoa_balance, proxy_balance = await self.fund_manager.check_balance()
            total_balance = eoa_balance + proxy_balance
            balance_ok = total_balance >= Decimal("10.0")
            
            if not balance_ok:
                issues.append(f"Low balance: ${total_balance:.2f} (min: $10.00)")
        except Exception as e:
            logger.error(f"Failed to check balance: {e}")
            eoa_balance = proxy_balance = total_balance = Decimal("0")
            balance_ok = False
            issues.append(f"Balance check failed: {e}")
        
        # Check gas price
        try:
            gas_price_wei = self.web3.eth.gas_price
            gas_price_gwei = gas_price_wei // 10**9
            gas_ok = gas_price_gwei <= self.config.max_gas_price_gwei
            
            if not gas_ok:
                issues.append(f"High gas price: {gas_price_gwei} gwei (max: {self.config.max_gas_price_gwei})")
        except Exception as e:
            logger.error(f"Failed to check gas price: {e}")
            gas_price_gwei = 0
            gas_ok = False
            issues.append(f"Gas price check failed: {e}")
        
        # Check pending transactions
        try:
            pending_tx_count = self.transaction_manager.get_pending_count()
            pending_tx_ok = pending_tx_count < self.config.max_pending_tx
            
            if not pending_tx_ok:
                issues.append(f"Too many pending TXs: {pending_tx_count} (max: {self.config.max_pending_tx})")
        except Exception as e:
            logger.error(f"Failed to check pending TXs: {e}")
            pending_tx_count = 0
            pending_tx_ok = False
            issues.append(f"Pending TX check failed: {e}")
        
        # Check API connectivity and RPC latency
        try:
            start_time = time.time()
            block_number = self.web3.eth.block_number
            rpc_latency_ms = (time.time() - start_time) * 1000
            api_connectivity_ok = True
        except Exception as e:
            logger.error(f"Failed to check RPC connectivity: {e}")
            block_number = 0
            rpc_latency_ms = 0
            api_connectivity_ok = False
            issues.append(f"RPC connectivity failed: {e}")
        
        # Get performance metrics
        stats = self.trade_statistics.get_summary()
        
        # Check circuit breaker
        circuit_breaker_open = self.circuit_breaker.is_open
        if circuit_breaker_open:
            issues.append("Circuit breaker is OPEN - trading halted")
        
        # Overall health
        is_healthy = (
            balance_ok and
            gas_ok and
            pending_tx_ok and
            api_connectivity_ok and
            not circuit_breaker_open
        )
        
        health_status = HealthStatus(
            timestamp=datetime.now(),
            is_healthy=is_healthy,
            eoa_balance=eoa_balance,
            proxy_balance=proxy_balance,
            total_balance=total_balance,
            balance_ok=balance_ok,
            gas_ok=gas_ok,
            gas_price_gwei=gas_price_gwei,
            pending_tx_ok=pending_tx_ok,
            pending_tx_count=pending_tx_count,
            api_connectivity_ok=api_connectivity_ok,
            rpc_latency_ms=rpc_latency_ms,
            block_number=block_number,
            total_trades=stats['total_trades'],
            win_rate=stats['win_rate'],
            total_profit=stats['total_profit'],
            avg_profit_per_trade=stats['avg_profit_per_trade'],
            total_gas_cost=stats['total_gas_cost'],
            net_profit=stats['net_profit'],
            circuit_breaker_open=circuit_breaker_open,
            consecutive_failures=self.circuit_breaker.consecutive_failures,
            ai_safety_active=self.ai_safety_guard is not None,
            issues=issues
        )
        
        # Log heartbeat
        self.monitoring.log_heartbeat(health_status)
        
        # Update dashboard
        self.dashboard.update_health_status(health_status)
        
        return health_status
    
    def _check_gas_price(self) -> bool:
        """
        Check if gas price is acceptable for trading.
        
        Validates Requirement 6.6: Halt trading if gas > 800 gwei
        
        Returns:
            bool: True if gas price is acceptable, False if trading should halt
        """
        try:
            gas_price_wei = self.web3.eth.gas_price
            gas_price_gwei = gas_price_wei // 10**9
            
            if gas_price_gwei > self.config.max_gas_price_gwei:
                if not self.gas_price_halted:
                    logger.warning(
                        f"Gas price too high: {gas_price_gwei} gwei "
                        f"(max: {self.config.max_gas_price_gwei}). Halting trading."
                    )
                    self.monitoring.send_alert(
                        "warning",
                        f"Trading halted: Gas price {gas_price_gwei} gwei exceeds limit"
                    )
                    self.gas_price_halted = True
                return False
            else:
                if self.gas_price_halted:
                    logger.info(
                        f"Gas price normalized: {gas_price_gwei} gwei. Resuming trading."
                    )
                    self.monitoring.send_alert(
                        "info",
                        f"Trading resumed: Gas price {gas_price_gwei} gwei"
                    )
                    self.gas_price_halted = False
                return True
                
        except Exception as e:
            logger.error(f"Failed to check gas price: {e}")
            return False
    
    async def _scan_and_execute(self) -> None:
        """
        Scan markets for opportunities and execute trades.
        
        Main trading logic that:
        1. Fetches markets from CLOB API
        2. Parses and filters to 15-min crypto markets
        3. Scans for opportunities across all strategies
        4. Validates safety checks
        5. Executes profitable trades
        """
        try:
            # Fetch markets
            logger.debug("Fetching markets from CLOB API...")
            markets_response = self.clob_client.get_markets()
            raw_markets = markets_response.get('data', [])
            
            # Parse and filter markets
            markets = []
            for raw_market in raw_markets:
                market = self.market_parser.parse_market(raw_market)
                if market and market.is_crypto_15min():
                    markets.append(market)
            
            logger.debug(f"Found {len(markets)} active 15-min crypto markets")
            self.monitoring.record_markets_scanned(len(markets))
            
            # Update dashboard
            self.dashboard.update_scan_info(len(raw_markets), len(markets))
            
            # Scan for opportunities across all strategies
            opportunities = []
            
            # Internal arbitrage
            internal_opps = await self.internal_arbitrage.scan_opportunities(markets)
            opportunities.extend(internal_opps)
            
            # Cross-platform arbitrage (if enabled)
            if self.cross_platform_arbitrage:
                cross_opps = await self.cross_platform_arbitrage.scan_opportunities()
                opportunities.extend(cross_opps)
            
            # Latency arbitrage
            latency_opps = await self.latency_arbitrage.scan_opportunities(markets)
            opportunities.extend(latency_opps)
            
            # Resolution farming
            resolution_opps = await self.resolution_farming.scan_closing_markets(markets)
            opportunities.extend(resolution_opps)
            
            logger.debug(f"Found {len(opportunities)} total opportunities")
            self.monitoring.record_opportunities_found(len(opportunities))
            
            # Update dashboard with opportunities
            self.dashboard.update_opportunities(opportunities)
            
            # Execute opportunities
            for opp in opportunities:
                # Check if we should continue trading
                if self.shutdown_requested:
                    logger.info("Shutdown requested, stopping execution")
                    break
                
                if self.circuit_breaker.is_open:
                    logger.warning("Circuit breaker is open, skipping trade")
                    break
                
                # Execute based on strategy
                try:
                    if opp.strategy == "internal":
                        result = await self.internal_arbitrage.execute(opp)
                    elif opp.strategy == "cross_platform":
                        result = await self.cross_platform_arbitrage.execute(opp)
                    elif opp.strategy == "latency":
                        result = await self.latency_arbitrage.execute(opp)
                    elif opp.strategy == "resolution_farming":
                        result = await self.resolution_farming.execute(opp)
                    else:
                        logger.warning(f"Unknown strategy: {opp.strategy}")
                        continue
                    
                    # Record trade
                    self.trade_history.insert_trade(result)
                    self.trade_statistics.update(result)
                    self.monitoring.record_trade(result)
                    
                    # Update dashboard
                    self.dashboard.add_trade(result)
                    
                    # Update circuit breaker
                    if result.was_successful():
                        self.circuit_breaker.record_success()
                    else:
                        self.circuit_breaker.record_failure()
                    
                except Exception as e:
                    logger.error(f"Failed to execute opportunity: {e}", exc_info=True)
                    self.monitoring.record_error(e, {"opportunity": opp})
                    self.circuit_breaker.record_failure()
            
        except Exception as e:
            logger.error(f"Error in scan_and_execute: {e}", exc_info=True)
            self.monitoring.record_error(e, {"operation": "scan_and_execute"})
    
    async def run(self) -> None:
        """
        Main event loop.
        
        Validates Requirements:
        - 9.1: Continuous operation with market scanning
        - 9.6: Heartbeat checks every 60 seconds
        - 6.6: Gas price monitoring
        - 9.3: Periodic state persistence
        
        Runs continuously until shutdown is requested:
        1. Check gas price
        2. Scan markets and execute trades
        3. Perform heartbeat checks (every 60s)
        4. Check fund management (every 60s)
        5. Save state (every 60s)
        6. Update dashboard
        """
        self.running = True
        logger.info("=" * 80)
        logger.info("POLYMARKET ARBITRAGE BOT STARTED")
        logger.info("=" * 80)
        logger.info(f"Wallet: {self.account.address}")
        logger.info(f"Chain ID: {self.config.chain_id}")
        logger.info(f"DRY RUN: {self.config.dry_run}")
        logger.info(f"Scan interval: {self.config.scan_interval_seconds}s")
        logger.info(f"Min profit threshold: {self.config.min_profit_threshold * 100}%")
        logger.info("=" * 80)
        
        # Start dashboard
        self.dashboard.start()
        
        # Perform initial heartbeat
        await self.heartbeat_check()
        
        try:
            while self.running and not self.shutdown_requested:
                loop_start = time.time()
                
                # Check gas price
                gas_ok = self._check_gas_price()
                
                if gas_ok and not self.circuit_breaker.is_open:
                    # Scan and execute
                    await self._scan_and_execute()
                    self.scan_count += 1
                else:
                    if self.circuit_breaker.is_open:
                        logger.warning("Circuit breaker is open, trading halted")
                    else:
                        logger.debug("Gas price too high, waiting...")
                
                # Heartbeat check (every 60 seconds)
                if time.time() - self.last_heartbeat >= self.config.heartbeat_interval_seconds:
                    health_status = await self.heartbeat_check()
                    self.last_heartbeat = time.time()
                    
                    # Check for critical issues
                    if not health_status.is_healthy:
                        logger.warning(f"System unhealthy: {health_status.issues}")
                
                # Fund management check (every 60 seconds)
                if time.time() - self.last_fund_check >= 60:
                    try:
                        await self.fund_manager.check_and_manage_balance()
                    except Exception as e:
                        logger.error(f"Fund management error: {e}")
                    self.last_fund_check = time.time()
                
                # Save state (every 60 seconds)
                if time.time() - self.last_state_save >= 60:
                    self._save_state()
                    self.last_state_save = time.time()
                
                # Update dashboard
                self.dashboard.render()
                
                # Sleep for remaining interval
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.config.scan_interval_seconds - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.critical(f"Fatal error in main loop: {e}", exc_info=True)
            self.monitoring.send_alert("critical", f"Fatal error: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """
        Graceful shutdown.
        
        Validates Requirement 9.1: Graceful shutdown on SIGTERM/SIGINT
        
        Performs cleanup:
        1. Stop accepting new trades
        2. Wait for pending transactions
        3. Save final state
        4. Close connections
        5. Flush logs
        """
        if not self.running:
            return
        
        logger.info("=" * 80)
        logger.info("SHUTTING DOWN GRACEFULLY")
        logger.info("=" * 80)
        
        self.running = False
        self.shutdown_requested = True
        
        # Stop dashboard
        self.dashboard.stop()
        
        # Wait for pending transactions
        logger.info("Waiting for pending transactions...")
        max_wait = 60  # seconds
        start_wait = time.time()
        while time.time() - start_wait < max_wait:
            pending = self.transaction_manager.get_pending_count()
            if pending == 0:
                break
            logger.info(f"Waiting for {pending} pending transactions...")
            await asyncio.sleep(5)
        
        # Save final state
        logger.info("Saving final state...")
        self._save_state()
        
        # Final heartbeat
        logger.info("Performing final heartbeat...")
        await self.heartbeat_check()
        
        # Close connections
        logger.info("Closing connections...")
        # Web3 connections are stateless, no need to close
        
        # Final statistics
        stats = self.trade_statistics.get_summary()
        logger.info("=" * 80)
        logger.info("FINAL STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total Trades: {stats['total_trades']}")
        logger.info(f"Win Rate: {stats['win_rate']:.2f}%")
        logger.info(f"Total Profit: ${stats['total_profit']:.2f}")
        logger.info(f"Total Gas Cost: ${stats['total_gas_cost']:.2f}")
        logger.info(f"Net Profit: ${stats['net_profit']:.2f}")
        logger.info("=" * 80)
        logger.info("SHUTDOWN COMPLETE")
        logger.info("=" * 80)
    
    def setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful shutdown.
        
        Handles SIGTERM and SIGINT (Ctrl+C).
        """
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("Signal handlers registered")


async def main():
    """Main entry point."""
    # Load configuration
    from config.config import load_config
    config = load_config()
    
    # Create orchestrator
    orchestrator = MainOrchestrator(config)
    
    # Setup signal handlers
    orchestrator.setup_signal_handlers()
    
    # Run
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
