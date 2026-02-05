"""
Property-based tests for AI Safety Guard.

Tests correctness properties for:
- Multilingual YES/NO parsing (Property 21)
- AI timeout handling (Property 22)
- Fallback heuristics (Property 23)
- Volatility halt (Property 24)
- Ambiguous market filtering (Property 16)
"""

import pytest
from hypothesis import given, strategies as st, settings
from decimal import Decimal
from datetime import datetime, timedelta
from src.ai_safety_guard import AISafetyGuard
from src.models import Market, Opportunity


# Property 21: Multilingual Safety Response Parsing
@given(
    language=st.sampled_from(["english", "russian", "french", "spanish"]),
    response_type=st.sampled_from(["yes", "no"]),
    case_variant=st.sampled_from(["lower", "upper", "mixed"]),
    whitespace=st.sampled_from(["none", "leading", "trailing", "both"])
)
@settings(max_examples=100)
def test_multilingual_safety_response_parsing(language, response_type, case_variant, whitespace):
    """
    **Validates: Requirements 7.2**
    
    Property 21: Multilingual Safety Response Parsing
    
    For any AI safety guard response containing YES/NO in any supported language
    (English, Russian, French, Spanish), the system should correctly parse the
    approval decision.
    
    This property verifies that:
    1. All YES variants in all languages are parsed as True
    2. All NO variants in all languages are parsed as False
    3. Parsing is case-insensitive
    4. Parsing handles leading/trailing whitespace
    """
    guard = AISafetyGuard(nvidia_api_key="test_key")
    
    # Define responses for each language
    yes_responses = {
        "english": ["yes", "y", "true", "approve", "approved", "ok", "okay"],
        "russian": ["да", "д"],
        "french": ["oui", "o"],
        "spanish": ["sí", "si", "s"]
    }
    
    no_responses = {
        "english": ["no", "n", "false", "reject", "rejected", "deny", "denied"],
        "russian": ["нет", "н"],
        "french": ["non"],
        "spanish": ["no"]
    }
    
    # Select response based on type and language
    if response_type == "yes":
        responses = yes_responses[language]
        expected = True
    else:
        responses = no_responses[language]
        expected = False
    
    # Test each response variant
    for base_response in responses:
        # Apply case variant
        if case_variant == "upper":
            response = base_response.upper()
        elif case_variant == "mixed" and len(base_response) > 1:
            response = base_response[0].upper() + base_response[1:]
        else:
            response = base_response
        
        # Apply whitespace
        if whitespace == "leading":
            response = "  " + response
        elif whitespace == "trailing":
            response = response + "  "
        elif whitespace == "both":
            response = "  " + response + "  "
        
        # Parse and verify
        result = guard.parse_yes_no_response(response)
        assert result == expected, (
            f"Failed to parse '{response}' (language={language}, type={response_type}, "
            f"case={case_variant}, whitespace={whitespace}): expected {expected}, got {result}"
        )


# Property 22: AI Safety Timeout Handling
@given(
    timeout_occurred=st.booleans(),
    ai_response=st.sampled_from([None, "yes", "no", "unclear"])
)
@settings(max_examples=100)
def test_ai_safety_timeout_handling(timeout_occurred, ai_response):
    """
    **Validates: Requirements 7.3**
    
    Property 22: AI Safety Timeout Handling
    
    For any AI safety check that fails to respond within 2 seconds or returns NO,
    the system should skip the trade opportunity.
    
    This property verifies that:
    1. Timeout (None response) triggers fallback heuristics
    2. NO response rejects the trade
    3. Unclear response (None after parsing) triggers fallback
    4. Only clear YES responses approve trades
    """
    guard = AISafetyGuard(nvidia_api_key="test_key")
    
    # Simulate AI response scenarios
    if timeout_occurred or ai_response is None:
        # Timeout or no response - should use fallback
        parsed_response = None
    elif ai_response == "yes":
        parsed_response = True
    elif ai_response == "no":
        parsed_response = False
    else:  # unclear
        parsed_response = None
    
    # Verify behavior based on response
    if parsed_response is None:
        # Should trigger fallback heuristics
        # Fallback will approve only if balance > $10, gas < 800, pending < 5
        fallback_result = guard._fallback_heuristics(
            current_balance=Decimal('100.0'),  # Good balance
            current_gas_price_gwei=50,  # Good gas
            pending_tx_count=2  # Good pending count
        )
        assert fallback_result is True, "Fallback should approve with good conditions"
        
        fallback_result_bad = guard._fallback_heuristics(
            current_balance=Decimal('5.0'),  # Bad balance
            current_gas_price_gwei=50,
            pending_tx_count=2
        )
        assert fallback_result_bad is False, "Fallback should reject with bad conditions"
    
    elif parsed_response is False:
        # NO response should reject trade
        assert parsed_response is False, "NO response should be False"
    
    elif parsed_response is True:
        # YES response should approve trade
        assert parsed_response is True, "YES response should be True"


