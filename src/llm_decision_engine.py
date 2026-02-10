"""
LLM Decision Engine V1 - Backwards Compatibility Module.

This module wraps LLMDecisionEngineV2 to provide the V1 API surface
that existing tests expect. All functionality is delegated to V2.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.llm_decision_engine_v2 import (
    LLMDecisionEngineV2,
    TradeAction,
    OrderType,
    TradeDecision,
)


@dataclass
class MarketContext:
    """V1 MarketContext with simpler to_prompt_context()."""
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

    def to_prompt_context(self) -> str:
        """V1 prompt context (no opportunity_type arg)."""
        return (
            f"Market: {self.question}\n"
            f"Asset: {self.asset}\n"
            f"YES Price: ${self.yes_price:.4f}\n"
            f"NO Price: ${self.no_price:.4f}\n"
            f"YES Liquidity: ${self.yes_liquidity:.2f}\n"
            f"NO Liquidity: ${self.no_liquidity:.2f}\n"
            f"Volume 24h: ${self.volume_24h:.2f}\n"
            f"Time to Resolution: {self.time_to_resolution} minutes\n"
            f"Spread: ${self.spread:.4f}"
        )


@dataclass
class PortfolioState:
    """V1 PortfolioState."""
    available_balance: Decimal
    total_balance: Decimal
    open_positions: List[Dict[str, Any]]
    daily_pnl: Decimal
    win_rate_today: float
    trades_today: int
    max_position_size: Decimal

    def to_prompt_context(self) -> str:
        return (
            f"Available Balance: ${self.available_balance:.2f}\n"
            f"Total Portfolio: ${self.total_balance:.2f}\n"
            f"Open Positions: {len(self.open_positions)}\n"
            f"Daily P&L: ${self.daily_pnl:.2f}\n"
            f"Win Rate Today: {self.win_rate_today*100:.1f}%\n"
            f"Trades Today: {self.trades_today}\n"
            f"Max Position Size: ${self.max_position_size:.2f}"
        )


class LLMDecisionEngine(LLMDecisionEngineV2):
    """
    V1-compatible wrapper around LLMDecisionEngineV2.

    Provides the same constructor and method signatures that the
    existing test suite expects.
    """

    def __init__(
        self,
        nvidia_api_key: str,
        nvidia_api_url: str = "https://integrate.api.nvidia.com/v1",
        min_confidence_threshold: float = 60.0,
        max_position_pct: float = 5.0,
        decision_timeout: float = 5.0,
    ):
        super().__init__(
            nvidia_api_key=nvidia_api_key,
            nvidia_api_url=nvidia_api_url,
            min_confidence_threshold=min_confidence_threshold,
            max_position_pct=max_position_pct,
            decision_timeout=decision_timeout,
        )

    def _fallback_decision(self, market_context, portfolio_state, reason="fallback"):
        """V1-compatible fallback: auto-detect arbitrage using V1 MarketContext."""
        total = market_context.yes_price + market_context.no_price
        after_fees = Decimal("1.0") - total - Decimal("0.03")

        if after_fees > 0:
            position_size = min(
                portfolio_state.available_balance * Decimal(str(self.max_position_pct / 100)),
                portfolio_state.max_position_size,
            )
            return TradeDecision(
                action=TradeAction.BUY_BOTH,
                confidence=80.0,
                position_size=position_size,
                order_type=OrderType.FOK,
                limit_price=None,
                reasoning=f"Fallback: clear arbitrage opportunity (profit after fees: ${after_fees:.4f})",
                risk_assessment="low",
                expected_profit=after_fees,
            )

        return TradeDecision(
            action=TradeAction.SKIP,
            confidence=90.0,
            position_size=Decimal("0"),
            order_type=OrderType.FOK,
            limit_price=None,
            reasoning=f"Fallback: no profitable arbitrage ({reason})",
            risk_assessment="low",
            expected_profit=Decimal("0"),
        )

    def _parse_llm_response(self, response_text, market_context, portfolio_state):
        """V1-compatible parse that delegates to V2 for JSON extraction."""
        try:
            import json

            json_text = response_text
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(json_text.strip())

            action_map = {
                "buy_both": TradeAction.BUY_BOTH,
                "buy_yes": TradeAction.BUY_YES,
                "buy_no": TradeAction.BUY_NO,
                "sell_yes": TradeAction.SELL_YES,
                "sell_no": TradeAction.SELL_NO,
                "hold": TradeAction.HOLD,
                "skip": TradeAction.SKIP,
            }
            action = action_map.get(data.get("action", "skip"), TradeAction.SKIP)

            order_type_map = {
                "market": OrderType.MARKET,
                "limit": OrderType.LIMIT,
                "fok": OrderType.FOK,
            }
            order_type = order_type_map.get(data.get("order_type", "market"), OrderType.MARKET)

            position_size_pct = min(
                float(data.get("position_size_pct", 2.0)),
                self.max_position_pct,
            )
            position_size = portfolio_state.available_balance * Decimal(str(position_size_pct / 100))

            return TradeDecision(
                action=action,
                confidence=float(data.get("confidence", 0)),
                position_size=position_size,
                order_type=order_type,
                limit_price=Decimal(str(data.get("limit_price"))) if data.get("limit_price") else None,
                reasoning=data.get("reasoning", "No reasoning provided"),
                risk_assessment=data.get("risk_assessment", "unknown"),
                expected_profit=Decimal(str(data.get("expected_profit_pct", 0))) / 100,
            )

        except Exception:
            return self._fallback_decision(market_context, portfolio_state, "parse_error")

    def _build_decision_prompt(self, market_context, portfolio_state, opportunity_type="arbitrage"):
        """V1-compatible prompt builder."""
        prompt = f"TRADING OPPORTUNITY: {opportunity_type.upper()}\n\n"
        prompt += market_context.to_prompt_context() if hasattr(market_context, 'to_prompt_context') else str(market_context)
        prompt += f"\n\nPortfolio State:\n"
        prompt += portfolio_state.to_prompt_context() if hasattr(portfolio_state, 'to_prompt_context') else str(portfolio_state)
        prompt += "\n\nAnalyze and provide JSON decision."
        return prompt

    def get_statistics(self):
        """V1-compatible statistics."""
        if not self.decision_history:
            return {
                "total_decisions": 0,
                "fallback_rate": 0,
                "avg_confidence": 0,
            }
        total = len(self.decision_history)
        avg_conf = sum(d.confidence for d in self.decision_history) / total
        return {
            "total_decisions": total,
            "fallback_rate": 0,
            "avg_confidence": avg_conf,
        }
