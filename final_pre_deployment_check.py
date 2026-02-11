"""
Final comprehensive check before AWS deployment.
Verifies all fixes are in place and working.
"""
import sys
import os
from decimal import Decimal

print("="*80)
print("FINAL PRE-DEPLOYMENT CHECK")
print("="*80)

errors = []
warnings = []

# Test 1: Check file existence
print("\n[1/8] Checking file existence...")
required_files = [
    'src/main_orchestrator.py',
    'src/fifteen_min_crypto_strategy.py',
    'src/ensemble_decision_engine.py',
]

for file in required_files:
    if os.path.exists(file):
        print(f"  ✅ {file}")
    else:
        print(f"  ❌ {file} - NOT FOUND")
        errors.append(f"Missing file: {file}")

# Test 2: Check async/await fix
print("\n[2/8] Checking async/await fix in main_orchestrator.py...")
with open('src/main_orchestrator.py', 'r', encoding='utf-8') as f:
    content = f.read()
    if 'gas_ok = await self._check_gas_price()' in content:
        print("  ✅ Async/await fix present")
    elif 'gas_ok = self._check_gas_price()' in content:
        print("  ❌ Missing await keyword!")
        errors.append("main_orchestrator.py: Missing 'await' for _check_gas_price()")
    else:
        print("  ⚠️  Cannot find _check_gas_price() call")
        warnings.append("main_orchestrator.py: Cannot verify gas price check")

# Test 3: Check missing methods
print("\n[3/8] Checking for missing methods in fifteen_min_crypto_strategy.py...")
with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
    if 'def _check_circuit_breaker(self)' in content:
        print("  ✅ _check_circuit_breaker() method exists")
    else:
        print("  ❌ _check_circuit_breaker() method MISSING")
        errors.append("fifteen_min_crypto_strategy.py: Missing _check_circuit_breaker()")
    
    if 'def _check_daily_loss_limit(self)' in content:
        print("  ✅ _check_daily_loss_limit() method exists")
    else:
        print("  ❌ _check_daily_loss_limit() method MISSING")
        errors.append("fifteen_min_crypto_strategy.py: Missing _check_daily_loss_limit()")

# Test 4: Check min_consensus value
print("\n[4/8] Checking min_consensus value...")
with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
    # Find the line with min_consensus in EnsembleDecisionEngine initialization
    lines = content.split('\n')
    found_consensus = False
    for i, line in enumerate(lines):
        if 'self.ensemble_engine = EnsembleDecisionEngine(' in line:
            # Look at next 10 lines for min_consensus
            for j in range(i, min(i+10, len(lines))):
                if 'min_consensus=' in lines[j]:
                    if 'min_consensus=15.0' in lines[j] or 'min_consensus=15' in lines[j]:
                        print(f"  ✅ min_consensus=15.0 (line {j+1})")
                        found_consensus = True
                    elif 'min_consensus=60.0' in lines[j] or 'min_consensus=60' in lines[j]:
                        print(f"  ❌ min_consensus=60.0 (line {j+1}) - TOO HIGH!")
                        errors.append("fifteen_min_crypto_strategy.py: min_consensus is 60%, should be 15%")
                        found_consensus = True
                    elif 'min_consensus=30.0' in lines[j] or 'min_consensus=30' in lines[j]:
                        print(f"  ⚠️  min_consensus=30.0 (line {j+1}) - Could be lower")
                        warnings.append("fifteen_min_crypto_strategy.py: min_consensus is 30%, recommend 15%")
                        found_consensus = True
                    else:
                        # Extract the value
                        import re
                        match = re.search(r'min_consensus=(\d+\.?\d*)', lines[j])
                        if match:
                            value = float(match.group(1))
                            print(f"  ℹ️  min_consensus={value} (line {j+1})")
                            if value > 20:
                                warnings.append(f"fifteen_min_crypto_strategy.py: min_consensus={value}% might be too high")
                            found_consensus = True
                    break
            break
    
    if not found_consensus:
        print("  ⚠️  Could not find min_consensus setting")
        warnings.append("fifteen_min_crypto_strategy.py: Cannot verify min_consensus value")

# Test 5: Check ensemble approval logic
print("\n[5/8] Checking ensemble approval logic...")
with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
    # Check if using should_execute or bypass
    if 'if self.ensemble_engine.should_execute(ensemble_decision):' in content:
        print("  ✅ Using ensemble.should_execute() - respects min_consensus")
    elif 'if ensemble_decision.action != "skip":' in content:
        print("  ⚠️  Using bypass check (action != 'skip') - ignores consensus threshold")
        warnings.append("fifteen_min_crypto_strategy.py: Bypassing consensus check")
    else:
        print("  ⚠️  Cannot determine ensemble approval logic")
        warnings.append("fifteen_min_crypto_strategy.py: Cannot verify ensemble approval logic")

# Test 6: Check log message
print("\n[6/8] Checking log messages...")
with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
    if 'need >= 50%' in content:
        print("  ⚠️  Log message says 'need >= 50%' - should match actual threshold")
        warnings.append("fifteen_min_crypto_strategy.py: Log message shows wrong threshold (50%)")
    elif 'need >= 15%' in content:
        print("  ✅ Log message says 'need >= 15%' - matches threshold")
    else:
        print("  ℹ️  No threshold in log message")

# Test 7: Check detailed logging
print("\n[7/8] Checking detailed model vote logging...")
with open('src/ensemble_decision_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
    if 'for model_name, vote in model_votes.items():' in content and 'logger.info(f"   {model_name}:' in content:
        print("  ✅ Detailed model vote logging present")
    else:
        print("  ⚠️  Detailed model vote logging might be missing")
        warnings.append("ensemble_decision_engine.py: Detailed logging might be missing")

# Test 8: Python syntax check
print("\n[8/8] Checking Python syntax...")
import py_compile
syntax_ok = True

for file in required_files:
    try:
        py_compile.compile(file, doraise=True)
        print(f"  ✅ {file} - syntax OK")
    except py_compile.PyCompileError as e:
        print(f"  ❌ {file} - SYNTAX ERROR")
        print(f"     {e}")
        errors.append(f"Syntax error in {file}")
        syntax_ok = False

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

if errors:
    print(f"\n❌ {len(errors)} CRITICAL ERROR(S) FOUND:")
    for i, error in enumerate(errors, 1):
        print(f"  {i}. {error}")
    print("\n⚠️  DO NOT DEPLOY - Fix errors first!")
    sys.exit(1)

if warnings:
    print(f"\n⚠️  {len(warnings)} WARNING(S):")
    for i, warning in enumerate(warnings, 1):
        print(f"  {i}. {warning}")
    print("\n✅ No critical errors, but review warnings before deploying")
else:
    print("\n✅ ALL CHECKS PASSED!")
    print("\n🚀 Ready to deploy to AWS")

print("\n" + "="*80)
print("DEPLOYMENT CHECKLIST:")
print("="*80)
print("1. ✅ Run this script - PASSED")
print("2. ⏳ Copy files to AWS server")
print("3. ⏳ Clear Python cache on server")
print("4. ⏳ Restart polybot service")
print("5. ⏳ Monitor logs for:")
print("     - Gas price checks")
print("     - Ensemble model votes")
print("     - Trade approvals")
print("     - Order placements")
print("="*80)
