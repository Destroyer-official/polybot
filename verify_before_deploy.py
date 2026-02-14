"""
Pre-deployment verification script.
Checks all critical configurations before AWS deployment.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

def verify():
    """Verify all critical configurations."""
    print("="*80)
    print("PRE-DEPLOYMENT VERIFICATION")
    print("="*80)
    
    load_dotenv()
    
    issues = []
    warnings = []
    
    # 1. Check .env file exists
    if not Path(".env").exists():
        issues.append(".env file not found")
    else:
        print("[OK] .env file found")
    
    # 2. Check critical environment variables
    critical_vars = [
        "PRIVATE_KEY",
        "WALLET_ADDRESS",
        "POLYGON_RPC_URL",
        "DRY_RUN"
    ]
    
    for var in critical_vars:
        value = os.getenv(var)
        if not value:
            issues.append(f"{var} not set in .env")
        else:
            if var == "DRY_RUN":
                print(f"[OK] {var}={value}")
            else:
                print(f"[OK] {var} is set")
    
    # 3. Check DRY_RUN setting
    dry_run = os.getenv("DRY_RUN", "true").lower()
    if dry_run == "true":
        warnings.append("DRY_RUN=true (simulation mode - no real trades)")
    else:
        print("[INFO] DRY_RUN=false (REAL TRADING MODE)")
    
    # 4. Check essential files exist
    essential_files = [
        "bot.py",
        "requirements.txt",
        "README.md",
        "money.pem",
        "src/main_orchestrator.py",
        "src/fifteen_min_crypto_strategy.py",
        "config/config.py"
    ]
    
    for file_path in essential_files:
        if not Path(file_path).exists():
            issues.append(f"Essential file missing: {file_path}")
        else:
            print(f"[OK] {file_path} exists")
    
    # 5. Check src directory
    src_files = list(Path("src").glob("*.py"))
    print(f"[OK] Found {len(src_files)} Python files in src/")
    
    # 6. Check tests directory
    test_files = list(Path("tests").glob("test_*.py"))
    print(f"[OK] Found {len(test_files)} test files in tests/")
    
    # Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    if issues:
        print("\n[CRITICAL ISSUES]")
        for issue in issues:
            print(f"  - {issue}")
    
    if warnings:
        print("\n[WARNINGS]")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not issues and not warnings:
        print("\n[SUCCESS] All checks passed - Ready for deployment!")
        return 0
    elif issues:
        print(f"\n[ERROR] {len(issues)} critical issue(s) found - Fix before deployment")
        return 1
    else:
        print(f"\n[WARNING] {len(warnings)} warning(s) - Review before deployment")
        return 0

if __name__ == "__main__":
    import sys
    sys.exit(verify())
