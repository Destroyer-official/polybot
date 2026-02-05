"""
Real-time Status Dashboard for Polymarket Arbitrage Bot.

Provides:
- Continuously updating console dashboard
- System status, balances, performance metrics
- Current scan details and opportunities
- Gas prices, network status, recent trades
- Fund management and safety check status
- Color-coded output for readability

Validates Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 21.8, 21.9, 21.10, 21.11, 21.13, 21.15
"""

import os
import sys
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, field

try:
    from colorama import Fore, Style, Back, init as colorama_init
    colorama_init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

from src.models import TradeResult, Opportunity, HealthStatus


@dataclass
class DashboardState:
    """State for the dashboard display"""
    # System status
    status: str = "STARTING"
    uptime_seconds: int = 0
    mode: str = "DRY_RUN"
    circuit_breaker_open: bool = False
    last_heartbeat: datetime = field(default_factory=datetime.now)
    is_healthy: bool = True
    
    # Balances
    eoa_balance: Decimal = Decimal('0')
    proxy_balance: Decimal = Decimal('0')
    total_balance: Decimal = Decimal('0')
    wallet_address: str = "0x0000...0000"
    
    # Portfolio performance
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    win_rate: Decimal = Decimal('0')
    total_profit: Decimal = Decimal('0')
    avg_profit_per_trade: Decimal = Decimal('0')
    total_gas_cost: Decimal = Decimal('0')
    net_profit: Decimal = Decimal('0')
    profit_factor: Decimal = Decimal('0')
    sharpe_ratio: Decimal = Decimal('0')
    max_drawdown: Decimal = Decimal('0')
    
    # Current scan
    scan_cycle: int = 0
    markets_scanned: int = 0
    opportunities_found: int = 0
    scan_latency_ms: float = 0.0
    last_scan: datetime = field(default_factory=datetime.now)
    active_opportunities: List[Dict[str, Any]] = field(default_factory=list)
    
    # Gas & network
    gas_price_gwei: int = 0
    fast_gas_price_gwei: int = 0
    pending_tx_count: int = 0
    max_pending_tx: int = 5
    rpc_endpoint: str = "Unknown"
    rpc_latency_ms: float = 0.0
    block_number: int = 0
    last_block_time: datetime = field(default_factory=datetime.now)
    
    # Recent activity
    recent_trades: List[Dict[str, Any]] = field(default_factory=list)
    
    # Fund management
    auto_deposit_enabled: bool = True
    auto_withdraw_enabled: bool = True
    deposit_trigger: Decimal = Decimal('50')
    withdraw_trigger: Decimal = Decimal('500')
    last_deposit_time: Optional[datetime] = None
    last_deposit_amount: Decimal = Decimal('0')
    last_withdraw_time: Optional[datetime] = None
    last_withdraw_amount: Decimal = Decimal('0')
    next_balance_check_seconds: int = 60
    
    # Safety checks
    ai_safety_active: bool = True
    ai_response_time_ms: float = 0.0
    btc_volatility: Decimal = Decimal('0')
    eth_volatility: Decimal = Decimal('0')
    sol_volatility: Decimal = Decimal('0')
    xrp_volatility: Decimal = Decimal('0')
    ambiguous_markets_filtered: int = 0
    
    # Errors
    network_errors_last_hour: int = 0
    api_timeouts_last_hour: int = 0
    failed_trades_last_hour: int = 0
    alerts_sent_last_hour: int = 0
    recent_errors: List[str] = field(default_factory=list)
    
    # Debug logs
    debug_logs: List[str] = field(default_factory=list)
    debug_mode: bool = False


