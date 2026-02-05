"""
Market data parser for Polymarket CLOB API responses.

Validates Requirements 17.1, 17.2, 17.3, 17.4, 17.6:
- Parse JSON from CLOB API to Market objects
- Validate all required fields
- Skip invalid markets with warnings
- Filter to 15-minute crypto markets only
- Exclude expired markets
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any

from src.models import Market

logger = logging.getLogger(__name__)


class MarketParser:
    """
    Parses and validates market data from Polymarket CLOB API.
    
    Validates Requirements:
    - 17.1: Parse JSON responses into structured Market objects
    - 17.2: Validate required fields
    - 17.3: Skip invalid markets with warnings
    - 17.4: Filter to 15-minute crypto markets only
    - 17.6: Exclude expired markets
    """
    
    # Required fields for a valid market
    REQUIRED_FIELDS = [
        'condition_id',
        'question',
        'tokens',
        'end_date_iso',
    ]
    
    # Crypto assets we trade
    CRYPTO_ASSETS = ['BTC', 'ETH', 'SOL', 'XRP']
    
    def __init__(self):
        """Initialize the market parser."""
        self.markets_parsed = 0
        self.markets_skipped = 0
        self.skip_reasons: Dict[str, int] = {}
    
    def parse_markets(self, api_response: Dict[str, Any]) -> List[Market]:
        """
        Parse markets from CLOB API response.
        
        Validates Requirement 17.1: Parse JSON responses into structured Market objects
        
        Args:
            api_response: Raw API response from CLOB API
            
        Returns:
            List[Market]: List of valid, parsed Market objects
        """
        markets = []
        raw_markets = api_response.get('data', [])
        
        logger.debug(f"Parsing {len(raw_markets)} markets from API response")
        
        for raw_market in raw_markets:
            market = self.parse_single_market(raw_market)
            if market:
                markets.append(market)
        
        logger.info(
            f"Parsed {len(markets)} valid markets "
            f"(skipped {self.markets_skipped}, reasons: {self.skip_reasons})"
        )
        
        return markets
    
    def parse_single_market(self, raw_market: Dict[str, Any]) -> Optional[Market]:
        """
        Parse a single market from raw API data.
        
        Validates Requirements:
        - 17.1: Parse JSON to Market objects
        - 17.2: Validate required fields
        - 17.3: Skip invalid markets with warnings
        - 17.4: Filter to 15-minute crypto markets
        - 17.6: Exclude expired markets
        
        Args:
            raw_market: Raw market data from API
            
        Returns:
            Optional[Market]: Parsed Market object or None if invalid
        """
        try:
            # Validate required fields (Requirement 17.2)
            if not self._validate_required_fields(raw_market):
                return None
            
            # Extract basic fields
            market_id = raw_market['condition_id']
            question = raw_market['question']
            
            # Parse tokens (YES and NO)
            tokens = raw_market.get('tokens', [])
            if len(tokens) < 2:
                self._skip_market(market_id, "insufficient_tokens")
                logger.warning(f"Market {market_id} has < 2 tokens, skipping")
                return None
            
            # Extract token information
            yes_token = tokens[0]
            no_token = tokens[1]
            
            yes_token_id = yes_token.get('token_id', '')
            no_token_id = no_token.get('token_id', '')
            
            # Parse prices as Decimal (Requirement 17.5)
            yes_price = self._parse_decimal(yes_token.get('price', '0'))
            no_price = self._parse_decimal(no_token.get('price', '0'))
            
            if yes_price is None or no_price is None:
                self._skip_market(market_id, "invalid_price")
                logger.warning(f"Market {market_id} has invalid prices, skipping")
                return None
            
            # Parse volume and liquidity
            volume = self._parse_decimal(raw_market.get('volume', '0')) or Decimal('0')
            liquidity = self._parse_decimal(raw_market.get('liquidity', '0')) or Decimal('0')
            
            # Parse end time
            end_time = self._parse_datetime(raw_market.get('end_date_iso'))
            if end_time is None:
                self._skip_market(market_id, "invalid_end_time")
                logger.warning(f"Market {market_id} has invalid end_time, skipping")
                return None
            
            # Check if market is expired (Requirement 17.6)
            if self._is_expired(end_time):
                self._skip_market(market_id, "expired")
                logger.debug(f"Market {market_id} is expired, skipping")
                return None
            
            # Determine asset from question
            asset = self._extract_asset(question)
            if asset is None:
                self._skip_market(market_id, "non_crypto")
                logger.debug(f"Market {market_id} is not a crypto market, skipping")
                return None
            
            # Extract resolution source
            resolution_source = raw_market.get('resolution_source', 'unknown')
            
            # Create Market object
            market = Market(
                market_id=market_id,
                question=question,
                asset=asset,
                outcomes=["YES", "NO"],
                yes_price=yes_price,
                no_price=no_price,
                yes_token_id=yes_token_id,
                no_token_id=no_token_id,
                volume=volume,
                liquidity=liquidity,
                end_time=end_time,
                resolution_source=resolution_source
            )
            
            # Filter to 15-minute crypto markets only (Requirement 17.4)
            if not market.is_crypto_15min():
                self._skip_market(market_id, "not_15min_crypto")
                logger.debug(f"Market {market_id} is not a 15-minute crypto market, skipping")
                return None
            
            self.markets_parsed += 1
            logger.debug(f"Successfully parsed market {market_id}: {question}")
            return market
            
        except Exception as e:
            market_id = raw_market.get('condition_id', 'unknown')
            self._skip_market(market_id, "parse_error")
            logger.warning(f"Error parsing market {market_id}: {e}")
            return None
    
    def _validate_required_fields(self, raw_market: Dict[str, Any]) -> bool:
        """
        Validate that all required fields are present.
        
        Validates Requirement 17.2: Validate required fields
        
        Args:
            raw_market: Raw market data
            
        Returns:
            bool: True if all required fields present
        """
        for field in self.REQUIRED_FIELDS:
            if field not in raw_market:
                market_id = raw_market.get('condition_id', 'unknown')
                self._skip_market(market_id, f"missing_{field}")
                logger.warning(f"Market {market_id} missing required field: {field}")
                return False
        return True
    
    def _parse_decimal(self, value: Any) -> Optional[Decimal]:
        """
        Parse a value to Decimal type.
        
        Validates Requirement 17.5: Use Decimal types for price precision
        
        Args:
            value: Value to parse (string, int, float, or Decimal)
            
        Returns:
            Optional[Decimal]: Parsed Decimal or None if invalid
        """
        if value is None:
            return None
        
        try:
            if isinstance(value, Decimal):
                decimal_value = value
            else:
                decimal_value = Decimal(str(value))
            
            # Check for NaN and Infinity
            if decimal_value.is_nan() or decimal_value.is_infinite():
                return None
            
            return decimal_value
        except (ValueError, InvalidOperation, TypeError):
            return None
    
    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse ISO datetime string.
        
        Args:
            date_str: ISO format datetime string
            
        Returns:
            Optional[datetime]: Parsed datetime or None if invalid
        """
        if not date_str:
            return None
        
        try:
            # Try parsing with timezone
            if 'Z' in date_str or '+' in date_str or date_str.endswith('00:00'):
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                # Assume UTC if no timezone
                dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, AttributeError):
            return None
    
    def _is_expired(self, end_time: datetime) -> bool:
        """
        Check if market has expired.
        
        Validates Requirement 17.6: Exclude expired markets
        
        Args:
            end_time: Market end time
            
        Returns:
            bool: True if market is expired
        """
        now = datetime.now(tz=end_time.tzinfo) if end_time.tzinfo else datetime.now()
        return end_time < now
    
    def _extract_asset(self, question: str) -> Optional[str]:
        """
        Extract crypto asset from question text.
        
        Validates Requirement 17.4: Filter to crypto markets
        
        Args:
            question: Market question text
            
        Returns:
            Optional[str]: Asset symbol (BTC, ETH, SOL, XRP) or None
        """
        question_upper = question.upper()
        for asset in self.CRYPTO_ASSETS:
            if asset in question_upper:
                return asset
        return None
    
    def _skip_market(self, market_id: str, reason: str) -> None:
        """
        Record that a market was skipped.
        
        Validates Requirement 17.3: Skip invalid markets with warnings
        
        Args:
            market_id: Market identifier
            reason: Reason for skipping
        """
        self.markets_skipped += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get parsing statistics.
        
        Returns:
            Dict: Statistics about parsed and skipped markets
        """
        return {
            'markets_parsed': self.markets_parsed,
            'markets_skipped': self.markets_skipped,
            'skip_reasons': self.skip_reasons
        }
    
    def reset_stats(self) -> None:
        """Reset parsing statistics."""
        self.markets_parsed = 0
        self.markets_skipped = 0
        self.skip_reasons = {}
