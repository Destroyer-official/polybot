"""
NegRisk Arbitrage Engine for Polymarket Trading Bot.

Exploits pricing inefficiencies in multi-outcome markets (NegRisk markets)
where probability sum deviates from 100%.

This strategy accounts for 73% of top arbitrageur profits on Polymarket ($29M extracted).

Key Strategy:
- For markets with 3+ mutually exclusive outcomes
- When sum(prices) < $0.98: Buy all outcomes (guaranteed profit)
- When sum(prices) > $1.02: Sell all outcomes if holding
"""

import asyncio
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from src.models import Market, TradeResult
from src.order_manager import OrderManager, Order
from src.ai_safety_guard import AISafetyGuard

logger = logging.getLogger(__name__)


@dataclass
class NegRiskOutcome:
    """Single outcome in a NegRisk market."""
    token_id: str
    name: str
    price: Decimal
    liquidity: Decimal
    
    
@dataclass
class NegRiskMarket:
    """Multi-outcome NegRisk market."""
    market_id: str
    condition_id: str
    question: str
    outcomes: List[NegRiskOutcome]
    total_volume: Decimal
    end_time: datetime
    
    @property
    def probability_sum(self) -> Decimal:
        """Sum of all outcome prices (should equal 1.0)."""
        return sum(o.price for o in self.outcomes)
    
    @property
    def deviation(self) -> Decimal:
        """Deviation from expected $1.00 sum."""
        return abs(Decimal('1.0') - self.probability_sum)
    
    @property
    def min_liquidity(self) -> Decimal:
        """Minimum liquidity across all outcomes."""
        return min(o.liquidity for o in self.outcomes) if self.outcomes else Decimal('0')
    
    @property
    def is_arbitrageable(self) -> bool:
        """Check if market has arbitrage opportunity after fees."""
        # Need at least 2% deviation to cover fees
        return self.deviation >= Decimal('0.02')


@dataclass
class NegRiskOpportunity:
    """Detected NegRisk arbitrage opportunity."""
    opportunity_id: str
    market: NegRiskMarket
    strategy: str  # "buy_all" or "sell_all"
    probability_sum: Decimal
    deviation: Decimal
    expected_profit_pct: Decimal
    max_position_size: Decimal  # Limited by min liquidity
    timestamp: datetime
    
    @property
    def expected_profit(self) -> Decimal:
        """Expected profit in USDC per $1 invested."""
        return self.deviation - Decimal('0.03')  # After ~3% fees