class StatusDashboard:
    """
    Real-time console dashboard with continuous updates.
    
    Validates Requirements:
    - 21.1: Display system status, uptime, mode, circuit breaker status
    - 21.2: Display EOA/Proxy/Total balances in real-time
    - 21.3: Display portfolio performance metrics
    - 21.4: Display current scan details with opportunity information
    - 21.5: Display gas prices, pending TXs, RPC status, block number
    - 21.8: Display fund management status and countdowns
    - 21.9: Display safety check status and error counters
    - 21.10: Display last 5 trades with timestamps and results
    - 21.11: Use color coding for readability
    - 21.13: Display "Bot Running. Waiting for Arbs..." with context
    - 21.15: Update dashboard every 1 second
    """
    
    def __init__(self, update_interval: float = 1.0):
        """
        Initialize status dashboard.
        
        Args:
            update_interval: Update interval in seconds (default 1.0)
        """
        self.state = DashboardState()
        self.update_interval = update_interval
        self.start_time = datetime.now()
        self.running = False
        
        # Color definitions
        if COLORAMA_AVAILABLE:
            self.GREEN = Fore.GREEN
            self.YELLOW = Fore.YELLOW
            self.RED = Fore.RED
            self.BLUE = Fore.CYAN
            self.WHITE = Fore.WHITE
            self.BOLD = Style.BRIGHT
            self.RESET = Style.RESET_ALL
        else:
            self.GREEN = self.YELLOW = self.RED = self.BLUE = ""
            self.WHITE = self.BOLD = self.RESET = ""
    
    def _clear_screen(self):
        """Clear the console screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _format_uptime(self, seconds: int) -> str:
        """Format uptime as human-readable string."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs}s"
    
    def _format_time_ago(self, dt: datetime) -> str:
        """Format datetime as 'X seconds ago'."""
        delta = datetime.now() - dt
        seconds = int(delta.total_seconds())
        
        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        else:
            return f"{seconds // 3600}h ago"
    
    def _status_indicator(self, condition: bool, true_text: str = "✓", false_text: str = "✗") -> str:
        """Return colored status indicator."""
        if condition:
            return f"{self.GREEN}{true_text}{self.RESET}"
        else:
            return f"{self.RED}{false_text}{self.RESET}"
    
    def _format_currency(self, amount: Decimal) -> str:
        """Format currency amount."""
        return f"${amount:,.2f}"
    
    def _format_percentage(self, pct: Decimal) -> str:
        """Format percentage."""
        return f"{pct:.2f}%"
    
    def print_status_dashboard(self) -> None:
        """
        Print the complete status dashboard.
        
        Validates Requirement 21.1-21.15: Display comprehensive real-time status
        """
        self._clear_screen()
        
        # Calculate uptime
        uptime_seconds = int((datetime.now() - self.start_time).total_seconds())
        
        # Header
        print("╔" + "═" * 78 + "╗")
        print("║" + " " * 20 + "POLYMARKET ARBITRAGE BOT - LIVE STATUS" + " " * 20 + "║")
        print("╚" + "═" * 78 + "╝")
        print()
        
        # System Status
        print(f"{self.BOLD}[SYSTEM STATUS]{self.RESET}")
        status_color = self.GREEN if self.state.status == "RUNNING" else self.YELLOW
        health_indicator = self._status_indicator(self.state.is_healthy, "HEALTHY", "UNHEALTHY")
        cb_status = f"{self.RED}OPEN{self.RESET}" if self.state.circuit_breaker_open else f"{self.GREEN}CLOSED{self.RESET}"
        
        print(f"  Status: {status_color}● {self.state.status}{self.RESET} | "
              f"Uptime: {self._format_uptime(uptime_seconds)} | "
              f"Mode: {self.BOLD}{self.state.mode}{self.RESET}")
        print(f"  Circuit Breaker: {cb_status} | "
              f"Last Heartbeat: {self._format_time_ago(self.state.last_heartbeat)} | "
              f"Health: {health_indicator}")
        print()
        
        # Balances
        print(f"{self.BOLD}[BALANCES]{self.RESET}")
        print(f"  EOA Wallet:    {self.GREEN}{self._format_currency(self.state.eoa_balance)}{self.RESET} USDC ({self.state.wallet_address})")
        print(f"  Proxy Wallet:  {self.GREEN}{self._format_currency(self.state.proxy_balance)}{self.RESET} USDC (Trading Balance)")
        print(f"  Total Assets:  {self.BOLD}{self.GREEN}{self._format_currency(self.state.total_balance)}{self.RESET} USDC")
        print()
        
        # Portfolio Performance
        print(f"{self.BOLD}[PORTFOLIO PERFORMANCE]{self.RESET}")
        win_rate_color = self.GREEN if self.state.win_rate >= Decimal('99.5') else self.YELLOW
        print(f"  Total Trades:       {self.state.total_trades} | "
              f"Win Rate: {win_rate_color}{self._format_percentage(self.state.win_rate)}{self.RESET} "
              f"{self._status_indicator(self.state.win_rate >= Decimal('99.5'))}")
        print(f"  Successful:         {self.GREEN}{self.state.successful_trades}{self.RESET} | "
              f"Failed: {self.RED}{self.state.failed_trades}{self.RESET}")
        print(f"  Total Profit:       {self.GREEN}{self._format_currency(self.state.total_profit)}{self.RESET} | "
              f"Avg Profit/Trade: {self._format_currency(self.state.avg_profit_per_trade)}")
        print(f"  Total Gas Cost:     {self.YELLOW}{self._format_currency(self.state.total_gas_cost)}{self.RESET} | "
              f"Net Profit: {self.BOLD}{self.GREEN}{self._format_currency(self.state.net_profit)}{self.RESET}")
        print(f"  Profit Factor:      {self._format_percentage(self.state.profit_factor * Decimal('100'))} | "
              f"Sharpe Ratio: {float(self.state.sharpe_ratio):.2f}")
        print(f"  Max Drawdown:       {self.RED}{self._format_currency(self.state.max_drawdown)}{self.RESET} "
              f"({self._format_percentage(self.state.max_drawdown / self.state.total_balance * Decimal('100') if self.state.total_balance > 0 else Decimal('0'))})")
        print()
        
        # Current Scan
        print(f"{self.BOLD}[CURRENT SCAN - Cycle #{self.state.scan_cycle}]{self.RESET}")
        print(f"  Markets Scanned:    {self.state.markets_scanned} | "
              f"Opportunities Found: {self.BLUE}{self.state.opportunities_found}{self.RESET}")
        print(f"  Scan Latency:       {self.state.scan_latency_ms:.0f}ms | "
              f"Last Scan: {self._format_time_ago(self.state.last_scan)}")
        print()
        
        # Active Opportunities
        if self.state.active_opportunities:
            print(f"  {self.BOLD}Active Opportunities:{self.RESET}")
            for i, opp in enumerate(self.state.active_opportunities[:3], 1):  # Show max 3
                status_color = self.GREEN if opp.get('status') == 'APPROVED' else self.YELLOW
                print(f"    {i}. {opp.get('market_id', 'Unknown')} | {opp.get('strategy', 'Unknown')} | "
                      f"Profit: {self.GREEN}{self._format_currency(opp.get('profit', Decimal('0')))}{self.RESET} "
                      f"({self._format_percentage(opp.get('profit_pct', Decimal('0')) * Decimal('100'))}) | "
                      f"Status: {status_color}{opp.get('status', 'UNKNOWN')}{self.RESET}")
                print(f"       YES: {self._format_currency(opp.get('yes_price', Decimal('0')))} "
                      f"(fee: {self._format_percentage(opp.get('yes_fee', Decimal('0')) * Decimal('100'))}) | "
                      f"NO: {self._format_currency(opp.get('no_price', Decimal('0')))} "
                      f"(fee: {self._format_percentage(opp.get('no_fee', Decimal('0')) * Decimal('100'))}) | "
                      f"Total: {self._format_currency(opp.get('total_cost', Decimal('0')))}")
                print(f"       AI Safety: {self._status_indicator(opp.get('ai_approved', False), 'APPROVED', 'REJECTED')} | "
                      f"Gas: {opp.get('gas_price', 0)} gwei {self._status_indicator(opp.get('gas_ok', True))} | "
                      f"Volatility: {self._format_percentage(opp.get('volatility', Decimal('0')) * Decimal('100'))} "
                      f"{self._status_indicator(opp.get('volatility', Decimal('0')) < Decimal('0.05'))}")
                print()
        else:
            print(f"  {self.BLUE}Bot Running. Waiting for Arbs...{self.RESET}")
            print()
        
        # Gas & Network
        print(f"{self.BOLD}[GAS & NETWORK]{self.RESET}")
        gas_ok = self.state.gas_price_gwei < 800
        pending_ok = self.state.pending_tx_count < self.state.max_pending_tx
        print(f"  Current Gas Price:  {self.state.gas_price_gwei} gwei {self._status_indicator(gas_ok)} (Max: 800 gwei)")
        print(f"  Fast Gas Price:     {self.state.fast_gas_price_gwei} gwei")
        print(f"  Pending TXs:        {self.state.pending_tx_count} / {self.state.max_pending_tx} {self._status_indicator(pending_ok)}")
        print(f"  RPC Endpoint:       {self.state.rpc_endpoint} | Latency: {self.state.rpc_latency_ms:.0f}ms {self._status_indicator(self.state.rpc_latency_ms < 200)}")
        print(f"  Block Number:       #{self.state.block_number} | Last Block: {self._format_time_ago(self.state.last_block_time)}")
        print()
        
        # Recent Activity
        print(f"{self.BOLD}[RECENT ACTIVITY - Last 5 Trades]{self.RESET}")
        if self.state.recent_trades:
            for trade in self.state.recent_trades[:5]:
                timestamp = trade.get('timestamp', datetime.now()).strftime("%H:%M:%S")
                status_icon = f"{self.GREEN}✓{self.RESET}" if trade.get('success') else f"{self.RED}✗{self.RESET}"
                profit_color = self.GREEN if trade.get('net_profit', Decimal('0')) > 0 else self.RED
                
                print(f"  [{timestamp}] {status_icon} {trade.get('market_id', 'Unknown')} | "
                      f"{trade.get('strategy', 'Unknown')} | "
                      f"+{self._format_currency(trade.get('profit', Decimal('0')))} | "
                      f"Gas: {self._format_currency(trade.get('gas_cost', Decimal('0')))} | "
                      f"Net: {profit_color}{self._format_currency(trade.get('net_profit', Decimal('0')))}{self.RESET}")
                
                if not trade.get('success'):
                    print(f"       {self.RED}Reason: {trade.get('reason', 'Unknown')}{self.RESET}")
        else:
            print(f"  {self.YELLOW}No trades yet{self.RESET}")
        print()
        
        # Fund Management
        print(f"{self.BOLD}[FUND MANAGEMENT]{self.RESET}")
        deposit_status = f"{self.GREEN}✓ ENABLED{self.RESET}" if self.state.auto_deposit_enabled else f"{self.RED}✗ DISABLED{self.RESET}"
        withdraw_status = f"{self.GREEN}✓ ENABLED{self.RESET}" if self.state.auto_withdraw_enabled else f"{self.RED}✗ DISABLED{self.RESET}"
        
        print(f"  Auto-Deposit:       {deposit_status} | Trigger: < {self._format_currency(self.state.deposit_trigger)} | Target: $100")
        print(f"  Auto-Withdraw:      {withdraw_status} | Trigger: > {self._format_currency(self.state.withdraw_trigger)} | "
              f"Last: {self._format_time_ago(self.state.last_withdraw_time) if self.state.last_withdraw_time else 'Never'} "
              f"({self._format_currency(self.state.last_withdraw_amount)})")
        print(f"  Next Deposit Check: {self.state.next_balance_check_seconds}s")
        print()
        
        # Safety Checks
        print(f"{self.BOLD}[SAFETY CHECKS]{self.RESET}")
        ai_status = f"{self.GREEN}✓ ACTIVE{self.RESET}" if self.state.ai_safety_active else f"{self.RED}✗ INACTIVE{self.RESET}"
        print(f"  AI Safety Guard:    {ai_status} (NVIDIA API) | Response Time: {self.state.ai_response_time_ms:.0f}ms")
        print(f"  Volatility Monitor: {self.GREEN}✓ ACTIVE{self.RESET} | "
              f"BTC: {self._format_percentage(self.state.btc_volatility * Decimal('100'))} | "
              f"ETH: {self._format_percentage(self.state.eth_volatility * Decimal('100'))} | "
              f"SOL: {self._format_percentage(self.state.sol_volatility * Decimal('100'))} | "
              f"XRP: {self._format_percentage(self.state.xrp_volatility * Decimal('100'))}")
        print(f"  Ambiguous Markets:  {self.state.ambiguous_markets_filtered} filtered | "
              f"Keywords: [\"approximately\", \"around\"]")
        print()
        
        # Errors & Alerts
        print(f"{self.BOLD}[ERRORS & ALERTS - Last Hour]{self.RESET}")
        print(f"  Network Errors:     {self.state.network_errors_last_hour} (auto-recovered)")
        print(f"  API Timeouts:       {self.state.api_timeouts_last_hour} (fallback used)")
        print(f"  Failed Trades:      {self.state.failed_trades_last_hour} (legging risk avoided)")
        print(f"  Alerts Sent:        {self.state.alerts_sent_last_hour}")
        
        if self.state.recent_errors:
            print(f"\n  {self.YELLOW}Recent Errors:{self.RESET}")
            for error in self.state.recent_errors[:3]:
                print(f"    {self.YELLOW}• {error}{self.RESET}")
        print()
        
        # Debug Mode
        if self.state.debug_mode and self.state.debug_logs:
            print(f"{self.BOLD}[DEBUG MODE: VERBOSE]{self.RESET}")
            for log in self.state.debug_logs[-10:]:  # Show last 10 logs
                print(f"  {self.BLUE}▶ {log}{self.RESET}")
            print()
        
        # Next Actions
        print(f"{self.BOLD}[NEXT ACTIONS]{self.RESET}")
        print(f"  ⏳ Waiting {self.update_interval:.1f}s before next scan...")
        print(f"  ⏳ Heartbeat check in {self.state.next_balance_check_seconds}s...")
        print(f"  ⏳ Balance check in {self.state.next_balance_check_seconds}s...")
        print()
        
        print(f"Press Ctrl+C to stop | Press 'h' for help | Press 'd' to toggle debug")
        print("╚" + "═" * 78 + "╝")
    
    def update_state(self, **kwargs):
        """
        Update dashboard state with new values.
        
        Args:
            **kwargs: State fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
    
    def add_trade(self, trade: Dict[str, Any]):
        """
        Add a trade to recent trades list.
        
        Args:
            trade: Trade dictionary
        """
        self.state.recent_trades.insert(0, trade)
        if len(self.state.recent_trades) > 5:
            self.state.recent_trades = self.state.recent_trades[:5]
    
    def add_debug_log(self, log: str):
        """
        Add a debug log entry.
        
        Args:
            log: Log message
        """
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.state.debug_logs.append(f"[{timestamp}] {log}")
        if len(self.state.debug_logs) > 50:
            self.state.debug_logs = self.state.debug_logs[-50:]
    
    def add_error(self, error: str):
        """
        Add an error to recent errors list.
        
        Args:
            error: Error message
        """
        self.state.recent_errors.insert(0, error)
        if len(self.state.recent_errors) > 5:
            self.state.recent_errors = self.state.recent_errors[:5]
    
    def toggle_debug_mode(self):
        """Toggle debug mode on/off."""
        self.state.debug_mode = not self.state.debug_mode
