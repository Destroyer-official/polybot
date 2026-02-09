"""
ADVANCED Adaptive Learning Engine for Trading Bot - SUPER SMART VERSION

This module makes the bot EXTREMELY INTELLIGENT by:
1. Learning from EVERY trade (wins AND losses)
2. Recognizing profitable patterns and avoiding losing patterns
3. Adapting to different market conditions (volatile, calm, trending)
4. Learning optimal entry and exit timing
5. Adjusting strategy based on time of day and market phase
6. Self-optimizing position sizing based on confidence
7. Detecting when strategies stop working and switching tactics
8. Learning from mistakes and never repeating them

The bot becomes SMARTER, FASTER, and MORE PROFITABLE over time!
"""

import json
import logging
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import statistics

logger = logging.getLogger(__name__)


@dataclass
class TradeOutcome:
    """Record of a completed trade."""
    timestamp: datetime
    asset: str
    side: str  # "UP" or "DOWN"
    entry_price: Decimal
    exit_price: Decimal
    profit_pct: Decimal
    hold_time_minutes: float
    exit_reason: str  # "take_profit", "stop_loss", "time_exit", "market_closing"
    strategy_used: str = "unknown"  # "sum_to_one", "latency", "directional"
    market_volatility: Optional[Decimal] = None
    binance_signal_strength: Optional[Decimal] = None
    time_of_day: Optional[int] = None  # Hour of day (0-23)


@dataclass
class MarketConditions:
    """Current market conditions."""
    volatility: Decimal  # Price volatility (std dev)
    trend: str  # "bullish", "bearish", "neutral"
    liquidity: Decimal  # Market liquidity
    spread: Decimal  # Bid-ask spread


@dataclass
class AdaptiveParameters:
    """Dynamically adjusted trading parameters."""
    take_profit_pct: Decimal
    stop_loss_pct: Decimal
    time_exit_minutes: int
    position_size_multiplier: Decimal  # 1.0 = normal, >1.0 = increase, <1.0 = decrease
    confidence_threshold: Decimal  # Minimum confidence to enter trade


