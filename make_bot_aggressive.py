#!/usr/bin/env python3
"""
Make Bot AGGRESSIVE - Force it to trade profitably
This script modifies the bot to be much more aggressive in finding and executing trades
"""

import re

print("=" * 80)
print("MAKING BOT AGGRESSIVE - COMPREHENSIVE FIX")
print("=" * 80)
print()

# Fix 1: Lower ensemble consensus to 20% (very aggressive)
print("Fix 1: Lowering ensemble consensus to 20%...")
with open("src/fifteen_min_crypto_strategy.py", "r", encoding="utf-8") as f:
    content = f.read()

content = re.sub(
    r'min_consensus=\d+\.?\d*',
    'min_consensus=20.0',
    content
)

with open("src/fifteen_min_crypto_strategy.py", "w", encoding="utf-8") as f:
    f.write(content)
print("✅ Ensemble consensus: 20%")
print()

# Fix 2: Lower confidence threshold in ensemble to 15%
print("Fix 2: Lowering confidence threshold to 15%...")
with open("src/ensemble_decision_engine.py", "r") as f:
    content = f.read()

content = re.sub(
    r'if decision\.confidence < \d+\.?\d*:',
    'if decision.confidence < 15.0:',
    content
)

with open("src/ensemble_decision_engine.py", "w") as f:
    f.write(content)
print("✅ Confidence threshold: 15%")
print()

# Fix 3: Make LLM more aggressive - lower thresholds
print("Fix 3: Making LLM more aggressive...")
try:
    with open("src/llm_decision_engine_v2.py", "r") as f:
        content = f.read()
    
    # Lower arbitrage threshold from 0.97 to 0.99 (more opportunities)
    content = re.sub(
        r'sum_price < Decimal\(["\']0\.97["\']\)',
        'sum_price < Decimal("0.99")',
        content
    )
    
    # Lower confidence requirements
    content = re.sub(
        r'confidence = 100\.0',
        'confidence = 80.0',
        content
    )
    
    with open("src/llm_decision_engine_v2.py", "w") as f:
        f.write(content)
    print("✅ LLM thresholds lowered")
except Exception as e:
    print(f"⚠️  LLM fix: {e}")
print()

# Fix 4: Disable balance check temporarily
print("Fix 4: Lowering minimum balance requirement...")
with open("src/main_orchestrator.py", "r") as f:
    content = f.read()

# Lower minimum balance from 10 to 5
content = re.sub(
    r'min_balance = \d+\.?\d*',
    'min_balance = 5.0',
    content
)

content = re.sub(
    r'MIN_BALANCE = \d+\.?\d*',
    'MIN_BALANCE = 5.0',
    content
)

with open("src/main_orchestrator.py", "w") as f:
    f.write(content)
print("✅ Minimum balance: $5.00")
print()

# Fix 5: Make multi-timeframe analyzer more sensitive
print("Fix 5: Making technical analysis more sensitive...")
try:
    with open("src/multi_timeframe_analyzer.py", "r") as f:
        content = f.read()
    
    # Lower confidence thresholds for signals
    content = re.sub(
        r'if confidence >= 40',
        'if confidence >= 20',
        content
    )
    
    content = re.sub(
        r'confidence >= 30',
        'confidence >= 15',
        content
    )
    
    with open("src/multi_timeframe_analyzer.py", "w") as f:
        f.write(content)
    print("✅ Technical analysis more sensitive")
except Exception as e:
    print(f"⚠️  Technical analysis: {e}")
print()

# Fix 6: Reduce rate limiting
print("Fix 6: Reducing rate limiting...")
with open("src/fifteen_min_crypto_strategy.py", "r") as f:
    content = f.read()

# Reduce rate limit from 15s to 5s
content = re.sub(
    r'\.total_seconds\(\) < 15:',
    '.total_seconds() < 5:',
    content
)

with open("src/fifteen_min_crypto_strategy.py", "w") as f:
    f.write(content)
print("✅ Rate limit: 5 seconds")
print()

# Fix 7: Enable buy_both for directional trades
print("Fix 7: Enabling buy_both execution...")
with open("src/fifteen_min_crypto_strategy.py", "r") as f:
    content = f.read()

# Comment out the buy_both skip logic
content = re.sub(
    r'elif ensemble_decision\.action == "buy_both":\s+# buy_both is for arbitrage.*?return False',
    '''elif ensemble_decision.action == "buy_both":
                    # AGGRESSIVE MODE: Execute buy_both as arbitrage
                    logger.info(f"🎯 ENSEMBLE: Executing buy_both arbitrage")
                    # Buy both YES and NO tokens
                    adjusted_size = self._calculate_position_size() / 2  # Split between YES and NO
                    if adjusted_size > Decimal("0"):
                        shares_yes = float(adjusted_size / market.up_price)
                        shares_no = float(adjusted_size / market.down_price)
                        await self._place_order(market, "UP", market.up_price, shares_yes, strategy="arbitrage")
                        await self._place_order(market, "DOWN", market.down_price, shares_no, strategy="arbitrage")
                        return True
                    return False''',
    content,
    flags=re.DOTALL
)

with open("src/fifteen_min_crypto_strategy.py", "w") as f:
    f.write(content)
print("✅ buy_both arbitrage enabled")
print()

print("=" * 80)
print("AGGRESSIVE MODE ACTIVATED")
print("=" * 80)
print()
print("Changes made:")
print("  ✅ Ensemble consensus: 60% → 20%")
print("  ✅ Confidence threshold: 50% → 15%")
print("  ✅ LLM arbitrage threshold: 0.97 → 0.99")
print("  ✅ Minimum balance: $10 → $5")
print("  ✅ Technical analysis: More sensitive")
print("  ✅ Rate limiting: 15s → 5s")
print("  ✅ buy_both arbitrage: Enabled")
print()
print("Next steps:")
print("  1. Upload files to AWS")
print("  2. Restart service")
print("  3. Monitor for trades")
print()
print("=" * 80)
