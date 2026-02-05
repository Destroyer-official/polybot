"""
Backtest simulator for testing arbitrage strategies on historical data.

Simulates order execution with realistic fills, calculates slippage and fees,
and tracks portfolio over time.

Validates Requirement 12.2.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import random

from src.models import Market, Opportunity, TradeResult

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest simulation."""
    initial_balance: Decimal = Decimal('100.0')  # Starting USDC balance
    fill_rate: Decimal = Decimal('0.95')  # 95% of orders fill successfully
    slippage_rate: Decimal = Decimal('0.001')  # 0.1% average slippage
    gas_cost_per_trade: Decimal = Decimal('0.02')  # $0.02 average gas cost
    max_position_size: Decimal = Decimal('5.0')  # Maximum position size
    min_position_size: Decimal = Decimal('0.1')  # Minimum position size
    simulate_failures: bool = True  # Simulate realistic trade failures
    random_seed: Optional[int] = None  # For reproducible results


@dataclass
class PortfolioSnapshot:
    """Snapshot of portfolio state at a point in time."""
    timestamp: datetime
    balance: Decimal
    total_trades: int
    successful_trades: int
    failed_trades: int
    total_profit: Decimal
    total_gas_cost: Decimal
    net_profit: Decimal
    win_rate: Decimal
    
    # Performance metrics
    max_balance: Decimal
    max_drawdown: Decimal  # Maximum peak-to-trough decline
    sharpe_ratio: Optional[Decimal] = None


