"""
UPGRADED Dynamic Position Sizer for Polymarket Arbitrage Bot.

Based on research showing successful bots use:
- 10-20% risk for small balances (< $50)
- 5-10% risk for medium balances ($50-$100)
- 3-5% risk for large balances (> $100)

This enables faster compound growth from small starting capital.
"""

import logging
from decimal import Decimal
from typing import Optional
from datetime import datetime, timedelta

from src.models import Opportunity, Market

logger = logging.getLogger(__name__)


class DynamicPositionSizerV2:
    """
    UPGRADED: Dynamically adjusts position size based on balance and market conditions.
    
    Key improvements:
    - Aggressive sizing for small balances (10-20% risk)
    - Dynamic profit threshold adjustment
    - Better liquidity handling
    - Compound growth optimization
    """
    
    def __init__(
        self,
        min_position_size: Decimal = Decimal('0.10'),
        max_position_size: Decimal = Decimal('20.00'),  # Increased from $5
        min_win_rate_threshold: float = 0.70
    ):
        """
        Initialize Upgraded Dynamic Position Sizer.
        
        Args:
            min_position_size: Minimum position size ($0.10)
            max_position_size: Maximum position size ($20.00)
            min_win_rate_threshold: Win rate threshold for size reduction
        """
        self.min_position_size = min_position_size
        self.max_position_size = max_position_size
        self.min_win_rate_threshold = min_win_rate_threshold
        
        logger.info(
            f"DynamicPositionSizerV2 initialized: "
            f"min=${min_position_size}, max=${max_position_size}"
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
        Calculate optimal position size with aggressive scaling for small balances.
        
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
        
        # DYNAMIC BASE RISK: Aggressive for small balances
        # Research shows successful bots use 10-20% for small capital
        base_risk_pct = self._get_base_risk_pct(total_balance)
        
        # Base position size
        base_size = total_balance * base_risk_pct
        
        logger.debug(
            f"Base calculation: balance=${total_balance}, "
            f"risk={base_risk_pct*100}%, base_size=${base_size}"
        )
        
        # Adjust for opportunity quality
        profit_multiplier = self._calculate_profit_multiplier(opportunity)
        position_size = base_size * profit_multiplier
        
        logger.debug(f"After profit multiplier ({profit_multiplier}): ${position_size}")
        
        # Adjust for recent performance
        if recent_win_rate is not None:
            performance_multiplier = self._calculate_performance_multiplier(recent_win_rate)
            position_size *= performance_multiplier
            logger.debug(
                f"After performance multiplier ({performance_multiplier}, "
                f"win_rate={recent_win_rate*100}%): ${position_size}"
            )
        
        # Adjust for market liquidity (if available)
        if market is not None:
            liquidity_limit = self._calculate_liquidity_limit(market)
            if position_size > liquidity_limit:
                logger.debug(
                    f"Liquidity limit applied: ${position_size} -> ${liquidity_limit}"
                )
                position_size = liquidity_limit
        
        # Apply absolute limits
        position_size = max(position_size, self.min_position_size)
        position_size = min(position_size, self.max_position_size)
        
        # Can't trade more than 95% of available balance (keep 5% buffer)
        max_tradeable = total_balance * Decimal('0.95')
        position_size = min(position_size, max_tradeable)
        
        logger.info(
            f"✅ Position size: ${position_size:.2f} "
            f"(balance: ${total_balance:.2f}, risk: {base_risk_pct*100:.0f}%, "
            f"profit: {opportunity.profit_percentage*100:.2f}%)"
        )
        
        return position_size
    
    def _get_base_risk_pct(self, total_balance: Decimal) -> Decimal:
        """
        Get base risk percentage based on balance size.
        
        Research-backed scaling:
        - < $10: 15% (aggressive growth mode)
        - $10-$50: 10% (moderate growth)
        - $50-$100: 7% (balanced)
        - > $100: 5% (conservative)
        
        Args:
            total_balance: Total available balance
            
        Returns:
            Base risk percentage
        """
        if total_balance < Decimal('10.0'):
            return Decimal('0.15')  # 15% for micro balances
        elif total_balance < Decimal('50.0'):
            return Decimal('0.10')  # 10% for small balances
        elif total_balance < Decimal('100.0'):
            return Decimal('0.07')  # 7% for medium balances
        else:
            return Decimal('0.05')  # 5% for large balances
    
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
        elif profit_pct >= Decimal('0.005'):  # >= 0.5% profit
            return Decimal('0.9')
        else:  # < 0.5% profit
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
    
    def get_dynamic_profit_threshold(self, total_balance: Decimal) -> Decimal:
        """
        Get dynamic profit threshold based on balance.
        
        Small balances need lower thresholds to find more opportunities.
        
        Args:
            total_balance: Total available balance
            
        Returns:
            Minimum profit threshold
        """
        if total_balance < Decimal('10.0'):
            return Decimal('0.003')  # 0.3% for micro balances
        elif total_balance < Decimal('50.0'):
            return Decimal('0.004')  # 0.4% for small balances
        else:
            return Decimal('0.005')  # 0.5% for larger balances
