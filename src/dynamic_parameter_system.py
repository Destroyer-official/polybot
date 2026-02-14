"""
Dynamic Parameter System for Polymarket Arbitrage Bot.

Implements adaptive position sizing using Kelly Criterion with:
- Fractional Kelly (25-50%) for risk management
- Edge calculation with transaction costs
- Performance tracking (last 20 trades)
- Dynamic threshold adjustments based on recent performance

Validates Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.9, 4.12, 4.13, 4.14
"""

import logging
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class TradeResult:
    """Record of a completed trade for performance tracking."""
    timestamp: datetime
    position_size: Decimal
    profit: Decimal
    was_successful: bool
    edge: Decimal
    odds: Decimal


@dataclass
class PerformanceMetrics:
    """Performance metrics from recent trades."""
    win_rate: float
    avg_profit: Decimal
    avg_edge: Decimal
    total_trades: int
    profitable_trades: int


class DynamicParameterSystem:
    """
    Adaptive position sizing system using Kelly Criterion with dynamic adjustments.
    
    Features:
    - Kelly Criterion: f = (edge / odds) for optimal position sizing
    - Fractional Kelly: Uses 25-50% of full Kelly to reduce variance
    - Edge calculation: Accounts for transaction costs (fees, slippage)
    - Performance tracking: Monitors last 20 trades for win rate and profitability
    - Dynamic thresholds: Adjusts fractional Kelly based on recent performance
    """
    
    def __init__(
        self,
        min_fractional_kelly: float = 0.25,
        max_fractional_kelly: float = 0.50,
        performance_window: int = 20,
        transaction_cost_pct: Decimal = Decimal('0.02'),  # 2% for fees + slippage
        min_edge_threshold: Decimal = Decimal('0.005'),  # 0.5% minimum edge (LOWERED: allows trading with stop-loss protection)
        max_position_pct: Decimal = Decimal('0.20'),  # 20% max of bankroll
        min_position_size: Decimal = Decimal('0.10')  # $0.10 minimum
    ):
        """
        Initialize Dynamic Parameter System.
        
        Args:
            min_fractional_kelly: Minimum fractional Kelly (default: 0.25 = 25%)
            max_fractional_kelly: Maximum fractional Kelly (default: 0.50 = 50%)
            performance_window: Number of recent trades to track (default: 20)
            transaction_cost_pct: Transaction costs as percentage (default: 2%)
            min_edge_threshold: Minimum edge required to trade (default: 0.5% - LOWERED to allow trading with stop-loss protection)
            max_position_pct: Maximum position as % of bankroll (default: 20%)
            min_position_size: Minimum position size in USD (default: $0.10)
        """
        self.min_fractional_kelly = min_fractional_kelly
        self.max_fractional_kelly = max_fractional_kelly
        self.performance_window = performance_window
        self.transaction_cost_pct = transaction_cost_pct
        self.min_edge_threshold = min_edge_threshold
        self.max_position_pct = max_position_pct
        self.min_position_size = min_position_size
        
        # Track recent trades (last 20)
        self.trade_history: deque[TradeResult] = deque(maxlen=performance_window)
        
        # Current fractional Kelly (starts at midpoint)
        self.current_fractional_kelly = (min_fractional_kelly + max_fractional_kelly) / 2
        
        # Dynamic thresholds (Requirement 4.11)
        self.take_profit_pct = Decimal('0.02')  # 2% base
        self.stop_loss_pct = Decimal('0.02')  # 2% base
        self.daily_trade_limit = 100  # Base limit
        self.circuit_breaker_threshold = 5  # Base threshold
        
        # EMA smoothing factor for parameter updates
        self.ema_alpha = 0.2  # 20% weight to new values
        
        logger.info(
            f"DynamicParameterSystem initialized: "
            f"fractional_kelly={self.current_fractional_kelly:.2%}, "
            f"transaction_cost={transaction_cost_pct:.2%}, "
            f"min_edge={min_edge_threshold:.2%}"
        )
    
    def calculate_edge(
        self,
        profit_pct: Decimal,
        win_probability: Decimal = Decimal('0.995')
    ) -> Decimal:
        """
        Calculate edge accounting for transaction costs.
        
        Edge = (win_prob * profit_pct) - transaction_costs
        
        Args:
            profit_pct: Expected profit percentage (e.g., 0.05 for 5%)
            win_probability: Probability of winning (default: 99.5% for arbitrage)
            
        Returns:
            Edge as decimal (e.g., 0.03 for 3% edge)
        """
        # Expected profit considering win probability
        expected_profit = win_probability * profit_pct
        
        # Subtract transaction costs
        edge = expected_profit - self.transaction_cost_pct
        
        return edge
    
    def calculate_kelly_fraction(
        self,
        edge: Decimal,
        odds: Decimal
    ) -> Decimal:
        """
        Calculate Kelly Criterion fraction: f = edge / odds
        
        Args:
            edge: Edge (expected profit - costs)
            odds: Odds (profit / cost ratio)
            
        Returns:
            Kelly fraction (e.g., 0.05 for 5% of bankroll)
        """
        if odds <= 0:
            return Decimal('0')
        
        kelly_fraction = edge / odds
        
        # Ensure non-negative
        kelly_fraction = max(kelly_fraction, Decimal('0'))
        
        return kelly_fraction
    
    def calculate_position_size(
        self,
        bankroll: Decimal,
        profit_pct: Decimal,
        cost: Decimal,
        win_probability: Decimal = Decimal('0.995')
    ) -> Tuple[Decimal, Dict]:
        """
        Calculate optimal position size using Kelly Criterion with dynamic adjustments.
        
        Args:
            bankroll: Current available bankroll
            profit_pct: Expected profit percentage
            cost: Cost of the position
            win_probability: Probability of winning (default: 99.5%)
            
        Returns:
            Tuple of (position_size, details_dict)
            - position_size: Optimal position size in USD
            - details_dict: Breakdown of calculation for logging
        """
        # Calculate edge with transaction costs
        edge = self.calculate_edge(profit_pct, win_probability)
        
        # Check if edge meets minimum threshold
        if edge < self.min_edge_threshold:
            logger.debug(
                f"Edge {edge:.2%} below threshold {self.min_edge_threshold:.2%}, skipping trade"
            )
            return Decimal('0'), {
                'edge': edge,
                'threshold': self.min_edge_threshold,
                'reason': 'edge_too_low'
            }
        
        # Calculate odds (profit / cost)
        if cost <= 0:
            return Decimal('0'), {'reason': 'invalid_cost'}
        
        profit = cost * profit_pct
        odds = profit / cost
        
        # Calculate full Kelly fraction
        kelly_fraction = self.calculate_kelly_fraction(edge, odds)
        
        # Apply fractional Kelly (25-50% based on recent performance)
        fractional_kelly = Decimal(str(self.current_fractional_kelly))
        adjusted_kelly = kelly_fraction * fractional_kelly
        
        # Calculate position size
        position_size = bankroll * adjusted_kelly
        
        # Apply maximum position limit (20% of bankroll)
        max_position = bankroll * self.max_position_pct
        was_capped = position_size > max_position
        position_size = min(position_size, max_position)
        
        # Apply minimum position size
        if position_size < self.min_position_size:
            logger.debug(
                f"Position size ${position_size:.2f} below minimum ${self.min_position_size:.2f}"
            )
            return Decimal('0'), {
                'edge': edge,
                'kelly_fraction': kelly_fraction,
                'position_size': position_size,
                'reason': 'below_minimum'
            }
        
        # Ensure we don't exceed bankroll
        position_size = min(position_size, bankroll)
        
        details = {
            'edge': edge,
            'odds': odds,
            'kelly_fraction': kelly_fraction,
            'fractional_kelly': fractional_kelly,
            'adjusted_kelly': adjusted_kelly,
            'position_size': position_size,
            'was_capped': was_capped,
            'max_position': max_position,
            'bankroll': bankroll
        }
        
        logger.info(
            f"Position calculated: ${position_size:.2f} "
            f"(edge={edge:.2%}, kelly={kelly_fraction:.2%}, "
            f"fractional={fractional_kelly:.2%})"
        )
        
        return position_size, details
    def analyze_cost_benefit(
        self,
        expected_profit: Decimal,
        transaction_costs: Decimal,
        estimated_slippage: Decimal
    ) -> Tuple[bool, Dict]:
        """
        Analyze cost-benefit to ensure trade is profitable after all costs.

        Validates Requirements 4.13, 4.14:
        - 4.13: Skip trade if transaction costs > 50% of expected profit
        - 4.14: Skip trade if estimated slippage > 25% of expected profit

        Args:
            expected_profit: Expected profit from the trade
            transaction_costs: Total transaction costs (fees, gas, etc.)
            estimated_slippage: Estimated slippage cost

        Returns:
            Tuple of (should_trade, details_dict)
            - should_trade: True if trade passes cost-benefit analysis
            - details_dict: Breakdown of costs and profit for logging
        """
        # Calculate cost percentages relative to expected profit
        if expected_profit <= 0:
            logger.debug("Expected profit <= 0, skipping trade")
            return False, {
                'expected_profit': expected_profit,
                'reason': 'no_profit_expected'
            }

        transaction_cost_pct = (transaction_costs / expected_profit) * 100
        slippage_pct = (estimated_slippage / expected_profit) * 100

        # Check if transaction costs > 50% of expected profit (Requirement 4.13)
        if transaction_cost_pct > 50:
            logger.info(
                f"Transaction costs ({transaction_cost_pct:.1f}%) > 50% of expected profit, skipping trade"
            )
            return False, {
                'expected_profit': expected_profit,
                'transaction_costs': transaction_costs,
                'transaction_cost_pct': transaction_cost_pct,
                'reason': 'transaction_costs_too_high'
            }

        # Check if estimated slippage > 25% of expected profit (Requirement 4.14)
        if slippage_pct > 25:
            logger.info(
                f"Estimated slippage ({slippage_pct:.1f}%) > 25% of expected profit, skipping trade"
            )
            return False, {
                'expected_profit': expected_profit,
                'estimated_slippage': estimated_slippage,
                'slippage_pct': slippage_pct,
                'reason': 'slippage_too_high'
            }

        # Calculate net profit after all costs
        total_costs = transaction_costs + estimated_slippage
        net_profit = expected_profit - total_costs

        # Skip trade if net profit <= 0
        if net_profit <= 0:
            logger.info(
                f"Net profit (${net_profit:.4f}) <= 0 after costs, skipping trade"
            )
            return False, {
                'expected_profit': expected_profit,
                'transaction_costs': transaction_costs,
                'estimated_slippage': estimated_slippage,
                'total_costs': total_costs,
                'net_profit': net_profit,
                'reason': 'net_profit_negative'
            }

        # Trade passes cost-benefit analysis
        details = {
            'expected_profit': expected_profit,
            'transaction_costs': transaction_costs,
            'transaction_cost_pct': transaction_cost_pct,
            'estimated_slippage': estimated_slippage,
            'slippage_pct': slippage_pct,
            'total_costs': total_costs,
            'net_profit': net_profit,
            'net_profit_pct': (net_profit / expected_profit) * 100
        }

        logger.info(
            f"Cost-benefit analysis passed: "
            f"expected=${expected_profit:.4f}, "
            f"costs=${total_costs:.4f} ({transaction_cost_pct:.1f}% + {slippage_pct:.1f}%), "
            f"net=${net_profit:.4f}"
        )

        return True, details

    
    def analyze_cost_benefit(
        self,
        expected_profit: Decimal,
        transaction_costs: Decimal,
        estimated_slippage: Decimal
    ) -> Tuple[bool, Dict]:
        """
        Analyze cost-benefit to ensure trade is profitable after all costs.
        
        Validates Requirements 4.13, 4.14:
        - 4.13: Skip trade if transaction costs > 50% of expected profit
        - 4.14: Skip trade if estimated slippage > 25% of expected profit
        
        Args:
            expected_profit: Expected profit from the trade
            transaction_costs: Total transaction costs (fees, gas, etc.)
            estimated_slippage: Estimated slippage cost
            
        Returns:
            Tuple of (should_trade, details_dict)
            - should_trade: True if trade passes cost-benefit analysis
            - details_dict: Breakdown of costs and profit for logging
        """
        # Calculate cost percentages relative to expected profit
        if expected_profit <= 0:
            logger.debug("Expected profit <= 0, skipping trade")
            return False, {
                'expected_profit': expected_profit,
                'reason': 'no_profit_expected'
            }
        
        transaction_cost_pct = (transaction_costs / expected_profit) * 100
        slippage_pct = (estimated_slippage / expected_profit) * 100
        
        # Check if transaction costs > 50% of expected profit (Requirement 4.13)
        if transaction_cost_pct > 50:
            logger.info(
                f"Transaction costs ({transaction_cost_pct:.1f}%) > 50% of expected profit, skipping trade"
            )
            return False, {
                'expected_profit': expected_profit,
                'transaction_costs': transaction_costs,
                'transaction_cost_pct': transaction_cost_pct,
                'reason': 'transaction_costs_too_high'
            }
        
        # Check if estimated slippage > 25% of expected profit (Requirement 4.14)
        if slippage_pct > 25:
            logger.info(
                f"Estimated slippage ({slippage_pct:.1f}%) > 25% of expected profit, skipping trade"
            )
            return False, {
                'expected_profit': expected_profit,
                'estimated_slippage': estimated_slippage,
                'slippage_pct': slippage_pct,
                'reason': 'slippage_too_high'
            }
        
        # Calculate net profit after all costs
        total_costs = transaction_costs + estimated_slippage
        net_profit = expected_profit - total_costs
        
        # Skip trade if net profit <= 0
        if net_profit <= 0:
            logger.info(
                f"Net profit (${net_profit:.4f}) <= 0 after costs, skipping trade"
            )
            return False, {
                'expected_profit': expected_profit,
                'transaction_costs': transaction_costs,
                'estimated_slippage': estimated_slippage,
                'total_costs': total_costs,
                'net_profit': net_profit,
                'reason': 'net_profit_negative'
            }
        
        # Trade passes cost-benefit analysis
        details = {
            'expected_profit': expected_profit,
            'transaction_costs': transaction_costs,
            'transaction_cost_pct': transaction_cost_pct,
            'estimated_slippage': estimated_slippage,
            'slippage_pct': slippage_pct,
            'total_costs': total_costs,
            'net_profit': net_profit,
            'net_profit_pct': (net_profit / expected_profit) * 100
        }
        
        logger.info(
            f"Cost-benefit analysis passed: "
            f"expected=${expected_profit:.4f}, "
            f"costs=${total_costs:.4f} ({transaction_cost_pct:.1f}% + {slippage_pct:.1f}%), "
            f"net=${net_profit:.4f}"
        )
        
        return True, details
    
    def record_trade(
        self,
        position_size: Decimal,
        profit: Decimal,
        was_successful: bool,
        edge: Decimal,
        odds: Decimal
    ) -> None:
        """
        Record a completed trade for performance tracking.
        
        Args:
            position_size: Size of the position
            profit: Actual profit/loss
            was_successful: Whether trade was profitable
            edge: Edge used for this trade
            odds: Odds used for this trade
        """
        trade = TradeResult(
            timestamp=datetime.now(),
            position_size=position_size,
            profit=profit,
            was_successful=was_successful,
            edge=edge,
            odds=odds
        )
        
        self.trade_history.append(trade)
        
        # Update fractional Kelly based on recent performance
        self._adjust_fractional_kelly()
        
        logger.debug(
            f"Trade recorded: ${position_size:.2f}, "
            f"profit=${profit:.2f}, success={was_successful}"
        )
    
    def _adjust_fractional_kelly(self) -> None:
        """
        Dynamically adjust fractional Kelly based on recent performance.
        
        Logic:
        - High win rate (>95%): Increase fractional Kelly toward max (50%)
        - Good win rate (85-95%): Keep fractional Kelly at midpoint (37.5%)
        - Low win rate (<85%): Decrease fractional Kelly toward min (25%)
        """
        if len(self.trade_history) < 10:
            # Not enough data, keep at midpoint
            return
        
        metrics = self.get_performance_metrics()
        win_rate = metrics.win_rate
        
        if win_rate >= 0.95:
            # Excellent performance, increase to max
            self.current_fractional_kelly = self.max_fractional_kelly
            logger.info(
                f"High win rate ({win_rate:.1%}), "
                f"increasing fractional Kelly to {self.current_fractional_kelly:.2%}"
            )
        elif win_rate >= 0.85:
            # Good performance, use midpoint
            self.current_fractional_kelly = (
                self.min_fractional_kelly + self.max_fractional_kelly
            ) / 2
        else:
            # Poor performance, decrease to min
            self.current_fractional_kelly = self.min_fractional_kelly
            logger.warning(
                f"Low win rate ({win_rate:.1%}), "
                f"decreasing fractional Kelly to {self.current_fractional_kelly:.2%}"
            )
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """
        Calculate performance metrics from recent trades.
        
        Returns:
            PerformanceMetrics with win rate, avg profit, avg edge, etc.
        """
        if not self.trade_history:
            return PerformanceMetrics(
                win_rate=0.0,
                avg_profit=Decimal('0'),
                avg_edge=Decimal('0'),
                total_trades=0,
                profitable_trades=0
            )
        
        total_trades = len(self.trade_history)
        profitable_trades = sum(1 for t in self.trade_history if t.was_successful)
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0.0
        
        total_profit = sum(t.profit for t in self.trade_history)
        avg_profit = total_profit / total_trades if total_trades > 0 else Decimal('0')
        
        total_edge = sum(t.edge for t in self.trade_history)
        avg_edge = total_edge / total_trades if total_trades > 0 else Decimal('0')
        
        return PerformanceMetrics(
            win_rate=win_rate,
            avg_profit=avg_profit,
            avg_edge=avg_edge,
            total_trades=total_trades,
            profitable_trades=profitable_trades
        )
    
    def get_current_state(self) -> Dict:
        """
        Get current state of the system for logging/monitoring.
        
        Returns:
            Dictionary with current parameters and performance metrics
        """
        metrics = self.get_performance_metrics()
        
        return {
            'fractional_kelly': self.current_fractional_kelly,
            'min_edge_threshold': float(self.min_edge_threshold),
            'transaction_cost_pct': float(self.transaction_cost_pct),
            'performance': {
                'win_rate': metrics.win_rate,
                'avg_profit': float(metrics.avg_profit),
                'avg_edge': float(metrics.avg_edge),
                'total_trades': metrics.total_trades,
                'profitable_trades': metrics.profitable_trades
            }
        }
    
    def reset_performance_tracking(self) -> None:
        """Reset trade history and performance tracking."""
        self.trade_history.clear()
        self.current_fractional_kelly = (
            self.min_fractional_kelly + self.max_fractional_kelly
        ) / 2
        logger.info("Performance tracking reset")
    
    def update_dynamic_parameters(
        self,
        supersmart_params: Optional[Dict] = None,
        adaptive_params: Optional[Dict] = None
    ) -> None:
        """
        Update dynamic parameters using EMA of recent outcomes and learned parameters.
        
        Validates Requirement 4.2, 4.11:
        - Updates take-profit/stop-loss using EMA of recent outcomes
        - Adjusts daily trade limit based on win rate (50-200 trades)
        - Adjusts circuit breaker threshold based on confidence (3-7 losses)
        - Blends with learned parameters from SuperSmart and Adaptive engines
        
        Args:
            supersmart_params: Learned parameters from SuperSmartLearning engine
            adaptive_params: Learned parameters from AdaptiveLearningEngine
        """
        metrics = self.get_performance_metrics()
        
        # Calculate EMA-based take-profit and stop-loss from recent outcomes
        if len(self.trade_history) >= 5:
            # Calculate average profit percentage from winning trades
            winning_trades = [t for t in self.trade_history if t.was_successful]
            if winning_trades:
                avg_win_profit = sum(
                    abs(t.profit / t.position_size) for t in winning_trades
                ) / len(winning_trades)
                
                # Update take-profit using EMA
                new_tp = avg_win_profit * Decimal('1.2')  # 20% above average win
                self.take_profit_pct = (
                    Decimal(str(self.ema_alpha)) * new_tp +
                    Decimal(str(1 - self.ema_alpha)) * self.take_profit_pct
                )
            
            # Calculate average loss percentage from losing trades
            losing_trades = [t for t in self.trade_history if not t.was_successful]
            if losing_trades:
                avg_loss = sum(
                    abs(t.profit / t.position_size) for t in losing_trades
                ) / len(losing_trades)
                
                # Update stop-loss using EMA
                new_sl = avg_loss * Decimal('0.8')  # 20% tighter than average loss
                self.stop_loss_pct = (
                    Decimal(str(self.ema_alpha)) * new_sl +
                    Decimal(str(1 - self.ema_alpha)) * self.stop_loss_pct
                )
        
        # Blend with SuperSmart learned parameters
        if supersmart_params:
            if 'take_profit_pct' in supersmart_params:
                supersmart_tp = Decimal(str(supersmart_params['take_profit_pct']))
                # 50/50 blend
                self.take_profit_pct = (self.take_profit_pct + supersmart_tp) / 2
            
            if 'stop_loss_pct' in supersmart_params:
                supersmart_sl = Decimal(str(supersmart_params['stop_loss_pct']))
                # 50/50 blend
                self.stop_loss_pct = (self.stop_loss_pct + supersmart_sl) / 2
        
        # Blend with Adaptive learned parameters
        if adaptive_params:
            if 'take_profit_pct' in adaptive_params:
                adaptive_tp = Decimal(str(adaptive_params['take_profit_pct']))
                # 50/50 blend
                self.take_profit_pct = (self.take_profit_pct + adaptive_tp) / 2
            
            if 'stop_loss_pct' in adaptive_params:
                adaptive_sl = Decimal(str(adaptive_params['stop_loss_pct']))
                # 50/50 blend
                self.stop_loss_pct = (self.stop_loss_pct + adaptive_sl) / 2
        
        # Adjust daily trade limit based on win rate (50-200 trades)
        if metrics.total_trades >= 10:
            if metrics.win_rate >= 0.80:
                # High win rate: increase limit
                self.daily_trade_limit = 200
            elif metrics.win_rate >= 0.60:
                # Good win rate: moderate limit
                self.daily_trade_limit = 150
            elif metrics.win_rate >= 0.40:
                # Mediocre win rate: base limit
                self.daily_trade_limit = 100
            else:
                # Low win rate: reduce limit
                self.daily_trade_limit = 50
        
        # Adjust circuit breaker threshold based on confidence (3-7 losses)
        if metrics.total_trades >= 10:
            avg_confidence = metrics.avg_edge / Decimal('0.10')  # Normalize to 0-1
            
            if avg_confidence >= Decimal('0.80'):
                # High confidence: allow more losses before halting
                self.circuit_breaker_threshold = 7
            elif avg_confidence >= Decimal('0.60'):
                # Good confidence: moderate threshold
                self.circuit_breaker_threshold = 5
            elif avg_confidence >= Decimal('0.40'):
                # Low confidence: stricter threshold
                self.circuit_breaker_threshold = 4
            else:
                # Very low confidence: very strict
                self.circuit_breaker_threshold = 3
        
        # Clamp parameters to reasonable ranges
        self.take_profit_pct = max(Decimal('0.01'), min(Decimal('0.10'), self.take_profit_pct))
        self.stop_loss_pct = max(Decimal('0.01'), min(Decimal('0.05'), self.stop_loss_pct))
        
        logger.info(
            f"Dynamic parameters updated: "
            f"TP={self.take_profit_pct:.2%}, SL={self.stop_loss_pct:.2%}, "
            f"daily_limit={self.daily_trade_limit}, "
            f"circuit_breaker={self.circuit_breaker_threshold}"
        )
    
    def adjust_for_volatility(
        self,
        volatility: Decimal,
        base_take_profit: Optional[Decimal] = None,
        base_stop_loss: Optional[Decimal] = None
    ) -> Dict:
        """
        Adjust take-profit and stop-loss based on market volatility.
        
        Validates Requirements 4.5, 4.6:
        - High volatility (>5%): widen stop-loss (1.5-2.5×), tighten take-profit (0.5-0.8×)
        - Low volatility (<1%): tighten stop-loss (0.7-0.9×), widen take-profit (1.2-1.8×)
        - Normal volatility: use base parameters
        
        Args:
            volatility: Current market volatility as decimal (e.g., 0.05 for 5%)
            base_take_profit: Base take-profit percentage (uses self.take_profit_pct if None)
            base_stop_loss: Base stop-loss percentage (uses self.stop_loss_pct if None)
            
        Returns:
            Dictionary with adjusted take_profit_pct and stop_loss_pct
        """
        # Use current parameters as base if not provided
        if base_take_profit is None:
            base_take_profit = self.take_profit_pct
        if base_stop_loss is None:
            base_stop_loss = self.stop_loss_pct
        
        # Determine volatility regime
        if volatility > Decimal('0.05'):  # High volatility (>5%)
            # Widen stop-loss to avoid getting stopped out prematurely
            # Range: 1.5× to 2.5× based on how high volatility is
            volatility_factor = min(volatility / Decimal('0.05'), Decimal('2.5'))
            sl_multiplier = Decimal('1.5') + (volatility_factor - Decimal('1.0')) * Decimal('0.5')
            sl_multiplier = min(sl_multiplier, Decimal('2.5'))  # Cap at 2.5×
            
            # Tighten take-profit to lock in gains quickly in volatile markets
            # Range: 0.5× to 0.8× based on volatility
            tp_multiplier = Decimal('0.8') - (volatility_factor - Decimal('1.0')) * Decimal('0.15')
            tp_multiplier = max(tp_multiplier, Decimal('0.5'))  # Floor at 0.5×
            
            regime = "HIGH"
            
        elif volatility < Decimal('0.01'):  # Low volatility (<1%)
            # Tighten stop-loss in calm markets
            # Range: 0.7× to 0.9× based on how low volatility is
            volatility_factor = volatility / Decimal('0.01')  # 0 to 1
            sl_multiplier = Decimal('0.7') + volatility_factor * Decimal('0.2')
            
            # Widen take-profit to capture more profit in calm markets
            # Range: 1.2× to 1.8× based on volatility
            tp_multiplier = Decimal('1.8') - volatility_factor * Decimal('0.6')
            
            regime = "LOW"
            
        else:  # Normal volatility (1-5%)
            # Use base parameters with minor adjustments
            sl_multiplier = Decimal('1.0')
            tp_multiplier = Decimal('1.0')
            regime = "NORMAL"
        
        # Apply multipliers
        adjusted_tp = base_take_profit * tp_multiplier
        adjusted_sl = base_stop_loss * sl_multiplier
        
        # Clamp to reasonable ranges
        adjusted_tp = max(Decimal('0.005'), min(Decimal('0.15'), adjusted_tp))  # 0.5% to 15%
        adjusted_sl = max(Decimal('0.005'), min(Decimal('0.10'), adjusted_sl))  # 0.5% to 10%
        
        logger.info(
            f"Volatility adjustment ({regime}): "
            f"vol={volatility*100:.2f}%, "
            f"TP={base_take_profit*100:.2f}%→{adjusted_tp*100:.2f}% ({tp_multiplier:.2f}×), "
            f"SL={base_stop_loss*100:.2f}%→{adjusted_sl*100:.2f}% ({sl_multiplier:.2f}×)"
        )
        
        return {
            'take_profit_pct': adjusted_tp,
            'stop_loss_pct': adjusted_sl,
            'volatility': volatility,
            'volatility_regime': regime,
            'tp_multiplier': tp_multiplier,
            'sl_multiplier': sl_multiplier
        }
    
    def get_dynamic_thresholds(self) -> Dict:
        """
        Get current dynamic thresholds for use by trading strategy.
        
        Returns:
            Dictionary with current take-profit, stop-loss, daily limit, and circuit breaker threshold
        """
        return {
            'take_profit_pct': float(self.take_profit_pct),
            'stop_loss_pct': float(self.stop_loss_pct),
            'daily_trade_limit': self.daily_trade_limit,
            'circuit_breaker_threshold': self.circuit_breaker_threshold
        }
