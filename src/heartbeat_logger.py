"""
Heartbeat Logger for Polymarket Arbitrage Bot.

Provides:
- Comprehensive status logging every 60 seconds
- Balance, network, performance, and safety status
- Detected issues and alerts

Validates Requirements: 9.6, 21.14
"""

import logging
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from src.models import HealthStatus
from src.logging_config import get_logger


class HeartbeatLogger:
    """
    Heartbeat logger for comprehensive status logging.
    
    Validates Requirements:
    - 9.6: Perform heartbeat check every 60 seconds
    - 21.14: Log comprehensive status including balances, network status,
             performance, safety status, and detected issues
    """
    
    def __init__(self, logger_name: str = __name__):
        """
        Initialize heartbeat logger.
        
        Args:
            logger_name: Name for the logger
        """
        self.logger = get_logger(logger_name)
    
    def log_heartbeat(self, status: HealthStatus) -> None:
        """
        Log comprehensive heartbeat status.
        
        Validates Requirements 9.6, 21.14: Log comprehensive status every 60 seconds
        
        Args:
            status: HealthStatus object containing all system status information
        """
        separator = "=" * 80
        
        self.logger.info(separator)
        self.logger.info("HEARTBEAT CHECK")
        self.logger.info(separator)
        
        # Timestamp and overall health
        self.logger.info(f"Timestamp: {status.timestamp.isoformat()}")
        health_str = "✓ HEALTHY" if status.is_healthy else "✗ UNHEALTHY"
        self.logger.info(f"Overall Health: {health_str}")
        self.logger.info("")
        
        # Balances
        self.logger.info("BALANCES:")
        self.logger.info(f"  EOA Wallet:   ${status.eoa_balance:.2f} USDC")
        self.logger.info(f"  Proxy Wallet: ${status.proxy_balance:.2f} USDC")
        self.logger.info(f"  Total:        ${status.total_balance:.2f} USDC")
        
        balance_status = "✓" if status.balance_ok else "✗"
        self.logger.info(f"  Status:       {balance_status} (Min: $10.00)")
        self.logger.info("")
        
        # Network status
        self.logger.info("NETWORK:")
        gas_status = "✓" if status.gas_ok else "✗"
        self.logger.info(f"  Gas Price:    {status.gas_price_gwei} gwei {gas_status} (Max: 800 gwei)")
        
        pending_status = "✓" if status.pending_tx_ok else "✗"
        self.logger.info(f"  Pending TXs:  {status.pending_tx_count}/5 {pending_status}")
        
        self.logger.info(f"  RPC Latency:  {status.rpc_latency_ms:.2f}ms")
        self.logger.info(f"  Block Number: #{status.block_number}")
        
        api_status = "✓" if status.api_connectivity_ok else "✗"
        self.logger.info(f"  API Status:   {api_status}")
        self.logger.info("")
        
        # Performance metrics
        self.logger.info("PERFORMANCE:")
        self.logger.info(f"  Total Trades:     {status.total_trades}")
        
        win_rate_status = "✓" if status.win_rate >= Decimal('99.5') else "✗"
        self.logger.info(f"  Win Rate:         {status.win_rate:.2f}% {win_rate_status} (Target: ≥99.5%)")
        
        self.logger.info(f"  Total Profit:     ${status.total_profit:.2f}")
        self.logger.info(f"  Avg Profit/Trade: ${status.avg_profit_per_trade:.2f}")
        self.logger.info(f"  Total Gas Cost:   ${status.total_gas_cost:.2f}")
        self.logger.info(f"  Net Profit:       ${status.net_profit:.2f}")
        
        if status.total_trades > 0:
            self.logger.info(f"  Recent Win Rate:  {status.recent_win_rate:.2f}% (Last 100 trades)")
            self.logger.info(f"  Recent Error Rate: {status.recent_error_rate:.2f}%")
            self.logger.info(f"  Avg Latency:      {status.avg_latency_ms:.2f}ms")
        self.logger.info("")
        
        # Safety status
        self.logger.info("SAFETY:")
        
        cb_status = "OPEN ✗" if status.circuit_breaker_open else "CLOSED ✓"
        self.logger.info(f"  Circuit Breaker:      {cb_status}")
        self.logger.info(f"  Consecutive Failures: {status.consecutive_failures}/10")
        
        ai_status = "✓" if status.ai_safety_active else "✗"
        self.logger.info(f"  AI Safety Active:     {ai_status}")
        self.logger.info("")
        
        # Issues detected
        if status.issues:
            self.logger.warning("ISSUES DETECTED:")
            for issue in status.issues:
                self.logger.warning(f"  - {issue}")
        else:
            self.logger.info("No issues detected ✓")
        
        self.logger.info(separator)
    
    def log_heartbeat_failure(
        self,
        failure_count: int,
        reason: str,
        last_successful_heartbeat: Optional[datetime] = None,
    ) -> None:
        """
        Log heartbeat check failure.
        
        Args:
            failure_count: Number of consecutive failures
            reason: Reason for failure
            last_successful_heartbeat: Timestamp of last successful heartbeat
        """
        self.logger.error("=" * 80)
        self.logger.error("HEARTBEAT CHECK FAILED")
        self.logger.error("=" * 80)
        self.logger.error(f"Consecutive Failures: {failure_count}/3")
        self.logger.error(f"Reason: {reason}")
        
        if last_successful_heartbeat:
            time_since = datetime.now() - last_successful_heartbeat
            self.logger.error(f"Last Successful: {last_successful_heartbeat.isoformat()} "
                            f"({time_since.total_seconds():.0f}s ago)")
        
        if failure_count >= 3:
            self.logger.critical("CRITICAL: 3 consecutive heartbeat failures - halting trading")
        
        self.logger.error("=" * 80)
    
    def log_quick_status(
        self,
        balance: Decimal,
        gas_price: int,
        pending_tx: int,
        trades_today: int,
        profit_today: Decimal,
    ) -> None:
        """
        Log quick status summary (for more frequent updates).
        
        Args:
            balance: Total balance
            gas_price: Current gas price in gwei
            pending_tx: Number of pending transactions
            trades_today: Number of trades today
            profit_today: Profit today
        """
        self.logger.info(
            f"Status: Balance=${balance:.2f} | Gas={gas_price}gwei | "
            f"Pending={pending_tx} | Trades={trades_today} | Profit=${profit_today:.2f}"
        )
    
    def log_system_startup(
        self,
        version: str,
        config: dict,
        wallet_address: str,
    ) -> None:
        """
        Log system startup information.
        
        Args:
            version: System version
            config: Configuration summary
            wallet_address: Wallet address
        """
        self.logger.info("=" * 80)
        self.logger.info("POLYMARKET ARBITRAGE BOT - STARTING")
        self.logger.info("=" * 80)
        self.logger.info(f"Version: {version}")
        self.logger.info(f"Wallet: {wallet_address}")
        self.logger.info(f"Mode: {config.get('mode', 'UNKNOWN')}")
        self.logger.info("")
        
        self.logger.info("CONFIGURATION:")
        for key, value in config.items():
            # Don't log sensitive information
            if 'key' in key.lower() or 'secret' in key.lower() or 'private' in key.lower():
                self.logger.info(f"  {key}: ***REDACTED***")
            else:
                self.logger.info(f"  {key}: {value}")
        
        self.logger.info("=" * 80)
    
    def log_system_shutdown(
        self,
        reason: str,
        final_balance: Decimal,
        total_trades: int,
        total_profit: Decimal,
        uptime_seconds: int,
    ) -> None:
        """
        Log system shutdown information.
        
        Args:
            reason: Shutdown reason
            final_balance: Final balance
            total_trades: Total trades executed
            total_profit: Total profit earned
            uptime_seconds: System uptime in seconds
        """
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        
        self.logger.info("=" * 80)
        self.logger.info("POLYMARKET ARBITRAGE BOT - SHUTTING DOWN")
        self.logger.info("=" * 80)
        self.logger.info(f"Reason: {reason}")
        self.logger.info(f"Uptime: {hours}h {minutes}m")
        self.logger.info("")
        
        self.logger.info("FINAL STATISTICS:")
        self.logger.info(f"  Final Balance:  ${final_balance:.2f}")
        self.logger.info(f"  Total Trades:   {total_trades}")
        self.logger.info(f"  Total Profit:   ${total_profit:.2f}")
        
        if uptime_seconds > 0:
            profit_per_hour = (total_profit / Decimal(uptime_seconds)) * Decimal('3600')
            self.logger.info(f"  Profit/Hour:    ${profit_per_hour:.2f}")
        
        self.logger.info("=" * 80)


