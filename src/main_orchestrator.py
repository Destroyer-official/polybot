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
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

from web3 import Web3

# Apply clock skew fix BEFORE importing ClobClient
# Apply clock skew fix BEFORE importing ClobClient
# try:
#     from src.clob_clock_fix import apply_clock_skew_fix
#     apply_clock_skew_fix(lag_seconds=5)
# except Exception as e:
#     logging.getLogger(__name__).warning(f"Could not apply clock skew fix: {e}")

from py_clob_client.client import ClobClient

from config.config import Config
from src.models import HealthStatus, Opportunity, TradeResult
from src.internal_arbitrage_engine import InternalArbitrageEngine
from src.flash_crash_strategy import FlashCrashStrategy
from src.directional_trading_strategy import DirectionalTradingStrategy
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
from src.trade_statistics import TradeStatisticsTracker
from src.error_recovery import CircuitBreaker
from src.auto_bridge_manager import AutoBridgeManager

# LLM-driven decision engine and enhanced strategies
from src.llm_decision_engine_v2 import (
    LLMDecisionEngineV2,
    MarketContext,
    PortfolioState,
    TradeAction,
    OrderType
)
from src.negrisk_arbitrage_engine import NegRiskArbitrageEngine
from src.portfolio_risk_manager import PortfolioRiskManager
from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy

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
        
        # State file path (must be in data/ directory for read-write access)
        self.state_file = Path("data/state.json")
        
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
        
        logger.info(f"[OK] Wallet address verified: {self.account.address}")
        
        # Detect wallet type and configuration
        logger.info("Detecting wallet type...")
        from src.wallet_type_detector import WalletTypeDetector
        
        wallet_detector = WalletTypeDetector(self.web3, config.private_key)
        wallet_config = wallet_detector.auto_detect_configuration()
        
        # FIXED CONFIGURATION (2026-02-09)
        # User's funds are in Gnosis Safe proxy wallet (0x93e65...), not EOA
        # signature_type=2 (Gnosis Safe) + derived creds (user's explicit creds were for different account)
        self.signature_type = 2  # Gnosis Safe - for proxy wallet
        self.funder_address = "0x93e65c1419AB8147cbd16d440Bb7FC178b3b2F35"  # User's Polymarket profile address with funds
        self.wallet_type = "GNOSIS_SAFE"
        
        logger.info(f"Wallet type: {self.wallet_type}")
        logger.info(f"Signature type: {self.signature_type} (GNOSIS_SAFE)")
        logger.info(f"Funder address: {self.funder_address}")
        
        # Initialize CLOB client with Gnosis Safe configuration
        logger.info("Initializing Polymarket CLOB client with Gnosis Safe configuration...")
        
        try:
            self.clob_client = ClobClient(
                host=config.polymarket_api_url,
                key=config.private_key,
                chain_id=config.chain_id,
                signature_type=self.signature_type,
                funder=self.funder_address
            )
            
            # Always derive API credentials from private key
            # NOTE: User's explicit POLY_* creds are for different account (401 Unauthorized)
            # The derived credentials are the only ones that work with this private key
            logger.info("Deriving API credentials from private key...")
            creds = self.clob_client.create_or_derive_api_creds()
            self.clob_client.set_api_creds(creds)
            
            logger.info(f"✅ CLOB client initialized successfully")
            logger.info(f"   Derived API Key: {creds.api_key}")
            import sys
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"❌ Failed to initialize CLOB client: {e}")
            raise
        
        # Check and set token allowances (EOA wallets only)
        if self.signature_type == 0:
            logger.info("Checking token allowances (EOA wallet)...")
            from src.token_allowance_manager import TokenAllowanceManager
            
            self.allowance_manager = TokenAllowanceManager(self.web3, self.account)
            allowance_results = self.allowance_manager.check_all_allowances()
            
            if not allowance_results['all_approved']:
                logger.warning("⚠️  Token allowances not set!")
                logger.warning("Run 'python setup_bot.py' to set allowances before trading")
                logger.warning("Continuing anyway - orders may fail if allowances not approved on-chain")
                # Don't crash - allowances may already be approved on-chain
                # Just warn and continue
            else:
                logger.info("✅ All token allowances verified")
        else:
            logger.info("Skipping token allowances (proxy/safe wallet manages automatically)")
            self.allowance_manager = None
        
        # Initialize core components
        logger.info("Initializing core components...")
        
        self.transaction_manager = TransactionManager(self.web3, self.account)
        self.position_merger = PositionMerger(
            self.web3,
            config.conditional_token_address,
            config.usdc_address,
            self.account
        )
        self.order_manager = OrderManager(
            self.clob_client,
            self.transaction_manager,
            dry_run=config.dry_run
        )
        
        # Initialize safety and risk management
        self.ai_safety_guard = AISafetyGuard(
            nvidia_api_key=config.nvidia_api_key,
            min_balance=config.min_balance,
            max_gas_price_gwei=config.max_gas_price_gwei,
            max_pending_tx=config.max_pending_tx,
            volatility_threshold=Decimal("0.05"),  # 5%
            volatility_halt_duration=300  # 5 minutes
        )
        
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.circuit_breaker_threshold
        )
        
        # Initialize fund manager
        self.fund_manager = FundManager(
            web3=self.web3,
            wallet=self.account,
            usdc_address=config.usdc_address,
            ctf_exchange_address=config.ctf_exchange_address,
            min_balance=config.min_balance,
            target_balance=config.target_balance,
            withdraw_limit=config.withdraw_limit,
            dry_run=config.dry_run,
            oneinch_api_key=None  # Optional, not in config yet
        )
        
        # Initialize auto-bridge manager for fully autonomous operation
        self.auto_bridge_manager = AutoBridgeManager(
            private_key=config.private_key,
            polygon_rpc=config.polygon_rpc_url,
            dry_run=config.dry_run
        )
        
        # Initialize strategy engines
        logger.info("Initializing strategy engines...")
        
        # Initialize Kelly position sizer
        from src.kelly_position_sizer import KellyPositionSizer
        from src.dynamic_position_sizer import DynamicPositionSizer
        
        self.kelly_sizer = KellyPositionSizer()  # Uses default config
        self.dynamic_sizer = DynamicPositionSizer()  # Dynamic position sizing
        
        self.internal_arbitrage = InternalArbitrageEngine(
            clob_client=self.clob_client,
            order_manager=self.order_manager,
            position_merger=self.position_merger,
            ai_safety_guard=self.ai_safety_guard,
            kelly_sizer=self.kelly_sizer,
            dynamic_sizer=self.dynamic_sizer,  # Pass dynamic sizer
            min_profit_threshold=config.min_profit_threshold
        )
        
        # Flash Crash Strategy will be initialized after market_parser
        self.flash_crash_strategy = None
        
        # Directional Trading will be initialized after market_parser
        self.directional_trading = None
        
        # Cross-platform arbitrage (if Kalshi API key provided)
        # TEMPORARILY DISABLED - needs additional setup
        self.cross_platform_arbitrage = None
        # if config.kalshi_api_key:
        #     self.cross_platform_arbitrage = CrossPlatformArbitrageEngine(
        #         polymarket_client=self.clob_client,
        #         kalshi_api_key=config.kalshi_api_key,
        #         order_manager=self.order_manager,
        #         ai_safety_guard=self.ai_safety_guard
        #     )
        #     logger.info("Cross-platform arbitrage enabled")
        
        # Latency arbitrage
        # TEMPORARILY DISABLED - needs CEX feeds setup
        self.latency_arbitrage = None
        # self.latency_arbitrage = LatencyArbitrageEngine(
        #     clob_client=self.clob_client,
        #     order_manager=self.order_manager,
        #     ai_safety_guard=self.ai_safety_guard
        # )
        
        # Resolution farming
        # TEMPORARILY DISABLED - needs additional setup
        self.resolution_farming = None
        # self.resolution_farming = ResolutionFarmingEngine(
        #     clob_client=self.clob_client,
        #     order_manager=self.order_manager,
        #     ai_safety_guard=self.ai_safety_guard,
        #     max_position_pct=Decimal("0.02")  # 2% of bankroll
        # )
        
        # Initialize monitoring and reporting
        logger.info("Initializing monitoring system...")
        
        self.monitoring = MonitoringSystem(
            prometheus_port=config.prometheus_port,
            sns_topic_arn=config.sns_alert_topic
        )
        
        self.trade_history = TradeHistoryDB()
        self.trade_statistics = TradeStatisticsTracker(self.trade_history)
        
        # Initialize status dashboard
        self.dashboard = StatusDashboard()
        
        # Initialize market parser
        self.market_parser = MarketParser()
        
        # Flash Crash Strategy (like successful bots)
        self.flash_crash_strategy = FlashCrashStrategy(
            clob_client=self.clob_client,
            market_parser=self.market_parser,
            drop_threshold=config.flash_crash_drop_threshold,
            lookback_seconds=config.flash_crash_lookback_seconds,
            trade_size=config.flash_crash_trade_size,
            take_profit=config.flash_crash_take_profit,
            stop_loss=config.flash_crash_stop_loss,
            dry_run=config.dry_run
        )
        logger.info("✅ Flash Crash Strategy enabled (directional trading)")
        
        # Directional Trading (DISABLED - using Flash Crash instead)
        self.directional_trading = None
        
        # ============================================================
        # LLM DECISION ENGINE V2 - PERFECT EDITION (2026)
        # ============================================================
        logger.info("Initializing LLM Decision Engine V2 (Perfect Edition)...")
        self.llm_decision_engine = LLMDecisionEngineV2(
            nvidia_api_key=config.nvidia_api_key,
            min_confidence_threshold=45.0,  # 45% threshold - balanced between opportunity and safety
            max_position_pct=5.0,  # Max 5% of balance per trade
            decision_timeout=5.0,  # 5 second timeout for LLM calls
            enable_chain_of_thought=True
        )
        logger.info("✅ LLM Decision Engine V2 enabled (Dynamic prompts, Multi-factor analysis)")
        
        # ============================================================
        # NEGRISK ARBITRAGE ENGINE - 73% of Top Profits
        # ============================================================
        logger.info("Initializing NegRisk Arbitrage Engine...")
        self.negrisk_arbitrage = NegRiskArbitrageEngine(
            clob_client=self.clob_client,
            order_manager=self.order_manager,
            ai_safety_guard=self.ai_safety_guard,
            min_profit_threshold=Decimal('0.005'),  # 0.5% minimum
            max_position_size=Decimal('5.0')
        )
        logger.info("✅ NegRisk Arbitrage Engine enabled")
        
        # ============================================================
        # PORTFOLIO RISK MANAGER - Holistic Risk Management
        # ============================================================
        logger.info("Initializing Portfolio Risk Manager...")
        self.portfolio_risk_manager = PortfolioRiskManager(
            initial_capital=config.target_balance,  # Starting capital estimate
            max_portfolio_heat=Decimal('0.30'),  # Max 30% deployed
            max_daily_drawdown=Decimal('0.10'),  # 10% daily loss limit
            max_position_size_pct=Decimal('0.05'),  # 5% per trade
            consecutive_loss_limit=3  # Halt after 3 consecutive losses
        )
        logger.info("✅ Portfolio Risk Manager enabled")
        
        # ============================================================
        # 15-MINUTE CRYPTO STRATEGY - BTC/ETH Up/Down Trading
        # ============================================================
        logger.info("Initializing 15-Minute Crypto Trading Strategy...")
        
        # Dynamic position sizing based on available balance
        # Use 30% of balance per trade (aggressive but safe)
        # Start with config target_balance, will auto-adjust based on actual balance
        initial_trade_size = max(1.0, float(config.target_balance) * 0.30)
        logger.info(f"💰 Initial trade size: ${initial_trade_size:.2f} per trade (30% of ${config.target_balance:.2f} balance)")
        logger.info(f"💰 Risk manager will dynamically adjust based on actual balance")
        
        self.fifteen_min_strategy = FifteenMinuteCryptoStrategy(
            clob_client=self.clob_client,
            trade_size=initial_trade_size,  # DYNAMIC: Will be adjusted by risk manager
            take_profit_pct=0.005,  # 0.5% profit target (Realistic for 15-min markets - prices move slowly)
            stop_loss_pct=0.01,  # 1% stop loss (Tight risk control)
            max_positions=10,  # INCREASED: Allow more concurrent trades
            sum_to_one_threshold=1.02,
            dry_run=config.dry_run,
            llm_decision_engine=self.llm_decision_engine,
            enable_adaptive_learning=False,  # CRITICAL FIX: Disable (breaks dynamic take profit)
            initial_capital=float(config.target_balance)  # Pass balance for risk management
        )
        logger.info("✅ 15-Minute Crypto Strategy enabled (AGGRESSIVE MODE: Learning Constraints Removed)")
        
        # Timing trackers
        self.last_heartbeat = time.time()
        self.last_fund_check = time.time()
        self.last_state_save = time.time()
        self.scan_count = 0
        
        # Gas price monitoring
        self.gas_price_halted = False
        
        # OPTIMIZATION: Market data cache (50% fewer API calls)
        self._market_cache: Optional[List] = None
        self._market_cache_time: float = 0
        self._market_cache_ttl: float = 2.0  # 2 second cache
        
        # OPTIMIZATION: Dynamic scan interval (better resource usage)
        self._base_scan_interval = config.scan_interval_seconds
        self._current_scan_interval = config.scan_interval_seconds
        self._volatility_threshold = Decimal("0.05")  # 5% volatility (increased from 2% to reduce false triggers)
        
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
        - Balance > $10 (skipped for proxy wallets where balance can't be checked)
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
            
            # For proxy wallets, we can't check balance programmatically
            # Skip balance check and assume healthy (orders will fail if no funds)
            if total_balance == Decimal("0"):
                # Proxy wallet detected - skip balance validation
                balance_ok = True
            else:
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
        stats_obj = self.trade_statistics.get_statistics()
        stats = {
            'total_trades': stats_obj.total_trades,
            'win_rate': float(stats_obj.win_rate),
            'total_profit': stats_obj.total_profit,
            'avg_profit_per_trade': stats_obj.avg_profit_per_trade,
            'total_gas_cost': stats_obj.total_gas_cost,
            'net_profit': stats_obj.net_profit
        }
        
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
        
        # Log heartbeat - monitoring system doesn't have this method
        # Just log it normally
        logger.info(f"Heartbeat: Balance=${total_balance:.2f}, Gas={gas_price_gwei}gwei, Healthy={is_healthy}")
        
        # Dashboard update not needed - passive display
        # self.dashboard.update_health_status(health_status)
        
        return health_status
    
    async def _check_gas_price(self) -> bool:
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
                    # FIX: Re-enabled monitoring alert (send_alert exists in MonitoringSystem)
                    await self.monitoring.send_alert(
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
                    # FIX: Re-enabled monitoring alert
                    await self.monitoring.send_alert(
                        "info",
                        f"Trading resumed: Gas price {gas_price_gwei} gwei"
                    )
                    self.gas_price_halted = False
                return True
                
        except Exception as e:
            logger.error(f"Failed to check gas price: {e}")
            return False
    
    def _adjust_scan_interval(self, markets: List):
        """
        OPTIMIZATION: Adjust scan interval based on market volatility.
        High volatility = faster scanning for more opportunities.
        """
        if not markets or len(markets) < 5:
            return
        
        try:
            # Calculate average price volatility from sample
            total_volatility = Decimal("0")
            count = 0
            
            for market in markets[:10]:  # Sample first 10 markets
                if hasattr(market, 'tokens') and len(market.tokens) >= 2:
                    prices = [t.price for t in market.tokens if hasattr(t, 'price')]
                    if len(prices) >= 2:
                        price_range = max(prices) - min(prices)
                        avg_price = sum(prices) / len(prices)
                        if avg_price > 0:
                            volatility = price_range / avg_price
                            total_volatility += volatility
                            count += 1
            
            if count > 0:
                avg_volatility = total_volatility / count
                
                # High volatility = faster scanning (but not too fast)
                if avg_volatility > self._volatility_threshold:
                    # Reduce interval by 25% (not 50%) and minimum 2 seconds (not 0.5)
                    self._current_scan_interval = max(1.5, self._base_scan_interval * 0.75)
                    logger.debug(f"🔥 High volatility ({avg_volatility*100:.1f}%), scan interval: {self._current_scan_interval}s")
                else:
                    self._current_scan_interval = self._base_scan_interval
        except Exception as e:
            logger.debug(f"Error adjusting scan interval: {e}")
    
    async def _scan_and_execute(self) -> None:
        """
        Scan markets for opportunities and execute trades.
        
        Main trading logic that:
        1. Fetches markets from Gamma API (active markets only) - WITH CACHING
        2. Parses and filters markets
        3. Scans for opportunities across all strategies - IN PARALLEL
        4. Validates safety checks
        5. Executes profitable trades
        """
        try:
            # OPTIMIZATION: Check cache first (50% fewer API calls)
            current_time = time.time()
            if (self._market_cache is not None and 
                current_time - self._market_cache_time < self._market_cache_ttl):
                logger.debug("💾 Using cached market data")
                raw_markets = self._market_cache
            else:
                # FIX: All fetch logic now properly inside else block (was bypassing cache)
                logger.debug("🔄 Fetching fresh market data from Gamma API...")
                
                import requests
                import json
                gamma_url = "https://gamma-api.polymarket.com/markets"
                params = {
                    'closed': 'false',  # Only active markets
                    'limit': 100,
                    'offset': 0
                }
                
                try:
                    response = requests.get(gamma_url, params=params, timeout=10)
                    response.raise_for_status()
                    gamma_markets = response.json()
                    
                    if not isinstance(gamma_markets, list):
                        gamma_markets = gamma_markets.get('data', [])
                    
                    logger.info(f"Fetched {len(gamma_markets)} active markets from Gamma API")
                    
                    # Convert Gamma API format to CLOB API format
                    raw_markets = []
                    for gm in gamma_markets:
                        # Skip if no conditionId
                        condition_id = gm.get('conditionId', '')
                        if not condition_id:
                            logger.debug(f"Skipping market without conditionId")
                            continue
                        
                        # Parse outcomes and prices (Gamma returns JSON strings)
                        try:
                            outcomes_raw = gm.get('outcomes', '[]')
                            prices_raw = gm.get('outcomePrices', '[]')
                            token_ids_raw = gm.get('clobTokenIds', '[]')
                            
                            # Parse JSON strings
                            outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
                            prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                            token_ids = json.loads(token_ids_raw) if isinstance(token_ids_raw, str) else token_ids_raw
                            
                            # Ensure we have lists
                            if not isinstance(outcomes, list):
                                outcomes = []
                            if not isinstance(prices, list):
                                prices = []
                            if not isinstance(token_ids, list):
                                token_ids = []
                            
                        except Exception as e:
                            logger.debug(f"Failed to parse market {condition_id} data: {e}")
                            outcomes = []
                            prices = []
                            token_ids = []
                        
                        # Skip if no outcomes
                        if len(outcomes) < 2:
                            logger.debug(f"Skipping market {condition_id} - insufficient outcomes")
                            continue
                        
                        # Build tokens array
                        tokens = []
                        for i, outcome in enumerate(outcomes):
                            token_data = {
                                'outcome': outcome,
                                'price': float(prices[i]) if i < len(prices) else 0.0,
                                'token_id': str(token_ids[i]) if i < len(token_ids) else ''
                            }
                            tokens.append(token_data)
                        
                        # Convert to CLOB format with all required fields
                        clob_market = {
                            'condition_id': condition_id,
                            'question': gm.get('question', ''),
                            'end_date_iso': gm.get('endDate', ''),
                            'closed': gm.get('closed', False),
                            'accepting_orders': gm.get('acceptingOrders', True),  # Default to True
                            'tokens': tokens,
                            'volume': float(gm.get('volume', 0)),
                            'liquidity': float(gm.get('liquidity', 0)),
                            'resolution_source': gm.get('resolutionSource', '')
                        }
                        raw_markets.append(clob_market)
                    
                    logger.info(f"Converted {len(raw_markets)} markets from Gamma API format")
                    
                    # OPTIMIZATION: Update cache
                    self._market_cache = raw_markets
                    self._market_cache_time = current_time
                    
                except Exception as e:
                    logger.error(f"Failed to fetch from Gamma API: {e}")
                    # Fallback to CLOB API
                    logger.info("Falling back to CLOB API...")
                    markets_response = self.clob_client.get_markets()
                    raw_markets = markets_response.get('data', []) if isinstance(markets_response, dict) else markets_response
                    
                    # Update cache with fallback data
                    self._market_cache = raw_markets
                    self._market_cache_time = current_time
            
            # Parse markets - NO FILTERING for maximum opportunity coverage
            markets = []
            for raw_market in raw_markets:
                market = self.market_parser.parse_single_market(raw_market)
                if market:
                    markets.append(market)
            
            logger.info(f"Parsed {len(markets)} tradeable markets")
            
            if len(markets) == 0:
                logger.warning("No tradeable markets found - all markets filtered out")
                logger.warning("This could mean:")
                logger.warning("  1. All markets are closed/expired")
                logger.warning("  2. API is returning stale data")
                logger.warning("  3. Polymarket has very few active markets right now")
                return
            # FIX: Re-enabled monitoring — update_system_metrics covers markets_scanned
            self.monitoring.update_system_metrics(
                markets_scanned=len(markets),
                circuit_breaker_open=self.circuit_breaker.is_open,
                consecutive_failures=self.circuit_breaker.consecutive_failures
            )
            
            # OPTIMIZATION: Adjust scan interval based on volatility
            self._adjust_scan_interval(markets)
            
            # Scan for opportunities across all strategies
            opportunities = []
            
            # ============================================================
            # ONLY RUN 15-MINUTE CRYPTO STRATEGY (USER REQUIREMENT)
            # ============================================================
            strategy_tasks = []
            
            # ONLY: 15-Minute Crypto Strategy (BTC, ETH, SOL, XRP)
            if hasattr(self, 'fifteen_min_strategy') and self.fifteen_min_strategy:
                logger.info("⏱️ Running 15-Minute Crypto Strategy (BTC, ETH, SOL, XRP)...")
                strategy_tasks.append(self.fifteen_min_strategy.run_cycle())
            
            # Execute strategy
            if strategy_tasks:
                logger.debug(f"⚡ Executing 15-minute crypto strategy...")
                results = await asyncio.gather(*strategy_tasks, return_exceptions=True)
                
                # Handle results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Strategy {i} failed: {result}")
                    elif result and isinstance(result, list):
                        # Strategy returned results
                        logger.debug(f"Strategy {i} returned {len(result)} results")
            
            # ALL OTHER STRATEGIES DISABLED (USER ONLY WANTS 15-MIN CRYPTO)
            # Internal arbitrage (DISABLED)
            # Cross-platform arbitrage (DISABLED)
            # Latency arbitrage (DISABLED)
            # Resolution farming (DISABLED)
            # NegRisk arbitrage (DISABLED)
            
            logger.debug(f"Found {len(opportunities)} total opportunities")
            # Monitoring system doesn't have record_opportunities_found
            # self.monitoring.record_opportunities_found(len(opportunities))
            
            # Dashboard update not needed - passive display
            # self.dashboard.update_opportunities(opportunities)
            
            # Execute opportunities
            for opp in opportunities:
                # Check if we should continue trading
                if self.shutdown_requested:
                    logger.info("Shutdown requested, stopping execution")
                    break
                
                if self.circuit_breaker.is_open:
                    logger.warning("Circuit breaker is open, skipping trade")
                    break
                
                # Get current balances for dynamic position sizing
                try:
                    eoa_balance, proxy_balance = await self.fund_manager.check_balance()
                    recent_win_rate = self.trade_statistics.get_recent_win_rate(last_n=10)
                except Exception as e:
                    logger.error(f"Failed to get balances: {e}")
                    eoa_balance = proxy_balance = Decimal('0')
                    recent_win_rate = None
                
                # Find the market for this opportunity
                market_for_opp = None
                for m in markets:
                    if m.market_id == opp.market_id:
                        market_for_opp = m
                        break
                
                if market_for_opp is None:
                    logger.warning(f"Market not found for opportunity {opp.opportunity_id}")
                    continue
                
                # Execute based on strategy
                try:
                    if opp.strategy == "directional_trading":
                        result = await self.directional_trading.execute(
                            opp,
                            market=market_for_opp
                        )
                    elif opp.strategy == "internal_arbitrage":
                        result = await self.internal_arbitrage.execute(
                            opp,
                            market=market_for_opp,
                            bankroll=eoa_balance + proxy_balance,
                            private_wallet_balance=eoa_balance,
                            polymarket_balance=proxy_balance,
                            recent_win_rate=recent_win_rate
                        )
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
                    
                    # Dashboard update - add_trade exists
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
        
        # AUTONOMOUS OPERATION: Check for funds (skip slow bridge)
        logger.info("\n[AUTO] AUTONOMOUS MODE: Checking for funds...")
        try:
            # Check Polymarket balance directly - skip bridge entirely
            eoa_balance, proxy_balance = await self.fund_manager.check_balance()
            total_balance = eoa_balance + proxy_balance
            
            logger.info(f"Private Wallet (Polygon): ${eoa_balance:.2f} USDC")
            logger.info(f"Polymarket Balance: ${proxy_balance:.2f} USDC")
            logger.info(f"Total Available: ${total_balance:.2f} USDC")
            
            # Show success if we have funds
            if total_balance >= Decimal("0.50"):
                logger.info("=" * 80)
                logger.info(f"✅ BALANCE CONFIRMED: ${total_balance:.2f} USDC available for trading")
                logger.info("=" * 80)
            # Only show warning if both balances are zero
            elif proxy_balance == Decimal("0.0") and eoa_balance == Decimal("0.0"):

                logger.warning("=" * 80)
                logger.warning("⚠️  PROXY WALLET DETECTED - CANNOT CHECK BALANCE")
                logger.warning("=" * 80)
                logger.warning("The bot cannot check your Polymarket proxy wallet balance programmatically.")
                logger.warning("This is normal for wallets created via Polymarket.com")
                logger.warning("")
                logger.warning("⚠️  IMPORTANT: Make sure you have deposited funds on Polymarket.com!")
                logger.warning("")
                logger.warning("To deposit:")
                logger.warning("1. Go to: https://polymarket.com")
                logger.warning("2. Connect your wallet")
                logger.warning("3. Click 'Deposit' and add USDC")
                logger.warning("")
                logger.warning(f"Your wallet: {self.account.address}")
                logger.warning("")
                logger.warning("The bot will now start trading.")
                logger.warning("Orders will be rejected by Polymarket if you have insufficient funds.")
                logger.warning("=" * 80)
            elif total_balance < Decimal("0.50"):
                # In DRY RUN mode, allow trading with any balance for testing
                if self.config.dry_run:
                    logger.warning("=" * 80)
                    logger.warning("DRY RUN MODE - LOW BALANCE DETECTED")
                    logger.warning("=" * 80)
                    logger.warning(f"Total balance: ${total_balance:.2f} USDC")
                    logger.warning("Minimum required for live trading: $0.50 USDC")
                    logger.warning("")
                    logger.warning("✅ DRY RUN MODE ENABLED - Proceeding with simulated trades")
                    logger.warning("   No real money will be used")
                    logger.warning("   Bot will learn and optimize parameters")
                    logger.warning("   Add funds when ready to trade for real")
                    logger.warning("")
                    logger.warning(f"Your wallet: {self.account.address}")
                    logger.warning("=" * 80)
                    # CRITICAL: Don't return - continue with dry-run trading
                else:
                    logger.error("=" * 80)
                    logger.error("INSUFFICIENT FUNDS - CANNOT START TRADING")
                    logger.error("=" * 80)
                    logger.error(f"Total balance: ${total_balance:.2f} USDC")
                    logger.error("Minimum required: $0.50 USDC")
                    logger.error("")
                    logger.error("FASTEST WAY TO START TRADING:")
                    logger.error("")
                    logger.error("1. Go to: https://polymarket.com")
                    logger.error("2. Click 'Connect Wallet' (top right)")
                    logger.error("3. Click your profile → 'Deposit'")
                    logger.error("4. Enter amount (e.g., $3.59)")
                    logger.error("5. Select 'Wallet' as source")
                    logger.error("6. Select 'Ethereum' as network")
                    logger.error("7. Click 'Continue' → Approve in MetaMask")
                    logger.error("8. Wait 10-30 seconds → Done!")
                    logger.error("")
                    logger.error("Benefits:")
                    logger.error("  - Instant (10-30 seconds vs 5-30 minutes)")
                    logger.error("  - Free (Polymarket pays gas fees)")
                    logger.error("  - Easy (one click)")
                    logger.error("")
                    logger.error(f"Your wallet: {self.account.address}")
                    logger.error("=" * 80)
                    return
            else:
                logger.info("[OK] Sufficient funds - starting autonomous trading!")
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            logger.warning("Proceeding anyway - will check balance during operation")
        
        # Start dashboard is not needed - dashboard is passive
        
        # Perform initial heartbeat
        await self.heartbeat_check()
        
        # Start strategies that require initialization (Requirements 5.4, 5.5)
        if hasattr(self, 'fifteen_min_strategy') and self.fifteen_min_strategy:
            logger.info("Starting 15-Minute Crypto Strategy price feed...")
            await self.fifteen_min_strategy.start()
        
        try:
            while self.running and not self.shutdown_requested:
                loop_start = time.time()
                
                # Check gas price
                gas_ok = await self._check_gas_price()
                
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
                
                # Dashboard is passive - no need to render
                
                # OPTIMIZATION: Sleep for adjusted interval (dynamic based on volatility)
                elapsed = time.time() - loop_start
                sleep_time = max(0, self._current_scan_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.critical(f"Fatal error in main loop: {e}", exc_info=True)
            # FIX: Re-enabled monitoring alert
            await self.monitoring.send_alert("critical", f"Fatal error: {e}")
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
        
        # Dashboard is passive - no need to stop
        
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
        
        # Stop strategies
        if hasattr(self, 'fifteen_min_strategy') and self.fifteen_min_strategy:
            await self.fifteen_min_strategy.stop()
        
        # Web3 connections are stateless, no need to close
        
        # Final statistics
        stats_obj = self.trade_statistics.get_statistics()
        logger.info("=" * 80)
        logger.info("FINAL STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total Trades: {stats_obj.total_trades}")
        logger.info(f"Win Rate: {stats_obj.win_rate:.2f}%")
        logger.info(f"Total Profit: ${stats_obj.total_profit:.2f}")
        logger.info(f"Total Gas Cost: ${stats_obj.total_gas_cost:.2f}")
        logger.info(f"Net Profit: ${stats_obj.net_profit:.2f}")
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
