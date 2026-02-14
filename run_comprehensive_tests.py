"""
Comprehensive test suite runner for Polymarket Arbitrage Bot.
Runs all critical tests to verify functionality before deployment.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*80}")
    print(f"Running: {description}")
    print(f"{'='*80}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    if result.returncode == 0:
        print(f"[PASS] {description}")
        return True
    else:
        print(f"[FAIL] {description}")
        return False

def main():
    """Run comprehensive test suite."""
    print("="*80)
    print("COMPREHENSIVE TEST SUITE - Polymarket Arbitrage Bot")
    print("="*80)
    
    results = {}
    
    # 1. Configuration validation
    results['config'] = run_command(
        "python -m pytest tests/test_config.py -v",
        "Configuration Validation"
    )
    
    # 2. Core trading logic
    results['trading'] = run_command(
        "python -m pytest tests/test_fifteen_min_crypto_strategy.py -v",
        "15-Minute Crypto Strategy"
    )
    
    # 3. Risk management
    results['risk'] = run_command(
        "python -m pytest tests/test_portfolio_risk_manager.py -v",
        "Portfolio Risk Manager"
    )
    
    # 4. Order management
    results['orders'] = run_command(
        "python -m pytest tests/test_order_manager_unit.py -v",
        "Order Manager"
    )
    
    # 5. Fund management
    results['funds'] = run_command(
        "python -m pytest tests/test_fund_manager_unit.py -v",
        "Fund Manager"
    )
    
    # 6. Safety guards
    results['safety'] = run_command(
        "python -m pytest tests/test_ai_safety_guard_unit.py -v",
        "AI Safety Guard"
    )
    
    # 7. Auto-recovery system
    results['recovery'] = run_command(
        "python -m pytest tests/test_auto_recovery_system.py -v",
        "Auto-Recovery System"
    )
    
    # 8. Memory monitoring
    results['memory'] = run_command(
        "python -m pytest tests/test_memory_monitor.py -v",
        "Memory Monitor"
    )
    
    # 9. Log management
    results['logs'] = run_command(
        "python -m pytest tests/test_log_manager.py -v",
        "Log Manager"
    )
    
    # 10. Startup validation
    results['startup'] = run_command(
        "python -m pytest tests/test_startup_validation.py -v",
        "Startup Validation"
    )
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_status in results.items():
        status = "[PASS]" if passed_status else "[FAIL]"
        print(f"{status} - {test_name}")
    
    print("="*80)
    print(f"Total: {passed}/{total} test suites passed")
    print("="*80)
    
    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED - Ready for deployment!")
        return 0
    else:
        print(f"\n[ERROR] {total - passed} test suite(s) failed - Fix issues before deployment")
        return 1

if __name__ == "__main__":
    sys.exit(main())
