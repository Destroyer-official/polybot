# Requirements Document

## Introduction

This specification defines the requirements for implementing dynamic position sizing and smart fund management for the Polymarket arbitrage bot. The current implementation uses hardcoded position sizes and checks incorrect balance sources for fund management. This feature will introduce intelligent, adaptive position sizing based on multiple factors including available balance, opportunity quality, and market conditions, while fixing the fund management logic to check the correct wallet balance.

## Glossary

- **Position_Sizer**: Component responsible for calculating optimal trade sizes based on available balance, opportunity quality, and risk parameters
- **Fund_Manager**: Component responsible for monitoring wallet balances and managing deposits between private wallet and Polymarket
- **Opportunity_Scorer**: Component that evaluates arbitrage opportunities based on profit potential, market conditions, and risk factors
- **Private_Wallet**: The user's Ethereum wallet containing USDC that can be deposited to Polymarket
- **Polymarket_Balance**: The user's available balance on the Polymarket platform for trading
- **Available_Balance**: Total funds available for trading, calculated as Private_Wallet + Polymarket_Balance - Pending_Trades
- **Kelly_Criterion**: Mathematical formula for optimal bet sizing that maximizes long-term growth
- **Opportunity_Score**: Numerical rating (0-1) representing the quality of an arbitrage opportunity based on multiple factors
- **Arbitrage_Engine**: Main trading component that identifies and executes arbitrage opportunities

## Requirements

### Requirement 1: Dynamic Position Sizing

**User Story:** As a bot operator, I want position sizes to be calculated dynamically based on available balance and opportunity quality, so that the bot maximizes returns while managing risk appropriately.

#### Acceptance Criteria

1. WHEN calculating position size, THE Position_Sizer SHALL consider Available_Balance, Opportunity_Score, and Kelly_Criterion
2. WHEN Available_Balance is insufficient for minimum trade, THE Position_Sizer SHALL return zero position size
3. WHEN an opportunity has high Opportunity_Score, THE Position_Sizer SHALL allocate larger position size within risk limits
4. WHEN an opportunity has low Opportunity_Score, THE Position_Sizer SHALL allocate smaller position size
5. THE Position_Sizer SHALL never allocate more than 20% of Available_Balance to a single trade
6. THE Position_Sizer SHALL never allocate less than $0.10 for any trade (minimum viable position)

### Requirement 2: Opportunity Scoring System

**User Story:** As a bot operator, I want arbitrage opportunities to be scored based on multiple quality factors, so that the bot prioritizes the best opportunities and sizes positions accordingly.

#### Acceptance Criteria

1. WHEN scoring an opportunity, THE Opportunity_Scorer SHALL evaluate profit percentage, market age, liquidity, and volatility
2. WHEN a market is newer (age < 24 hours), THE Opportunity_Scorer SHALL assign higher score weight
3. WHEN a market has higher volatility, THE Opportunity_Scorer SHALL assign higher score weight
4. WHEN a market has lower liquidity, THE Opportunity_Scorer SHALL assign higher score weight
5. WHEN profit percentage is higher, THE Opportunity_Scorer SHALL assign higher score weight
6. THE Opportunity_Scorer SHALL return a normalized score between 0 and 1
7. THE Opportunity_Scorer SHALL weight factors as: profit_pct (40%), volatility (25%), market_age (20%), liquidity (15%)

### Requirement 3: Real-Time Balance Checking

**User Story:** As a bot operator, I want the bot to check actual available balance before each trade, so that trades never fail due to insufficient funds.

#### Acceptance Criteria

1. WHEN preparing to execute a trade, THE Arbitrage_Engine SHALL query both Private_Wallet and Polymarket_Balance
2. WHEN calculating Available_Balance, THE Arbitrage_Engine SHALL subtract pending trade amounts
3. WHEN Available_Balance is less than required position size, THE Arbitrage_Engine SHALL skip the trade
4. WHEN Available_Balance check fails due to network error, THE Arbitrage_Engine SHALL retry up to 3 times with exponential backoff
5. THE Arbitrage_Engine SHALL cache balance data for maximum 30 seconds to reduce API calls

### Requirement 4: Smart Fund Management

**User Story:** As a bot operator, I want the bot to intelligently manage deposits from my private wallet to Polymarket, so that funds are available when needed without unnecessary deposits.

