# Implementation Tasks: Dynamic Position Sizing and Smart Fund Management

## Overview
This task list implements dynamic position sizing and smart fund management for the Polymarket arbitrage bot. The implementation replaces hardcoded position sizes with intelligent, adaptive sizing based on available balance, opportunity quality, and market conditions.

## Task List

### Phase 1: Core Components

- [ ] 1. Implement OpportunityScorer Component
  - [ ] 1.1 Create `src/opportunity_scorer.py` with OpportunityScorer class
  - [ ] 1.2 Implement `score_opportunity()` method with weighted scoring
  - [ ] 1.3 Implement component score calculations (profit, volatility, age, liquidity)
  - [ ] 1.4 Implement `get_score_breakdown()` for logging
  - [ ] 1.5 Add unit tests for opportunity scoring
  - [ ] 1.6 Add property-based tests for scoring invariants

- [ ] 2. Implement BalanceManager Component
  - [ ] 2.1 Create `src/balance_manager.py` with BalanceManager class
  - [ ] 2.2 Implement `get_available_balance()` with caching
  - [ ] 2.3 Implement `get_private_wallet_balance()` with retry logic
  - [ ] 2.4 Implement `get_polymarket_balance()` with retry logic
  - [ ] 2.5 Implement cache invalidation and TTL logic
  - [ ] 2.6 Add unit tests for balance queries and caching
  - [ ] 2.7 Add property-based tests for balance calculations

- [ ] 3. Enhance DynamicPositionSizer
  - [ ] 3.1 Integrate Kelly Criterion calculation
  - [ ] 3.2 Add opportunity score multiplier logic
  - [ ] 3.3 Implement fractional Kelly application
  - [ ] 3.4 Add detailed logging with `get_position_sizing_details()`
  - [ ] 3.5 Update unit tests for enhanced functionality
  - [ ] 3.6 Add property-based tests for position size bounds

### Phase 2: Fund Management

- [ ] 4. Update FundManager for Smart Deposits
  - [ ] 4.1 Modify `check_and_manage_balance()` to check PRIVATE wallet (not Polymarket)
  - [ ] 4.2 Implement deposit logic for $1-$50 private wallet balance
  - [ ] 4.3 Implement deposit logic for $50+ private wallet balance
  - [ ] 4.4 Implement `calculate_deposit_amount()` with trading history consideration
  - [ ] 4.5 Add dynamic deposit amount calculation based on market conditions
  - [ ] 4.6 Update unit tests for new deposit logic
  - [ ] 4.7 Add property-based tests for deposit amount bounds

### Phase 3: Integration

- [ ] 5. Integrate Components into ArbitrageEngine
  - [ ] 5.1 Add OpportunityScorer to InternalArbitrageEngine initialization
  - [ ] 5.2 Add BalanceManager to InternalArbitrageEngine initialization
  - [ ] 5.3 Update `scan_opportunities()` to score opportunities
  - [ ] 5.4 Update `execute()` to use BalanceManager for balance checks
  - [ ] 5.5 Update `execute()` to pass opportunity scores to DynamicPositionSizer
  - [ ] 5.6 Add integration tests for full arbitrage flow

- [ ] 6. Update MainOrchestrator
  - [ ] 6.1 Initialize OpportunityScorer in MainOrchestrator
  - [ ] 6.2 Initialize BalanceManager in MainOrchestrator
  - [ ] 6.3 Pass BalanceManager to FundManager
  - [ ] 6.4 Update fund management calls to use new logic
  - [ ] 6.5 Add logging for balance checks and deposits

### Phase 4: Configuration

- [ ] 7. Add Configuration Support
  - [ ] 7.1 Add position sizing config to `.env` (max_position_pct, min_position_size, fractional_kelly)
  - [ ] 7.2 Add fund management config to `.env` (min_polymarket_balance, private_wallet_threshold, max_deposit_pct)
  - [ ] 7.3 Update config loader to read new parameters
  - [ ] 7.4 Add configuration validation
  - [ ] 7.5 Update documentation with new config parameters

### Phase 5: Testing

- [ ] 8. Comprehensive Testing
  - [ ] 8.1 Write unit tests for OpportunityScorer
  - [ ] 8.2 Write unit tests for BalanceManager
  - [ ] 8.3 Write unit tests for enhanced DynamicPositionSizer
  - [ ] 8.4 Write unit tests for updated FundManager
  - [ ] 8.5 Write property-based tests for all correctness properties (Properties 1-12)
  - [ ] 8.6 Write integration tests for full trading flow
  - [ ] 8.7 Run full test suite and verify 100% pass rate

### Phase 6: Documentation and Deployment

- [ ] 9. Update Documentation
  - [ ] 9.1 Update README with dynamic position sizing explanation
  - [ ] 9.2 Update HOW_TO_RUN.md with new configuration parameters
  - [ ] 9.3 Update ENV_SETUP_GUIDE.md with fund management settings
  - [ ] 9.4 Create DYNAMIC_POSITION_SIZING.md with detailed explanation
  - [ ] 9.5 Update deployment guides with new requirements

- [ ] 10. Deployment and Validation
  - [ ] 10.1 Run dry-run test with dynamic sizing enabled
  - [ ] 10.2 Verify balance checks work correctly
  - [ ] 10.3 Verify deposit logic triggers appropriately
  - [ ] 10.4 Verify position sizes adjust based on balance
  - [ ] 10.5 Monitor logs for correct behavior
  - [ ] 10.6 Create deployment summary document

## Task Dependencies

- Tasks 1, 2, 3 can be done in parallel (Phase 1)
- Task 4 depends on Task 2 (needs BalanceManager)
- Task 5 depends on Tasks 1, 2, 3 (needs all core components)
- Task 6 depends on Task 5 (needs integrated components)
- Task 7 can be done in parallel with other tasks
- Task 8 depends on Tasks 1-6 (needs all implementations)
- Task 9 depends on Task 8 (needs working implementation)
- Task 10 depends on Tasks 8, 9 (needs tests and docs)

## Success Criteria

- All unit tests pass (100%)
- All property-based tests pass (100%)
- All integration tests pass (100%)
- Bot successfully adjusts position sizes based on available balance
- Bot successfully deposits from private wallet when balance is low
- Bot successfully manages funds dynamically based on market conditions
- All configuration parameters work correctly
- Documentation is complete and accurate
- Dry-run test shows correct behavior

## Notes

- This implementation addresses the user's requirement for dynamic fund management
- The bot will check PRIVATE wallet balance (not Polymarket balance) for deposit decisions
- Deposit amounts will be dynamic based on available funds and market conditions
- Position sizes will adjust automatically based on available balance
- The system is optimized for 40-90 trades per day with small position sizes