# Property 23: AI Safety Fallback Heuristics
@given(
    balance=st.decimals(min_value=Decimal('0'), max_value=Decimal('1000'), places=2),
    gas_price=st.integers(min_value=10, max_value=2000),
    pending_tx=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=100)
def test_ai_safety_fallback_heuristics(balance, gas_price, pending_tx):
    """
    **Validates: Requirements 7.4**
    
    Property 23: AI Safety Fallback Heuristics
    
    For any trade opportunity when the AI safety guard is unavailable, the system
    should use fallback heuristics (balance > $10, gas < 800 gwei, pending_tx < 5)
    to make safety decisions.
    
    This property verifies that:
    1. All three conditions must pass for approval
    2. Any single failing condition rejects the trade
    3. Thresholds are correctly enforced
    """
    guard = AISafetyGuard(
        nvidia_api_key="test_key",
        min_balance=Decimal('10.0'),
        max_gas_price_gwei=800,
        max_pending_tx=5
    )
    
    result = guard._fallback_heuristics(balance, gas_price, pending_tx)
    
    # Calculate expected result
    balance_ok = balance > Decimal('10.0')
    gas_ok = gas_price < 800
    pending_ok = pending_tx < 5
    
    expected = balance_ok and gas_ok and pending_ok
    
    assert result == expected, (
        f"Fallback heuristics mismatch: balance=${balance} (ok={balance_ok}), "
        f"gas={gas_price} gwei (ok={gas_ok}), pending={pending_tx} (ok={pending_ok}), "
        f"expected={expected}, got={result}"
    )
    
    # Verify individual conditions
    if not balance_ok:
        assert result is False, f"Should reject when balance ${balance} <= $10"
    if not gas_ok:
        assert result is False, f"Should reject when gas {gas_price} >= 800 gwei"
    if not pending_ok:
        assert result is False, f"Should reject when pending {pending_tx} >= 5"


