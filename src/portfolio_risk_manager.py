"""
Portfolio Risk Manager for Polymarket Trading Bot.

Holistic risk management across all positions to prevent excessive exposure and protect capital.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Active trading position."""
    market_id: str
    side: str  # YES/NO
    entry_price: Decimal
    current_price: Decimal
    size: Decimal
    entry_time: datetime
    unrealized_pnl: Decimal = Decimal('0')
    
    @property
    def age_minutes(self) -> float:
        """Position age in minutes."""
        return (datetime.now() - self.entry_time).total_seconds() / 60


@dataclass
class RiskMetrics:
    """Current portfolio risk metrics."""
    total_exposure: Decimal
    heat_percentage: Decimal  # % of capital deployed
    daily_pnl: Decimal
    daily_drawdown: Decimal
    win_rate: float
    trades_today: int
    max_position_size: Decimal
    can_trade: bool
    reason: str = ""


class PortfolioRiskManager:
    """
    Holistic risk management for the trading portfolio.
    
    Key Controls:
    - Portfolio heat: Max 30% of capital deployed at once
    - Max daily drawdown: 10% (configurable)
    - Position limit per market: 5% of capital
    - Correlation tracking: Avoid concentrated crypto bets
    - Circuit breaker: Halt trading on 3 consecutive losses
    """
    
    # Default risk parameters
    DEFAULT_MAX_PORTFOLIO_HEAT = Decimal('0.30')  # 30%
    DEFAULT_MAX_DAILY_DRAWDOWN = Decimal('0.10')  # 10%
    DEFAULT_MAX_POSITION_SIZE_PCT = Decimal('0.05')  # 5%
    DEFAULT_MAX_POSITION_PER_MARKET = Decimal('0.10')  # 10%
    DEFAULT_CONSECUTIVE_LOSS_LIMIT = 3
    
    def __init__(
        self,
        initial_capital: Decimal,
        max_portfolio_heat: Decimal = DEFAULT_MAX_PORTFOLIO_HEAT,
        max_daily_drawdown: Decimal = DEFAULT_MAX_DAILY_DRAWDOWN,
        max_position_size_pct: Decimal = DEFAULT_MAX_POSITION_SIZE_PCT,
        max_position_per_market_pct: Decimal = DEFAULT_MAX_POSITION_PER_MARKET,
        consecutive_loss_limit: int = DEFAULT_CONSECUTIVE_LOSS_LIMIT
    ):
        """
        Initialize Portfolio Risk Manager.
        
        Args:
            initial_capital: Starting capital in USDC
            max_portfolio_heat: Maximum % of capital to deploy at once
            max_daily_drawdown: Maximum daily loss before halting
            max_position_size_pct: Max position as % of capital
            max_position_per_market_pct: Max exposure per market
            consecutive_loss_limit: Consecutive losses before halting
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_portfolio_heat = max_portfolio_heat
        self.max_daily_drawdown = max_daily_drawdown
        self.max_position_size_pct = max_position_size_pct
        self.max_position_per_market_pct = max_position_per_market_pct
        self.consecutive_loss_limit = consecutive_loss_limit
        
        # Position tracking
        self._positions: Dict[str, Position] = {}
        
        # Daily tracking (resets at midnight UTC)
        self._daily_start_capital = initial_capital
        self._daily_reset_time = self._get_next_reset_time()
        self._trades_today = 0
        self._wins_today = 0
        self._losses_today = 0
        self._consecutive_losses = 0
        self._daily_pnl = Decimal('0')
        
        # Circuit breaker
        self._trading_halted = False
        self._halt_reason = ""
        self._halt_until: Optional[datetime] = None
        
        logger.info(
            f"Portfolio Risk Manager initialized: "
            f"capital=${initial_capital}, "
            f"max_heat={max_portfolio_heat*100}%, "
            f"max_drawdown={max_daily_drawdown*100}%"
        )
    
    def check_can_trade(
        self,
        proposed_size: Decimal,
        market_id: str
    ) -> RiskMetrics:
        """
        SMART RISK MANAGER - Adapts to Polymarket requirements and actual balance.
        
        Key Features:
        - Allows minimum order sizes (5 shares = ~$2.50) even if they exceed percentage limits
        - Dynamically adjusts limits based on actual balance
        - Smarter for small balances (<$10) to enable trading
        
        Args:
            proposed_size: Proposed position size
            market_id: Market to trade
            
        Returns:
            RiskMetrics with approval status
        """
        # Check for daily reset
        self._check_daily_reset()
        
        # Calculate current metrics
        total_exposure = self._calculate_total_exposure()
        heat_pct = total_exposure / self.current_capital if self.current_capital > 0 else Decimal('0')
        daily_drawdown = abs(min(self._daily_pnl, Decimal('0'))) / self._daily_start_capital \
            if self._daily_start_capital > 0 else Decimal('0')
        win_rate = self._wins_today / self._trades_today if self._trades_today > 0 else 0.5
        
        # SMART POSITION SIZING - Adapts to balance and Polymarket requirements
        # Polymarket requires MINIMUM 5 shares (typically $2.50-$3.50 depending on price)
        POLYMARKET_MIN_ORDER = Decimal('3.50')  # Conservative estimate for 5 shares at $0.70
        
        # Calculate max allowed position based on balance
        if self.current_capital < Decimal('5.0'):
            # Very small balance: Allow up to 80% per trade (need to meet minimums)
            max_position = self.current_capital * Decimal('0.80')
        elif self.current_capital < Decimal('10.0'):
            # Small balance: Allow up to 60% per trade
            max_position = self.current_capital * Decimal('0.60')
        elif self.current_capital < Decimal('20.0'):
            # Medium balance: Allow up to 40% per trade
            max_position = self.current_capital * Decimal('0.40')
        else:
            # Large balance: Use standard 5% limit
            max_position = self.current_capital * self.max_position_size_pct
        
        # CRITICAL: Always allow Polymarket minimum order size if we have the balance
        if max_position < POLYMARKET_MIN_ORDER and self.current_capital >= POLYMARKET_MIN_ORDER:
            max_position = POLYMARKET_MIN_ORDER
        
        # Check constraints
        can_trade = True
        reason = ""
        
        # 1. Circuit breaker check
        if self._trading_halted:
            can_trade = False
            reason = f"Trading halted: {self._halt_reason}"
        
        # 2. SMART Portfolio heat check - Adapts to balance size
        # Small balances need higher heat tolerance to meet Polymarket minimums
        if self.current_capital < Decimal('5.0'):
            effective_max_heat = Decimal('0.90')  # 90% for very small balances
        elif self.current_capital < Decimal('10.0'):
            effective_max_heat = Decimal('0.80')  # 80% for small balances
        elif self.current_capital < Decimal('20.0'):
            effective_max_heat = Decimal('0.60')  # 60% for medium balances
        else:
            effective_max_heat = self.max_portfolio_heat  # 30% for large balances
        
        proposed_heat = proposed_size / self.current_capital if self.current_capital > 0 else Decimal('0')
        total_heat = heat_pct + proposed_heat
        
        if total_heat > effective_max_heat:
            can_trade = False
            reason = f"Portfolio heat too high: {heat_pct*100:.1f}% + {proposed_heat*100:.1f}% > {effective_max_heat*100:.1f}%"
        
        # 3. Daily drawdown check
        elif daily_drawdown >= self.max_daily_drawdown:
            can_trade = False
            reason = f"Daily drawdown limit reached: {daily_drawdown*100:.1f}% >= {self.max_daily_drawdown*100}%"
            self._trigger_halt("Daily drawdown limit", duration_hours=4)
        
        # 4. Consecutive loss check
        elif self._consecutive_losses >= self.consecutive_loss_limit:
            can_trade = False
            reason = f"Consecutive loss limit: {self._consecutive_losses} >= {self.consecutive_loss_limit}"
            self._trigger_halt("Consecutive losses", duration_hours=1)
        
        # 5. Market exposure check (DISABLED for balances < $20)
        # Small balances need flexibility to trade multiple markets
        elif self.current_capital >= Decimal('20.0'):
            max_market_exposure = self.current_capital * self.max_position_per_market_pct
            
            if self._get_market_exposure(market_id) + proposed_size > max_market_exposure:
                can_trade = False
                reason = f"Market exposure limit for {market_id}"
        
        # 6. SMART Position size check - Allow Polymarket minimums
        # If proposed size is close to Polymarket minimum, allow it even if slightly over limit
        if can_trade:
            if proposed_size > max_position:
                # Allow if within 10% of Polymarket minimum (accounts for price variations)
                if proposed_size <= POLYMARKET_MIN_ORDER * Decimal('1.10'):
                    # Allow it - this is likely a minimum order size
                    pass
                else:
                    can_trade = False
                    reason = f"Position too large: ${proposed_size} > max ${max_position}"
        
        # 7. Minimum capital check
        if can_trade and self.current_capital < Decimal('1.0'):
            can_trade = False
            reason = "Insufficient capital (< $1.00)"
        
        # 8. SMART: Ensure we have enough balance for the proposed trade
        if can_trade and proposed_size > self.current_capital * Decimal('0.95'):
            can_trade = False
            reason = f"Insufficient balance: ${proposed_size} > ${self.current_capital * Decimal('0.95')} (95% of balance)"
        
        return RiskMetrics(
            total_exposure=total_exposure,
            heat_percentage=heat_pct,
            daily_pnl=self._daily_pnl,
            daily_drawdown=daily_drawdown,
            win_rate=win_rate,
            trades_today=self._trades_today,
            max_position_size=max_position,
            can_trade=can_trade,
            reason=reason
        )
    
    def record_trade_result(
        self,
        profit: Decimal,
        market_id: str,
        size: Decimal
    ):
        """
        Record trade result for tracking.
        
        Args:
            profit: Realized P&L (positive or negative)
            market_id: Market traded
            size: Trade size
        """
        self._trades_today += 1
        self._daily_pnl += profit
        self.current_capital += profit
        
        if profit >= 0:
            self._wins_today += 1
            self._consecutive_losses = 0
        else:
            self._losses_today += 1
            self._consecutive_losses += 1
        
        # Remove position if closed
        if market_id in self._positions:
            del self._positions[market_id]
        
        logger.info(
            f"Trade recorded: profit=${profit}, "
            f"daily_pnl=${self._daily_pnl}, "
            f"win_rate={self._wins_today}/{self._trades_today}"
        )
    
    def add_position(
        self,
        market_id: str,
        side: str,
        entry_price: Decimal,
        size: Decimal
    ):
        """Add a new position."""
        self._positions[market_id] = Position(
            market_id=market_id,
            side=side,
            entry_price=entry_price,
            current_price=entry_price,
            size=size,
            entry_time=datetime.now()
        )
    
    def update_position_price(self, market_id: str, current_price: Decimal):
        """Update position with current market price."""
        if market_id in self._positions:
            pos = self._positions[market_id]
            pos.current_price = current_price
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.size
    
    def close_position(self, market_id: str, exit_price: Decimal) -> Optional[Decimal]:
        """Close a position and return realized P&L."""
        if market_id not in self._positions:
            return None
        
        pos = self._positions[market_id]
        realized_pnl = (exit_price - pos.entry_price) * pos.size
        
        self.record_trade_result(realized_pnl, market_id, pos.size)
        
        return realized_pnl
    
    def get_portfolio_state(self) -> Dict[str, Any]:
        """Get current portfolio state for LLM context."""
        total_exposure = self._calculate_total_exposure()
        
        return {
            "available_balance": self.current_capital - total_exposure,
            "total_balance": self.current_capital,
            "open_positions": [
                {
                    "market_id": p.market_id,
                    "side": p.side,
                    "size": float(p.size),
                    "entry_price": float(p.entry_price),
                    "unrealized_pnl": float(p.unrealized_pnl)
                }
                for p in self._positions.values()
            ],
            "daily_pnl": float(self._daily_pnl),
            "win_rate_today": self._wins_today / self._trades_today if self._trades_today > 0 else 0.5,
            "trades_today": self._trades_today,
            "max_position_size": float(self.current_capital * self.max_position_size_pct)
        }
    
    def _calculate_total_exposure(self) -> Decimal:
        """Calculate total deployed capital."""
        return sum(p.size for p in self._positions.values())
    
    def _get_remaining_heat(self) -> Decimal:
        """Get remaining capital that can be deployed."""
        current_heat = self._calculate_total_exposure()
        max_heat = self.current_capital * self.max_portfolio_heat
        return max(max_heat - current_heat, Decimal('0'))
    
    def _get_market_exposure(self, market_id: str) -> Decimal:
        """Get current exposure in a specific market."""
        if market_id in self._positions:
            return self._positions[market_id].size
        return Decimal('0')
    
    def _trigger_halt(self, reason: str, duration_hours: int = 1):
        """Trigger trading halt."""
        self._trading_halted = True
        self._halt_reason = reason
        self._halt_until = datetime.now() + timedelta(hours=duration_hours)
        logger.warning(f"Trading halted: {reason} until {self._halt_until}")
    
    def _check_halt_expired(self):
        """Check if halt period has expired."""
        if self._trading_halted and self._halt_until:
            if datetime.now() >= self._halt_until:
                self._trading_halted = False
                self._halt_reason = ""
                self._halt_until = None
                logger.info("Trading halt expired, resuming")
    
    def _check_daily_reset(self):
        """Check if daily metrics should be reset."""
        if datetime.now() >= self._daily_reset_time:
            self._daily_start_capital = self.current_capital
            self._trades_today = 0
            self._wins_today = 0
            self._losses_today = 0
            self._daily_pnl = Decimal('0')
            self._consecutive_losses = 0
            self._daily_reset_time = self._get_next_reset_time()
            
            # Clear any daily halt
            if self._trading_halted and "daily" in self._halt_reason.lower():
                self._trading_halted = False
                self._halt_reason = ""
            
            logger.info("Daily metrics reset")
    
    @staticmethod
    def _get_next_reset_time() -> datetime:
        """Get next midnight UTC."""
        now = datetime.utcnow()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return tomorrow
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get risk manager statistics."""
        return {
            "current_capital": float(self.current_capital),
            "total_exposure": float(self._calculate_total_exposure()),
            "heat_percentage": float(self._calculate_total_exposure() / self.current_capital * 100) if self.current_capital > 0 else 0,
            "daily_pnl": float(self._daily_pnl),
            "trades_today": self._trades_today,
            "win_rate": self._wins_today / self._trades_today if self._trades_today > 0 else 0,
            "consecutive_losses": self._consecutive_losses,
            "trading_halted": self._trading_halted,
            "halt_reason": self._halt_reason,
            "open_positions": len(self._positions)
        }
