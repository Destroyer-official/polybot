"""
Cleanup script to remove unnecessary files and folders.
Keeps only essential files for production deployment.
"""

import os
import shutil
from pathlib import Path

def cleanup():
    """Remove unnecessary files and folders."""
    print("="*80)
    print("CLEANUP - Removing Unnecessary Files")
    print("="*80)
    
    # Folders to remove
    folders_to_remove = [
        "_cleanup_archive",
        ".hypothesis",
        ".pytest_cache",
        "__pycache__",
        "src/__pycache__",
        "tests/__pycache__",
        "config/__pycache__",
    ]
    
    # Markdown documentation files to remove (keep only README.md)
    md_files_to_remove = [
        "AGGRESSIVE_SELL_FIX_APPLIED.md",
        "AGGRESSIVE_TRADING_MODE_ENABLED.md",
        "ALL_FIXES_APPLIED_FINAL.md",
        "ALL_FIXES_APPLIED.md",
        "ALL_FIXES_DEPLOYED.md",
        "ALL_SELL_TESTS_PASSING.md",
        "ALL_SYSTEMS_DEPLOYED.md",
        "BOT_ANALYSIS_SUMMARY.md",
        "BOT_STATUS_EXPLAINED.md",
        "BUY_BOTH_FIX_COMPLETE.md",
        "BUY_BOTH_UNREACHABLE_CODE_FIX.md",
        "COMPREHENSIVE_AUDIT_REPORT.md",
        "COMPREHENSIVE_FINAL_AUDIT_REPORT.md",
        "COMPREHENSIVE_TRADING_FIXES.md",
        "CRITICAL_BUY_BOTH_FIX.md",
        "CRITICAL_EXIT_BUG_FIX.md",
        "CRITICAL_FIX_SUMMARY.md",
        "CRITICAL_ISSUES_FIXED.md",
        "CRITICAL_SELL_FIX.md",
        "CURRENT_STATUS_FINAL.md",
        "CURRENT_STATUS_SUMMARY.md",
        "DEEP_AUDIT_FINDINGS.md",
        "DEPLOY_NOW.md",
        "DEPLOY_VIA_SESSION_MANAGER.md",
        "DEPLOYMENT_COMPLETE_SUMMARY.md",
        "DEPLOYMENT_STATUS.md",
        "DEPLOYMENT_SUCCESS.md",
        "DEPLOYMENT.md",
        "DYNAMIC_TAKE_PROFIT_SYSTEM.md",
        "DYNAMIC_TRADING_ENABLED.md",
        "EMERGENCY_FIX_ALL_ISSUES.md",
        "EMERGENCY_FIX_SUMMARY.md",
        "EMERGENCY_STOP_ANALYSIS.md",
        "EVERYTHING_WORKING.md",
        "FINAL_CHECKLIST.md",
        "FINAL_COMPLETE_FIX.md",
        "FINAL_DYNAMIC_FIX.md",
        "FINAL_FIX_APPLIED.md",
        "FINAL_FIX_NEEDED.md",
        "FINAL_FIX_SUMMARY.md",
        "FINAL_PRODUCTION_STATUS.md",
        "FINAL_SOLUTION.md",
        "FINAL_SUMMARY.md",
        "IMPLEMENTATION_PLAN_FOR_PROFIT.md",
        "LOOP_SPEED_FIX.md",
        "LOSS_PREVENTION_RESEARCH.md",
        "MANUAL_DEPLOY.md",
        "MONITOR_README.md",
        "MONITOR_STATUS.md",
        "MONITORING_SYSTEM_COMPLETE.md",
        "OPTIMIZATION_COMPLETE.md",
        "OPTIMIZATION_ROADMAP.md",
        "PHANTOM_POSITION_FIX_COMPLETE.md",
        "POSITION_PROTECTION_SELL_PROBLEMS_RESEARCH.md",
        "PROBLEM_SOLVED.md",
        "PRODUCTION_DEPLOYMENT_CHECKLIST.md",
        "PRODUCTION_DEPLOYMENT_COMPLETE.md",
        "PRODUCTION_READY_STATUS.md",
        "PROFIT_OPTIMIZATION_APPLIED.md",
        "PROFITABLE_MODE_ANALYSIS.md",
        "QUICK_DEPLOY_GUIDE.md",
        "QUICK_FIX_GUIDE.md",
        "QUICK_START_MONITOR.md",
        "README_CRITICAL_FIX.md",
        "README_FIXES.md",
        "READY_TO_DEPLOY.md",
        "REPOSITORY_CLEANED.md",
        "RISK_MANAGER_FIX_COMPLETE.md",
        "SELL_FIX_COMPLETE.md",
        "SELL_FUNCTION_DIAGNOSIS.md",
        "SELL_FUNCTION_TEST_RESULTS.md",
        "SLIPPAGE_FIX.md",
        "SPEC_UPDATES_AUTONOMOUS_OPERATION.md",
        "TASK_13.4_COMPLETION_SUMMARY.md",
        "TASK_14.3_STARTUP_VALIDATION_SUMMARY.md",
        "TASK_15_COMPLETION_SUMMARY.md",
        "TASK_3.4_IMPROVEMENTS.md",
        "TASK_4_COMPLETION_SUMMARY.md",
        "TASK_4.1_COMPLETION_SUMMARY.md",
        "TASK_6.4_IMPLEMENTATION_SUMMARY.md",
        "TASK_8.2_COMPLETION_SUMMARY.md",
        "TASK_8.2_INTEGRATION_GUIDE.md",
        "TEST_CHECKPOINT_REPORT.md",
        "TRADING_ENABLED_FIXES.md",
        "ULTRA_AGGRESSIVE_MODE.md",
        "VERIFICATION_COMPLETE.md",
        "WHY_NO_TRADES_ANALYSIS.md",
        "WHY_NO_TRADES_FINAL_ANSWER.md",
    ]
    
    # Demo/test Python files to remove
    py_files_to_remove = [
        "demo_api_call_tracking.py",
        "demo_log_manager.py",
        "demo_realistic_caching.py",
        "diagnose_aws_connection.ps1",
        "diagnose_bot_issue.py",
        "emergency_close_positions.py",
        "final_production_readiness_check.py",
        "fix_buy_both.py",
        "integrate_daily_performance.py",
        "monitor_live.py",
        "monitor_premium.py",
        "monitor.py",
        "run_test_checkpoint.py",
        "test_all_fixes.py",
        "test_daily_performance.py",
        "test_exit_fix.py",
        "test_minimal_order.py",
        "test_sell_all_scenarios.py",
        "test_sell_function_comprehensive.py",
        "test_sell_neg_risk_validation.py",
        "test_sell_with_mock_prices.py",
        "test_trade_outcome_recording.py",
    ]
    
    # PowerShell deployment scripts to remove (keep only essential ones)
    ps_files_to_remove = [
        "check_1hr_performance.ps1",
        "check_bot_live.ps1",
        "check_positions_aws.ps1",
        "deploy_buy_both_fix.ps1",
        "deploy_critical_sell_fix.ps1",
        "deploy_direct.ps1",
        "deploy_dynamic_mode.sh",
        "deploy_dynamic_trading_fix.ps1",
        "deploy_fix_now.ps1",
        "deploy_fix.ps1",
        "deploy_phantom_position_fix.ps1",
        "deploy_production_fix.ps1",
        "deploy_profit_optimization.ps1",
        "deploy_smart_bot_final.ps1",
        "deploy_with_correct_ip.ps1",
        "upload_aggressive_fix.ps1",
        "upload_fixes.ps1",
        "upload_to_aws.sh",
    ]
    
    removed_count = 0
    
    # Remove folders
    for folder in folders_to_remove:
        folder_path = Path(folder)
        if folder_path.exists():
            try:
                shutil.rmtree(folder_path)
                print(f"✅ Removed folder: {folder}")
                removed_count += 1
            except Exception as e:
                print(f"⚠️  Failed to remove {folder}: {e}")
    
    # Remove markdown files
    for md_file in md_files_to_remove:
        file_path = Path(md_file)
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"✅ Removed file: {md_file}")
                removed_count += 1
            except Exception as e:
                print(f"⚠️  Failed to remove {md_file}: {e}")
    
    # Remove Python files
    for py_file in py_files_to_remove:
        file_path = Path(py_file)
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"✅ Removed file: {py_file}")
                removed_count += 1
            except Exception as e:
                print(f"⚠️  Failed to remove {py_file}: {e}")
    
    # Remove PowerShell files
    for ps_file in ps_files_to_remove:
        file_path = Path(ps_file)
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"✅ Removed file: {ps_file}")
                removed_count += 1
            except Exception as e:
                print(f"⚠️  Failed to remove {ps_file}: {e}")
    
    print("\n" + "="*80)
    print(f"✅ Cleanup complete! Removed {removed_count} items")
    print("="*80)

if __name__ == "__main__":
    cleanup()