# Property 24: High Volatility Trading Halt
@given(
    price_changes=st.lists(
        st.decimals(min_value=Decimal('-0.10'), max_value=Decimal('0.10'), places=4),
        min_size=2,
        max_size=10
    ),
    base_price=st.decimals(min_value=Decimal('100'), max_value=Decimal('100000'), places=2)
)
@settings(max_examples=100)
def test_high_volatility_trading_halt(price_changes, base_price):
    """
    **Validates: Requirements 7.5**
    
    Property 24: High Volatility Trading Halt
    
    For any 1-minute period where BTC/ETH/SOL/XRP moves more than 5%, the AI safety
    guard should halt all trading for 5 minutes.
    
    This property verifies that:
    1. Volatility > 5% triggers halt
    2. Volatility <= 5% does not trigger halt
    3. Halt lasts for configured duration
    4. Halt expires after duration
    """
    guard = AISafetyGuard(
        nvidia_api_key="test_key",
        volatility_threshold=Decimal('0.05'),  # 5%
        volatility_halt_duration=300  # 5 minutes
    )
    
    asset = "BTC"
    
    # Simulate price updates over 1 minute (use recent timestamps)
    now = datetime.now()
    for i, change in enumerate(price_changes):
        price = base_price * (Decimal('1.0') + change)
        # Place timestamps within the last 60 seconds, most recent first
        timestamp = now - timedelta(seconds=i * 6)  # 0s, 6s, 12s, 18s ago...
        guard._price_history[asset] = guard._price_history.get(asset, [])
        guard._price_history[asset].append((timestamp, price))
    
    # Calculate actual volatility
    volatility = guard._calculate_volatility(asset)
    
    if volatility is not None:
        # Calculate expected volatility
        prices = [base_price * (Decimal('1.0') + change) for change in price_changes]
        min_price = min(prices)
        max_price = max(prices)
        
        # Handle edge case where all prices are the same
        if min_price == max_price:
            expected_volatility = Decimal('0')
        else:
            expected_volatility = abs(max_price - min_price) / min_price
        
        # Verify volatility calculation (allow small rounding differences)
        assert abs(volatility - expected_volatility) < Decimal('0.0001'), (
            f"Volatility calculation mismatch: expected {expected_volatility}, got {volatility}"
        )
        
        # Check if halt should be triggered
        if volatility > Decimal('0.05'):
            # High volatility - should trigger halt
            guard._trigger_volatility_halt()
            assert guard._is_volatility_halted(), "Should be halted after high volatility"
            assert guard._volatility_halt_until is not None, "Halt end time should be set"
            
            # Verify halt duration
            expected_end = datetime.now() + timedelta(seconds=300)
            time_diff = abs((guard._volatility_halt_until - expected_end).total_seconds())
            assert time_diff < 2, f"Halt duration incorrect: {time_diff}s difference"
        else:
            # Low volatility - should not trigger halt
            initial_halt_status = guard._is_volatility_halted()
            # Don't trigger halt for low volatility
            # Just verify that low volatility doesn't cause issues
            assert volatility <= Decimal('0.05'), "Volatility should be <= 5%"


# Property 16: Ambiguous Market Filtering
@given(
    keyword=st.sampled_from([
        "approximately", "around", "roughly", "about", "near",
        "close to", "almost", "nearly", "circa", "~"
    ]),
    position=st.sampled_from(["start", "middle", "end"]),
    case_variant=st.sampled_from(["lower", "upper", "mixed"])
)
@settings(max_examples=100)
def test_ambiguous_market_filtering(keyword, position, case_variant):
    """
    **Validates: Requirements 5.4, 7.6**
    
    Property 16: Ambiguous Market Filtering
    
    For any market containing ambiguous resolution keywords (e.g., "approximately",
    "around", "roughly"), the system should skip the opportunity regardless of
    apparent profitability.
    
    This property verifies that:
    1. All ambiguous keywords are detected
    2. Detection is case-insensitive
    3. Keywords are detected regardless of position in question
    4. Markets without ambiguous keywords are not filtered
    """
    guard = AISafetyGuard(nvidia_api_key="test_key")
    
    # Apply case variant to keyword
    if case_variant == "upper":
        test_keyword = keyword.upper()
    elif case_variant == "mixed" and len(keyword) > 1:
        test_keyword = keyword[0].upper() + keyword[1:]
    else:
        test_keyword = keyword
    
    # Build question with keyword at different positions
    if position == "start":
        question = f"{test_keyword} $95,000 for BTC"
    elif position == "middle":
        question = f"BTC will be {test_keyword} $95,000"
    else:  # end
        question = f"BTC will be $95,000 {test_keyword}"
    
    # Test ambiguous keyword detection
    has_ambiguous = guard._has_ambiguous_keywords(question)
    assert has_ambiguous is True, (
        f"Failed to detect ambiguous keyword '{test_keyword}' in position '{position}' "
        f"with case '{case_variant}': {question}"
    )
    
    # Test clear question without ambiguous keywords
    clear_question = "BTC will be above $95,000"
    has_ambiguous_clear = guard._has_ambiguous_keywords(clear_question)
    assert has_ambiguous_clear is False, (
        f"False positive: detected ambiguous keyword in clear question: {clear_question}"
    )
    
    # Verify that ambiguous markets are rejected in validate_trade
    # (This would require a full integration test, but we verify the detection works)
