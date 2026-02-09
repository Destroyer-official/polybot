# Project Cleanup Plan - February 9, 2026

## Files to Move/Archive

### ✅ COMPLETED: Moved to docs/reports/
- All status reports (40+ markdown files)
- Test summaries and performance reports
- Deployment checklists and fix summaries

### ✅ COMPLETED: Moved to deployment/
- All shell scripts (check_bot_*.sh, deploy_*.sh, monitor_*.sh)
- Deployment and upgrade scripts

### ✅ COMPLETED: Moved to tests/
- test_clob_auth.py
- test_llm.py
- test_trading_fixes.py
- verify_api_fix.py
- verify_binance_fallback.py
- diagnose_signature.py
- funder_diagnostic.py
- derive_funder.py
- get_funder_address.py
- manual_trade_test.py
- real_trade_test.py
- final_trade_test.py
- run_all_tests.py

### ✅ COMPLETED: Moved to logs/
- bot_8hr_full_aws.log
- bot_debug.log
- crash.log
- test_output.log

### ✅ COMPLETED: Moved to data/
- state.json
- trade_history_aws.db

### ✅ COMPLETED: Moved to docs/
- 1606.02825v2.pdf (research paper)
- 8HR_REMINDER.txt

## Unused/Duplicate Files in src/ to Archive

### Files NOT Used in Production:
1. **improved_order_manager.py** - NOT imported anywhere (use order_manager.py instead)
2. **llm_decision_engine.py** (v1) - Replaced by llm_decision_engine_v2.py
3. **dynamic_position_sizer_v2.py** - NOT used (use dynamic_position_sizer.py)
4. **advanced_high_win_rate_strategy.py** - NOT used in main_orchestrator
5. **advanced_momentum_detector.py** - NOT used in main_orchestrator
6. **enhanced_binance_signal_detector.py** - NOT used in main_orchestrator
7. **high_probability_bonding.py** - NOT used in main_orchestrator

### Action: Move to _archive/unused_implementations/

## Files Currently Used in Production

### Core Components (DO NOT MOVE):
- main_orchestrator.py ✅
- bot.py ✅
- models.py ✅

### Active Strategy Engines:
- flash_crash_strategy.py ✅
- fifteen_min_crypto_strategy.py ✅
- negrisk_arbitrage_engine.py ✅
- internal_arbitrage_engine.py ✅ (initialized but disabled)
- directional_trading_strategy.py ✅ (initialized but set to None)
- cross_platform_arbitrage_engine.py ✅ (disabled)
- latency_arbitrage_engine.py ✅ (disabled)
- resolution_farming_engine.py ✅ (disabled)

### Active Managers:
- order_manager.py ✅
- fund_manager.py ✅
- transaction_manager.py ✅
- portfolio_risk_manager.py ✅
- auto_bridge_manager.py ✅
- token_allowance_manager.py ✅
- secrets_manager.py ✅

### Active Engines:
- llm_decision_engine_v2.py ✅
- adaptive_learning_engine.py ✅
- super_smart_learning.py ✅

### Active Utilities:
- market_parser.py ✅
- position_merger.py ✅
- ai_safety_guard.py ✅
- error_recovery.py ✅
- monitoring_system.py ✅
- status_dashboard.py ✅
- trade_history.py ✅
- trade_statistics.py ✅
- wallet_verifier.py ✅
- wallet_type_detector.py ✅
- kelly_position_sizer.py ✅
- dynamic_position_sizer.py ✅

### Support Files:
- logging_config.py ✅
- debug_logger.py ✅
- heartbeat_logger.py ✅
- report_generator.py ✅

### Backtest Components (Keep for future use):
- backtest_runner.py
- backtest_simulator.py
- backtest_data_loader.py
- backtest_report.py

### WebSocket/Price Feeds:
- realtime_price_feed.py
- websocket_price_feed.py

### Flash Crash Components:
- flash_crash_detector.py
- flash_crash_engine.py

### Signature Detection:
- signature_type_detector.py
- clob_clock_fix.py

## Summary

**Total Files Moved**: 60+
- Reports: 40+ files → docs/reports/
- Scripts: 11 files → deployment/
- Tests: 13 files → tests/
- Logs: 4 files → logs/
- Data: 2 files → data/
- Docs: 2 files → docs/

**Files to Archive**: 7 unused implementations → _archive/unused_implementations/

**Active Production Files**: 40+ files in src/ (all currently used or planned for use)
