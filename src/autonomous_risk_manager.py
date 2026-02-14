"""
Autonomous Risk Manager for Polymarket Trading Bot.

Provides fully autonomous risk management with dynamic thresholds that adapt based on performance.
Includes circuit breaker state management, conservative mode, and automatic recovery.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DynamicThresholds:
    """Dynamic risk thresholds that adapt based on performance."""
    portfolio_heat_limit: Decimal  # % of capital that can be deployed
    daily_drawdown_limit: Decimal  # % daily loss before halting
    consecutive_loss_limit: int  # Number of losses before circuit breaker
    per_asset_limit: int  # Max positions per asset
    trailing_stop_activation: Decimal  # % profit to activate trailing stop
    trailing_stop_distance: Decimal  # % drop from peak to trigger exit
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "portfolio_heat_limit": float(self.portfolio_heat_limit),
            "daily_drawdown_limit": float(self.daily_drawdown_limit),
            "consecutive_loss_limit": self.consecutive_loss_limit,
            "per_asset_limit": self.per_asset_limit,
            "trailing_stop_activation": float(self.trailing_stop_activation),
            "trailing_stop_distance": float(self.trailing_stop_distance)
        }


@dataclass
class PerformanceMetrics:
    """Performance tracking for threshold adaptation."""
    win_rate: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    daily_pnl: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    avg_win: Decimal = Decimal('0')
    avg_loss: Decimal = Decimal('0')
    
    def update_win_rate(self):
        """Update win rate based on current trades."""
        if self.total_trades > 0:
            self.win_rate = self.wins / self.total_trades
        else:
            self.win_rate = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "daily_pnl": float(self.daily_pnl),
            "total_pnl": float(self.total_pnl),
            "avg_win": float(self.avg_win),
            "avg_loss": float(self.avg_loss)
        }


@dataclass
class CircuitBreakerState:
    """Circuit breaker state management."""
    is_active: bool = False
    activation_time: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    activation_reason: str = ""
    cooldown_hours: int = 0
    activation_count: int = 0  # Track how many times activated today
    
    def activate(self, reason: str, cooldown_hours: int):
        """Activate circuit breaker."""
        self.is_active = True
        self.activation_time = datetime.now()
        self.cooldown_until = datetime.now() + timedelta(hours=cooldown_hours)
        self.activation_reason = reason
        self.cooldown_hours = cooldown_hours
        self.activation_count += 1
        logger.warning(
            f"Circuit breaker ACTIVATED: {reason} "
            f"(cooldown: {cooldown_hours}h until {self.cooldown_until})"
        )
    
    def check_and_reset(self) -> bool:
        """Check if cooldown expired and reset if so. Returns True if reset."""
        if self.is_active and self.cooldown_until:
            if datetime.now() >= self.cooldown_until:
                logger.info(
                    f"Circuit breaker AUTO-RESET after {self.cooldown_hours}h cooldown "
                    f"(reason was: {self.activation_reason})"
                )
                self.is_active = False
                self.activation_time = None
                self.cooldown_until = None
                self.activation_reason = ""
                self.cooldown_hours = 0
                return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_active": self.is_active,
            "activation_time": self.activation_time.isoformat() if self.activation_time else None,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "activation_reason": self.activation_reason,
            "cooldown_hours": self.cooldown_hours,
            "activation_count": self.activation_count
        }


@dataclass
class ConservativeModeState:
    """Conservative mode state management."""
    is_active: bool = False
    activation_time: Optional[datetime] = None
    activation_balance: Decimal = Decimal('0')
    starting_balance: Decimal = Decimal('0')
    min_confidence_required: Decimal = Decimal('0.80')  # 80% confidence required
    
    def check_activation(self, current_balance: Decimal, starting_balance: Decimal) -> bool:
        """Check if should activate conservative mode (balance < 20% of starting)."""
        threshold = starting_balance * Decimal('0.20')
        if not self.is_active and current_balance < threshold:
            self.is_active = True
            self.activation_time = datetime.now()
            self.activation_balance = current_balance
            self.starting_balance = starting_balance
            logger.warning(
                f"Conservative mode ACTIVATED: balance ${current_balance} < 20% of ${starting_balance}"
            )
            return True
        return False
    
    def check_deactivation(self, current_balance: Decimal) -> bool:
        """Check if should deactivate conservative mode (balance > 50% of starting)."""
        if self.is_active:
            threshold = self.starting_balance * Decimal('0.50')
            if current_balance >= threshold:
                logger.info(
                    f"Conservative mode DEACTIVATED: balance ${current_balance} recovered to 50% of ${self.starting_balance}"
                )
                self.is_active = False
                self.activation_time = None
                return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_active": self.is_active,
            "activation_time": self.activation_time.isoformat() if self.activation_time else None,
            "activation_balance": float(self.activation_balance),
            "starting_balance": float(self.starting_balance),
            "min_confidence_required": float(self.min_confidence_required)
        }


class AutonomousRiskManager:
    """
    Fully autonomous risk management system with dynamic thresholds.
    
    Key Features:
    - Dynamic threshold adaptation based on performance
    - Automatic circuit breaker activation and reset
    - Conservative mode for capital preservation
    - Trailing stop-loss management
    - Daily automatic reset
    - Performance tracking for learning
    """
    
    # Base thresholds (will be adapted dynamically)
    BASE_PORTFOLIO_HEAT = Decimal('0.50')  # 50% base
    BASE_DAILY_DRAWDOWN = Decimal('0.15')  # 15% base
    BASE_CONSECUTIVE_LOSSES = 5  # 5 losses base
    BASE_PER_ASSET_LIMIT = 2  # 2 positions per asset base
    BASE_TRAILING_ACTIVATION = Decimal('0.005')  # 0.5% profit base
    BASE_TRAILING_DISTANCE = Decimal('0.02')  # 2% drop base
    
    def __init__(
        self,
        starting_balance: Decimal,
        current_balance: Decimal
    ):
        """
        Initialize Autonomous Risk Manager.
        
        Args:
            starting_balance: Initial starting balance
            current_balance: Current balance
        """
        self.starting_balance = starting_balance
        self.current_balance = current_balance
        
        # Initialize dynamic thresholds with base values
        self.thresholds = DynamicThresholds(
            portfolio_heat_limit=self.BASE_PORTFOLIO_HEAT,
            daily_drawdown_limit=self.BASE_DAILY_DRAWDOWN,
            consecutive_loss_limit=self.BASE_CONSECUTIVE_LOSSES,
            per_asset_limit=self.BASE_PER_ASSET_LIMIT,
            trailing_stop_activation=self.BASE_TRAILING_ACTIVATION,
            trailing_stop_distance=self.BASE_TRAILING_DISTANCE
        )
        
        # Initialize performance tracking
        self.performance = PerformanceMetrics()
        
        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreakerState()
        
        # Initialize conservative mode
        self.conservative_mode = ConservativeModeState()
        self.conservative_mode.starting_balance = starting_balance
        
        # Daily reset tracking
        self._daily_reset_time = self._get_next_reset_time()
        
        # Position tracking by asset
        self._positions_by_asset: Dict[str, int] = {}  # asset -> count
        
        logger.info(
            f"Autonomous Risk Manager initialized: "
            f"balance=${current_balance}, "
            f"thresholds={self.thresholds.to_dict()}"
        )
    
    def adapt_thresholds(self):
        """
        Adapt risk thresholds based on current performance.
        
        Adaptation rules:
        - High win rate (>70%): Increase portfolio heat, reduce drawdown limit
        - Low win rate (<50%): Decrease portfolio heat, increase drawdown limit
        - High confidence: Reduce consecutive loss limit (more aggressive)
        - Low confidence: Increase consecutive loss limit (more conservative)
        """
        win_rate = self.performance.win_rate
        
        # Adapt portfolio heat based on win rate (50-200% of base)
        if win_rate >= 0.70:
            # High win rate: Allow more heat
            heat_multiplier = Decimal('2.0')  # 200%
        elif win_rate >= 0.60:
            heat_multiplier = Decimal('1.5')  # 150%
        elif win_rate >= 0.50:
            heat_multiplier = Decimal('1.0')  # 100%
        else:
            # Low win rate: Reduce heat
            heat_multiplier = Decimal('0.5')  # 50%
        
        new_heat = self.BASE_PORTFOLIO_HEAT * heat_multiplier
        
        # Adapt daily drawdown based on performance (10-20%)
        if win_rate >= 0.70:
            new_drawdown = Decimal('0.20')  # Allow more drawdown when winning
        elif win_rate >= 0.60:
            new_drawdown = Decimal('0.15')
        else:
            new_drawdown = Decimal('0.10')  # Tighter when losing
        
        # Adapt consecutive loss limit based on confidence (3-7)
        if win_rate >= 0.70:
            new_loss_limit = 7  # More tolerance when winning
        elif win_rate >= 0.60:
            new_loss_limit = 5
        else:
            new_loss_limit = 3  # Less tolerance when losing
        
        # Adapt per-asset limit based on volatility (1-3 positions)
        # For now, use win rate as proxy
        if win_rate >= 0.70:
            new_asset_limit = 3
        elif win_rate >= 0.60:
            new_asset_limit = 2
        else:
            new_asset_limit = 1
        
        # Log changes if significant
        if (abs(new_heat - self.thresholds.portfolio_heat_limit) > Decimal('0.05') or
            abs(new_drawdown - self.thresholds.daily_drawdown_limit) > Decimal('0.02') or
            new_loss_limit != self.thresholds.consecutive_loss_limit):
            
            logger.info(
                f"Thresholds adapted (win_rate={win_rate:.1%}): "
                f"heat {self.thresholds.portfolio_heat_limit:.1%} -> {new_heat:.1%}, "
                f"drawdown {self.thresholds.daily_drawdown_limit:.1%} -> {new_drawdown:.1%}, "
                f"loss_limit {self.thresholds.consecutive_loss_limit} -> {new_loss_limit}"
            )
        
        # Update thresholds
        self.thresholds.portfolio_heat_limit = new_heat
        self.thresholds.daily_drawdown_limit = new_drawdown
        self.thresholds.consecutive_loss_limit = new_loss_limit
        self.thresholds.per_asset_limit = new_asset_limit
    
    def record_trade_outcome(self, profit: Decimal, asset: str):
        """
        Record trade outcome and update performance metrics.
        
        Args:
            profit: Realized P&L (positive or negative)
            asset: Asset traded (BTC, ETH, SOL, XRP)
        """
        self.performance.total_trades += 1
        self.performance.daily_pnl += profit
        self.performance.total_pnl += profit
        self.current_balance += profit
        
        if profit >= 0:
            # Win
            self.performance.wins += 1
            self.performance.consecutive_wins += 1
            self.performance.consecutive_losses = 0
            
            # Update average win
            if self.performance.wins > 0:
                self.performance.avg_win = (
                    (self.performance.avg_win * (self.performance.wins - 1) + profit) /
                    self.performance.wins
                )
        else:
            # Loss
            self.performance.losses += 1
            self.performance.consecutive_losses += 1
            self.performance.consecutive_wins = 0
            
            # Update average loss
            if self.performance.losses > 0:
                self.performance.avg_loss = (
                    (self.performance.avg_loss * (self.performance.losses - 1) + abs(profit)) /
                    self.performance.losses
                )
        
        # Update win rate
        self.performance.update_win_rate()
        
        # Decrement position count for asset
        if asset in self._positions_by_asset:
            self._positions_by_asset[asset] = max(0, self._positions_by_asset[asset] - 1)
        
        # Check circuit breaker conditions
        self._check_circuit_breaker()
        
        # Check conservative mode
        self.conservative_mode.check_activation(self.current_balance, self.starting_balance)
        self.conservative_mode.check_deactivation(self.current_balance)
        
        # Adapt thresholds based on new performance
        if self.performance.total_trades % 5 == 0:  # Adapt every 5 trades
            self.adapt_thresholds()
        
        logger.info(
            f"Trade recorded: profit=${profit}, asset={asset}, "
            f"win_rate={self.performance.win_rate:.1%}, "
            f"consecutive_losses={self.performance.consecutive_losses}"
        )
    
    def add_position(self, asset: str):
        """
        Track new position for asset.
        
        Args:
            asset: Asset (BTC, ETH, SOL, XRP)
        """
        if asset not in self._positions_by_asset:
            self._positions_by_asset[asset] = 0
        self._positions_by_asset[asset] += 1
    
    def can_add_position(self, asset: str) -> tuple[bool, str]:
        """
        Check if can add another position for this asset.
        
        Args:
            asset: Asset to check
            
        Returns:
            (can_add, reason) tuple
        """
        # Check circuit breaker
        if self.circuit_breaker.is_active:
            return False, f"Circuit breaker active: {self.circuit_breaker.activation_reason}"
        
        # Check per-asset limit
        current_count = self._positions_by_asset.get(asset, 0)
        if current_count >= self.thresholds.per_asset_limit:
            return False, f"Per-asset limit reached: {current_count}/{self.thresholds.per_asset_limit} for {asset}"
        
        return True, ""
    
    def _check_circuit_breaker(self):
        """Check if circuit breaker should be activated."""
        # Check if already active and should reset
        if self.circuit_breaker.check_and_reset():
            return
        
        # Don't activate if already active
        if self.circuit_breaker.is_active:
            return
        
        # Check consecutive losses
        if self.performance.consecutive_losses >= self.thresholds.consecutive_loss_limit:
            # Calculate cooldown based on severity (1-6 hours)
            if self.performance.consecutive_losses >= 7:
                cooldown_hours = 6
            elif self.performance.consecutive_losses >= 5:
                cooldown_hours = 3
            else:
                cooldown_hours = 1
            
            self.circuit_breaker.activate(
                f"{self.performance.consecutive_losses} consecutive losses",
                cooldown_hours
            )
            return  # Only activate once per check
        
        # Check daily drawdown
        if self.starting_balance > 0:
            drawdown = abs(min(self.performance.daily_pnl, Decimal('0'))) / self.starting_balance
            if drawdown >= self.thresholds.daily_drawdown_limit:
                self.circuit_breaker.activate(
                    f"Daily drawdown {drawdown:.1%} >= {self.thresholds.daily_drawdown_limit:.1%}",
                    4  # 4 hour cooldown for drawdown
                )
    
    def check_daily_reset(self):
        """Check if should perform daily reset."""
        if datetime.now() >= self._daily_reset_time:
            logger.info(
                f"Daily reset: trades={self.performance.total_trades}, "
                f"win_rate={self.performance.win_rate:.1%}, "
                f"daily_pnl=${self.performance.daily_pnl}"
            )
            
            # Reset daily counters
            self.performance.daily_pnl = Decimal('0')
            self.performance.consecutive_losses = 0
            self.performance.consecutive_wins = 0
            
            # Update starting balance for new day
            self.starting_balance = self.current_balance
            
            # Reset circuit breaker activation count
            self.circuit_breaker.activation_count = 0
            
            # Check if should exit conservative mode
            self.conservative_mode.check_deactivation(self.current_balance)
            
            # Set next reset time
            self._daily_reset_time = self._get_next_reset_time()
    
    @staticmethod
    def _get_next_reset_time() -> datetime:
        """Get next midnight UTC."""
        now = datetime.utcnow()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return tomorrow
    
    def get_state(self) -> Dict[str, Any]:
        """Get complete state for serialization."""
        return {
            "starting_balance": float(self.starting_balance),
            "current_balance": float(self.current_balance),
            "thresholds": self.thresholds.to_dict(),
            "performance": self.performance.to_dict(),
            "circuit_breaker": self.circuit_breaker.to_dict(),
            "conservative_mode": self.conservative_mode.to_dict(),
            "positions_by_asset": self._positions_by_asset.copy(),
            "daily_reset_time": self._daily_reset_time.isoformat()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for monitoring."""
        return {
            "balance": float(self.current_balance),
            "win_rate": self.performance.win_rate,
            "total_trades": self.performance.total_trades,
            "daily_pnl": float(self.performance.daily_pnl),
            "total_pnl": float(self.performance.total_pnl),
            "consecutive_losses": self.performance.consecutive_losses,
            "circuit_breaker_active": self.circuit_breaker.is_active,
            "circuit_breaker_reason": self.circuit_breaker.activation_reason,
            "conservative_mode_active": self.conservative_mode.is_active,
            "thresholds": self.thresholds.to_dict(),
            "positions_by_asset": self._positions_by_asset.copy()
        }