#### Acceptance Criteria

1. WHEN Polymarket_Balance falls below $1, THE Fund_Manager SHALL check Private_Wallet balance
2. WHEN Private_Wallet balance is greater than $1 AND less than $50, THE Fund_Manager SHALL deposit available funds to Polymarket
3. WHEN Private_Wallet balance is greater than $50, THE Fund_Manager SHALL deposit amount based on recent trading activity and market conditions
4. WHEN calculating deposit amount, THE Fund_Manager SHALL consider average trade size from last 24 hours
5. WHEN no trading activity exists, THE Fund_Manager SHALL deposit minimum of $10 or 50% of Private_Wallet balance, whichever is smaller
6. THE Fund_Manager SHALL never deposit more than 80% of Private_Wallet balance in a single transaction
7. WHEN deposit transaction fails, THE Fund_Manager SHALL log error and retry after 5 minutes

### Requirement 5: Kelly Criterion Integration

**User Story:** As a bot operator, I want position sizing to incorporate Kelly Criterion for optimal long-term growth, so that the bot maximizes returns while managing drawdown risk.

#### Acceptance Criteria

1. WHEN calculating Kelly position size, THE Position_Sizer SHALL use win probability derived from historical arbitrage success rate
2. WHEN calculating Kelly position size, THE Position_Sizer SHALL use profit-to-loss ratio from opportunity profit percentage
3. WHEN Kelly Criterion suggests position larger than 20% of Available_Balance, THE Position_Sizer SHALL cap at 20%
4. WHEN Kelly Criterion suggests position smaller than minimum ($0.10), THE Position_Sizer SHALL use minimum or skip trade
5. THE Position_Sizer SHALL apply fractional Kelly (50% of full Kelly) to reduce variance
6. WHEN historical data is insufficient (< 10 trades), THE Position_Sizer SHALL use conservative default win probability of 0.85

### Requirement 6: Configuration and Fallback Parameters

**User Story:** As a bot operator, I want configurable parameters with sensible defaults, so that I can tune the bot's behavior without code changes.

#### Acceptance Criteria

1. THE Position_Sizer SHALL read maximum position percentage from configuration (default: 20%)
2. THE Position_Sizer SHALL read minimum position size from configuration (default: $0.10)
3. THE Position_Sizer SHALL read fractional Kelly multiplier from configuration (default: 0.5)
4. THE Fund_Manager SHALL read minimum Polymarket balance threshold from configuration (default: $1)
5. THE Fund_Manager SHALL read private wallet threshold from configuration (default: $50)
6. THE Fund_Manager SHALL read maximum deposit percentage from configuration (default: 80%)
7. WHEN configuration values are invalid or missing, THE system SHALL use hardcoded defaults and log warning

### Requirement 7: Balance Monitoring and Logging

**User Story:** As a bot operator, I want detailed logging of balance checks and position sizing decisions, so that I can monitor bot behavior and debug issues.

#### Acceptance Criteria

1. WHEN checking balances, THE system SHALL log Private_Wallet, Polymarket_Balance, and Available_Balance
2. WHEN calculating position size, THE Position_Sizer SHALL log Opportunity_Score, Kelly_Size, and final position size
3. WHEN skipping a trade due to insufficient balance, THE Arbitrage_Engine SHALL log reason and required amount
4. WHEN depositing funds, THE Fund_Manager SHALL log deposit amount, source balance, and destination balance
5. THE system SHALL log all balance-related errors with full context for debugging
6. THE system SHALL include timestamps in all log entries

### Requirement 8: Error Handling and Recovery

**User Story:** As a bot operator, I want the bot to handle balance check failures gracefully, so that temporary network issues don't stop trading.

#### Acceptance Criteria

1. WHEN balance check fails due to network error, THE system SHALL retry with exponential backoff
2. WHEN balance check fails after all retries, THE system SHALL use cached balance if less than 5 minutes old
3. WHEN no cached balance is available, THE system SHALL skip the current trade and continue monitoring
4. WHEN deposit transaction fails, THE Fund_Manager SHALL not retry immediately to avoid duplicate deposits
5. IF deposit fails due to insufficient gas, THE Fund_Manager SHALL log error and wait for manual intervention
6. THE system SHALL continue operating even when balance checks fail, using conservative fallback behavior

