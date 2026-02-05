"""
Unit tests for AI Safety Guard.

Tests specific examples and edge cases for:
- Multilingual YES/NO parsing
- Ambiguous keyword detection
- Volatility monitoring
- Fallback heuristics
- AI timeout handling

Validates Requirements 7.1-7.6.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ai_safety_guard import AISafetyGuard
from src.models import Market, Opportunity


class TestMultilingualParsing:
    """Test multilingual YES/NO response parsing (Requirement 7.2)"""
    
    def test_parse_english_yes_lowercase(self):
        """Test parsing English 'yes' in lowercase"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("yes") is True
    
    def test_parse_english_yes_uppercase(self):
        """Test parsing English 'YES' in uppercase"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("YES") is True
    
    def test_parse_english_no_lowercase(self):
        """Test parsing English 'no' in lowercase"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("no") is False
    
    def test_parse_english_no_uppercase(self):
        """Test parsing English 'NO' in uppercase"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("NO") is False
    
    def test_parse_russian_yes(self):
        """Test parsing Russian 'да' (yes)"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("да") is True
        assert guard.parse_yes_no_response("Да") is True
        assert guard.parse_yes_no_response("ДА") is True
    
    def test_parse_russian_no(self):
        """Test parsing Russian 'нет' (no)"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("нет") is False
        assert guard.parse_yes_no_response("Нет") is False
        assert guard.parse_yes_no_response("НЕТ") is False
    
    def test_parse_french_yes(self):
        """Test parsing French 'oui' (yes)"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("oui") is True
        assert guard.parse_yes_no_response("Oui") is True
        assert guard.parse_yes_no_response("OUI") is True
    
    def test_parse_french_no(self):
        """Test parsing French 'non' (no)"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("non") is False
        assert guard.parse_yes_no_response("Non") is False
        assert guard.parse_yes_no_response("NON") is False
    
    def test_parse_spanish_yes(self):
        """Test parsing Spanish 'sí' (yes)"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("sí") is True
        assert guard.parse_yes_no_response("si") is True  # Without accent
        assert guard.parse_yes_no_response("Sí") is True
        assert guard.parse_yes_no_response("SÍ") is True
    
    def test_parse_spanish_no(self):
        """Test parsing Spanish 'no' (no) - same as English"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("no") is False
    
    def test_parse_with_leading_whitespace(self):
        """Test parsing with leading whitespace"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("  yes") is True
        assert guard.parse_yes_no_response("  no") is False
    
    def test_parse_with_trailing_whitespace(self):
        """Test parsing with trailing whitespace"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("yes  ") is True
        assert guard.parse_yes_no_response("no  ") is False
    
    def test_parse_with_both_whitespace(self):
        """Test parsing with leading and trailing whitespace"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("  yes  ") is True
        assert guard.parse_yes_no_response("  no  ") is False
    
    def test_parse_empty_string(self):
        """Test parsing empty string returns None"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("") is None
    
    def test_parse_unclear_response(self):
        """Test parsing unclear response returns None"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard.parse_yes_no_response("maybe") is None
        assert guard.parse_yes_no_response("unclear") is None
        assert guard.parse_yes_no_response("I don't know") is None
    
    def test_parse_english_variants(self):
        """Test parsing English YES/NO variants"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        # YES variants
        assert guard.parse_yes_no_response("y") is True
        assert guard.parse_yes_no_response("true") is True
        assert guard.parse_yes_no_response("approve") is True
        assert guard.parse_yes_no_response("approved") is True
        assert guard.parse_yes_no_response("ok") is True
        assert guard.parse_yes_no_response("okay") is True
        
        # NO variants
        assert guard.parse_yes_no_response("n") is False
        assert guard.parse_yes_no_response("false") is False
        assert guard.parse_yes_no_response("reject") is False
        assert guard.parse_yes_no_response("rejected") is False
        assert guard.parse_yes_no_response("deny") is False
        assert guard.parse_yes_no_response("denied") is False


class TestAmbiguousKeywordDetection:
    """Test ambiguous keyword detection (Requirement 7.6)"""
    
    def test_detect_approximately(self):
        """Test detection of 'approximately' keyword"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC approximately $95,000") is True
        assert guard._has_ambiguous_keywords("BTC APPROXIMATELY $95,000") is True
    
    def test_detect_around(self):
        """Test detection of 'around' keyword"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC around $95,000") is True
        assert guard._has_ambiguous_keywords("BTC AROUND $95,000") is True
    
    def test_detect_roughly(self):
        """Test detection of 'roughly' keyword"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC roughly $95,000") is True
    
    def test_detect_about(self):
        """Test detection of 'about' keyword"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC about $95,000") is True
    
    def test_detect_near(self):
        """Test detection of 'near' keyword"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC near $95,000") is True
    
    def test_detect_close_to(self):
        """Test detection of 'close to' keyword"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC close to $95,000") is True
    
    def test_detect_almost(self):
        """Test detection of 'almost' keyword"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC almost $95,000") is True
    
    def test_detect_nearly(self):
        """Test detection of 'nearly' keyword"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC nearly $95,000") is True
    
    def test_detect_circa(self):
        """Test detection of 'circa' keyword"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC circa $95,000") is True
    
    def test_detect_tilde_symbol(self):
        """Test detection of '~' symbol"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC ~$95,000") is True
    
    def test_clear_question_no_ambiguity(self):
        """Test clear question without ambiguous keywords"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC above $95,000") is False
        assert guard._has_ambiguous_keywords("BTC below $95,000") is False
        assert guard._has_ambiguous_keywords("BTC exactly $95,000") is False
    
    def test_ambiguous_keyword_at_start(self):
        """Test ambiguous keyword at start of question"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("Approximately $95,000 for BTC") is True
    
    def test_ambiguous_keyword_at_end(self):
        """Test ambiguous keyword at end of question"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC will be $95,000 approximately") is True
    
    def test_ambiguous_keyword_in_middle(self):
        """Test ambiguous keyword in middle of question"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._has_ambiguous_keywords("BTC will be around $95,000 in 15 minutes") is True


class TestFallbackHeuristics:
    """Test fallback safety heuristics (Requirement 7.4)"""
    
    def test_fallback_all_conditions_good(self):
        """Test fallback approves when all conditions are good"""
        guard = AISafetyGuard(
            nvidia_api_key="test_key",
            min_balance=Decimal('10.0'),
            max_gas_price_gwei=800,
            max_pending_tx=5
        )
        
        result = guard._fallback_heuristics(
            current_balance=Decimal('100.0'),
            current_gas_price_gwei=50,
            pending_tx_count=2
        )
        assert result is True
    
    def test_fallback_low_balance(self):
        """Test fallback rejects when balance too low"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        result = guard._fallback_heuristics(
            current_balance=Decimal('5.0'),  # Below $10 threshold
            current_gas_price_gwei=50,
            pending_tx_count=2
        )
        assert result is False
    
    def test_fallback_high_gas(self):
        """Test fallback rejects when gas price too high"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        result = guard._fallback_heuristics(
            current_balance=Decimal('100.0'),
            current_gas_price_gwei=900,  # Above 800 gwei threshold
            pending_tx_count=2
        )
        assert result is False
    
    def test_fallback_too_many_pending_tx(self):
        """Test fallback rejects when too many pending transactions"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        result = guard._fallback_heuristics(
            current_balance=Decimal('100.0'),
            current_gas_price_gwei=50,
            pending_tx_count=6  # Above 5 threshold
        )
        assert result is False
    
    def test_fallback_balance_at_threshold(self):
        """Test fallback rejects when balance exactly at threshold"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        result = guard._fallback_heuristics(
            current_balance=Decimal('10.0'),  # Exactly at threshold
            current_gas_price_gwei=50,
            pending_tx_count=2
        )
        assert result is False  # Must be > threshold, not >=
    
    def test_fallback_gas_at_threshold(self):
        """Test fallback rejects when gas exactly at threshold"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        result = guard._fallback_heuristics(
            current_balance=Decimal('100.0'),
            current_gas_price_gwei=800,  # Exactly at threshold
            pending_tx_count=2
        )
        assert result is False  # Must be < threshold, not <=
    
    def test_fallback_pending_at_threshold(self):
        """Test fallback rejects when pending TX exactly at threshold"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        result = guard._fallback_heuristics(
            current_balance=Decimal('100.0'),
            current_gas_price_gwei=50,
            pending_tx_count=5  # Exactly at threshold
        )
        assert result is False  # Must be < threshold, not <=
    
    def test_fallback_multiple_failures(self):
        """Test fallback rejects when multiple conditions fail"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        result = guard._fallback_heuristics(
            current_balance=Decimal('5.0'),  # Too low
            current_gas_price_gwei=900,  # Too high
            pending_tx_count=6  # Too many
        )
        assert result is False