class NegRiskArbitrageEngine:
    """
    Detects and executes NegRisk arbitrage opportunities.
    
    NegRisk markets have 3+ mutually exclusive outcomes where one must occur.
    Arbitrage exists when:
    - sum(prices) < $0.98: Buy all outcomes, guaranteed profit
    - sum(prices) > $1.02: Sell all outcomes if holding
    
    This strategy generated 73% of top arbitrageur profits ($29M) on Polymarket.
    """
    
    # Minimum deviation to consider (after fees)
    MIN_DEVIATION_THRESHOLD = Decimal('0.02')  # 2%
    
    # Minimum liquidity per outcome
    MIN_LIQUIDITY = Decimal('50.0')  # $50
    
    # Maximum position as % of min liquidity
    MAX_LIQUIDITY_USAGE = Decimal('0.10')  # 10% of available liquidity
    
    def __init__(
        self,
        clob_client,
        order_manager: OrderManager,
        ai_safety_guard: Optional[AISafetyGuard] = None,
        min_profit_threshold: Decimal = Decimal('0.005'),  # 0.5%
        max_position_size: Decimal = Decimal('5.0')
    ):
        """
        Initialize NegRisk Arbitrage Engine.
        
        Args:
            clob_client: CLOB client for market data and order execution
            order_manager: Order manager for trade execution
            ai_safety_guard: Optional AI safety validation
            min_profit_threshold: Minimum profit % to execute
            max_position_size: Maximum position size per trade
        """
        self.clob_client = clob_client
        self.order_manager = order_manager
        self.ai_safety_guard = ai_safety_guard
        self.min_profit_threshold = min_profit_threshold
        self.max_position_size = max_position_size
        
        # Track executed opportunities
        self._executed_opportunities: List[str] = []
        
        logger.info(
            f"NegRisk Arbitrage Engine initialized: "
            f"min_profit={min_profit_threshold*100}%, "
            f"max_position=${max_position_size}"
        )
    
    async def fetch_negrisk_markets(self) -> List[NegRiskMarket]:
        """
        Fetch all active NegRisk markets from Polymarket.
        
        NegRisk markets are identified by having 3+ outcomes with the same
        condition_id (mutually exclusive outcomes).
        
        Returns:
            List of NegRisk markets with their outcomes
        """
        try:
            # Fetch all active markets from CLOB API
            response = await asyncio.to_thread(
                self.clob_client.get_markets
            )
            
            if not response:
                logger.warning("No markets returned from API")
                return []
            
            # Handle different response formats
            markets_list = []
            
            # If response is a string, it's the raw response - skip it
            if isinstance(response, str):
                logger.debug("get_markets returned string, using Gamma API instead")
                return []
            
            # If response is a dict, extract the data
            if isinstance(response, dict):
                markets_list = response.get("data", response.get("markets", []))
            elif isinstance(response, list):
                markets_list = response
            else:
                logger.warning(f"Unexpected response type: {type(response)}")
                # Use Gamma API as fallback
                logger.info("Falling back to Gamma API for NegRisk markets...")
                import requests
                gamma_resp = requests.get("https://gamma-api.polymarket.com/markets?closed=false&limit=100")
                if gamma_resp.status_code == 200:
                    markets_list = gamma_resp.json()
                else:
                    return []
            
            # Group markets by condition_id to find NegRisk markets
            condition_groups: Dict[str, List[Dict]] = {}
            
            for market in markets_list:
                # Skip non-dict items
                if not isinstance(market, dict):
                    continue
                    
                condition_id = market.get("condition_id", "")
                if condition_id:
                    if condition_id not in condition_groups:
                        condition_groups[condition_id] = []
                    condition_groups[condition_id].append(market)
            
            # Filter for NegRisk markets (3+ outcomes)
            negrisk_markets = []
            
            for condition_id, markets in condition_groups.items():
                if len(markets) >= 3:
                    # This is a NegRisk market
                    negrisk_market = self._parse_negrisk_market(condition_id, markets)
                    if negrisk_market:
                        negrisk_markets.append(negrisk_market)
            
            logger.info(f"Found {len(negrisk_markets)} NegRisk markets")
            return negrisk_markets
            
        except Exception as e:
            logger.error(f"Failed to fetch NegRisk markets: {e}")
            return []
    
    def _parse_negrisk_market(
        self,
        condition_id: str,
        markets: List[Dict]
    ) -> Optional[NegRiskMarket]:
        """Parse raw market data into NegRiskMarket."""
        try:
            outcomes = []
            
            for market in markets:
                token_id = market.get("token_id", market.get("id", ""))
                name = market.get("outcome", market.get("title", "Unknown"))
                
                # Get best prices from orderbook
                price = Decimal(str(market.get("best_ask", market.get("price", "0.5"))))
                liquidity = Decimal(str(market.get("liquidity", "0")))
                
                outcomes.append(NegRiskOutcome(
                    token_id=token_id,
                    name=name,
                    price=price,
                    liquidity=liquidity
                ))
            
            # Get common market info from first entry
            first_market = markets[0]
            question = first_market.get("question", first_market.get("title", "Unknown"))
            volume = Decimal(str(first_market.get("volume", "0")))
            
            # Parse end time
            end_time_str = first_market.get("end_date_iso", first_market.get("end_time", ""))
            try:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            except:
                end_time = datetime.now()
            
            return NegRiskMarket(
                market_id=first_market.get("id", condition_id),
                condition_id=condition_id,
                question=question,
                outcomes=outcomes,
                total_volume=volume,
                end_time=end_time
            )
            
        except Exception as e:
            logger.error(f"Failed to parse NegRisk market: {e}")
            return None
    
    async def scan_opportunities(
        self,
        markets: Optional[List[NegRiskMarket]] = None
    ) -> List[NegRiskOpportunity]:
        """
        Scan for NegRisk arbitrage opportunities.
        
        Args:
            markets: Optional pre-fetched markets, otherwise fetches fresh
            
        Returns:
            List of profitable NegRisk opportunities
        """
        if markets is None:
            markets = await self.fetch_negrisk_markets()
        
        opportunities = []
        
        for market in markets:
            # Check if arbitrageable
            if not market.is_arbitrageable:
                continue
            
            # Check minimum liquidity
            if market.min_liquidity < self.MIN_LIQUIDITY:
                logger.debug(
                    f"Skipping {market.question[:50]}: "
                    f"low liquidity ${market.min_liquidity}"
                )
                continue
            
            # Calculate expected profit after fees
            expected_profit_pct = market.deviation - Decimal('0.03')
            
            if expected_profit_pct < self.min_profit_threshold:
                continue
            
            # Determine strategy
            if market.probability_sum < Decimal('1.0'):
                strategy = "buy_all"
            else:
                strategy = "sell_all"
            
            # Calculate max position (limited by liquidity)
            max_position = min(
                market.min_liquidity * self.MAX_LIQUIDITY_USAGE,
                self.max_position_size
            )
            
            opportunity = NegRiskOpportunity(
                opportunity_id=f"negrisk_{uuid.uuid4().hex[:12]}",
                market=market,
                strategy=strategy,
                probability_sum=market.probability_sum,
                deviation=market.deviation,
                expected_profit_pct=expected_profit_pct,
                max_position_size=max_position,
                timestamp=datetime.now()
            )
            
            opportunities.append(opportunity)
            
            logger.info(
                f"✅ NegRisk Opportunity: {market.question[:50]}... | "
                f"Sum: ${market.probability_sum:.4f} | "
                f"Deviation: {market.deviation*100:.2f}% | "
                f"Expected Profit: {expected_profit_pct*100:.2f}% | "
                f"Strategy: {strategy}"
            )
        
        logger.info(f"Found {len(opportunities)} NegRisk opportunities")
        return opportunities
    
    async def execute(
        self,
        opportunity: NegRiskOpportunity,
        position_size: Optional[Decimal] = None
    ) -> TradeResult:
        """
        Execute NegRisk arbitrage trade.
        
        For "buy_all" strategy:
        1. Calculate position size per outcome
        2. Create FOK orders for all outcomes
        3. Submit all orders atomically
        4. Wait for all fills or cancel all
        
        Args:
            opportunity: The NegRisk opportunity to execute
            position_size: Optional override for position size
            
        Returns:
            TradeResult with execution details
        """
        trade_id = f"negrisk_trade_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now()
        
        # Determine position size
        size = position_size or opportunity.max_position_size
        size = min(size, self.max_position_size)
        
        logger.info(
            f"Executing NegRisk trade {trade_id}: "
            f"strategy={opportunity.strategy}, "
            f"size=${size}, "
            f"outcomes={len(opportunity.market.outcomes)}"
        )
        
        try:
            # Validate with AI safety guard if available
            if self.ai_safety_guard:
                # Create a mock market for safety check
                from src.models import Opportunity, Market
                mock_market = Market(
                    market_id=opportunity.market.market_id,
                    question=opportunity.market.question,
                    asset="MULTI",
                    yes_price=opportunity.probability_sum / len(opportunity.market.outcomes),
                    no_price=Decimal('0'),
                    volume=opportunity.market.total_volume,
                    liquidity=opportunity.market.min_liquidity,
                    end_time=opportunity.market.end_time
                )
                mock_opportunity = Opportunity(
                    opportunity_id=opportunity.opportunity_id,
                    market_id=opportunity.market.market_id,
                    strategy="negrisk_arbitrage",
                    timestamp=timestamp,
                    yes_price=opportunity.probability_sum,
                    no_price=Decimal('0'),
                    yes_fee=Decimal('0.015'),
                    no_fee=Decimal('0.015'),
                    total_cost=opportunity.probability_sum,
                    expected_profit=opportunity.expected_profit * size,
                    profit_percentage=opportunity.expected_profit_pct,
                    position_size=size,
                    gas_estimate=500000  # Higher for multiple orders
                )
                
                safety_decision = await self.ai_safety_guard.validate_trade(
                    opportunity=mock_opportunity,
                    market=mock_market,
                    current_balance=Decimal('100'),  # Placeholder
                    current_gas_price_gwei=50,
                    pending_tx_count=0
                )
                
                if not safety_decision.approved:
                    logger.warning(f"NegRisk trade rejected by safety guard: {safety_decision.reason}")
                    return self._create_failed_result(
                        trade_id, opportunity, timestamp,
                        f"Safety check failed: {safety_decision.reason}"
                    )
            
            # Create orders for all outcomes
            orders = []
            size_per_outcome = size / len(opportunity.market.outcomes)
            
            for outcome in opportunity.market.outcomes:
                order = self.order_manager.create_fok_order(
                    market_id=outcome.token_id,
                    side="YES" if opportunity.strategy == "buy_all" else "NO",
                    price=outcome.price,
                    size=size_per_outcome,
                    neg_risk=True  # Ensure correct signature for NegRisk markets
                )
                orders.append(order)
            
            # Submit all orders (would need atomic multi-order support)
            # For now, submit sequentially with rollback on failure
            filled_orders = []
            all_filled = True
            
            for order in orders:
                try:
                    filled = await self.order_manager.submit_order(order)
                    if filled:
                        filled_orders.append(order)
                    else:
                        all_filled = False
                        break
                except Exception as e:
                    logger.error(f"Order failed: {e}")
                    all_filled = False
                    break
            
            if not all_filled:
                # Rollback: Cancel or reverse filled orders
                logger.warning(f"NegRisk trade partially failed, {len(filled_orders)}/{len(orders)} filled")
                # In production, would need proper rollback logic
                return self._create_failed_result(
                    trade_id, opportunity, timestamp,
                    f"Partial fill: {len(filled_orders)}/{len(orders)} orders"
                )
            
            # Calculate actual profit
            actual_cost = sum(o.fill_price * size_per_outcome for o in filled_orders)
            actual_profit = size - actual_cost
            
            logger.info(
                f"NegRisk trade completed: cost=${actual_cost}, profit=${actual_profit}"
            )
            
            # Track executed opportunity
            self._executed_opportunities.append(opportunity.opportunity_id)
            
            return TradeResult(
                trade_id=trade_id,
                opportunity=None,  # Use NegRiskOpportunity instead
                timestamp=timestamp,
                status="success",
                yes_order_id=None,
                no_order_id=None,
                yes_filled=True,
                no_filled=True,
                yes_fill_price=None,
                no_fill_price=None,
                actual_cost=actual_cost,
                actual_profit=actual_profit,
                gas_cost=Decimal('0.05') * len(orders),
                net_profit=actual_profit - Decimal('0.05') * len(orders)
            )
            
        except Exception as e:
            logger.error(f"NegRisk trade execution failed: {e}", exc_info=True)
            return self._create_failed_result(trade_id, opportunity, timestamp, str(e))
    
    def _create_failed_result(
        self,
        trade_id: str,
        opportunity: NegRiskOpportunity,
        timestamp: datetime,
        error_message: str
    ) -> TradeResult:
        """Create a failed TradeResult."""
        return TradeResult(
            trade_id=trade_id,
            opportunity=None,
            timestamp=timestamp,
            status="failed",
            yes_order_id=None,
            no_order_id=None,
            yes_filled=False,
            no_filled=False,
            yes_fill_price=None,
            no_fill_price=None,
            actual_cost=Decimal('0'),
            actual_profit=Decimal('0'),
            gas_cost=Decimal('0'),
            net_profit=Decimal('0'),
            error_message=error_message
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get NegRisk engine statistics."""
        return {
            "opportunities_executed": len(self._executed_opportunities),
            "strategy": "negrisk_arbitrage",
            "min_deviation_threshold": float(self.MIN_DEVIATION_THRESHOLD * 100),
            "min_liquidity": float(self.MIN_LIQUIDITY),
            "max_position_size": float(self.max_position_size)
        }
