"""
Flash Crash Detection Engine for Polymarket 15-minute markets.

Based on 86% ROI strategy: Detect 15% price drops within 3 seconds.
"""

import time
from decimal import Decimal
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class PriceSnapshot:
    """Price snapshot at a specific time."""
    timestamp: float
    yes_price: Decimal
    no_price: Decimal


@dataclass
class FlashCrash:
    """Detected flash crash event."""
    market_id: str
    side: str  # "YES" or "NO"
    crash_pct: Decimal
    pre_crash_price: Decimal
    post_crash_price: Decimal
    timestamp: float


class FlashCrashDetector:
    """
    Detects flash crashes in Polymarket markets.
    
    Strategy: Monitor for 15% price drops within 3 seconds.
    When detected, signal to buy the crashed side (Leg 1).
    """
    
    def __init__(
        self,
        crash_threshold: Decimal = Decimal("0.15"),  # 15% drop
        time_window: float = 3.0,  # 3 seconds
        history_size: int = 10  # Keep last 10 snapshots
    ):
        """
        Initialize flash crash detector.
        
        Args:
            crash_threshold: Minimum price drop to trigger (0.15 = 15%)
            time_window: Time window for crash detection (seconds)
            history_size: Number of price snapshots to keep
        """
        self.crash_threshold = crash_threshold
        self.time_window = time_window
        self.history_size = history_size
        
        # Price history per market
        self.price_history: Dict[str, list[PriceSnapshot]] = {}
        
        # Track detected crashes to avoid duplicates
        self.detected_crashes: Dict[str, float] = {}  # market_id -> timestamp
        self.crash_cooldown = 60.0  # Don't detect same market for 60s
        
        logger.info(
            f"FlashCrashDetector initialized: "
            f"threshold={crash_threshold*100}%, "
            f"window={time_window}s"
        )
    
    def update_price(
        self,
        market_id: str,
        yes_price: Decimal,
        no_price: Decimal
    ) -> Optional[FlashCrash]:
        """
        Update price for a market and check for flash crash.
        
        Args:
            market_id: Market identifier
            yes_price: Current YES price
            no_price: Current NO price
            
        Returns:
            FlashCrash if detected, None otherwise
        """
        now = time.time()
        
        # Create snapshot
        snapshot = PriceSnapshot(
            timestamp=now,
            yes_price=yes_price,
            no_price=no_price
        )
        
        # Initialize history if needed
        if market_id not in self.price_history:
            self.price_history[market_id] = []
        
        # Add to history
        self.price_history[market_id].append(snapshot)
        
        # Keep only recent history
        if len(self.price_history[market_id]) > self.history_size:
            self.price_history[market_id].pop(0)
        
        # Need at least 2 snapshots to detect crash
        if len(self.price_history[market_id]) < 2:
            return None
        
        # Check if we're in cooldown for this market
        if market_id in self.detected_crashes:
            last_crash = self.detected_crashes[market_id]
            if now - last_crash < self.crash_cooldown:
                return None
        
        # Check for crash in recent history
        crash = self._detect_crash(market_id, snapshot)
        
        if crash:
            # Record crash to avoid duplicates
            self.detected_crashes[market_id] = now
            logger.warning(
                f"🚨 FLASH CRASH DETECTED: {market_id} "
                f"{crash.side} dropped {crash.crash_pct*100:.1f}% "
                f"(${crash.pre_crash_price:.3f} → ${crash.post_crash_price:.3f})"
            )
        
        return crash
    
    def _detect_crash(
        self,
        market_id: str,
        current: PriceSnapshot
    ) -> Optional[FlashCrash]:
        """
        Check if current price represents a flash crash.
        
        Args:
            market_id: Market identifier
            current: Current price snapshot
            
        Returns:
            FlashCrash if detected, None otherwise
        """
        history = self.price_history[market_id]
        
        # Check each recent snapshot within time window
        for old_snapshot in reversed(history[:-1]):
            time_diff = current.timestamp - old_snapshot.timestamp
            
            # Only check within time window
            if time_diff > self.time_window:
                break
            
            # Check YES side for crash
            yes_drop = (old_snapshot.yes_price - current.yes_price) / old_snapshot.yes_price
            if yes_drop >= self.crash_threshold:
                return FlashCrash(
                    market_id=market_id,
                    side="YES",
                    crash_pct=yes_drop,
                    pre_crash_price=old_snapshot.yes_price,
                    post_crash_price=current.yes_price,
                    timestamp=current.timestamp
                )
            
            # Check NO side for crash
            no_drop = (old_snapshot.no_price - current.no_price) / old_snapshot.no_price
            if no_drop >= self.crash_threshold:
                return FlashCrash(
                    market_id=market_id,
                    side="NO",
                    crash_pct=no_drop,
                    pre_crash_price=old_snapshot.no_price,
                    post_crash_price=current.no_price,
                    timestamp=current.timestamp
                )
        
        return None
    
    def should_hedge(
        self,
        market_id: str,
        leg1_side: str,
        leg1_price: Decimal,
        sum_target: Decimal = Decimal("0.95")
    ) -> Tuple[bool, Optional[Decimal]]:
        """
        Check if we should execute hedge (Leg 2).
        
        Args:
            market_id: Market identifier
            leg1_side: Side bought in Leg 1 ("YES" or "NO")
            leg1_price: Price paid in Leg 1
            sum_target: Maximum sum for hedging (default 0.95)
            
        Returns:
            (should_hedge, opposite_price) tuple
        """
        if market_id not in self.price_history:
            return False, None
        
        # Get latest prices
        latest = self.price_history[market_id][-1]
        
        # Determine opposite side price
        opposite_price = latest.no_price if leg1_side == "YES" else latest.yes_price
        
        # Check if sum meets target
        total_cost = leg1_price + opposite_price
        
        if total_cost <= sum_target:
            logger.info(
                f"✅ HEDGE SIGNAL: {market_id} "
                f"Leg1({leg1_side})=${leg1_price:.3f} + "
                f"Leg2({'NO' if leg1_side == 'YES' else 'YES'})=${opposite_price:.3f} = "
                f"${total_cost:.3f} ≤ ${sum_target:.3f}"
            )
            return True, opposite_price
        
        return False, opposite_price
    
    def clear_history(self, market_id: str):
        """Clear price history for a market."""
        if market_id in self.price_history:
            del self.price_history[market_id]
        if market_id in self.detected_crashes:
            del self.detected_crashes[market_id]
    
    def get_stats(self) -> Dict:
        """Get detector statistics."""
        return {
            'markets_tracked': len(self.price_history),
            'crashes_detected': len(self.detected_crashes),
            'crash_threshold': float(self.crash_threshold),
            'time_window': self.time_window
        }
