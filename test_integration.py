#!/usr/bin/env python3
"""
Comprehensive Integration Test
Tests all components of the full integration
"""

import sys

def test_file_syntax():
    """Test 1: File compiles without syntax errors"""
    print("Test 1: Syntax Check...")
    try:
        import py_compile
        py_compile.compile('src/fifteen_min_crypto_strategy.py', doraise=True)
        print("✅ PASSED: No syntax errors")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

def test_components_present():
    """Test 2: All integration components are present"""
    print("\nTest 2: Component Verification...")
    
    with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    components = {
        'Layered Parameters': 'self.base_take_profit_pct',
        'Circuit Breaker': 'def _check_circuit_breaker',
        'Daily Loss Limit': 'def _check_daily_loss_limit',
        'Dynamic Stop Loss': 'def _calculate_dynamic_stop_loss',
        'Ensemble Decision': 'ensemble_decision = await self.ensemble_engine.make_decision',
        'Ensemble Approved Log': 'ENSEMBLE APPROVED',
        'Ensemble Rejected Log': 'ENSEMBLE REJECTED',
        'Self-Healing Latency': 'Circuit breaker active - skipping latency',
        'Self-Healing Directional': 'Circuit breaker active - skipping directional',
        'Layered Dynamic TP': 'FINAL Dynamic TP',
        'Daily Loss Tracking': 'self.daily_loss += loss_amount'
    }
    
    all_passed = True
    for name, pattern in components.items():
        if pattern in content:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} - MISSING!")
            all_passed = False
    
    if all_passed:
        print("✅ PASSED: All components present")
    else:
        print("❌ FAILED: Some components missing")
    
    return all_passed

def test_self_healing_integration():
    """Test 3: Self-healing checks are in all strategy methods"""
    print("\nTest 3: Self-Healing Integration...")
    
    with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all strategy methods
    methods = {
        'sum_to_one': 'async def check_sum_to_one_arbitrage',
        'latency': 'async def check_latency_arbitrage',
        'directional': 'async def check_directional_trade'
    }
    
    all_passed = True
    for name, method_sig in methods.items():
        # Find method start
        method_start = content.find(method_sig)
        if method_start == -1:
            print(f"  ❌ {name} method not found")
            all_passed = False
            continue
        
        # Find next method (approximate end)
        next_method = content.find('async def', method_start + 100)
        if next_method == -1:
            next_method = len(content)
        
        method_content = content[method_start:next_method]
        
        # Check for self-healing
        has_circuit_breaker = '_check_circuit_breaker' in method_content
        has_daily_loss = '_check_daily_loss_limit' in method_content
        
        if has_circuit_breaker and has_daily_loss:
            print(f"  ✅ {name}: Circuit breaker + Daily loss")
        elif has_circuit_breaker:
            print(f"  ⚠️ {name}: Circuit breaker only (missing daily loss)")
            all_passed = False
        elif has_daily_loss:
            print(f"  ⚠️ {name}: Daily loss only (missing circuit breaker)")
            all_passed = False
        else:
            print(f"  ❌ {name}: No self-healing checks")
            all_passed = False
    
    if all_passed:
        print("✅ PASSED: Self-healing in all methods")
    else:
        print("❌ FAILED: Self-healing incomplete")
    
    return all_passed

def test_ensemble_integration():
    """Test 4: Ensemble engine is properly integrated"""
    print("\nTest 4: Ensemble Integration...")
    
    with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('Ensemble initialization', 'self.ensemble_engine = EnsembleDecisionEngine'),
        ('Ensemble decision call', 'ensemble_decision = await self.ensemble_engine.make_decision'),
        ('Ensemble should_execute', 'self.ensemble_engine.should_execute(ensemble_decision)'),
        ('Ensemble approved logging', 'ENSEMBLE APPROVED'),
        ('Ensemble rejected logging', 'ENSEMBLE REJECTED'),
    ]
    
    all_passed = True
    for name, pattern in checks:
        if pattern in content:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} - MISSING!")
            all_passed = False
    
    if all_passed:
        print("✅ PASSED: Ensemble fully integrated")
    else:
        print("❌ FAILED: Ensemble integration incomplete")
    
    return all_passed

def test_dynamic_tp_sl():
    """Test 5: Dynamic TP/SL with layered system"""
    print("\nTest 5: Dynamic TP/SL...")
    
    with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('Base parameters', 'self.base_take_profit_pct'),
        ('Layered TP calculation', 'dynamic_take_profit = self.base_take_profit_pct'),
        ('TP time adjustment', 'time_remaining_minutes'),
        ('TP position age adjustment', 'position_age_minutes'),
        ('TP momentum adjustment', 'binance_change'),
        ('TP streak adjustment', 'consecutive_wins'),
        ('Final TP logging', 'FINAL Dynamic TP'),
        ('Dynamic SL method', 'def _calculate_dynamic_stop_loss'),
        ('Daily loss tracking', 'self.daily_loss += loss_amount'),
    ]
    
    all_passed = True
    for name, pattern in checks:
        if pattern in content:
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} - MISSING!")
            all_passed = False
    
    if all_passed:
        print("✅ PASSED: Dynamic TP/SL complete")
    else:
        print("❌ FAILED: Dynamic TP/SL incomplete")
    
    return all_passed

def main():
    print("=" * 70)
    print("COMPREHENSIVE INTEGRATION TEST")
    print("=" * 70)
    
    tests = [
        test_file_syntax,
        test_components_present,
        test_self_healing_integration,
        test_ensemble_integration,
        test_dynamic_tp_sl,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    if all(results):
        print("\n✅ ALL TESTS PASSED - READY TO DEPLOY!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - FIX BEFORE DEPLOYING!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
