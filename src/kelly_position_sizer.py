"""
Kelly Position Sizer for optimal position sizing using Kelly Criterion.

Implements Requirements 11.1, 11.2, 11.3, 11.4, 11.5:
- Kelly Criterion formula for position sizing
- 5% bankroll cap
- Small bankroll fixed sizing ($0.10-$1.00 for <$100)
- Large bankroll proportional sizing (up to $5.00 for >$100)
- Bankroll recalculation every 10 trades
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass

from src.models import Opportunity


@dataclass
class PositionSizingConfig:
    """Configuration for position sizing"""
    max_kelly_fraction: Decimal = Decimal('0.05')  # 5% cap
    small_bankroll_threshold: Decimal = Decimal('100.0')
    small_bankroll_min: Decimal = Decimal('0.10')
    small_bankroll_max: Decimal = Decimal('1.00')
    large_bankroll_max: Decimal = Decimal('5.00')
    win_probability: Decimal = Decimal('0.995')  # 99.5% for arbitrage
    bankroll_recalc_interval: int = 10  # Recalculate every 10 trades


class KellyPositionSizer:
    """
    Calculates optimal position sizes using Kelly Criterion.
    
    The Kelly Criterion formula: f = (bp - q) / b
    where:
        f = fraction of bankroll to bet
        b = odds (profit / cost)
        p = win probability
        q = 1 - p (loss probability)
    
    For arbitrage trading, win probability is very high (~99.5%).
    """
    
    def __init__(self, config: Optional[PositionSizingConfig] = None):
        """
        Initialize Kelly Position Sizer.
        
        Args:
            config: Position sizing configuration (uses defaults if None)
        """
        self.config = config or PositionSizingConfig()
        self._trade_count = 0
        self._last_bankroll = Decimal('0')
    
    def calculate_position_size(
        self, 
        opportunity: Opportunity, 
        bankroll: Decimal
    ) -> Decimal:
        """
        Calculate optimal position size using Kelly Criterion.
        
        Implements Requirements:
        - 11.1: Kelly Criterion formula
        - 11.2: 5% bankroll cap
        - 11.3: Small bankroll fixed sizing ($0.10-$1.00 for <$100)
        - 11.4: Large bankroll proportional sizing (up to $5.00 for >$100)
        
        Args:
            opportunity: The arbitrage opportunity
            bankroll: Current bankroll amount
            
        Returns:
            Optimal position size in USDC
        """
        # Track trade count for bankroll recalculation
        self._trade_count += 1
        
        # Update bankroll if recalculation interval reached
        if self._trade_count % self.config.bankroll_recalc_interval == 0:
            self._last_bankroll = bankroll
        
        # Calculate win and loss probabilities
        win_prob = self.config.win_probability
        loss_prob = Decimal('1.0') - win_prob
        
        # Calculate odds (profit / cost)
        cost = opportunity.total_cost
        profit = opportunity.expected_profit
        
        if cost <= 0:
            return Decimal('0')
        
        odds = profit / cost
        
        # Kelly Criterion formula: f = (bp - q) / b
        if odds <= 0:
            kelly_fraction = Decimal('0')
        else:
            kelly_fraction = (odds * win_prob - loss_prob) / odds
        
        # Cap at maximum Kelly fraction (5% of bankroll)
        kelly_fraction = min(kelly_fraction, self.config.max_kelly_fraction)
        
        # Ensure non-negative
        kelly_fraction = max(kelly_fraction, Decimal('0'))
        
        # Calculate position size
        position_size = bankroll * kelly_fraction
        
        # Apply bankroll-specific constraints
        if bankroll < self.config.small_bankroll_threshold:
            # Small bankroll: use fixed sizes between $0.10 and $1.00
            position_size = min(position_size, self.config.small_bankroll_max)
            position_size = max(position_size, self.config.small_bankroll_min)
        else:
            # Large bankroll: scale up to $5.00 maximum
            position_size = min(position_size, self.config.large_bankroll_max)
        
        return position_size
    
    def get_max_position_size(self) -> Decimal:
        """
        Get maximum allowed position size.
        
        Returns:
            Maximum position size in USDC
        """
        return self.config.large_bankroll_max
    
    def get_trade_count(self) -> int:
        """
        Get current trade count.
        
        Returns:
            Number of trades since initialization
        """
        return self._trade_count
    
    def reset_trade_count(self) -> None:
        """Reset trade count to zero."""
        self._trade_count = 0
    
    def should_recalculate_bankroll(self) -> bool:
        """
        Check if bankroll should be recalculated.
        
        Implements Requirement 11.5: Bankroll recalculation every 10 trades
        
        Returns:
            True if bankroll should be recalculated
        """
        return self._trade_count % self.config.bankroll_recalc_interval == 0