class BacktestSimulator:
    """
    Simulates arbitrage trading on historical market data.
    
    Validates Requirement 12.2:
    - Simulate order execution with realistic fills
    - Calculate slippage and fees
    - Track portfolio over time
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Initialize the backtest simulator.
        
        Args:
            config: Backtest configuration parameters
        """
        self.config = config
        self.balance = config.initial_balance
        self.initial_balance = config.initial_balance
        
        # Trade tracking
        self.trades: List[TradeResult] = []
        self.portfolio_history: List[PortfolioSnapshot] = []
        
        # Performance metrics
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_profit = Decimal('0.0')
        self.total_gas_cost = Decimal('0.0')
        self.max_balance = config.initial_balance
        self.max_drawdown = Decimal('0.0')
        
        # Set random seed for reproducibility
        if config.random_seed is not None:
            random.seed(config.random_seed)
        
        logger.info(
            f"Initialized BacktestSimulator with balance: ${self.balance}, "
            f"fill_rate: {self.config.fill_rate}, slippage: {self.config.slippage_rate}"
        )
    
    def simulate_trade(self, opportunity: Opportunity) -> TradeResult:
        """
        Simulate execution of an arbitrage opportunity.
        
        Args:
            opportunity: The arbitrage opportunity to execute
            
        Returns:
            TradeResult: Result of the simulated trade
            
        Validates Requirement 12.2: Simulate order execution with realistic fills
        """
        self.total_trades += 1
        
        # Check if we have sufficient balance
        if self.balance < opportunity.total_cost:
            return self._create_failed_trade(
                opportunity,
                "Insufficient balance"
            )
        
        # Simulate order fills with realistic success rate
        yes_filled, no_filled = self._simulate_order_fills(opportunity)
        
        if not yes_filled or not no_filled:
            # One or both orders failed to fill (legging risk)
            self.failed_trades += 1
            return self._create_failed_trade(
                opportunity,
                "FOK order not filled" if not yes_filled else "NO order not filled"
            )
        
        # Calculate actual execution prices with slippage
        yes_fill_price, no_fill_price = self._calculate_fill_prices(opportunity)
        
        # Calculate actual costs and profits
        actual_cost = (yes_fill_price + no_fill_price) + \
                     (yes_fill_price * opportunity.yes_fee) + \
                     (no_fill_price * opportunity.no_fee)
        
        # Redemption value is always $1.00 for internal arbitrage
        redemption_value = Decimal('1.0') * opportunity.position_size
        
        # Calculate profit and gas cost
        actual_profit = redemption_value - (actual_cost * opportunity.position_size)
        gas_cost = self._calculate_gas_cost()
        net_profit = actual_profit - gas_cost
        
        # Update balance
        self.balance += net_profit
        self.total_profit += actual_profit
        self.total_gas_cost += gas_cost
        
        # Track max balance and drawdown
        if self.balance > self.max_balance:
            self.max_balance = self.balance
        
        current_drawdown = (self.max_balance - self.balance) / self.max_balance
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
        
        # Create successful trade result
        self.successful_trades += 1
        
        trade_result = TradeResult(
            trade_id=f"backtest_{self.total_trades}",
            opportunity=opportunity,
            timestamp=opportunity.timestamp,
            status="success",
            yes_order_id=f"yes_{self.total_trades}",
            no_order_id=f"no_{self.total_trades}",
            yes_filled=True,
            no_filled=True,
            yes_fill_price=yes_fill_price,
            no_fill_price=no_fill_price,
            actual_cost=actual_cost * opportunity.position_size,
            actual_profit=actual_profit,
            gas_cost=gas_cost,
            net_profit=net_profit,
            yes_tx_hash=f"0xyes{self.total_trades:08x}",
            no_tx_hash=f"0xno{self.total_trades:08x}",
            merge_tx_hash=f"0xmerge{self.total_trades:08x}"
        )
        
        self.trades.append(trade_result)
        
        # Record portfolio snapshot
        self._record_portfolio_snapshot(opportunity.timestamp)
        
        logger.debug(
            f"Trade {self.total_trades}: "
            f"Profit=${actual_profit:.4f}, Gas=${gas_cost:.4f}, "
            f"Net=${net_profit:.4f}, Balance=${self.balance:.2f}"
        )
        
        return trade_result
    
    def _simulate_order_fills(self, opportunity: Opportunity) -> tuple[bool, bool]:
        """
        Simulate whether orders fill successfully.
        
        Uses configured fill rate to determine success.
        For atomic FOK orders, both must fill or neither fills.
        
        Returns:
            tuple[bool, bool]: (yes_filled, no_filled)
        """
        if not self.config.simulate_failures:
            # Always fill in optimistic mode
            return (True, True)
        
        # Simulate fill probability
        # In reality, both orders are atomic (FOK), so they fill together or not at all
        fill_success = random.random() < float(self.config.fill_rate)
        
        return (fill_success, fill_success)
    
    def _calculate_fill_prices(
        self,
        opportunity: Opportunity
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate actual fill prices including slippage.
        
        Validates Requirement 12.2: Calculate slippage
        
        Args:
            opportunity: The opportunity being executed
            
        Returns:
            tuple[Decimal, Decimal]: (yes_fill_price, no_fill_price)
        """
        # Simulate slippage (prices move slightly against us)
        yes_slippage = opportunity.yes_price * self.config.slippage_rate
        no_slippage = opportunity.no_price * self.config.slippage_rate
        
        # Add slippage to prices (we pay slightly more)
        yes_fill_price = opportunity.yes_price + yes_slippage
        no_fill_price = opportunity.no_price + no_slippage
        
        # Ensure prices stay within valid range [0, 1]
        yes_fill_price = min(yes_fill_price, Decimal('1.0'))
        no_fill_price = min(no_fill_price, Decimal('1.0'))
        
        return (yes_fill_price, no_fill_price)
    
    def _calculate_gas_cost(self) -> Decimal:
        """
        Calculate gas cost for the trade.
        
        Validates Requirement 12.2: Calculate fees
        
        Returns:
            Decimal: Gas cost in USDC
        """
        # Use configured average gas cost with small random variation
        if self.config.simulate_failures:
            variation = Decimal(str(random.uniform(0.8, 1.2)))
            return self.config.gas_cost_per_trade * variation
        
        return self.config.gas_cost_per_trade
    
    def _create_failed_trade(
        self,
        opportunity: Opportunity,
        error_message: str
    ) -> TradeResult:
        """Create a TradeResult for a failed trade."""
        self.failed_trades += 1
        
        # Still pay gas for failed transactions
        gas_cost = self._calculate_gas_cost()
        self.balance -= gas_cost
        self.total_gas_cost += gas_cost
        
        trade_result = TradeResult(
            trade_id=f"backtest_{self.total_trades}",
            opportunity=opportunity,
            timestamp=opportunity.timestamp,
            status="failed",
            yes_order_id=None,
            no_order_id=None,
            yes_filled=False,
            no_filled=False,
            yes_fill_price=None,
            no_fill_price=None,
            actual_cost=Decimal('0.0'),
            actual_profit=Decimal('0.0'),
            gas_cost=gas_cost,
            net_profit=-gas_cost,
            error_message=error_message
        )
        
        self.trades.append(trade_result)
        self._record_portfolio_snapshot(opportunity.timestamp)
        
        logger.debug(f"Trade {self.total_trades} failed: {error_message}")
        
        return trade_result
    
    def _record_portfolio_snapshot(self, timestamp: datetime):
        """
        Record current portfolio state.
        
        Validates Requirement 12.2: Track portfolio over time
        """
        win_rate = (
            Decimal(str(self.successful_trades)) / Decimal(str(self.total_trades))
            if self.total_trades > 0
            else Decimal('0.0')
        )
        
        net_profit = self.total_profit - self.total_gas_cost
        
        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            balance=self.balance,
            total_trades=self.total_trades,
            successful_trades=self.successful_trades,
            failed_trades=self.failed_trades,
            total_profit=self.total_profit,
            total_gas_cost=self.total_gas_cost,
            net_profit=net_profit,
            win_rate=win_rate,
            max_balance=self.max_balance,
            max_drawdown=self.max_drawdown
        )
        
        self.portfolio_history.append(snapshot)
    
    def get_current_snapshot(self) -> PortfolioSnapshot:
        """
        Get current portfolio snapshot.
        
        Returns:
            PortfolioSnapshot: Current portfolio state
        """
        win_rate = (
            Decimal(str(self.successful_trades)) / Decimal(str(self.total_trades))
            if self.total_trades > 0
            else Decimal('0.0')
        )
        
        net_profit = self.total_profit - self.total_gas_cost
        
        return PortfolioSnapshot(
            timestamp=datetime.now(),
            balance=self.balance,
            total_trades=self.total_trades,
            successful_trades=self.successful_trades,
            failed_trades=self.failed_trades,
            total_profit=self.total_profit,
            total_gas_cost=self.total_gas_cost,
            net_profit=net_profit,
            win_rate=win_rate,
            max_balance=self.max_balance,
            max_drawdown=self.max_drawdown
        )
    
    def get_trade_history(self) -> List[TradeResult]:
        """
        Get complete trade history.
        
        Returns:
            List[TradeResult]: All executed trades
        """
        return self.trades.copy()
    
    def get_portfolio_history(self) -> List[PortfolioSnapshot]:
        """
        Get portfolio history over time.
        
        Returns:
            List[PortfolioSnapshot]: Portfolio snapshots at each trade
        """
        return self.portfolio_history.copy()
    
    def reset(self):
        """Reset simulator to initial state."""
        self.balance = self.config.initial_balance
        self.trades.clear()
        self.portfolio_history.clear()
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_profit = Decimal('0.0')
        self.total_gas_cost = Decimal('0.0')
        self.max_balance = self.config.initial_balance
        self.max_drawdown = Decimal('0.0')
        
        logger.info("Backtest simulator reset to initial state")
