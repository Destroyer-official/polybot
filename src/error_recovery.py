"""
Error recovery utilities for the Polymarket Arbitrage Bot.

This module provides decorators and utilities for handling errors gracefully,
including exponential backoff retry logic, RPC failover, gas price escalation,
and circuit breaker pattern implementation.
"""

import asyncio
import functools
import logging
import time
from typing import Callable, Optional, Type, Tuple, Any
from decimal import Decimal

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator that retries a function with exponential backoff.
    
    Implements exponential backoff retry pattern with configurable parameters.
    Delays follow the pattern: base_delay, base_delay * 2, base_delay * 4, base_delay * 8, ...
    up to max_delay.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 5)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential calculation (default: 2.0)
        exceptions: Tuple of exception types to catch and retry (default: all exceptions)
    
    Returns:
        Decorated function that retries on failure with exponential backoff
    
    Example:
        @retry_with_backoff(max_attempts=5, base_delay=1.0)
        async def fetch_data():
            return await api.get_data()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}",
                            extra={
                                "function": func.__name__,
                                "attempts": max_attempts,
                                "error": str(e)
                            }
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {delay:.1f}s: {e}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    
                    await asyncio.sleep(delay)
            
            # Should never reach here, but just in case
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}",
                            extra={
                                "function": func.__name__,
                                "attempts": max_attempts,
                                "error": str(e)
                            }
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {delay:.1f}s: {e}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    
                    time.sleep(delay)
            
            # Should never reach here, but just in case
            raise last_exception
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RPCEndpointManager:
    """
    Manages RPC endpoint failover for blockchain connectivity.
    
    Automatically switches to backup RPC endpoints when the primary endpoint
    becomes unavailable, ensuring continuous blockchain connectivity.
    """
    
    def __init__(self, primary_url: str, backup_urls: list[str]):
        """
        Initialize RPC endpoint manager.
        
        Args:
            primary_url: Primary RPC endpoint URL
            backup_urls: List of backup RPC endpoint URLs
        """
        self.primary_url = primary_url
        self.backup_urls = backup_urls
        self.current_url = primary_url
        self.current_index = -1  # -1 indicates primary
        self.failed_endpoints = set()
        
        logger.info(
            f"Initialized RPC manager with primary: {primary_url}, "
            f"backups: {len(backup_urls)}"
        )
    
    def get_current_endpoint(self) -> str:
        """Get the currently active RPC endpoint URL."""
        return self.current_url
    
    def mark_endpoint_failed(self, url: str) -> None:
        """
        Mark an endpoint as failed.
        
        Args:
            url: The RPC endpoint URL that failed
        """
        self.failed_endpoints.add(url)
        logger.warning(
            f"Marked RPC endpoint as failed: {url}",
            extra={"failed_endpoint": url, "total_failed": len(self.failed_endpoints)}
        )
    
    def failover_to_next(self) -> Optional[str]:
        """
        Failover to the next available RPC endpoint.
        
        Returns:
            The next available RPC endpoint URL, or None if all endpoints have failed
        """
        # Try backup endpoints in order
        for i, backup_url in enumerate(self.backup_urls):
            if backup_url not in self.failed_endpoints:
                self.current_url = backup_url
                self.current_index = i
                logger.warning(
                    f"Failed over to backup RPC endpoint: {backup_url}",
                    extra={
                        "new_endpoint": backup_url,
                        "backup_index": i,
                        "failed_count": len(self.failed_endpoints)
                    }
                )
                return backup_url
        
        # All endpoints have failed
        logger.critical(
            "All RPC endpoints have failed!",
            extra={
                "primary": self.primary_url,
                "backups": self.backup_urls,
                "failed_count": len(self.failed_endpoints)
            }
        )
        return None
    
    def reset_failed_endpoints(self) -> None:
        """Reset the failed endpoints set, allowing retry of previously failed endpoints."""
        logger.info(
            f"Resetting {len(self.failed_endpoints)} failed endpoints",
            extra={"failed_endpoints": list(self.failed_endpoints)}
        )
        self.failed_endpoints.clear()
        self.current_url = self.primary_url
        self.current_index = -1
    
    def is_primary_active(self) -> bool:
        """Check if the primary endpoint is currently active."""
        return self.current_index == -1


