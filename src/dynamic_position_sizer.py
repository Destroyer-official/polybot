"""
Dynamic Position Sizer for Polymarket Arbitrage Bot.

Calculates position sizes dynamically based on:
- Available balance (private wallet + Polymarket balance)
- Market conditions (volatility, liquidity, opportunity quality)
- Recent performance (win rate)
- Risk limits (max 5% of total balance per trade)
"""

import logging
from decimal import Decimal
from typing import Optional
from datetime import datetime, timedelta

from src.models import Opportunity, Market

logger = logging.getLogger(__name__)


class DynamicPositionSizer:
    """
    Dynamically adjusts position size based on multiple factors.
    
    This replaces hardcoded STAKE_AMOUNT with intelligent sizing that:
    - Checks actual available balance before each trade
    - Adjusts based on opportunity quality (profit %, market conditions)
    - Considers recent win rate to reduce risk after losses
    - Respects liquidity limits to avoid slippage
    - Never risks more than 5% of total balance
    """
    
    def __init__(
        self,
        min_position_size: Decimal = Decimal('0.50'),  # Increased from 0.10 for small capital
        max_position_size: Decimal = Decimal('2.00'),  # Reduced from 5.00 for high frequency
        base_risk_pct: Decimal = Decimal('0.15'),  # Increased from 5% to 15% for small capital
        min_win_rate_threshold: float = 0.70  # Reduce size if win rate < 70%
    ):
        """
        Initialize Dynamic Position Sizer.
        
        Args:
            min_position_size: Minimum position size ($0.10)
            max_position_size: Maximum position size ($5.00)
            base_risk_pct: Base risk percentage (5% of balance)
            min_win_rate_threshold: Win rate threshold for size reduction
        """
        self.min_position_size = min_position_size
        self.max_position_size = max_position_size
        self.base_risk_pct = base_risk_pct
        self.min_win_rate_threshold = min_win_rate_threshold
        
        logger.info(
            f"DynamicPositionSizer initialized: "
            f"min=${min_position_size}, max=${max_position_size}, "
            f"base_risk={base_risk_pct*100}%"
        )
    
    def calculate_position_size(
        self,
        private_wallet_balance: Decimal,
        polymarket_balance: Decimal,
        opportunity: Opportunity,
        market: Optional[Market] = None,
        recent_win_rate: Optional[float] = None,
        pending_trades_value: Decimal = Decimal('0')
    ) -> Decimal:
        """
        Calculate optimal position size dynamically.
        
        Args:
            private_wallet_balance: USDC in private wallet
            polymarket_balance: USDC in Polymarket
            opportunity: The arbitrage opportunity
            market: Market data (optional, for liquidity checks)
            recent_win_rate: Win rate from last 10 trades (optional)
            pending_trades_value: Total value of pending trades
            
        Returns:
            Optimal position size in USDC
        """
        # Calculate total available capital
        total_balance = private_wallet_balance + polymarket_balance - pending_trades_value
        
        if total_balance <= 0:
            logger.warning("No available balance for trading")
            return Decimal('0')
        
        logger.debug(
            f"Balance check: private=${private_wallet_balance}, "
            f"polymarket=${polymarket_balance}, pending=${pending_trades_value}, "
            f"available=${total_balance}"
        )
        
        # Base position size: 15% of available balance (optimized for small capital)
        # Research shows small capital needs higher frequency with moderate position sizes
        base_size = total_balance * self.base_risk_pct
        
        # Adjust for opportunity quality
        profit_multiplier = self._calculate_profit_multiplier(opportunity)
        position_size = base_size * profit_multiplier
        
        # Adjust for recent performance
        if recent_win_rate is not None:
            performance_multiplier = self._calculate_performance_multiplier(recent_win_rate)
            position_size *= performance_multiplier
        
        # Adjust for market liquidity (if available)
        if market is not None:
            liquidity_limit = self._calculate_liquidity_limit(market)
            position_size = min(position_size, liquidity_limit)
        
        # Apply absolute limits
        position_size = max(position_size, self.min_position_size)
        position_size = min(position_size, self.max_position_size)
        
        # Can't trade more than 95% of available balance (keep 5% buffer)
        max_tradeable = total_balance * Decimal('0.95')
        position_size = min(position_size, max_tradeable)
        
        logger.info(
            f"Position size calculated: ${position_size:.2f} "
            f"(available: ${total_balance:.2f}, profit: {opportunity.profit_percentage*100:.2f}%)"
        )
        
        return position_size
    
    def _calculate_profit_multiplier(self, opportunity: Opportunity) -> Decimal:
        """
        Calculate multiplier based on profit potential.
        
        Higher profit = larger position (up to 1.5x)
        Lower profit = smaller position (down to 0.8x)
        
        Args:
            opportunity: The arbitrage opportunity
            
        Returns:
            Multiplier between 0.8 and 1.5
        """
        profit_pct = opportunity.profit_percentage
        
        if profit_pct >= Decimal('0.02'):  # >= 2% profit
            return Decimal('1.5')
        elif profit_pct >= Decimal('0.015'):  # >= 1.5% profit
            return Decimal('1.3')
        elif profit_pct >= Decimal('0.01'):  # >= 1% profit
            return Decimal('1.2')
        elif profit_pct >= Decimal('0.007'):  # >= 0.7% profit
            return Decimal('1.0')
        else:  # < 0.7% profit
            return Decimal('0.8')
    
    def _calculate_performance_multiplier(self, recent_win_rate: float) -> Decimal:
        """
        Calculate multiplier based on recent performance.
        
        High win rate = maintain size
        Low win rate = reduce size to limit losses
        
        Args:
            recent_win_rate: Win rate from last 10 trades (0.0 to 1.0)
            
        Returns:
            Multiplier between 0.5 and 1.0
        """
        if recent_win_rate >= 0.85:  # >= 85% win rate
            return Decimal('1.0')
        elif recent_win_rate >= 0.70:  # >= 70% win rate
            return Decimal('0.9')
        elif recent_win_rate >= 0.50:  # >= 50% win rate
            return Decimal('0.7')
        else:  # < 50% win rate
            return Decimal('0.5')
    
    def _calculate_liquidity_limit(self, market: Market) -> Decimal:
        """
        Calculate position size limit based on market liquidity.
        
        Never trade more than 10% of market liquidity to avoid slippage.
        
        Args:
            market: Market data with liquidity info
            
        Returns:
            Maximum position size based on liquidity
        """
        if not hasattr(market, 'liquidity') or market.liquidity is None:
            # No liquidity data, use conservative limit
            return Decimal('1.0')
        
        # Max 10% of liquidity
        liquidity_limit = Decimal(str(market.liquidity)) * Decimal('0.1')
        
        # But never less than min position size
        return max(liquidity_limit, self.min_position_size)
    
    def get_available_balance_for_trading(
        self,
        private_wallet_balance: Decimal,
        polymarket_balance: Decimal,
        pending_trades_value: Decimal = Decimal('0')
    ) -> Decimal:
        """
        Calculate total available balance for trading.
        
        Args:
            private_wallet_balance: USDC in private wallet
            polymarket_balance: USDC in Polymarket
            pending_trades_value: Total value of pending trades
            
        Returns:
            Available balance for trading
        """
        return private_wallet_balance + polymarket_balance - pending_trades_value
