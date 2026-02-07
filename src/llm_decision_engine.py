"""
LLM Decision Engine for Polymarket Trading Bot.

Replaces hardcoded decision logic with intelligent, context-aware LLM-driven decisions.
Uses NVIDIA DeepSeek API for reasoning with fallback to rule-based logic.

Key Responsibilities:
- Analyze market conditions and opportunities
- Make entry/exit decisions with confidence scoring
- Determine optimal position sizing
- Select appropriate order types (market/limit)
- Adapt to changing market conditions
"""

import asyncio
import logging
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from openai import OpenAI

logger = logging.getLogger(__name__)


class TradeAction(Enum):
    """Possible trade actions."""
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    BUY_BOTH = "buy_both"  # For arbitrage
    SELL_YES = "sell_yes"
    SELL_NO = "sell_no"
    HOLD = "hold"
    SKIP = "skip"


class OrderType(Enum):
    """Order types for execution."""
    MARKET = "market"
    LIMIT = "limit"
    FOK = "fok"  # Fill-or-Kill


@dataclass
class MarketContext:
    """Market context for LLM decision making."""
    market_id: str
    question: str
    asset: str
    yes_price: Decimal
    no_price: Decimal
    yes_liquidity: Decimal
    no_liquidity: Decimal
    volume_24h: Decimal
    time_to_resolution: float  # minutes
    spread: Decimal
    volatility_1h: Optional[Decimal] = None
    recent_price_changes: Optional[List[Decimal]] = None
    
    def to_prompt_context(self) -> str:
        """Convert to string for LLM prompt."""
        return f"""
Market: {self.question}
Asset: {self.asset}
YES Price: ${self.yes_price:.4f}
NO Price: ${self.no_price:.4f}
Sum (YES+NO): ${self.yes_price + self.no_price:.4f}
Spread: ${self.spread:.4f}
YES Liquidity: ${self.yes_liquidity:.2f}
NO Liquidity: ${self.no_liquidity:.2f}
24h Volume: ${self.volume_24h:.2f}
Time to Resolution: {self.time_to_resolution:.1f} minutes
1h Volatility: {f'{self.volatility_1h*100:.2f}%' if self.volatility_1h else 'N/A'}
"""


@dataclass
class PortfolioState:
    """Current portfolio state for decision context."""
    available_balance: Decimal
    total_balance: Decimal
    open_positions: List[Dict[str, Any]]
    daily_pnl: Decimal
    win_rate_today: float
    trades_today: int
    max_position_size: Decimal
    
    def to_prompt_context(self) -> str:
        """Convert to string for LLM prompt."""
        return f"""
Available Balance: ${self.available_balance:.2f}
Total Portfolio: ${self.total_balance:.2f}
Open Positions: {len(self.open_positions)}
Daily P&L: ${self.daily_pnl:.2f}
Win Rate Today: {self.win_rate_today*100:.1f}%
Trades Today: {self.trades_today}
Max Position Size: ${self.max_position_size:.2f}
"""


@dataclass
class TradeDecision:
    """LLM-generated trade decision with reasoning."""
    action: TradeAction
    confidence: float  # 0-100
    position_size: Decimal
    order_type: OrderType
    limit_price: Optional[Decimal]
    reasoning: str
    risk_assessment: str
    expected_profit: Decimal
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def should_execute(self) -> bool:
        """Check if decision meets confidence threshold."""
        return self.confidence >= 70 and self.action not in [TradeAction.HOLD, TradeAction.SKIP]


