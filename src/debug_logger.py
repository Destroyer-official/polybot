"""
Verbose Debug Logger for Polymarket Arbitrage Bot.

Provides:
- Millisecond-precision timestamps
- Operation-level logging
- API response time tracking
- Transaction hash logging
- Full context in error logs

Validates Requirements: 21.6, 21.7, 21.12
"""

import logging
import time
import traceback
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from decimal import Decimal
from functools import wraps

from src.logging_config import get_logger, log_with_context


class DebugLogger:
    """
    Verbose debug logger with millisecond timestamps.
    
    Validates Requirements:
    - 21.6: Log every operation with millisecond timestamps
    - 21.7: Log market scanning, fee calculations, AI checks, order creation,
            transaction submission, position merging, balance updates
    - 21.12: Include full context in error logs (stack trace, recovery action)
    """
    
    def __init__(self, logger_name: str = __name__, enabled: bool = True):
        """
        Initialize debug logger.
        
        Args:
            logger_name: Name for the logger
            enabled: Whether debug logging is enabled
        """
        self.logger = get_logger(logger_name)
        self.enabled = enabled
        self.operation_timers: Dict[str, float] = {}
    
    def _get_timestamp_ms(self) -> str:
        """Get current timestamp with milliseconds."""
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    def _format_decimal(self, value: Decimal) -> str:
        """Format Decimal for logging."""
        return f"${value:.4f}" if value >= 0 else f"-${abs(value):.4f}"
    
    def log_operation_start(
        self,
        operation: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log the start of an operation.
        
        Validates Requirement 21.6: Log every operation with millisecond timestamps
        
        Args:
            operation: Operation name
            params: Optional operation parameters
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        self.operation_timers[operation] = time.time()
        
        message = f"[{timestamp}] Starting: {operation}"
        if params:
            message += f" | Params: {params}"
        
        self.logger.debug(message)
    
    def log_operation_complete(
        self,
        operation: str,
        result: Optional[Any] = None,
        success: bool = True,
    ) -> None:
        """
        Log the completion of an operation.
        
        Args:
            operation: Operation name
            result: Optional operation result
            success: Whether operation succeeded
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        
        # Calculate duration if timer exists
        duration_ms = None
        if operation in self.operation_timers:
            duration_ms = (time.time() - self.operation_timers[operation]) * 1000
            del self.operation_timers[operation]
        
        status = "✓" if success else "✗"
        message = f"[{timestamp}] {status} Completed: {operation}"
        
        if duration_ms is not None:
            message += f" | Duration: {duration_ms:.2f}ms"
        
        if result is not None:
            message += f" | Result: {result}"
        
        self.logger.debug(message)
    
    def log_market_scan(
        self,
        markets_count: int,
        scan_duration_ms: float,
        opportunities_found: int,
    ) -> None:
        """
        Log market scanning operation.
        
        Validates Requirement 21.7: Log market scanning
        
        Args:
            markets_count: Number of markets scanned
            scan_duration_ms: Scan duration in milliseconds
            opportunities_found: Number of opportunities found
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        self.logger.debug(
            f"[{timestamp}] Scanned {markets_count} markets in {scan_duration_ms:.2f}ms | "
            f"Found {opportunities_found} opportunities"
        )
    
    def log_fee_calculation(
        self,
        price: Decimal,
        fee: Decimal,
        cached: bool = False,
    ) -> None:
        """
        Log fee calculation.
        
        Validates Requirement 21.7: Log fee calculations
        
        Args:
            price: Position price
            fee: Calculated fee
            cached: Whether result was from cache
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        cache_str = " (cached)" if cached else ""
        self.logger.debug(
            f"[{timestamp}] Fee calculation: price={self._format_decimal(price)} → "
            f"fee={fee * Decimal('100'):.2f}%{cache_str}"
        )
    
    def log_ai_safety_check(
        self,
        market_id: str,
        approved: bool,
        response_time_ms: float,
        reason: Optional[str] = None,
        fallback_used: bool = False,
    ) -> None:
        """
        Log AI safety check.
        
        Validates Requirement 21.7: Log AI checks
        
        Args:
            market_id: Market ID being checked
            approved: Whether trade was approved
            response_time_ms: API response time in milliseconds
            reason: Optional reason for decision
            fallback_used: Whether fallback heuristics were used
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        status = "APPROVED" if approved else "REJECTED"
        fallback_str = " (fallback)" if fallback_used else ""
        
        message = (
            f"[{timestamp}] AI Safety Check: {market_id} → {status}{fallback_str} | "
            f"Response time: {response_time_ms:.2f}ms"
        )
        
        if reason:
            message += f" | Reason: {reason}"
        
        self.logger.debug(message)
    
    def log_order_creation(
        self,
        market_id: str,
        side: str,
        price: Decimal,
        size: Decimal,
        order_type: str = "FOK",
    ) -> None:
        """
        Log order creation.
        
        Validates Requirement 21.7: Log order creation
        
        Args:
            market_id: Market ID
            side: Order side (YES/NO)
            price: Order price
            size: Order size
            order_type: Order type (default FOK)
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        self.logger.debug(
            f"[{timestamp}] Creating {order_type} order: {market_id} | "
            f"{side} @ {self._format_decimal(price)} | Size: {self._format_decimal(size)}"
        )
    
    def log_transaction_submission(
        self,
        tx_type: str,
        tx_hash: str,
        gas_price_gwei: int,
        gas_limit: int,
    ) -> None:
        """
        Log transaction submission.
        
        Validates Requirement 21.7: Log transaction submission
        
        Args:
            tx_type: Transaction type (order, merge, deposit, etc.)
            tx_hash: Transaction hash
            gas_price_gwei: Gas price in gwei
            gas_limit: Gas limit
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        self.logger.debug(
            f"[{timestamp}] Submitted {tx_type} transaction: {tx_hash} | "
            f"Gas: {gas_price_gwei} gwei | Limit: {gas_limit}"
        )
    
    def log_transaction_confirmation(
        self,
        tx_hash: str,
        success: bool,
        block_number: int,
        gas_used: int,
        confirmation_time_ms: float,
    ) -> None:
        """
        Log transaction confirmation.
        
        Args:
            tx_hash: Transaction hash
            success: Whether transaction succeeded
            block_number: Block number
            gas_used: Gas used
            confirmation_time_ms: Time to confirmation in milliseconds
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        status = "✓ CONFIRMED" if success else "✗ FAILED"
        
        self.logger.debug(
            f"[{timestamp}] {status}: {tx_hash} | "
            f"Block: #{block_number} | Gas used: {gas_used} | "
            f"Confirmation time: {confirmation_time_ms:.2f}ms"
        )
    
    def log_position_merge(
        self,
        market_id: str,
        amount: Decimal,
        tx_hash: str,
        redeemed_amount: Decimal,
    ) -> None:
        """
        Log position merging.
        
        Validates Requirement 21.7: Log position merging
        
        Args:
            market_id: Market ID
            amount: Amount of positions merged
            tx_hash: Transaction hash
            redeemed_amount: Amount of USDC redeemed
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        self.logger.debug(
            f"[{timestamp}] Merged positions: {market_id} | "
            f"Amount: {self._format_decimal(amount)} | "
            f"TX: {tx_hash} | "
            f"Redeemed: {self._format_decimal(redeemed_amount)} USDC"
        )
    
    def log_balance_update(
        self,
        wallet_type: str,
        old_balance: Decimal,
        new_balance: Decimal,
        change: Decimal,
    ) -> None:
        """
        Log balance update.
        
        Validates Requirement 21.7: Log balance updates
        
        Args:
            wallet_type: Wallet type (EOA/Proxy)
            old_balance: Previous balance
            new_balance: New balance
            change: Balance change
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        change_str = f"+{self._format_decimal(change)}" if change >= 0 else self._format_decimal(change)
        
        self.logger.debug(
            f"[{timestamp}] Balance update ({wallet_type}): "
            f"{self._format_decimal(old_balance)} → {self._format_decimal(new_balance)} "
            f"({change_str})"
        )
    
    def log_api_call(
        self,
        endpoint: str,
        method: str,
        response_time_ms: float,
        status_code: Optional[int] = None,
        success: bool = True,
    ) -> None:
        """
        Log API call with response time.
        
        Validates Requirement 21.7: Log API response times
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            response_time_ms: Response time in milliseconds
            status_code: HTTP status code
            success: Whether call succeeded
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        status = "✓" if success else "✗"
        status_str = f" | Status: {status_code}" if status_code else ""
        
        self.logger.debug(
            f"[{timestamp}] {status} API call: {method} {endpoint} | "
            f"Response time: {response_time_ms:.2f}ms{status_str}"
        )
    
    def log_error_with_full_context(
        self,
        error: Exception,
        operation: str,
        context: Optional[Dict[str, Any]] = None,
        recovery_action: Optional[str] = None,
    ) -> None:
        """
        Log error with full context including stack trace.
        
        Validates Requirement 21.12: Include full context in error logs
        
        Args:
            error: Exception that occurred
            operation: Operation that failed
            context: Optional context dictionary
            recovery_action: Optional recovery action taken
        """
        timestamp = self._get_timestamp_ms()
        
        error_context = {
            "timestamp": timestamp,
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stack_trace": traceback.format_exc(),
            **(context or {}),
        }
        
        if recovery_action:
            error_context["recovery_action"] = recovery_action
        
        log_with_context(
            self.logger,
            "error",
            f"[{timestamp}] ✗ Error in {operation}: {str(error)}",
            error_context,
            exc_info=True
        )
    
    def log_trade_complete(
        self,
        trade_id: str,
        market_id: str,
        strategy: str,
        profit: Decimal,
        gas_cost: Decimal,
        net_profit: Decimal,
        success: bool,
    ) -> None:
        """
        Log completed trade with all details.
        
        Args:
            trade_id: Trade ID
            market_id: Market ID
            strategy: Strategy type
            profit: Gross profit
            gas_cost: Gas cost
            net_profit: Net profit
            success: Whether trade succeeded
        """
        if not self.enabled:
            return
        
        timestamp = self._get_timestamp_ms()
        status = "✓" if success else "✗"
        
        self.logger.debug(
            f"[{timestamp}] {status} Trade complete: {trade_id} | "
            f"Market: {market_id} | Strategy: {strategy} | "
            f"Profit: {self._format_decimal(profit)} | "
            f"Gas: {self._format_decimal(gas_cost)} | "
            f"Net: {self._format_decimal(net_profit)}"
        )


def timed_operation(operation_name: str):
    """
    Decorator to automatically log operation timing.
    
    Args:
        operation_name: Name of the operation
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            debug_logger = DebugLogger()
            debug_logger.log_operation_start(operation_name, {"args": args, "kwargs": kwargs})
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                debug_logger.log_operation_complete(operation_name, result, success=True)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                debug_logger.log_error_with_full_context(
                    e,
                    operation_name,
                    context={"duration_ms": duration_ms}
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            debug_logger = DebugLogger()
            debug_logger.log_operation_start(operation_name, {"args": args, "kwargs": kwargs})
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                debug_logger.log_operation_complete(operation_name, result, success=True)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                debug_logger.log_error_with_full_context(
                    e,
                    operation_name,
                    context={"duration_ms": duration_ms}
                )
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Example usage
if __name__ == "__main__":
    from src.logging_config import setup_logging
    
    # Set up logging
    setup_logging(log_level="DEBUG", enable_console=True)
    
    # Create debug logger
    debug_logger = DebugLogger(enabled=True)
    
    # Test various logging functions
    debug_logger.log_operation_start("test_operation", {"param1": "value1"})
    time.sleep(0.1)
    debug_logger.log_operation_complete("test_operation", result="success")
    
    debug_logger.log_market_scan(47, 142.5, 2)
    debug_logger.log_fee_calculation(Decimal('0.48'), Decimal('0.028'))
    debug_logger.log_ai_safety_check("market_123", True, 234.5)
    debug_logger.log_order_creation("market_123", "YES", Decimal('0.48'), Decimal('1.0'))
    debug_logger.log_transaction_submission("order", "0xabc...def", 45, 100000)
    debug_logger.log_position_merge("market_123", Decimal('1.0'), "0x789...012", Decimal('1.0'))
    debug_logger.log_balance_update("Proxy", Decimal('100.0'), Decimal('101.0'), Decimal('1.0'))
    debug_logger.log_api_call("/markets", "GET", 89.3, 200, True)
    
    # Test error logging
    try:
        raise ValueError("Test error")
    except Exception as e:
        debug_logger.log_error_with_full_context(
            e,
            "test_operation",
            context={"market_id": "market_123"},
            recovery_action="Retry with backoff"
        )