# Example usage
if __name__ == "__main__":
    from src.logging_config import setup_logging
    
    # Set up logging
    setup_logging(log_level="INFO", enable_console=True)
    
    # Create heartbeat logger
    heartbeat_logger = HeartbeatLogger()
    
    # Test heartbeat logging
    status = HealthStatus(
        timestamp=datetime.now(),
        is_healthy=True,
        eoa_balance=Decimal('1234.56'),
        proxy_balance=Decimal('456.78'),
        total_balance=Decimal('1691.34'),
        balance_ok=True,
        gas_ok=True,
        gas_price_gwei=45,
        pending_tx_ok=True,
        pending_tx_count=2,
        api_connectivity_ok=True,
        rpc_latency_ms=89.5,
        block_number=52341234,
        total_trades=1247,
        win_rate=Decimal('99.6'),
        total_profit=Decimal('234.56'),
        avg_profit_per_trade=Decimal('0.19'),
        total_gas_cost=Decimal('12.34'),
        net_profit=Decimal('222.22'),
        circuit_breaker_open=False,
        consecutive_failures=0,
        ai_safety_active=True,
        recent_win_rate=Decimal('99.8'),
        recent_error_rate=Decimal('0.2'),
        avg_latency_ms=142.5,
        issues=[],
    )
    
    heartbeat_logger.log_heartbeat(status)
    
    # Test heartbeat failure
    heartbeat_logger.log_heartbeat_failure(
        failure_count=2,
        reason="RPC endpoint unavailable",
        last_successful_heartbeat=datetime.now(),
    )
    
    # Test quick status
    heartbeat_logger.log_quick_status(
        balance=Decimal('1691.34'),
        gas_price=45,
        pending_tx=2,
        trades_today=47,
        profit_today=Decimal('12.34'),
    )
    
    # Test system startup
    heartbeat_logger.log_system_startup(
        version="1.0.0",
        config={
            "mode": "LIVE",
            "min_profit_threshold": "0.005",
            "max_position_size": "5.0",
        },
        wallet_address="0x1234...5678",
    )
    
    # Test system shutdown
    heartbeat_logger.log_system_shutdown(
        reason="User requested shutdown",
        final_balance=Decimal('1691.34'),
        total_trades=1247,
        total_profit=Decimal('234.56'),
        uptime_seconds=9252,  # 2h 34m 12s
    )