class GasPriceEscalator:
    """
    Manages gas price escalation for transaction retries.
    
    Automatically increases gas prices when transactions fail due to insufficient gas,
    ensuring transactions eventually get mined during network congestion.
    """
    
    def __init__(self, escalation_factor: float = 1.1, max_escalations: int = 5):
        """
        Initialize gas price escalator.
        
        Args:
            escalation_factor: Factor to multiply gas price by on each escalation (default: 1.1 = 10% increase)
            max_escalations: Maximum number of escalations allowed (default: 5)
        """
        self.escalation_factor = Decimal(str(escalation_factor))
        self.max_escalations = max_escalations
        self.escalation_history = {}  # tx_hash -> escalation_count
        
        logger.info(
            f"Initialized gas price escalator: factor={escalation_factor}, "
            f"max_escalations={max_escalations}"
        )
    
    def escalate_gas_price(self, current_gas_price: int, tx_hash: Optional[str] = None) -> int:
        """
        Calculate escalated gas price.
        
        Args:
            current_gas_price: Current gas price in wei
            tx_hash: Optional transaction hash for tracking escalation count
        
        Returns:
            Escalated gas price in wei
        
        Raises:
            ValueError: If maximum escalations reached for this transaction
        """
        # Track escalation count if tx_hash provided
        if tx_hash:
            escalation_count = self.escalation_history.get(tx_hash, 0)
            
            if escalation_count >= self.max_escalations:
                raise ValueError(
                    f"Maximum gas escalations ({self.max_escalations}) reached for tx {tx_hash}"
                )
            
            self.escalation_history[tx_hash] = escalation_count + 1
        
        # Calculate new gas price
        current_price_decimal = Decimal(str(current_gas_price))
        new_gas_price = int(current_price_decimal * self.escalation_factor)
        
        logger.info(
            f"Escalating gas price: {current_gas_price} -> {new_gas_price} wei "
            f"({float(self.escalation_factor):.1%} increase)",
            extra={
                "old_gas_price": current_gas_price,
                "new_gas_price": new_gas_price,
                "escalation_factor": float(self.escalation_factor),
                "tx_hash": tx_hash,
                "escalation_count": self.escalation_history.get(tx_hash, 0) if tx_hash else None
            }
        )
        
        return new_gas_price
    
    def reset_escalation(self, tx_hash: str) -> None:
        """
        Reset escalation count for a transaction.
        
        Args:
            tx_hash: Transaction hash to reset
        """
        if tx_hash in self.escalation_history:
            del self.escalation_history[tx_hash]
            logger.debug(f"Reset escalation count for tx {tx_hash}")
    
    def get_escalation_count(self, tx_hash: str) -> int:
        """
        Get the current escalation count for a transaction.
        
        Args:
            tx_hash: Transaction hash
        
        Returns:
            Number of times gas has been escalated for this transaction
        """
        return self.escalation_history.get(tx_hash, 0)


class CircuitBreaker:
    """
    Implements circuit breaker pattern to halt trading during system failures.
    
    Tracks consecutive failures and opens the circuit after a threshold is reached,
    preventing further trading until manual reset. This protects against cascading
    failures and allows time for investigation.
    """
    
    def __init__(self, failure_threshold: int = 10):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of consecutive failures before opening circuit (default: 10)
        """
        self.failure_threshold = failure_threshold
        self.consecutive_failures = 0
        self.is_open = False
        self.last_failure_time = None
        self.failure_reasons = []
        
        logger.info(f"Initialized circuit breaker with threshold: {failure_threshold}")
    
    def record_success(self) -> None:
        """Record a successful operation, resetting the failure counter."""
        if self.consecutive_failures > 0:
            logger.info(
                f"Operation succeeded, resetting failure counter from {self.consecutive_failures}",
                extra={"previous_failures": self.consecutive_failures}
            )
        
        self.consecutive_failures = 0
        self.failure_reasons.clear()
    
    def record_failure(self, reason: str) -> None:
        """
        Record a failed operation.
        
        Args:
            reason: Description of why the operation failed
        """
        self.consecutive_failures += 1
        self.last_failure_time = time.time()
        self.failure_reasons.append(reason)
        
        # Keep only last 10 failure reasons
        if len(self.failure_reasons) > 10:
            self.failure_reasons = self.failure_reasons[-10:]
        
        logger.warning(
            f"Recorded failure ({self.consecutive_failures}/{self.failure_threshold}): {reason}",
            extra={
                "consecutive_failures": self.consecutive_failures,
                "threshold": self.failure_threshold,
                "reason": reason
            }
        )
        
        # Check if we should open the circuit
        if self.consecutive_failures >= self.failure_threshold and not self.is_open:
            self.open_circuit()
    
    def open_circuit(self) -> None:
        """Open the circuit breaker, halting all trading operations."""
        self.is_open = True
        
        logger.critical(
            f"CIRCUIT BREAKER OPENED after {self.consecutive_failures} consecutive failures!",
            extra={
                "consecutive_failures": self.consecutive_failures,
                "threshold": self.failure_threshold,
                "recent_failures": self.failure_reasons,
                "last_failure_time": self.last_failure_time
            }
        )
    
    def close_circuit(self) -> None:
        """
        Manually close the circuit breaker, allowing trading to resume.
        
        This should only be called after investigating and resolving the underlying issues.
        """
        logger.warning(
            "Circuit breaker manually closed - resuming operations",
            extra={
                "previous_failures": self.consecutive_failures,
                "was_open_for_seconds": time.time() - self.last_failure_time if self.last_failure_time else 0
            }
        )
        
        self.is_open = False
        self.consecutive_failures = 0
        self.failure_reasons.clear()
        self.last_failure_time = None
    
    def check_circuit(self) -> None:
        """
        Check if circuit is open and raise exception if it is.
        
        Raises:
            RuntimeError: If circuit breaker is open
        """
        if self.is_open:
            raise RuntimeError(
                f"Circuit breaker is OPEN - trading halted after {self.consecutive_failures} "
                f"consecutive failures. Manual reset required."
            )
    
    def get_status(self) -> dict:
        """
        Get current circuit breaker status.
        
        Returns:
            Dictionary containing circuit breaker status information
        """
        return {
            "is_open": self.is_open,
            "consecutive_failures": self.consecutive_failures,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "recent_failures": self.failure_reasons[-5:] if self.failure_reasons else []
        }
