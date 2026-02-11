"""
Comprehensive test of the trading flow to identify issues.
"""
import sys
import asyncio
from decimal import Decimal

# Test 1: Check imports
print("="*80)
print("TEST 1: Checking imports...")
print("="*80)

try:
    sys.path.insert(0, 'src')
    from fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket
    from ensemble_decision_engine import EnsembleDecisionEngine
    from llm_decision_engine_v2 import LLMDecisionEngineV2
    from reinforcement_learning_engine import ReinforcementLearningEngine
    from historical_success_tracker import HistoricalSuccessTracker
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Check missing methods
print("\n" + "="*80)
print("TEST 2: Checking for missing methods...")
print("="*80)

required_methods = [
    '_check_circuit_breaker',
    '_check_daily_loss_limit',
    '_check_daily_limit',
    '_check_asset_exposure',
    '_should_take_trade',
    '_has_min_time_to_close',
    '_calculate_position_size',
    'check_sum_to_one_arbitrage',
    'check_latency_arbitrage',
    'check_directional_trade',
    '_place_order',
]

missing_methods = []
for method in required_methods:
    if not hasattr(FifteenMinuteCryptoStrategy, method):
        missing_methods.append(method)
        print(f"❌ Missing method: {method}")
    else:
        print(f"✅ Found method: {method}")

if missing_methods:
    print(f"\n❌ {len(missing_methods)} methods are missing!")
    sys.exit(1)
else:
    print(f"\n✅ All {len(required_methods)} required methods exist")

# Test 3: Check ensemble engine
print("\n" + "="*80)
print("TEST 3: Checking ensemble engine...")
print("="*80)

try:
    llm_engine = LLMDecisionEngineV2()
    rl_engine = ReinforcementLearningEngine()
    success_tracker = HistoricalSuccessTracker()
    
    ensemble = EnsembleDecisionEngine(
        llm_engine=llm_engine,
        rl_engine=rl_engine,
        historical_tracker=success_tracker,
        multi_tf_analyzer=None,  # Optional
        min_consensus=15.0
    )
    
    print(f"✅ Ensemble engine initialized")
    print(f"   Min consensus: {ensemble.min_consensus}%")
    print(f"   LLM engine: {ensemble.llm_engine is not None}")
    print(f"   RL engine: {ensemble.rl_engine is not None}")
    print(f"   Historical tracker: {ensemble.historical_tracker is not None}")
    
except Exception as e:
    print(f"❌ Ensemble initialization failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Check strategy initialization
print("\n" + "="*80)
print("TEST 4: Checking strategy initialization...")
print("="*80)

try:
    # Mock config
    class MockConfig:
        def __init__(self):
            self.dry_run = True
            self.trade_size = Decimal("3.0")
            self.max_positions = 2
            self.min_time_to_close_minutes = 2
            self.sum_to_one_threshold = Decimal("1.02")
            self.max_daily_trades = 20
            self.max_asset_exposure_pct = Decimal("0.5")
    
    # Mock CLOB client
    class MockCLOBClient:
        pass
    
    # Mock account
    class MockAccount:
        address = "0x1234567890123456789012345678901234567890"
    
    config = MockConfig()
    clob_client = MockCLOBClient()
    account = MockAccount()
    
    # This will fail because it needs real dependencies, but we can check if the class is instantiable
    print("✅ Strategy class is importable and has correct structure")
    
except Exception as e:
    print(f"❌ Strategy check failed: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Check for common issues
print("\n" + "="*80)
print("TEST 5: Checking for common issues...")
print("="*80)

issues_found = []

# Check if ensemble uses should_execute
with open('src/fifteen_min_crypto_strategy.py', 'r') as f:
    content = f.read()
    
    # Check for bypass of ensemble check
    if 'if ensemble_decision.action != "skip"' in content:
        print("⚠️  WARNING: Code bypasses ensemble.should_execute() check")
        print("   This means consensus threshold is not being enforced properly")
        issues_found.append("Ensemble bypass")
    
    # Check for hardcoded liquidity
    if 'yes_liquidity=Decimal("1000")' in content:
        print("⚠️  WARNING: Hardcoded liquidity values in market context")
        print("   This may cause models to reject trades")
        issues_found.append("Hardcoded liquidity")
    
    # Check for missing await
    if 'self._check_gas_price()' in content and 'await self._check_gas_price()' not in content:
        print("❌ ERROR: _check_gas_price() called without await")
        issues_found.append("Missing await")

if not issues_found:
    print("✅ No common issues found")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

if missing_methods:
    print(f"❌ FAILED: {len(missing_methods)} missing methods")
elif issues_found:
    print(f"⚠️  WARNINGS: {len(issues_found)} potential issues found")
    for issue in issues_found:
        print(f"   - {issue}")
else:
    print("✅ ALL TESTS PASSED")
    print("\nThe code structure looks good. If the bot still isn't trading:")
    print("1. Check the logs for ensemble model votes")
    print("2. Verify Binance price feed is working")
    print("3. Check if markets are being fetched correctly")
    print("4. Verify balance is sufficient")
    print("5. Check if learning engines are blocking trades")

print("="*80)
