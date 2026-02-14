"""
AI Safety Guard for validating market conditions before trade execution.

Implements Requirements 7.1-7.6:
- NVIDIA API integration with 2-second timeout
- Multilingual YES/NO parsing (English, Russian, French, Spanish)
- Fallback heuristics when AI unavailable
- Volatility monitoring (5% threshold)
- Ambiguous keyword detection
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, List
import aiohttp

from src.models import Market, Opportunity, SafetyDecision

logger = logging.getLogger(__name__)


class AISafetyGuard:
    """
    AI-powered safety guard that validates market conditions before trade execution.
    
    Uses NVIDIA AI API for intelligent safety checks with fallback heuristics.
    Monitors volatility and filters ambiguous markets.
    """
    
    # Ambiguous keywords that indicate unclear resolution criteria (Requirement 7.6)
    AMBIGUOUS_KEYWORDS = [
        "approximately", "around", "roughly", "about", "near",
        "close to", "almost", "nearly", "circa", "~"
    ]
    
    # Multilingual YES/NO responses (Requirement 7.2)
    YES_RESPONSES = {
        # English
        "yes", "y", "true", "approve", "approved", "ok", "okay",
        # Russian
        "да", "д",
        # French
        "oui", "o",
        # Spanish
        "sí", "si", "s"
    }
    
    NO_RESPONSES = {
        # English
        "no", "n", "false", "reject", "rejected", "deny", "denied",
        # Russian
        "нет", "н",
        # French
        "non",
        # Spanish
        "no"
    }
    
    def __init__(
        self,
        nvidia_api_key: str,
        nvidia_api_url: str = "https://integrate.api.nvidia.com/v1",
        min_balance: Decimal = Decimal('0.10'),  # Dynamic: $0.10 minimum for micro trading
        max_gas_price_gwei: int = 800,
        max_pending_tx: int = 5,
        volatility_threshold: Decimal = Decimal('0.05'),  # 5%
        volatility_halt_duration: int = 300  # 5 minutes in seconds
    ):
        """
        Initialize AI Safety Guard.
        
        Args:
            nvidia_api_key: API key for NVIDIA AI service
            nvidia_api_url: NVIDIA API endpoint URL
            min_balance: Minimum balance required for trading (default $0.10, dynamic)
            max_gas_price_gwei: Maximum gas price in gwei (default 800)
            max_pending_tx: Maximum pending transactions (default 5)
            volatility_threshold: Volatility threshold for halting (default 5%)
            volatility_halt_duration: Duration to halt after high volatility (default 5 minutes)
        """
        self.nvidia_api_key = nvidia_api_key
        self.nvidia_api_url = nvidia_api_url
        self.min_balance = min_balance
        self.max_gas_price_gwei = max_gas_price_gwei
        self.max_pending_tx = max_pending_tx
        self.volatility_threshold = volatility_threshold
        self.volatility_halt_duration = volatility_halt_duration
        
        # Track price history for volatility monitoring
        self._price_history: Dict[str, List[tuple[datetime, Decimal]]] = {}
        
        # Track volatility halt status
        self._volatility_halt_until: Optional[datetime] = None
        
        logger.info(
            f"AI Safety Guard initialized: min_balance=${min_balance}, "
            f"max_gas={max_gas_price_gwei} gwei, volatility_threshold={volatility_threshold*100}%"
        )
    
    async def validate_trade(
        self,
        opportunity: Opportunity,
        market: Market,
        current_balance: Decimal,
        current_gas_price_gwei: int,
        pending_tx_count: int
    ) -> SafetyDecision:
        """
        Validate if a trade opportunity is safe to execute.
        
        Implements Requirements 7.1-7.6:
        - Queries NVIDIA AI API with market context
        - Parses multilingual YES/NO responses
        - Uses fallback heuristics if AI unavailable
        - Checks volatility and halts if needed
        - Filters ambiguous markets
        
        Args:
            opportunity: The arbitrage opportunity to validate
            market: The market associated with the opportunity
            current_balance: Current wallet balance
            current_gas_price_gwei: Current gas price in gwei
            pending_tx_count: Number of pending transactions
            
        Returns:
            SafetyDecision: Decision with approval status and reasoning
        """
        timestamp = datetime.now()
        checks_performed = {}
        
        # Check 1: Ambiguous market filtering (Requirement 7.6)
        if self._has_ambiguous_keywords(market.question):
            logger.info(f"Market rejected: ambiguous resolution criteria - {market.question}")
            return SafetyDecision(
                approved=False,
                reason="Ambiguous resolution criteria detected",
                timestamp=timestamp,
                checks_performed={"ambiguous_keywords": True},
                fallback_used=False
            )
        checks_performed["ambiguous_keywords"] = True
        
        # Check 2: Volatility halt (Requirement 7.5)
        if self._is_volatility_halted():
            logger.info(f"Trading halted due to high volatility until {self._volatility_halt_until}")
            return SafetyDecision(
                approved=False,
                reason=f"Trading halted due to high volatility until {self._volatility_halt_until}",
                timestamp=timestamp,
                checks_performed={"volatility_halt": True},
                fallback_used=False
            )
        checks_performed["volatility_halt"] = False
        
        # Check 3: Current volatility (Requirement 7.5)
        volatility = self._calculate_volatility(market.asset)
        if volatility is not None and volatility > self.volatility_threshold:
            logger.warning(
                f"High volatility detected for {market.asset}: {volatility*100:.2f}% "
                f"(threshold: {self.volatility_threshold*100}%)"
            )
            self._trigger_volatility_halt()
            return SafetyDecision(
                approved=False,
                reason=f"High volatility: {volatility*100:.2f}% > {self.volatility_threshold*100}%",
                timestamp=timestamp,
                checks_performed={"volatility_check": True},
                fallback_used=False
            )
        checks_performed["volatility_check"] = True
        
        # Check 4: NVIDIA AI API (Requirement 7.1, 7.2, 7.3)
        ai_approved = await self._check_nvidia_api(market, opportunity)
        checks_performed["nvidia_api"] = ai_approved is not None
        
        # Check 5: Fallback heuristics if AI unavailable (Requirement 7.4)
        if ai_approved is None:
            logger.info("NVIDIA API unavailable, using fallback heuristics")
            ai_approved = self._fallback_heuristics(
                current_balance,
                current_gas_price_gwei,
                pending_tx_count
            )
            checks_performed["fallback_heuristics"] = True
            fallback_used = True
        else:
            fallback_used = False
        
        # Final decision
        if not ai_approved:
            return SafetyDecision(
                approved=False,
                reason="AI safety check failed" if not fallback_used else "Fallback heuristics failed",
                timestamp=timestamp,
                checks_performed=checks_performed,
                fallback_used=fallback_used
            )
        
        logger.debug(f"Trade approved for market {market.market_id}")
        return SafetyDecision(
            approved=True,
            reason="All safety checks passed",
            timestamp=timestamp,
            checks_performed=checks_performed,
            fallback_used=fallback_used
        )
    
    async def _check_nvidia_api(
        self,
        market: Market,
        opportunity: Opportunity
    ) -> Optional[bool]:
        """
        Query NVIDIA AI API for safety validation with 2-second timeout.
        
        Uses DeepSeek v3.2 model via NVIDIA API for intelligent trade validation.
        
        Implements Requirements 7.1, 7.2, 7.3:
        - Queries NVIDIA API with market context
        - Parses multilingual YES/NO responses
        - Returns None if timeout or error (triggers fallback)
        
        Args:
            market: The market to validate
            opportunity: The opportunity to validate
            
        Returns:
            Optional[bool]: True if approved, False if rejected, None if unavailable
        """
        # Build context for AI
        context = self._build_market_context(market, opportunity)
        
        try:
            # Query NVIDIA API with 2-second timeout (Requirement 7.3)
            # Using OpenAI-compatible client as specified by user
            from openai import OpenAI
            
            client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=self.nvidia_api_key
            )
            
            # Create completion with DeepSeek v3.2 model
            completion = client.chat.completions.create(
                model="deepseek-ai/deepseek-v3.2",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a safety validator for cryptocurrency arbitrage trading. "
                            "Analyze the market and respond with YES if the trade is safe, "
                            "or NO if there are concerns. Consider: market clarity, price reasonableness, "
                            "volatility, and potential manipulation. Respond with only YES or NO."
                        )
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                temperature=1,
                top_p=0.95,
                max_tokens=8192,
                extra_body={"chat_template_kwargs": {"thinking": True}},
                timeout=2.0  # 2-second timeout
            )
            
            # Extract response
            ai_response = completion.choices[0].message.content if completion.choices else ""
            
            # Parse multilingual YES/NO response (Requirement 7.2)
            result = self.parse_yes_no_response(ai_response)
            
            logger.debug(f"NVIDIA API response: '{ai_response}' -> {result}")
            return result
        
        except Exception as e:
            logger.warning(f"NVIDIA API error: {e}")
            return None
    
    def parse_yes_no_response(self, response: str) -> Optional[bool]:
        """
        Parse multilingual YES/NO response from AI.
        
        Implements Requirement 7.2: Multilingual YES/NO parsing
        Supports: English, Russian, French, Spanish
        
        Args:
            response: AI response text
            
        Returns:
            Optional[bool]: True for YES, False for NO, None if unclear
        """
        if not response:
            return None
        
        # Normalize: lowercase and strip whitespace
        normalized = response.strip().lower()
        
        # Check for NO responses first (to avoid "no" matching "o" in YES)
        if any(no_word == normalized for no_word in self.NO_RESPONSES):
            return False
        
        # Check for YES responses
        if any(yes_word == normalized for yes_word in self.YES_RESPONSES):
            return True
        
        # Unclear response
        logger.warning(f"Could not parse AI response: '{response}'")
        return None
    
    def _fallback_heuristics(
        self,
        current_balance: Decimal,
        current_gas_price_gwei: int,
        pending_tx_count: int
    ) -> bool:
        """
        Apply fallback safety heuristics when AI is unavailable.
        
        Implements Requirement 7.4: Fallback heuristics
        Checks: balance > $10, gas < 800 gwei, pending_tx < 5
        
        Args:
            current_balance: Current wallet balance
            current_gas_price_gwei: Current gas price in gwei
            pending_tx_count: Number of pending transactions
            
        Returns:
            bool: True if all heuristics pass, False otherwise
        """
        balance_ok = current_balance > self.min_balance
        gas_ok = current_gas_price_gwei < self.max_gas_price_gwei
        pending_ok = pending_tx_count < self.max_pending_tx
        
        logger.info(
            f"Fallback heuristics: balance_ok={balance_ok} (${current_balance} > ${self.min_balance}), "
            f"gas_ok={gas_ok} ({current_gas_price_gwei} < {self.max_gas_price_gwei} gwei), "
            f"pending_ok={pending_ok} ({pending_tx_count} < {self.max_pending_tx})"
        )
        
        return balance_ok and gas_ok and pending_ok
    
    def _has_ambiguous_keywords(self, question: str) -> bool:
        """
        Check if market question contains ambiguous resolution keywords.
        
        Implements Requirement 7.6: Ambiguous keyword detection
        
        Args:
            question: Market question text
            
        Returns:
            bool: True if ambiguous keywords found
        """
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in self.AMBIGUOUS_KEYWORDS)
    
    def update_price(self, asset: str, price: Decimal) -> None:
        """
        Update price history for volatility monitoring.
        
        Implements Requirement 7.5: Volatility monitoring
        
        Args:
            asset: Asset symbol (BTC, ETH, SOL, XRP)
            price: Current price
        """
        now = datetime.now()
        
        # Initialize history for new asset
        if asset not in self._price_history:
            self._price_history[asset] = []
        
        # Add new price point
        self._price_history[asset].append((now, price))
        
        # Keep only last 2 minutes of history
        cutoff = now - timedelta(minutes=2)
        self._price_history[asset] = [
            (ts, p) for ts, p in self._price_history[asset]
            if ts > cutoff
        ]
    
    def _calculate_volatility(self, asset: str) -> Optional[Decimal]:
        """
        Calculate 1-minute volatility for an asset.
        
        Implements Requirement 7.5: Volatility monitoring (5% threshold)
        
        Args:
            asset: Asset symbol (BTC, ETH, SOL, XRP)
            
        Returns:
            Optional[Decimal]: Volatility as percentage change, None if insufficient data
        """
        if asset not in self._price_history or len(self._price_history[asset]) < 2:
            return None
        
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        
        # Get prices from last minute
        recent_prices = [
            price for ts, price in self._price_history[asset]
            if ts > one_minute_ago
        ]
        
        if len(recent_prices) < 2:
            return None
        
        # Calculate percentage change from min to max
        min_price = min(recent_prices)
        max_price = max(recent_prices)
        
        if min_price == 0:
            return None
        
        # If all prices are the same, volatility is 0
        if min_price == max_price:
            return Decimal('0')
        
        volatility = abs(max_price - min_price) / min_price
        return volatility
    
    def _is_volatility_halted(self) -> bool:
        """
        Check if trading is currently halted due to high volatility.
        
        Returns:
            bool: True if halted, False otherwise
        """
        if self._volatility_halt_until is None:
            return False
        
        now = datetime.now()
        if now >= self._volatility_halt_until:
            # Halt period expired
            logger.info("Volatility halt period expired, resuming trading")
            self._volatility_halt_until = None
            return False
        
        return True
    
    def _trigger_volatility_halt(self) -> None:
        """
        Trigger a volatility halt for the configured duration.
        
        Implements Requirement 7.5: Halt trading for 5 minutes after high volatility
        """
        self._volatility_halt_until = datetime.now() + timedelta(seconds=self.volatility_halt_duration)
        logger.warning(
            f"Volatility halt triggered until {self._volatility_halt_until} "
            f"({self.volatility_halt_duration} seconds)"
        )
    
    def _build_market_context(self, market: Market, opportunity: Opportunity) -> str:
        """
        Build context string for AI safety check.
        
        Args:
            market: The market to validate
            opportunity: The opportunity to validate
            
        Returns:
            str: Context string for AI
        """
        return (
            f"Market Question: {market.question}\n"
            f"Asset: {market.asset}\n"
            f"YES Price: ${market.yes_price}\n"
            f"NO Price: ${market.no_price}\n"
            f"Total Cost: ${opportunity.total_cost}\n"
            f"Expected Profit: ${opportunity.expected_profit} ({opportunity.profit_percentage*100:.2f}%)\n"
            f"Volume: ${market.volume}\n"
            f"Liquidity: ${market.liquidity}\n"
            f"Time to Close: {(market.end_time - datetime.now()).total_seconds() / 60:.1f} minutes\n"
            f"Strategy: {opportunity.strategy}"
        )