class LLMDecisionEngine:
    """
    Central intelligence for trading decisions using LLM reasoning.
    
    Architecture:
    1. Market Analyst - Evaluates opportunity quality
    2. Risk Manager - Assesses and mitigates risks
    3. Position Sizer - Determines optimal trade size
    4. Executor - Decides order type and timing
    
    Uses chain-of-thought reasoning for transparent, auditable decisions.
    """
    
    # System prompt for trading decisions
    TRADING_SYSTEM_PROMPT = """You are an expert cryptocurrency prediction market trader analyzing Polymarket opportunities.

Your role is to make intelligent, risk-aware trading decisions for 15-minute resolution crypto markets.

CRITICAL RULES:
1. Never risk more than 5% of available balance on a single trade
2. Only trade when confidence is HIGH (70%+)
3. Consider fees (2-3%) and gas costs (~$0.02) in profit calculations
4. For arbitrage: YES + NO must be < $0.97 to be profitable after fees
5. Prefer smaller, consistent profits over large risky bets
6. If uncertain, recommend SKIP

DECISION FACTORS:
- Arbitrage opportunity (YES + NO < $1.00)
- Market liquidity (higher = safer)
- Time to resolution (shorter = more certain)
- Recent volatility (high volatility = risky)
- Current portfolio exposure

OUTPUT FORMAT (JSON):
{
    "action": "buy_both|buy_yes|buy_no|skip|hold",
    "confidence": 0-100,
    "position_size_pct": 0-5,
    "order_type": "fok|limit|market",
    "limit_price": null or price,
    "reasoning": "brief explanation",
    "risk_assessment": "low|medium|high",
    "expected_profit_pct": 0-10
}

Always respond with valid JSON only."""

    def __init__(
        self,
        nvidia_api_key: str,
        nvidia_api_url: str = "https://integrate.api.nvidia.com/v1",
        min_confidence_threshold: float = 70.0,
        max_position_pct: float = 5.0,
        decision_timeout: float = 5.0,
        enable_chain_of_thought: bool = True
    ):
        """
        Initialize LLM Decision Engine.
        
        Args:
            nvidia_api_key: API key for NVIDIA AI service
            nvidia_api_url: NVIDIA API endpoint
            min_confidence_threshold: Minimum confidence to execute (default 70%)
            max_position_pct: Maximum position size as % of balance (default 5%)
            decision_timeout: Timeout for LLM calls in seconds
            enable_chain_of_thought: Enable detailed reasoning
        """
        self.nvidia_api_key = nvidia_api_key
        self.nvidia_api_url = nvidia_api_url
        self.min_confidence_threshold = min_confidence_threshold
        self.max_position_pct = max_position_pct
        self.decision_timeout = decision_timeout
        self.enable_chain_of_thought = enable_chain_of_thought
        
        # Initialize OpenAI-compatible client for NVIDIA API
        self.client = OpenAI(
            base_url=nvidia_api_url,
            api_key=nvidia_api_key
        )
        
        # Track decision history for learning
        self._decision_history: List[TradeDecision] = []
        self._fallback_count = 0
        self._success_count = 0
        
        logger.info(
            f"LLM Decision Engine initialized: "
            f"confidence_threshold={min_confidence_threshold}%, "
            f"max_position={max_position_pct}%, "
            f"timeout={decision_timeout}s"
        )
    
    async def make_decision(
        self,
        market_context: MarketContext,
        portfolio_state: PortfolioState,
        opportunity_type: str = "arbitrage"
    ) -> TradeDecision:
        """
        Make an intelligent trading decision using LLM reasoning.
        
        Args:
            market_context: Current market data and conditions
            portfolio_state: Current portfolio state
            opportunity_type: Type of opportunity (arbitrage, directional, etc.)
            
        Returns:
            TradeDecision with action, confidence, sizing, and reasoning
        """
        try:
            # Build prompt with all context
            user_prompt = self._build_decision_prompt(
                market_context, portfolio_state, opportunity_type
            )
            
            # Call LLM with timeout
            decision = await asyncio.wait_for(
                self._call_llm(user_prompt, market_context, portfolio_state),
                timeout=self.decision_timeout
            )
            
            self._success_count += 1
            self._decision_history.append(decision)
            
            logger.info(
                f"LLM Decision: {decision.action.value} | "
                f"Confidence: {decision.confidence}% | "
                f"Size: ${decision.position_size} | "
                f"Reasoning: {decision.reasoning[:100]}..."
            )
            
            return decision
            
        except asyncio.TimeoutError:
            logger.warning(f"LLM decision timeout ({self.decision_timeout}s), using fallback")
            return self._fallback_decision(market_context, portfolio_state)
            
        except Exception as e:
            logger.error(f"LLM decision error: {e}, using fallback")
            return self._fallback_decision(market_context, portfolio_state)
    
    async def _call_llm(
        self,
        user_prompt: str,
        market_context: MarketContext,
        portfolio_state: PortfolioState
    ) -> TradeDecision:
        """Call LLM API and parse response."""
        try:
            # Make API call
            completion = self.client.chat.completions.create(
                model="deepseek-ai/deepseek-v3.2",
                messages=[
                    {"role": "system", "content": self.TRADING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent decisions
                max_tokens=1024,
                timeout=self.decision_timeout
            )
            
            # Extract response
            response_text = completion.choices[0].message.content if completion.choices else ""
            
            # Parse JSON response
            return self._parse_llm_response(
                response_text, market_context, portfolio_state
            )
            
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise
    
    def _build_decision_prompt(
        self,
        market_context: MarketContext,
        portfolio_state: PortfolioState,
        opportunity_type: str
    ) -> str:
        """Build the decision prompt with all context."""
        prompt = f"""TRADING OPPORTUNITY: {opportunity_type.upper()}

{market_context.to_prompt_context()}

PORTFOLIO STATE:
{portfolio_state.to_prompt_context()}

OPPORTUNITY ANALYSIS:
- Price Sum: ${market_context.yes_price + market_context.no_price:.4f}
- Potential Arbitrage: ${Decimal('1.0') - (market_context.yes_price + market_context.no_price):.4f}
- After 3% Fees: ${Decimal('1.0') - (market_context.yes_price + market_context.no_price) - Decimal('0.03'):.4f}
- Min Profitable Threshold: YES + NO < $0.97

Analyze this opportunity and provide your trading decision as JSON."""

        return prompt
    
    def _parse_llm_response(
        self,
        response_text: str,
        market_context: MarketContext,
        portfolio_state: PortfolioState
    ) -> TradeDecision:
        """Parse LLM JSON response into TradeDecision."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = response_text
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0]
            
            data = json.loads(json_text.strip())
            
            # Map action string to enum
            action_map = {
                "buy_both": TradeAction.BUY_BOTH,
                "buy_yes": TradeAction.BUY_YES,
                "buy_no": TradeAction.BUY_NO,
                "sell_yes": TradeAction.SELL_YES,
                "sell_no": TradeAction.SELL_NO,
                "hold": TradeAction.HOLD,
                "skip": TradeAction.SKIP
            }
            action = action_map.get(data.get("action", "skip"), TradeAction.SKIP)
            
            # Map order type
            order_type_map = {
                "fok": OrderType.FOK,
                "limit": OrderType.LIMIT,
                "market": OrderType.MARKET
            }
            order_type = order_type_map.get(
                data.get("order_type", "fok"), OrderType.FOK
            )
            
            # Calculate position size
            position_pct = min(
                float(data.get("position_size_pct", 1.0)),
                self.max_position_pct
            )
            position_size = portfolio_state.available_balance * Decimal(str(position_pct / 100))
            
            # Cap at max allowed
            position_size = min(position_size, portfolio_state.max_position_size)
            
            # Calculate expected profit
            expected_profit_pct = float(data.get("expected_profit_pct", 0))
            expected_profit = position_size * Decimal(str(expected_profit_pct / 100))
            
            return TradeDecision(
                action=action,
                confidence=float(data.get("confidence", 0)),
                position_size=position_size,
                order_type=order_type,
                limit_price=Decimal(str(data["limit_price"])) if data.get("limit_price") else None,
                reasoning=data.get("reasoning", "No reasoning provided"),
                risk_assessment=data.get("risk_assessment", "unknown"),
                expected_profit=expected_profit
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}, response: {response_text[:200]}")
            return self._fallback_decision(market_context, portfolio_state)
    
    def _fallback_decision(
        self,
        market_context: MarketContext,
        portfolio_state: PortfolioState
    ) -> TradeDecision:
        """
        Rule-based fallback when LLM is unavailable or fails.
        
        Uses simple arbitrage detection logic:
        - If YES + NO < $0.97: BUY_BOTH with FOK orders
        - Otherwise: SKIP
        """
        self._fallback_count += 1
        
        # Calculate arbitrage opportunity
        total_price = market_context.yes_price + market_context.no_price
        profit_margin = Decimal('1.0') - total_price - Decimal('0.03')  # After ~3% fees
        
        # Simple arbitrage check
        if profit_margin > Decimal('0.005'):  # 0.5% minimum profit
            # Calculate conservative position size (2% of balance)
            position_size = min(
                portfolio_state.available_balance * Decimal('0.02'),
                portfolio_state.max_position_size,
                market_context.yes_liquidity * Decimal('0.1'),  # Max 10% of liquidity
                market_context.no_liquidity * Decimal('0.1')
            )
            
            return TradeDecision(
                action=TradeAction.BUY_BOTH,
                confidence=75.0,  # Higher confidence for clear arbitrage
                position_size=position_size,
                order_type=OrderType.FOK,
                limit_price=None,
                reasoning=f"Fallback: Clear arbitrage opportunity. "
                         f"Total price ${total_price:.4f}, profit margin {profit_margin*100:.2f}%",
                risk_assessment="low",
                expected_profit=position_size * profit_margin
            )
        
        return TradeDecision(
            action=TradeAction.SKIP,
            confidence=90.0,
            position_size=Decimal('0'),
            order_type=OrderType.FOK,
            limit_price=None,
            reasoning=f"Fallback: No profitable opportunity. "
                     f"Total price ${total_price:.4f}, profit margin {profit_margin*100:.2f}%",
            risk_assessment="low",
            expected_profit=Decimal('0')
        )
    
    async def evaluate_multiple_opportunities(
        self,
        opportunities: List[Tuple[MarketContext, str]],
        portfolio_state: PortfolioState,
        max_concurrent: int = 3
    ) -> List[TradeDecision]:
        """
        Evaluate multiple opportunities and rank by confidence/expected profit.
        
        Args:
            opportunities: List of (MarketContext, opportunity_type) tuples
            portfolio_state: Current portfolio state
            max_concurrent: Maximum concurrent LLM calls
            
        Returns:
            List of TradeDecisions sorted by expected value
        """
        decisions = []
        
        # Create async tasks for each opportunity
        async def evaluate_one(market_ctx: MarketContext, opp_type: str) -> TradeDecision:
            return await self.make_decision(market_ctx, portfolio_state, opp_type)
        
        # Process in batches to respect rate limits
        for i in range(0, len(opportunities), max_concurrent):
            batch = opportunities[i:i + max_concurrent]
            batch_tasks = [
                evaluate_one(ctx, opp_type) 
                for ctx, opp_type in batch
            ]
            batch_decisions = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for decision in batch_decisions:
                if isinstance(decision, TradeDecision):
                    decisions.append(decision)
                else:
                    logger.error(f"Decision evaluation failed: {decision}")
        
        # Sort by expected value (confidence × expected profit)
        decisions.sort(
            key=lambda d: d.confidence * float(d.expected_profit),
            reverse=True
        )
        
        return decisions
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get decision engine statistics."""
        total_decisions = len(self._decision_history)
        
        if total_decisions == 0:
            return {
                "total_decisions": 0,
                "success_rate": 0,
                "fallback_rate": 0,
                "avg_confidence": 0,
                "action_distribution": {}
            }
        
        action_counts = {}
        total_confidence = 0
        
        for decision in self._decision_history:
            action_name = decision.action.value
            action_counts[action_name] = action_counts.get(action_name, 0) + 1
            total_confidence += decision.confidence
        
        return {
            "total_decisions": total_decisions,
            "success_rate": self._success_count / (self._success_count + self._fallback_count) if (self._success_count + self._fallback_count) > 0 else 0,
            "fallback_rate": self._fallback_count / total_decisions,
            "avg_confidence": total_confidence / total_decisions,
            "action_distribution": action_counts
        }