class AdaptiveLearningEngine:
    """
    Machine learning engine that adapts trading strategy based on outcomes.
    
    Features:
    - Learns optimal exit thresholds from historical trades
    - Adjusts parameters based on win rate and profitability
    - Identifies profitable market conditions
    - Adapts to changing market dynamics
    - Reduces risk after losses, increases after wins
    """
    
    def __init__(
        self,
        data_file: str = "data/adaptive_learning.json",
        learning_rate: float = 0.1,  # How fast to adapt (0.1 = 10% adjustment)
        min_trades_for_learning: int = 10  # Minimum trades before adapting
    ):
        """
        Initialize Adaptive Learning Engine.
        
        Args:
            data_file: Path to store learning data
            learning_rate: How aggressively to adapt (0.0-1.0)
            min_trades_for_learning: Minimum trades before making adjustments
        """
        self.data_file = Path(data_file)
        self.learning_rate = learning_rate
        self.min_trades_for_learning = min_trades_for_learning
        
        # Trade history
        self.trade_outcomes: List[TradeOutcome] = []
        
        # Current adaptive parameters (start with defaults)
        self.current_params = AdaptiveParameters(
            take_profit_pct=Decimal("0.01"),  # 1%
            stop_loss_pct=Decimal("0.02"),  # 2%
            time_exit_minutes=12,
            position_size_multiplier=Decimal("1.0"),
            confidence_threshold=Decimal("0.6")  # 60%
        )
        
        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = Decimal("0")
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        
        # Advanced pattern recognition
        self.profitable_patterns: Dict[str, float] = {}
        self.strategy_performance: Dict[str, Dict] = {
            "sum_to_one": {"trades": 0, "wins": 0, "profit": Decimal("0")},
            "latency": {"trades": 0, "wins": 0, "profit": Decimal("0")},
            "directional": {"trades": 0, "wins": 0, "profit": Decimal("0")}
        }
        self.asset_performance: Dict[str, Dict] = {}
        self.hourly_performance: Dict[int, Dict] = {}  # Performance by hour of day
        
        # Load existing data
        self._load_data()
        
        logger.info("=" * 80)
        logger.info("ADAPTIVE LEARNING ENGINE INITIALIZED")
        logger.info("=" * 80)
        logger.info(f"Learning rate: {learning_rate * 100}%")
        logger.info(f"Min trades for learning: {min_trades_for_learning}")
        logger.info(f"Current parameters:")
        logger.info(f"  Take-profit: {self.current_params.take_profit_pct * 100}%")
        logger.info(f"  Stop-loss: {self.current_params.stop_loss_pct * 100}%")
        logger.info(f"  Time exit: {self.current_params.time_exit_minutes} minutes")
        logger.info(f"  Position size multiplier: {self.current_params.position_size_multiplier}")
        logger.info("=" * 80)
    
    def record_trade(self, outcome: TradeOutcome) -> None:
        """
        Record a completed trade and learn from it.
        
        Args:
            outcome: Trade outcome details
        """
        self.trade_outcomes.append(outcome)
        self.total_trades += 1
        
        # Update metrics
        is_win = outcome.profit_pct > 0
        if is_win:
            self.winning_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        self.total_profit += outcome.profit_pct
        
        # Update strategy performance
        strategy = outcome.strategy_used
        if strategy in self.strategy_performance:
            self.strategy_performance[strategy]["trades"] += 1
            if is_win:
                self.strategy_performance[strategy]["wins"] += 1
            self.strategy_performance[strategy]["profit"] += outcome.profit_pct
        
        # Update asset performance
        asset = outcome.asset
        if asset not in self.asset_performance:
            self.asset_performance[asset] = {"trades": 0, "wins": 0, "profit": Decimal("0")}
        self.asset_performance[asset]["trades"] += 1
        if is_win:
            self.asset_performance[asset]["wins"] += 1
        self.asset_performance[asset]["profit"] += outcome.profit_pct
        
        # Update hourly performance
        if outcome.time_of_day is not None:
            hour = outcome.time_of_day
            if hour not in self.hourly_performance:
                self.hourly_performance[hour] = {"trades": 0, "wins": 0, "profit": Decimal("0")}
            self.hourly_performance[hour]["trades"] += 1
            if is_win:
                self.hourly_performance[hour]["wins"] += 1
            self.hourly_performance[hour]["profit"] += outcome.profit_pct
        
        # Log trade with advanced insights
        logger.info(f"📊 TRADE RECORDED: {outcome.asset} {outcome.side} ({strategy})")
        logger.info(f"   Profit: {outcome.profit_pct * 100:.2f}% | Hold time: {outcome.hold_time_minutes:.1f}min")
        logger.info(f"   Exit reason: {outcome.exit_reason}")
        logger.info(f"   Overall: {self.get_win_rate() * 100:.1f}% win rate | {self.total_trades} trades")
        
        # Show strategy insights
        if strategy in self.strategy_performance:
            strat_perf = self.strategy_performance[strategy]
            if strat_perf["trades"] > 0:
                strat_wr = strat_perf["wins"] / strat_perf["trades"] * 100
                logger.info(f"   {strategy.upper()} strategy: {strat_wr:.1f}% win rate ({strat_perf['trades']} trades)")
        
        # Learn from trade if we have enough data
        if self.total_trades >= self.min_trades_for_learning:
            self._adapt_parameters()
            self._learn_patterns()
        
        # Save data
        self._save_data()
    
    def get_adaptive_parameters(self, market_conditions: Optional[MarketConditions] = None) -> AdaptiveParameters:
        """
        Get current adaptive parameters, optionally adjusted for market conditions.
        
        Args:
            market_conditions: Current market conditions
            
        Returns:
            Adaptive parameters to use for next trade
        """
        params = self.current_params
        
        # Adjust for market conditions if provided
        if market_conditions:
            # High volatility = wider stops
            if market_conditions.volatility > Decimal("0.05"):  # >5% volatility
                params.stop_loss_pct = params.stop_loss_pct * Decimal("1.5")
                logger.info(f"🌊 High volatility detected, widening stop-loss to {params.stop_loss_pct * 100:.2f}%")
            
            # Low liquidity = smaller positions
            if market_conditions.liquidity < Decimal("1000"):
                params.position_size_multiplier = params.position_size_multiplier * Decimal("0.5")
                logger.info(f"💧 Low liquidity detected, reducing position size by 50%")
        
        return params
    
    def get_win_rate(self) -> float:
        """Calculate current win rate."""
        if self.total_trades == 0:
            return 0.5  # 50% default
        return self.winning_trades / self.total_trades
    
    def get_average_profit(self) -> Decimal:
        """Calculate average profit per trade."""
        if self.total_trades == 0:
            return Decimal("0")
        return self.total_profit / self.total_trades
    
    def should_trade(self, confidence: Decimal) -> bool:
        """
        Determine if bot should enter a trade based on confidence and recent performance.
        
        Args:
            confidence: Confidence level for this trade (0.0-1.0)
            
        Returns:
            True if should trade, False otherwise
        """
        # After consecutive losses, require higher confidence
        if self.consecutive_losses >= 3:
            adjusted_threshold = self.current_params.confidence_threshold * Decimal("1.2")
            logger.info(f"⚠️ {self.consecutive_losses} consecutive losses, requiring {adjusted_threshold * 100:.0f}% confidence")
            return confidence >= adjusted_threshold
        
        # After consecutive wins, can be slightly more aggressive
        if self.consecutive_wins >= 3:
            adjusted_threshold = self.current_params.confidence_threshold * Decimal("0.9")
            logger.info(f"🔥 {self.consecutive_wins} consecutive wins, lowering threshold to {adjusted_threshold * 100:.0f}%")
            return confidence >= adjusted_threshold
        
        return confidence >= self.current_params.confidence_threshold
    
    def _adapt_parameters(self) -> None:
        """
        Adapt trading parameters based on recent performance.
        
        Uses machine learning principles to optimize parameters:
        - If win rate is high, can be more aggressive (tighter stops, larger positions)
        - If win rate is low, be more conservative (wider stops, smaller positions)
        - Learn optimal exit timing from successful trades
        """
        # Get recent trades (last 20)
        recent_trades = self.trade_outcomes[-20:]
        
        if len(recent_trades) < self.min_trades_for_learning:
            return
        
        # Calculate recent win rate
        recent_wins = sum(1 for t in recent_trades if t.profit_pct > 0)
        recent_win_rate = recent_wins / len(recent_trades)
        
        logger.info(f"🧠 LEARNING FROM {len(recent_trades)} RECENT TRADES")
        logger.info(f"   Recent win rate: {recent_win_rate * 100:.1f}%")
        
        # Adapt take-profit threshold
        winning_trades = [t for t in recent_trades if t.profit_pct > 0]
        if winning_trades:
            avg_winning_profit = statistics.mean([float(t.profit_pct) for t in winning_trades])
            
            # If average winning profit is much higher than take-profit, we're exiting too early
            if avg_winning_profit > float(self.current_params.take_profit_pct) * 1.5:
                old_tp = self.current_params.take_profit_pct
                self.current_params.take_profit_pct = Decimal(str(avg_winning_profit * 0.8))
                logger.info(f"   📈 Raising take-profit: {old_tp * 100:.2f}% → {self.current_params.take_profit_pct * 100:.2f}%")
            
            # If average winning profit is close to take-profit, we're doing well
            elif avg_winning_profit < float(self.current_params.take_profit_pct) * 0.7:
                old_tp = self.current_params.take_profit_pct
                self.current_params.take_profit_pct = Decimal(str(avg_winning_profit * 1.1))
                logger.info(f"   📉 Lowering take-profit: {old_tp * 100:.2f}% → {self.current_params.take_profit_pct * 100:.2f}%")
        
        # Adapt stop-loss threshold
        losing_trades = [t for t in recent_trades if t.profit_pct < 0]
        if losing_trades:
            avg_losing_loss = abs(statistics.mean([float(t.profit_pct) for t in losing_trades]))
            
            # If average loss is much larger than stop-loss, we're holding losers too long
            if avg_losing_loss > float(self.current_params.stop_loss_pct) * 1.5:
                old_sl = self.current_params.stop_loss_pct
                self.current_params.stop_loss_pct = Decimal(str(avg_losing_loss * 0.8))
                logger.info(f"   🛑 Tightening stop-loss: {old_sl * 100:.2f}% → {self.current_params.stop_loss_pct * 100:.2f}%")
        
        # Adapt position sizing based on win rate
        if recent_win_rate > 0.7:  # >70% win rate
            # Increase position size
            old_mult = self.current_params.position_size_multiplier
            self.current_params.position_size_multiplier = min(
                Decimal("1.5"),
                self.current_params.position_size_multiplier * Decimal("1.1")
            )
            if old_mult != self.current_params.position_size_multiplier:
                logger.info(f"   💪 Increasing position size: {old_mult} → {self.current_params.position_size_multiplier}")
        
        elif recent_win_rate < 0.5:  # <50% win rate
            # Decrease position size
            old_mult = self.current_params.position_size_multiplier
            self.current_params.position_size_multiplier = max(
                Decimal("0.5"),
                self.current_params.position_size_multiplier * Decimal("0.9")
            )
            if old_mult != self.current_params.position_size_multiplier:
                logger.info(f"   🔻 Decreasing position size: {old_mult} → {self.current_params.position_size_multiplier}")
        
        # Adapt time exit based on successful trades
        successful_quick_exits = [t for t in winning_trades if t.hold_time_minutes < 10]
        if len(successful_quick_exits) > len(winning_trades) * 0.7:  # >70% of wins are quick
            old_time = self.current_params.time_exit_minutes
            self.current_params.time_exit_minutes = max(8, int(self.current_params.time_exit_minutes * 0.9))
            if old_time != self.current_params.time_exit_minutes:
                logger.info(f"   ⏱️ Shortening time exit: {old_time}min → {self.current_params.time_exit_minutes}min")
        
        logger.info(f"   ✅ Parameters adapted based on performance")
    
    def _learn_patterns(self) -> None:
        """
        Learn profitable patterns from trade history.
        
        Identifies:
        - Best performing strategies
        - Most profitable assets
        - Best trading hours
        - Optimal hold times
        """
        recent_trades = self.trade_outcomes[-50:]  # Last 50 trades
        
        if len(recent_trades) < 20:
            return
        
        logger.info(f"🔍 ANALYZING PATTERNS FROM {len(recent_trades)} TRADES")
        
        # Find best strategy
        best_strategy = None
        best_strategy_wr = 0
        for strategy, perf in self.strategy_performance.items():
            if perf["trades"] >= 5:  # Need at least 5 trades
                wr = perf["wins"] / perf["trades"]
                if wr > best_strategy_wr:
                    best_strategy_wr = wr
                    best_strategy = strategy
        
        if best_strategy:
            logger.info(f"   🏆 Best strategy: {best_strategy.upper()} ({best_strategy_wr * 100:.1f}% win rate)")
        
        # Find best asset
        best_asset = None
        best_asset_wr = 0
        for asset, perf in self.asset_performance.items():
            if perf["trades"] >= 3:  # Need at least 3 trades
                wr = perf["wins"] / perf["trades"]
                if wr > best_asset_wr:
                    best_asset_wr = wr
                    best_asset = asset
        
        if best_asset:
            logger.info(f"   💎 Best asset: {best_asset} ({best_asset_wr * 100:.1f}% win rate)")
        
        # Find best trading hours
        best_hours = []
        for hour, perf in self.hourly_performance.items():
            if perf["trades"] >= 3:  # Need at least 3 trades
                wr = perf["wins"] / perf["trades"]
                if wr > 0.6:  # >60% win rate
                    best_hours.append((hour, wr))
        
        if best_hours:
            best_hours.sort(key=lambda x: x[1], reverse=True)
            top_hours = [f"{h}:00 ({wr*100:.0f}%)" for h, wr in best_hours[:3]]
            logger.info(f"   ⏰ Best hours: {', '.join(top_hours)}")
        
        # Find optimal hold time for winners
        winning_trades = [t for t in recent_trades if t.profit_pct > 0]
        if len(winning_trades) >= 5:
            avg_hold_time = statistics.mean([t.hold_time_minutes for t in winning_trades])
            logger.info(f"   ⏱️ Optimal hold time: {avg_hold_time:.1f} minutes (for winners)")
    
    def get_strategy_recommendation(self) -> str:
        """
        Recommend which strategy to prioritize based on learning.
        
        Returns:
            Strategy name: "directional", "latency", or "sum_to_one"
        """
        # Need at least 10 trades per strategy to make recommendation
        valid_strategies = {
            name: perf for name, perf in self.strategy_performance.items()
            if perf["trades"] >= 10
        }
        
        if not valid_strategies:
            return "directional"  # Default to directional for bigger profits
        
        # Find strategy with best win rate AND profit
        best_strategy = max(
            valid_strategies.items(),
            key=lambda x: (x[1]["wins"] / x[1]["trades"]) * float(x[1]["profit"])
        )
        
        return best_strategy[0]
    
    def should_trade_asset(self, asset: str) -> bool:
        """
        Determine if bot should trade this asset based on historical performance.
        
        Args:
            asset: Asset symbol (BTC, ETH, etc.)
            
        Returns:
            True if asset has good track record, False otherwise
        """
        if asset not in self.asset_performance:
            return True  # No data, allow trading
        
        perf = self.asset_performance[asset]
        if perf["trades"] < 5:
            return True  # Not enough data
        
        win_rate = perf["wins"] / perf["trades"]
        
        # Block asset if win rate < 40%
        if win_rate < 0.4:
            logger.warning(f"⚠️ Skipping {asset} - poor track record ({win_rate * 100:.1f}% win rate)")
            return False
        
        return True
    
    def is_good_trading_hour(self) -> bool:
        """
        Determine if current hour is a good time to trade based on history.
        
        Returns:
            True if good trading hour, False otherwise
        """
        current_hour = datetime.now(timezone.utc).hour
        
        if current_hour not in self.hourly_performance:
            return True  # No data, allow trading
        
        perf = self.hourly_performance[current_hour]
        if perf["trades"] < 5:
            return True  # Not enough data
        
        win_rate = perf["wins"] / perf["trades"]
        
        # Warn if this hour has poor performance
        if win_rate < 0.4:
            logger.warning(f"⚠️ Hour {current_hour}:00 UTC has poor track record ({win_rate * 100:.1f}% win rate)")
            return False
        
        return True
    
    def get_performance_summary(self) -> Dict:
        """Get comprehensive performance summary."""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.get_win_rate(),
            "total_profit_pct": float(self.total_profit),
            "avg_profit_pct": float(self.get_average_profit()),
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "current_parameters": {
                "take_profit_pct": float(self.current_params.take_profit_pct),
                "stop_loss_pct": float(self.current_params.stop_loss_pct),
                "time_exit_minutes": self.current_params.time_exit_minutes,
                "position_size_multiplier": float(self.current_params.position_size_multiplier),
                "confidence_threshold": float(self.current_params.confidence_threshold)
            }
        }
    
    def _save_data(self) -> None:
        """Save learning data to disk."""
        try:
            # Ensure data directory exists
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "total_profit": str(self.total_profit),
                "consecutive_wins": self.consecutive_wins,
                "consecutive_losses": self.consecutive_losses,
                "current_params": {
                    "take_profit_pct": str(self.current_params.take_profit_pct),
                    "stop_loss_pct": str(self.current_params.stop_loss_pct),
                    "time_exit_minutes": self.current_params.time_exit_minutes,
                    "position_size_multiplier": str(self.current_params.position_size_multiplier),
                    "confidence_threshold": str(self.current_params.confidence_threshold)
                },
                "strategy_performance": {
                    name: {
                        "trades": perf["trades"],
                        "wins": perf["wins"],
                        "profit": str(perf["profit"])
                    }
                    for name, perf in self.strategy_performance.items()
                },
                "asset_performance": {
                    asset: {
                        "trades": perf["trades"],
                        "wins": perf["wins"],
                        "profit": str(perf["profit"])
                    }
                    for asset, perf in self.asset_performance.items()
                },
                "hourly_performance": {
                    str(hour): {
                        "trades": perf["trades"],
                        "wins": perf["wins"],
                        "profit": str(perf["profit"])
                    }
                    for hour, perf in self.hourly_performance.items()
                },
                "trade_outcomes": [
                    {
                        "timestamp": t.timestamp.isoformat(),
                        "asset": t.asset,
                        "side": t.side,
                        "entry_price": str(t.entry_price),
                        "exit_price": str(t.exit_price),
                        "profit_pct": str(t.profit_pct),
                        "hold_time_minutes": t.hold_time_minutes,
                        "exit_reason": t.exit_reason,
                        "strategy_used": t.strategy_used,
                        "time_of_day": t.time_of_day
                    }
                    for t in self.trade_outcomes[-100:]  # Keep last 100 trades
                ]
            }
            
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Learning data saved to {self.data_file}")
            
        except Exception as e:
            logger.error(f"Failed to save learning data: {e}")
    
    def _load_data(self) -> None:
        """Load learning data from disk."""
        try:
            if not self.data_file.exists():
                logger.info("No existing learning data found, starting fresh")
                return
            
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            self.total_trades = data.get("total_trades", 0)
            self.winning_trades = data.get("winning_trades", 0)
            self.losing_trades = data.get("losing_trades", 0)
            self.total_profit = Decimal(data.get("total_profit", "0"))
            self.consecutive_wins = data.get("consecutive_wins", 0)
            self.consecutive_losses = data.get("consecutive_losses", 0)
            
            # Load parameters
            params = data.get("current_params", {})
            self.current_params = AdaptiveParameters(
                take_profit_pct=Decimal(params.get("take_profit_pct", "0.01")),
                stop_loss_pct=Decimal(params.get("stop_loss_pct", "0.02")),
                time_exit_minutes=params.get("time_exit_minutes", 12),
                position_size_multiplier=Decimal(params.get("position_size_multiplier", "1.0")),
                confidence_threshold=Decimal(params.get("confidence_threshold", "0.6"))
            )
            
            # Load strategy performance
            for name, perf in data.get("strategy_performance", {}).items():
                self.strategy_performance[name] = {
                    "trades": perf["trades"],
                    "wins": perf["wins"],
                    "profit": Decimal(perf["profit"])
                }
            
            # Load asset performance
            for asset, perf in data.get("asset_performance", {}).items():
                self.asset_performance[asset] = {
                    "trades": perf["trades"],
                    "wins": perf["wins"],
                    "profit": Decimal(perf["profit"])
                }
            
            # Load hourly performance
            for hour_str, perf in data.get("hourly_performance", {}).items():
                hour = int(hour_str)
                self.hourly_performance[hour] = {
                    "trades": perf["trades"],
                    "wins": perf["wins"],
                    "profit": Decimal(perf["profit"])
                }
            
            # Load trade outcomes
            for trade_data in data.get("trade_outcomes", []):
                outcome = TradeOutcome(
                    timestamp=datetime.fromisoformat(trade_data["timestamp"]),
                    asset=trade_data["asset"],
                    side=trade_data["side"],
                    entry_price=Decimal(trade_data["entry_price"]),
                    exit_price=Decimal(trade_data["exit_price"]),
                    profit_pct=Decimal(trade_data["profit_pct"]),
                    hold_time_minutes=trade_data["hold_time_minutes"],
                    exit_reason=trade_data["exit_reason"],
                    strategy_used=trade_data.get("strategy_used", "unknown"),
                    time_of_day=trade_data.get("time_of_day")
                )
                self.trade_outcomes.append(outcome)
            
            logger.info(f"Loaded learning data: {self.total_trades} trades, {self.get_win_rate() * 100:.1f}% win rate")
            
        except Exception as e:
            logger.error(f"Failed to load learning data: {e}")
            logger.info("Starting with fresh learning data")
