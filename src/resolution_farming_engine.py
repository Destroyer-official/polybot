"""
Resolution Farming Engine for buying near-certain positions before market close.

Implements Requirements 5.1, 5.2, 5.3, 5.4, 5.5:
- Scan markets closing within 2 minutes
- Verify outcome certainty using CEX data
- Buy 97-99¢ positions
- Limit position size to 2% of bankroll
- Skip markets with ambiguous resolution criteria
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict
import uuid

from src.models import Market, Opportunity
from src.ai_safety_guard import AISafetyGuard

logger = logging.getLogger(__name__)


class ResolutionFarmingEngine:
    """
    Resolution Farming strategy: buy near-certain positions (97-99¢) just before market close.
    
    This strategy targets markets closing within 2 minutes where the outcome is verifiable
    from CEX data and positions are priced attractively (97-99¢).
    """
    
    def __init__(
        self,
        cex_feeds: Dict[str, 'WebSocketFeed'],
        ai_safety_guard: AISafetyGuard,
        min_price: Decimal = Decimal('0.97'),
        max_price: Decimal = Decimal('0.99'),
        min_profit_threshold: Decimal = Decimal('0.01'),  # 1% minimum
        max_position_percentage: Decimal = Decimal('0.02'),  # 2% of bankroll
        closing_window_seconds: int = 120  # 2 minutes
    ):
        """
        Initialize Resolution Farming Engine.
        
        Args:
            cex_feeds: Dictionary of CEX WebSocket feeds by asset (BTC, ETH, SOL, XRP)
            ai_safety_guard: AI safety guard for ambiguous market filtering
            min_price: Minimum position price to consider (default 97¢)
            max_price: Maximum position price to consider (default 99¢)
            min_profit_threshold: Minimum profit percentage (default 1%)
            max_position_percentage: Maximum position size as % of bankroll (default 2%)
            closing_window_seconds: Time window before close to consider (default 120s)
        """
        self.cex_feeds = cex_feeds
        self.ai_safety_guard = ai_safety_guard
        self.min_price = min_price
        self.max_price = max_price
        self.min_profit_threshold = min_profit_threshold
        self.max_position_percentage = max_position_percentage
        self.closing_window_seconds = closing_window_seconds
        
        logger.info(
            f"Resolution Farming Engine initialized: "
            f"price_range={min_price}-{max_price}, "
            f"min_profit={min_profit_threshold*100}%, "
            f"max_position={max_position_percentage*100}% of bankroll, "
            f"closing_window={closing_window_seconds}s"
        )
    
    async def scan_closing_markets(self, markets: List[Market]) -> List[Opportunity]:
        """
        Find markets closing within 2 minutes with certain outcomes.
        
        Implements Requirements 5.1, 5.2:
        - Scan markets closing within 2 minutes
        - Identify positions priced at 97-99¢
        
        Args:
            markets: List of markets to scan
            
        Returns:
            List of resolution farming opportunities
        """
        opportunities = []
        now = datetime.now()
        closing_threshold = now + timedelta(seconds=self.closing_window_seconds)
        
        logger.debug(f"Scanning {len(markets)} markets for resolution farming opportunities")
        
        for market in markets:
            # Check if market is closing soon (Requirement 5.1)
            if not self._is_closing_soon(market, now, closing_threshold):
                continue
            
            # Skip markets with ambiguous resolution criteria (Requirement 5.4)
            if self.ai_safety_guard._has_ambiguous_keywords(market.question):
                logger.debug(f"Skipping ambiguous market: {market.question}")
                continue
            
            # Verify outcome certainty using CEX data (Requirement 5.3)
            certain_outcome = self.verify_outcome_certainty(market)
            if certain_outcome is None:
                logger.debug(f"Cannot verify outcome certainty for market: {market.market_id}")
                continue
            
            # Get price for the certain outcome
            outcome_price = market.yes_price if certain_outcome == "YES" else market.no_price
            
            # Check if price is in attractive range (97-99¢) (Requirement 5.2)
            if not (self.min_price <= outcome_price <= self.max_price):
                logger.debug(
                    f"Price {outcome_price} outside range {self.min_price}-{self.max_price} "
                    f"for market {market.market_id}"
                )
                continue
            
            # Calculate expected profit
            # For resolution farming, we buy one side and expect $1.00 redemption
            expected_profit = Decimal('1.00') - outcome_price
            profit_percentage = expected_profit / outcome_price if outcome_price > 0 else Decimal('0')
            
            # Check minimum profit threshold (1% for resolution farming)
            if profit_percentage < self.min_profit_threshold:
                logger.debug(
                    f"Profit {profit_percentage*100:.2f}% below threshold "
                    f"{self.min_profit_threshold*100}% for market {market.market_id}"
                )
                continue
            
            # Create opportunity
            opportunity = Opportunity(
                opportunity_id=str(uuid.uuid4()),
                market_id=market.market_id,
                strategy="resolution_farming",
                timestamp=now,
                yes_price=market.yes_price,
                no_price=market.no_price,
                yes_fee=Decimal('0'),  # Fees calculated separately
                no_fee=Decimal('0'),
                total_cost=outcome_price,
                expected_profit=expected_profit,
                profit_percentage=profit_percentage,
                position_size=Decimal('0'),  # Calculated later based on bankroll
                gas_estimate=0  # Estimated later
            )
            
            opportunities.append(opportunity)
            logger.info(
                f"Resolution farming opportunity found: {market.market_id} "
                f"({certain_outcome} @ ${outcome_price}, profit: {profit_percentage*100:.2f}%, "
                f"closes in {(market.end_time - now).total_seconds():.0f}s)"
            )
        
        logger.info(f"Found {len(opportunities)} resolution farming opportunities")
        return opportunities
    
    def verify_outcome_certainty(self, market: Market) -> Optional[str]:
        """
        Verify outcome is certain based on CEX data.
        
        Implements Requirement 5.3: Verify outcome matches current CEX price direction
        
        Args:
            market: The market to verify
            
        Returns:
            Optional[str]: "YES" or "NO" if outcome is certain, None if uncertain
        """
        # Get current CEX price for the asset
        current_price = self._get_current_cex_price(market.asset)
        if current_price is None:
            logger.warning(f"No CEX price available for {market.asset}")
            return None
        
        # Parse strike price from market question
        strike_price = market.parse_strike_price()
        if strike_price is None:
            logger.warning(f"Could not parse strike price from: {market.question}")
            return None
        
        # Determine certain outcome based on market question
        question_lower = market.question.lower()
        
        if "above" in question_lower or "over" in question_lower or ">" in question_lower:
            # Market asks if price will be ABOVE strike
            if current_price > strike_price:
                return "YES"  # Price is above, YES will win
            else:
                return "NO"  # Price is below, NO will win
        
        elif "below" in question_lower or "under" in question_lower or "<" in question_lower:
            # Market asks if price will be BELOW strike
            if current_price < strike_price:
                return "YES"  # Price is below, YES will win
            else:
                return "NO"  # Price is above, NO will win
        
        else:
            # Cannot determine market direction
            logger.warning(f"Cannot determine market direction from: {market.question}")
            return None
    
    def calculate_position_size(self, bankroll: Decimal) -> Decimal:
        """
        Calculate position size limited to 2% of bankroll.
        
        Implements Requirement 5.5: Limit position size to 2% of bankroll
        
        Args:
            bankroll: Current bankroll amount
            
        Returns:
            Position size in USDC
        """
        position_size = bankroll * self.max_position_percentage
        return position_size
    
    def _is_closing_soon(
        self,
        market: Market,
        now: datetime,
        closing_threshold: datetime
    ) -> bool:
        """
        Check if market is closing within the configured window.
        
        Args:
            market: The market to check
            now: Current datetime
            closing_threshold: Threshold datetime for closing window
            
        Returns:
            bool: True if market closes within window
        """
        # Ensure market hasn't already closed
        if market.end_time <= now:
            return False
        
        # Check if market closes within window
        return market.end_time <= closing_threshold
    
    def _get_current_cex_price(self, asset: str) -> Optional[Decimal]:
        """
        Get current CEX price for an asset.
        
        Args:
            asset: Asset symbol (BTC, ETH, SOL, XRP)
            
        Returns:
            Optional[Decimal]: Current price if available, None otherwise
        """
        if asset not in self.cex_feeds:
            logger.warning(f"No CEX feed configured for {asset}")
            return None
        
        try:
            # Get latest price from CEX feed
            feed = self.cex_feeds[asset]
            price = feed.get_latest_price()
            
            if price is None:
                logger.warning(f"No price data available from CEX feed for {asset}")
                return None
            
            return Decimal(str(price))
        
        except Exception as e:
            logger.error(f"Error getting CEX price for {asset}: {e}")
            return None