class TestVolatilityMonitoring:
    """Test volatility monitoring and halt (Requirement 7.5)"""
    
    def test_update_price_creates_history(self):
        """Test that updating price creates price history"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        guard.update_price("BTC", Decimal('95000'))
        assert "BTC" in guard._price_history
        assert len(guard._price_history["BTC"]) == 1
    
    def test_update_price_multiple_times(self):
        """Test updating price multiple times"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        guard.update_price("BTC", Decimal('95000'))
        guard.update_price("BTC", Decimal('95500'))
        guard.update_price("BTC", Decimal('96000'))
        
        assert len(guard._price_history["BTC"]) == 3
    
    def test_calculate_volatility_insufficient_data(self):
        """Test volatility calculation with insufficient data"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        # No data
        volatility = guard._calculate_volatility("BTC")
        assert volatility is None
        
        # Only one price point
        guard.update_price("BTC", Decimal('95000'))
        volatility = guard._calculate_volatility("BTC")
        assert volatility is None
    
    def test_calculate_volatility_no_change(self):
        """Test volatility calculation when price doesn't change"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        guard.update_price("BTC", Decimal('95000'))
        guard.update_price("BTC", Decimal('95000'))
        guard.update_price("BTC", Decimal('95000'))
        
        volatility = guard._calculate_volatility("BTC")
        assert volatility == Decimal('0')
    
    def test_calculate_volatility_small_change(self):
        """Test volatility calculation with small price change (< 5%)"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        guard.update_price("BTC", Decimal('95000'))
        guard.update_price("BTC", Decimal('96000'))  # 1.05% increase
        
        volatility = guard._calculate_volatility("BTC")
        assert volatility is not None
        assert volatility < Decimal('0.05')  # Less than 5%
    
    def test_calculate_volatility_large_change(self):
        """Test volatility calculation with large price change (> 5%)"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        guard.update_price("BTC", Decimal('95000'))
        guard.update_price("BTC", Decimal('100000'))  # 5.26% increase
        
        volatility = guard._calculate_volatility("BTC")
        assert volatility is not None
        assert volatility > Decimal('0.05')  # Greater than 5%
    
    def test_volatility_halt_not_active_initially(self):
        """Test that volatility halt is not active initially"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        assert guard._is_volatility_halted() is False
    
    def test_trigger_volatility_halt(self):
        """Test triggering volatility halt"""
        guard = AISafetyGuard(
            nvidia_api_key="test_key",
            volatility_halt_duration=300  # 5 minutes
        )
        
        guard._trigger_volatility_halt()
        assert guard._is_volatility_halted() is True
        assert guard._volatility_halt_until is not None
    
    def test_volatility_halt_duration(self):
        """Test volatility halt duration is correct"""
        guard = AISafetyGuard(
            nvidia_api_key="test_key",
            volatility_halt_duration=300  # 5 minutes
        )
        
        before = datetime.now()
        guard._trigger_volatility_halt()
        after = datetime.now()
        
        # Halt should end approximately 5 minutes from now
        expected_end = before + timedelta(seconds=300)
        time_diff = abs((guard._volatility_halt_until - expected_end).total_seconds())
        assert time_diff < 2  # Allow 2 seconds tolerance
    
    def test_volatility_halt_expires(self):
        """Test that volatility halt expires after duration"""
        guard = AISafetyGuard(
            nvidia_api_key="test_key",
            volatility_halt_duration=1  # 1 second for testing
        )
        
        guard._trigger_volatility_halt()
        assert guard._is_volatility_halted() is True
        
        # Wait for halt to expire
        import time
        time.sleep(1.1)
        
        assert guard._is_volatility_halted() is False


class TestMarketContextBuilding:
    """Test building market context for AI"""
    
    def test_build_market_context(self):
        """Test building context string for AI safety check"""
        guard = AISafetyGuard(nvidia_api_key="test_key")
        
        market = Market(
            market_id="market_1",
            question="Will BTC be above $95,000?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_token_id="token_yes",
            no_token_id="token_no",
            volume=Decimal('10000.0'),
            liquidity=Decimal('5000.0'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="Binance"
        )
        
        opportunity = Opportunity(
            opportunity_id="opp_1",
            market_id="market_1",
            strategy="internal",
            timestamp=datetime.now(),
            yes_price=Decimal('0.48'),
            no_price=Decimal('0.47'),
            yes_fee=Decimal('0.028'),
            no_fee=Decimal('0.029'),
            total_cost=Decimal('0.9748'),
            expected_profit=Decimal('0.0252'),
            profit_percentage=Decimal('0.0258'),
            position_size=Decimal('1.0'),
            gas_estimate=100000
        )
        
        context = guard._build_market_context(market, opportunity)
        
        # Verify context contains key information
        assert "Will BTC be above $95,000?" in context
        assert "BTC" in context
        assert "0.48" in context
        assert "0.47" in context
        assert "0.9748" in context
        assert "0.0252" in context
        assert "10000" in context
        assert "5000" in context
        assert "internal" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
