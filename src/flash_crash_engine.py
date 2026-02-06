"""
Flash Crash Detection Engine for Polymarket.

Based on research showing 86% ROI strategy:
- Monitor for rapid price drops (15% in 3 seconds)
- Buy the crashed side (Leg 1)
- Wait for recovery and hedge (Leg 2)
- Profit when sum < 0.95

Reference: https://www.htx.com/news/Trading-1lvJrZQN
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from collections import deque

from src.models import Market, Opportunity

logger = logging.getLogger(__name__)


class FlashCrashDetector:
    """
    Detects flash crashes in prediction markets and generates trading opportunities.
    
    Strategy:
    1. Monitor price movements in first N minutes of each round
    2. Detect crashes: >15% drop within 3 seconds
    3. Buy crashed side immediately (Leg 1)
    4. Wait for recovery: opposite_ask + leg1_price <= 0.95
    5. Hedge by buying opposite side (Leg 2)
    6. Profit: 1.00 - (leg1_price + leg2_price)
    """
    
    def __init__(
        self,
        crash_threshold: Decimal = Decimal('0.15'),  # 15% drop
        crash_window_seconds: int = 3,  # Within 3 seconds
        sum_target: Decimal = Decimal('0.95'),  # Hedge when sum <= 0.95
        window_minutes: int = 2,  # Only detect in first 2 minutes
        min_profit: Decimal = Decimal('0.03')  # 3% minimum profit
    ):
        """
        Initialize Flash Crash Detector.
        
        Args:
            crash_threshold: Minimum price drop to trigger (default 15%)
            crash_window_seconds: Time window for crash detection (default 3s)
            sum_target: Maximum sum for hedging (default 0.95)
            window_minutes: Detection window from round start (default 2 min)
            min_profit: Minimum profit threshold (default 3%)
        """
        self.crash_threshold = crash_threshold
        self.crash_window_seconds = crash_window_seconds
        self.sum_target = sum_target
        self.window_minutes = window_minutes
        self.min_profit = min_profit
        
        # Track price history for each market
        # Format: {market_id: deque([(timestamp, yes_price, no_price), ...])}
        self._price_history: Dict[str, deque] = {}
        
        # Track active crash opportunities (waiting for hedge)
        # Format: {market_id: {'side': 'YES'/'NO', 'entry_price': Decimal, 'timestamp': datetime}}
        self._active_crashes: Dict[str, Dict] = {}
        
        # Track round start times
        # Format: {market_id: datetime}
        self._round_starts: Dict[str, datetime] = {}
        
        logger.info(
            f"FlashCrashDetector initialized: "
            f"crash_threshold={crash_threshold*100}%, "
            f"window={crash_window_seconds}s, "
            f"sum_target={sum_target}, "
            f"detection_window={window_minutes}min"
        )
    
    def update_prices(
        self,
        market_id: str,
        yes_price: Decimal,
        no_price: Decimal,
        round_start: Optional[datetime] = None
    ) -> None:
        """
        Update price history for crash detection.
        
        Args:
            market_id: Market identifier
            yes_price: Current YES price
            no_price: Current NO price
            round_start: Round start time (if new round)
        """
        now = datetime.now()
        
        # Initialize history if new market
        if market_id not in self._price_history:
            self._price_history[market_id] = deque(maxlen=100)  # Keep last 100 updates
        
        # Update round start if provided
        if round_start:
            self._round_starts[market_id] = round_start
        
        # Add price point
        self._price_history[market_id].append((now, yes_price, no_price))
        
        # Clean old data (keep only last 10 seconds)
        cutoff = now - timedelta(seconds=10)
        while (self._price_history[market_id] and 
               self._price_history[market_id][0][0] < cutoff):
            self._price_history[market_id].popleft()
    
    def detect_crash(self, market_id: str) -> Optional[Tuple[str, Decimal]]:
        """
        Detect flash crash in market.
        
        Returns:
            Optional[Tuple[str, Decimal]]: (side, entry_price) if crash detected, None otherwise
        """
        # Check if we have enough history
        if market_id not in self._price_history or len(self._price_history[market_id]) < 2:
            return None
        
        # Check if we're within detection window
        if not self._is_within_detection_window(market_id):
            return None
        
        # Check if already have active crash for this market
        if market_id in self._active_crashes:
            return None
        
        now = datetime.now()
        history = self._price_history[market_id]
        
        # Get current prices
        current_time, current_yes, current_no = history[-1]
        
        # Look back crash_window_seconds
        window_start = current_time - timedelta(seconds=self.crash_window_seconds)
        
        # Find prices at window start
        window_prices = [
            (ts, yes, no) for ts, yes, no in history
            if ts >= window_start
        ]
        
        if len(window_prices) < 2:
            return None
        
        # Get starting prices
        _, start_yes, start_no = window_prices[0]
        
        # Calculate price changes
        yes_change = (current_yes - start_yes) / start_yes if start_yes > 0 else Decimal('0')
        no_change = (current_no - start_no) / start_no if start_no > 0 else Decimal('0')
        
        # Check for YES crash (price dropped)
        if yes_change <= -self.crash_threshold:
            logger.info(
                f"Flash crash detected in {market_id}: "
                f"YES dropped {abs(yes_change)*100:.1f}% "
                f"(${start_yes} -> ${current_yes})"
            )
            return ('YES', current_yes)
        
        # Check for NO crash (price dropped)
        if no_change <= -self.crash_threshold:
            logger.info(
                f"Flash crash detected in {market_id}: "
                f"NO dropped {abs(no_change)*100:.1f}% "
                f"(${start_no} -> ${current_no})"
            )
            return ('NO', current_no)
        
        return None
    
    def check_hedge_opportunity(
        self,
        market_id: str,
        current_yes_price: Decimal,
        current_no_price: Decimal
    ) -> Optional[Tuple[str, Decimal, Decimal]]:
        """
        Check if hedge opportunity exists for active crash.
        
        Returns:
            Optional[Tuple[str, Decimal, Decimal]]: (hedge_side, hedge_price, expected_profit) if opportunity exists
        """
        # Check if we have active crash for this market
        if market_id not in self._active_crashes:
            return None
        
        crash = self._active_crashes[market_id]
        leg1_side = crash['side']
        leg1_price = crash['entry_price']
        
        # Determine hedge side and price
        if leg1_side == 'YES':
            hedge_side = 'NO'
            hedge_price = current_no_price
        else:
            hedge_side = 'YES'
            hedge_price = current_yes_price
        
        # Check if sum meets target
        price_sum = leg1_price + hedge_price
        
        if price_sum <= self.sum_target:
            expected_profit = Decimal('1.00') - price_sum
            profit_pct = expected_profit / price_sum if price_sum > 0 else Decimal('0')
            
            # Check minimum profit threshold
            if profit_pct >= self.min_profit:
                logger.info(
                    f"Hedge opportunity in {market_id}: "
                    f"Leg1={leg1_side}@${leg1_price}, "
                    f"Leg2={hedge_side}@${hedge_price}, "
                    f"Sum=${price_sum}, Profit=${expected_profit} ({profit_pct*100:.1f}%)"
                )
                return (hedge_side, hedge_price, expected_profit)
        
        return None
    
    def register_crash_entry(
        self,
        market_id: str,
        side: str,
        entry_price: Decimal
    ) -> None:
        """
        Register that we've entered a crash position (Leg 1).
        
        Args:
            market_id: Market identifier
            side: Side entered ('YES' or 'NO')
            entry_price: Entry price
        """
        self._active_crashes[market_id] = {
            'side': side,
            'entry_price': entry_price,
            'timestamp': datetime.now()
        }
        logger.info(f"Registered crash entry: {market_id} {side}@${entry_price}")
    
    def complete_crash_trade(self, market_id: str) -> None:
        """
        Mark crash trade as complete (both legs executed).
        
        Args:
            market_id: Market identifier
        """
        if market_id in self._active_crashes:
            del self._active_crashes[market_id]
            logger.info(f"Completed crash trade: {market_id}")
    
    def abandon_crash_trade(self, market_id: str, reason: str = "timeout") -> None:
        """
        Abandon active crash trade.
        
        Args:
            market_id: Market identifier
            reason: Reason for abandonment
        """
        if market_id in self._active_crashes:
            crash = self._active_crashes[market_id]
            logger.warning(
                f"Abandoning crash trade: {market_id} "
                f"{crash['side']}@${crash['entry_price']} - {reason}"
            )
            del self._active_crashes[market_id]
    
    def _is_within_detection_window(self, market_id: str) -> bool:
        """
        Check if current time is within detection window from round start.
        
        Args:
            market_id: Market identifier
            
        Returns:
            bool: True if within window, False otherwise
        """
        if market_id not in self._round_starts:
            # No round start tracked, assume we're in window
            return True
        
        round_start = self._round_starts[market_id]
        now = datetime.now()
        elapsed = (now - round_start).total_seconds() / 60  # Minutes
        
        return elapsed <= self.window_minutes
    
    def get_active_crashes(self) -> Dict[str, Dict]:
        """
        Get all active crash positions waiting for hedge.
        
        Returns:
            Dict of active crashes
        """
        return self._active_crashes.copy()
    
    def cleanup_stale_crashes(self, max_age_minutes: int = 15) -> None:
        """
        Clean up crash positions that are too old.
        
        Args:
            max_age_minutes: Maximum age in minutes before abandoning
        """
        now = datetime.now()
        stale_markets = []
        
        for market_id, crash in self._active_crashes.items():
            age = (now - crash['timestamp']).total_seconds() / 60
            if age > max_age_minutes:
                stale_markets.append(market_id)
        
        for market_id in stale_markets:
            self.abandon_crash_trade(market_id, reason=f"stale (>{max_age_minutes}min)")
