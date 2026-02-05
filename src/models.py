"""
Data models for the Polymarket Arbitrage Bot.

All price and amount fields use Decimal types for precision (Requirement 17.5).
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict
import re


@dataclass
class Market:
    """Represents a Polymarket prediction market"""
    market_id: str
    question: str
    asset: str  # BTC, ETH, SOL, XRP
    outcomes: List[str]  # ["YES", "NO"]
    yes_price: Decimal
    no_price: Decimal
    yes_token_id: str
    no_token_id: str
    volume: Decimal
    liquidity: Decimal
    end_time: datetime
    resolution_source: str
    
    def is_crypto_15min(self) -> bool:
        """
        Check if this is a 15-minute crypto market.
        
        Validates Requirements 17.4, 17.6:
        - Filter to 15-minute crypto markets only
        - Exclude expired markets
        
        Returns:
            bool: True if market is a 15-minute crypto market
        """
        # Check if market has expired
        now = datetime.now(tz=self.end_time.tzinfo) if self.end_time.tzinfo else datetime.now()
        if self.end_time < now:
            return False
        
        # Calculate duration until market close
        duration = self.end_time - now
        duration_minutes = duration.total_seconds() / 60
        
        # Check if duration is approximately 15 minutes (14-16 minute window)
        is_15min = 14 <= duration_minutes <= 16
        
        # Check if question mentions crypto assets
        question_upper = self.question.upper()
        is_crypto = any(asset in question_upper for asset in ["BTC", "ETH", "SOL", "XRP"])
        
        return is_15min and is_crypto
    
    def parse_strike_price(self) -> Optional[Decimal]:
        """
        Extract strike price from question (e.g., 'BTC above $95,000').
        
        Validates Requirement 17.4: Parse strike price extraction
        
        Returns:
            Optional[Decimal]: Strike price if found, None otherwise
        """
        # Match patterns like: $95,000 or 95000 or $95000.50
        match = re.search(r'\$?([\d,]+(?:\.\d+)?)', self.question)
        if match:
            price_str = match.group(1).replace(',', '')
            try:
                return Decimal(price_str)
            except (ValueError, ArithmeticError):
                return None
        return None


@dataclass
class Opportunity:
    """Represents an arbitrage opportunity"""
    opportunity_id: str
    market_id: str
    strategy: str  # "internal", "cross_platform", "latency", "resolution_farming"
    timestamp: datetime
    
    # Pricing (all Decimal for precision)
    yes_price: Decimal
    no_price: Decimal
    yes_fee: Decimal
    no_fee: Decimal
    total_cost: Decimal
    expected_profit: Decimal
    profit_percentage: Decimal
    
    # Execution details
    position_size: Decimal
    gas_estimate: int
    
    # Cross-platform specific
    platform_a: Optional[str] = None
    platform_b: Optional[str] = None
    
    def is_profitable(self, min_profit_threshold: Decimal = Decimal('0.005')) -> bool:
        """
        Check if opportunity meets minimum profit threshold.
        
        Args:
            min_profit_threshold: Minimum profit percentage (default 0.5%)
            
        Returns:
            bool: True if profit percentage meets or exceeds threshold
        """
        return self.profit_percentage >= min_profit_threshold


@dataclass
class TradeResult:
    """Represents the result of an executed trade"""
    trade_id: str
    opportunity: Opportunity
    timestamp: datetime
    status: str  # "success", "failed", "partial"
    
    # Execution details
    yes_order_id: Optional[str]
    no_order_id: Optional[str]
    yes_filled: bool
    no_filled: bool
    yes_fill_price: Optional[Decimal]
    no_fill_price: Optional[Decimal]
    
    # Financial results (all Decimal for precision)
    actual_cost: Decimal
    actual_profit: Decimal
    gas_cost: Decimal
    net_profit: Decimal
    
    # Transaction hashes
    yes_tx_hash: Optional[str] = None
    no_tx_hash: Optional[str] = None
    merge_tx_hash: Optional[str] = None
    
    # Error information
    error_message: Optional[str] = None
    
    def was_successful(self) -> bool:
        """
        Check if trade was successful.
        
        Returns:
            bool: True if trade succeeded and both orders filled
        """
        return self.status == "success" and self.yes_filled and self.no_filled


@dataclass
class SafetyDecision:
    """Represents an AI safety check decision"""
    approved: bool
    reason: str
    timestamp: datetime
    checks_performed: Dict[str, bool]  # {"nvidia_api": True, "volatility": True, ...}
    ai_response: Optional[str] = None
    fallback_used: bool = False


@dataclass
class HealthStatus:
    """System health status"""
    timestamp: datetime
    is_healthy: bool
    
    # Balances (Decimal for precision)
    eoa_balance: Decimal
    proxy_balance: Decimal
    total_balance: Decimal
    
    # Component health
    balance_ok: bool
    gas_ok: bool
    gas_price_gwei: int
    pending_tx_ok: bool
    pending_tx_count: int
    api_connectivity_ok: bool
    rpc_latency_ms: float
    block_number: int
    
    # Performance metrics (Decimal for precision)
    total_trades: int
    win_rate: Decimal  # Percentage
    total_profit: Decimal
    avg_profit_per_trade: Decimal
    total_gas_cost: Decimal
    net_profit: Decimal
    
    # Safety status
    circuit_breaker_open: bool
    consecutive_failures: int
    ai_safety_active: bool
    
    # Issues
    issues: List[str] = field(default_factory=list)