@dataclass
class RecoveryAttempt:
    """Track a recovery attempt."""
    timestamp: datetime
    error_type: str
    error_message: str
    attempt_number: int
    backoff_delay: float
    success: bool = False


class AutoRecoverySystem:
    """
    Automatic recovery system for handling errors autonomously.
    
    Handles:
    - API errors (reconnect with exponential backoff)
    - Balance errors (refresh balance)
    - WebSocket errors (reconnect with exponential backoff)
    
    Uses exponential backoff: 10s, 30s, 60s
    Logs all recovery attempts for monitoring.
    
    Validates Requirement 7.12: Auto-recover from anomalies (API errors, network issues)
    """
    
    # Backoff delays in seconds
    BACKOFF_DELAYS = [10, 30, 60]  # 10s, 30s, 60s
    MAX_ATTEMPTS = 3  # Maximum recovery attempts before giving up
    
    def __init__(self):
        """Initialize auto-recovery system."""
        self._recovery_history: list[RecoveryAttempt] = []
        self._api_attempt_count = 0
        self._balance_attempt_count = 0
        self._websocket_attempt_count = 0
        
        logger.info("Auto-recovery system initialized with exponential backoff: 10s, 30s, 60s")
    
    async def recover_from_api_error(
        self,
        error: Exception,
        reconnect_func,
        context: str = ""
    ) -> bool:
        """
        Attempt recovery from API error with exponential backoff.
        
        Args:
            error: The exception that occurred
            reconnect_func: Async function to call for reconnection
            context: Additional context about the error
            
        Returns:
            True if recovery successful, False otherwise
        """
        self._api_attempt_count += 1
        attempt_number = min(self._api_attempt_count, self.MAX_ATTEMPTS)
        backoff_delay = self.BACKOFF_DELAYS[attempt_number - 1]
        
        logger.warning(
            f"API error detected (attempt {attempt_number}/{self.MAX_ATTEMPTS}): {error} "
            f"[{context}] - attempting recovery in {backoff_delay}s"
        )
        
        # Record attempt
        attempt = RecoveryAttempt(
            timestamp=datetime.now(),
            error_type="API_ERROR",
            error_message=str(error),
            attempt_number=attempt_number,
            backoff_delay=backoff_delay
        )
        
        # Wait with exponential backoff
        await asyncio.sleep(backoff_delay)
        
        # Attempt reconnection
        try:
            await reconnect_func()
            attempt.success = True
            self._api_attempt_count = 0  # Reset on success
            logger.info(f"✅ API recovery successful after {backoff_delay}s backoff")
            self._recovery_history.append(attempt)
            return True
        except Exception as e:
            attempt.success = False
            logger.error(f"❌ API recovery failed: {e}")
            self._recovery_history.append(attempt)
            
            # Check if max attempts reached
            if self._api_attempt_count >= self.MAX_ATTEMPTS:
                logger.critical(
                    f"API recovery failed after {self.MAX_ATTEMPTS} attempts - manual intervention required"
                )
                self._api_attempt_count = 0  # Reset for next error
            
            return False
    
    async def recover_from_balance_error(
        self,
        error: Exception,
        refresh_func,
        context: str = ""
    ) -> bool:
        """
        Attempt recovery from balance error by refreshing balance.
        
        Args:
            error: The exception that occurred
            refresh_func: Async function to call for balance refresh
            context: Additional context about the error
            
        Returns:
            True if recovery successful, False otherwise
        """
        self._balance_attempt_count += 1
        attempt_number = min(self._balance_attempt_count, self.MAX_ATTEMPTS)
        backoff_delay = self.BACKOFF_DELAYS[attempt_number - 1]
        
        logger.warning(
            f"Balance error detected (attempt {attempt_number}/{self.MAX_ATTEMPTS}): {error} "
            f"[{context}] - attempting refresh in {backoff_delay}s"
        )
        
        # Record attempt
        attempt = RecoveryAttempt(
            timestamp=datetime.now(),
            error_type="BALANCE_ERROR",
            error_message=str(error),
            attempt_number=attempt_number,
            backoff_delay=backoff_delay
        )
        
        # Wait with exponential backoff
        await asyncio.sleep(backoff_delay)
        
        # Attempt balance refresh
        try:
            await refresh_func()
            attempt.success = True
            self._balance_attempt_count = 0  # Reset on success
            logger.info(f"✅ Balance recovery successful after {backoff_delay}s backoff")
            self._recovery_history.append(attempt)
            return True
        except Exception as e:
            attempt.success = False
            logger.error(f"❌ Balance recovery failed: {e}")
            self._recovery_history.append(attempt)
            
            # Check if max attempts reached
            if self._balance_attempt_count >= self.MAX_ATTEMPTS:
                logger.critical(
                    f"Balance recovery failed after {self.MAX_ATTEMPTS} attempts - manual intervention required"
                )
                self._balance_attempt_count = 0  # Reset for next error
            
            return False
    
    async def recover_from_websocket_error(
        self,
        error: Exception,
        reconnect_func,
        context: str = ""
    ) -> bool:
        """
        Attempt recovery from WebSocket error with exponential backoff.
        
        Args:
            error: The exception that occurred
            reconnect_func: Async function to call for reconnection
            context: Additional context about the error
            
        Returns:
            True if recovery successful, False otherwise
        """
        self._websocket_attempt_count += 1
        attempt_number = min(self._websocket_attempt_count, self.MAX_ATTEMPTS)
        backoff_delay = self.BACKOFF_DELAYS[attempt_number - 1]
        
        logger.warning(
            f"WebSocket error detected (attempt {attempt_number}/{self.MAX_ATTEMPTS}): {error} "
            f"[{context}] - attempting reconnection in {backoff_delay}s"
        )
        
        # Record attempt
        attempt = RecoveryAttempt(
            timestamp=datetime.now(),
            error_type="WEBSOCKET_ERROR",
            error_message=str(error),
            attempt_number=attempt_number,
            backoff_delay=backoff_delay
        )
        
        # Wait with exponential backoff
        await asyncio.sleep(backoff_delay)
        
        # Attempt reconnection
        try:
            await reconnect_func()
            attempt.success = True
            self._websocket_attempt_count = 0  # Reset on success
            logger.info(f"✅ WebSocket recovery successful after {backoff_delay}s backoff")
            self._recovery_history.append(attempt)
            return True
        except Exception as e:
            attempt.success = False
            logger.error(f"❌ WebSocket recovery failed: {e}")
            self._recovery_history.append(attempt)
            
            # Check if max attempts reached
            if self._websocket_attempt_count >= self.MAX_ATTEMPTS:
                logger.critical(
                    f"WebSocket recovery failed after {self.MAX_ATTEMPTS} attempts - manual intervention required"
                )
                self._websocket_attempt_count = 0  # Reset for next error
            
            return False
    
    def get_recovery_statistics(self) -> Dict[str, Any]:
        """
        Get recovery statistics for monitoring.
        
        Returns:
            Dictionary with recovery statistics
        """
        total_attempts = len(self._recovery_history)
        successful_attempts = sum(1 for a in self._recovery_history if a.success)
        failed_attempts = total_attempts - successful_attempts
        
        # Group by error type
        by_type = {}
        for attempt in self._recovery_history:
            if attempt.error_type not in by_type:
                by_type[attempt.error_type] = {"total": 0, "successful": 0, "failed": 0}
            by_type[attempt.error_type]["total"] += 1
            if attempt.success:
                by_type[attempt.error_type]["successful"] += 1
            else:
                by_type[attempt.error_type]["failed"] += 1
        
        # Get recent attempts (last 10)
        recent_attempts = [
            {
                "timestamp": a.timestamp.isoformat(),
                "error_type": a.error_type,
                "error_message": a.error_message,
                "attempt_number": a.attempt_number,
                "backoff_delay": a.backoff_delay,
                "success": a.success
            }
            for a in self._recovery_history[-10:]
        ]
        
        return {
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "failed_attempts": failed_attempts,
            "success_rate": successful_attempts / total_attempts if total_attempts > 0 else 0.0,
            "by_type": by_type,
            "recent_attempts": recent_attempts,
            "current_api_attempts": self._api_attempt_count,
            "current_balance_attempts": self._balance_attempt_count,
            "current_websocket_attempts": self._websocket_attempt_count
        }
    
    def reset_attempt_counters(self):
        """Reset all attempt counters (useful for testing or manual reset)."""
        self._api_attempt_count = 0
        self._balance_attempt_count = 0
        self._websocket_attempt_count = 0
        logger.info("Recovery attempt counters reset")
    
    def clear_history(self):
        """Clear recovery history (useful for testing or cleanup)."""
        self._recovery_history.clear()
        logger.info("Recovery history cleared")
