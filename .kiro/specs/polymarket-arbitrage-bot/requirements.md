# Requirements Document

## Introduction

This document specifies the requirements for an autonomous 24/7 Polymarket arbitrage trading bot that achieves 99.5%+ win rates through mathematical arbitrage strategies on 15-minute crypto prediction markets (BTC, ETH, SOL, XRP). The system focuses on risk-free arbitrage opportunities rather than predictive trading, ensuring consistent profits through price inefficiencies.

## Glossary

- **Arbitrage_Engine**: The core system component that detects and executes arbitrage opportunities
- **Internal_Arbitrage**: Strategy where YES + NO positions are purchased when combined cost + fees < $1.00
- **Cross_Platform_Arbitrage**: Strategy exploiting price differences between Polymarket and Kalshi
- **Latency_Arbitrage**: Strategy exploiting lag between CEX price movements and Polymarket updates
- **Resolution_Farming**: Strategy buying near-certain positions (97-99¢) just before market close
- **FOK_Order**: Fill-Or-Kill order type that executes completely or not at all, preventing partial fills
- **Proxy_Wallet**: Polymarket's trading balance system where all trades execute
- **CTF_Exchange**: Conditional Token Framework Exchange contract for Polymarket trading
- **Position_Merger**: Component that combines YES and NO positions to redeem $1.00 USDC
- **AI_Safety_Guard**: System that validates market conditions before trade execution
- **Fund_Manager**: Component handling deposits, withdrawals, and balance management
- **Dynamic_Fee_Calculator**: Component implementing Polymarket's 2025 fee structure
- **Legging_Risk**: Risk where one side of arbitrage fills but the other doesn't
- **CEX**: Centralized Exchange (Binance, Coinbase, etc.)
- **CLOB_API**: Central Limit Order Book API for Polymarket market data
- **Kelly_Criterion**: Mathematical formula for optimal position sizing based on bankroll

## Requirements

### Requirement 1: Internal Arbitrage Detection and Execution

**User Story:** As a trader, I want the system to detect and execute internal arbitrage opportunities, so that I can earn guaranteed profits when YES + NO prices plus fees are less than $1.00.

#### Acceptance Criteria

1. WHEN the system scans a market, THE Arbitrage_Engine SHALL calculate the total cost as YES_price + NO_price + YES_fee + NO_fee
2. WHEN the total cost is less than $0.995 (0.5% minimum profit threshold), THE Arbitrage_Engine SHALL identify it as a valid arbitrage opportunity
3. WHEN a valid opportunity is identified, THE Arbitrage_Engine SHALL create FOK_Orders for both YES and NO positions simultaneously
4. WHEN both FOK_Orders are submitted, THE Arbitrage_Engine SHALL verify that both orders fill completely or neither fills
5. WHEN both positions are acquired, THE Position_Merger SHALL call mergePositions() on the Conditional Token contract
6. WHEN positions are merged, THE System SHALL receive exactly $1.00 USDC per position pair
7. THE Dynamic_Fee_Calculator SHALL use the formula: fee = max(0.001, 0.03 * (1.0 - abs(2.0 * price - 1.0)))

### Requirement 2: Dynamic Fee Calculation

**User Story:** As a trader, I want accurate fee calculations using Polymarket's 2025 dynamic fee structure, so that profit calculations reflect actual trading costs.

#### Acceptance Criteria

1. WHEN calculating fees for a position at any price, THE Dynamic_Fee_Calculator SHALL apply the formula: fee = max(0.001, 0.03 * (1.0 - abs(2.0 * price - 1.0)))
2. WHEN the position price is at 50% odds, THE Dynamic_Fee_Calculator SHALL return a fee of approximately 3.0%
3. WHEN the position price approaches 0% or 100% odds, THE Dynamic_Fee_Calculator SHALL return fees approaching 0.1%
4. WHEN calculating arbitrage profit, THE Arbitrage_Engine SHALL subtract both YES and NO fees from the $1.00 redemption value
5. THE Dynamic_Fee_Calculator SHALL cache fee calculations for identical prices to optimize performance

### Requirement 3: Cross-Platform Arbitrage with Kalshi

**User Story:** As a trader, I want to exploit price differences between Polymarket and Kalshi, so that I can profit from cross-platform inefficiencies.

#### Acceptance Criteria

1. WHEN the system starts, THE Cross_Platform_Arbitrage component SHALL establish connections to both Polymarket CLOB_API and Kalshi API
2. WHEN scanning for opportunities, THE System SHALL compare prices for equivalent markets on both platforms
3. WHEN Polymarket YES price + fees < Kalshi NO price - fees (or vice versa), THE System SHALL identify a cross-platform arbitrage opportunity
4. WHEN executing cross-platform arbitrage, THE System SHALL submit FOK_Orders on both platforms simultaneously
5. IF either platform order fails to fill, THEN THE System SHALL cancel the other platform's order immediately
6. THE System SHALL account for withdrawal fees and settlement times when calculating cross-platform profit

### Requirement 4: Latency Arbitrage with CEX Price Monitoring

**User Story:** As a trader, I want to exploit lag between CEX price movements and Polymarket updates, so that I can profit from temporary price inefficiencies.

#### Acceptance Criteria

1. WHEN the system starts, THE Latency_Arbitrage component SHALL establish WebSocket connections to Binance, Coinbase, and Kraken
2. WHEN a CEX price moves more than $100 for BTC (or equivalent for ETH/SOL/XRP), THE System SHALL immediately check corresponding Polymarket markets
3. WHEN Polymarket prices lag CEX prices by more than 1%, THE System SHALL calculate expected market direction
4. WHEN expected profit exceeds 0.5% after fees, THE System SHALL submit FOK_Orders in the profitable direction
5. THE System SHALL execute latency arbitrage orders within 150ms of detecting the CEX price movement
6. THE System SHALL skip latency arbitrage when volatility exceeds 5% in 1 minute to avoid false signals

### Requirement 5: Resolution Farming Strategy

**User Story:** As a trader, I want to buy near-certain positions just before market close, so that I can achieve 99.9%+ win rates with minimal risk.

#### Acceptance Criteria

1. WHEN a market has less than 2 minutes until close, THE Resolution_Farming component SHALL evaluate if the outcome is certain
2. WHEN a position is priced at 97-99¢ and the outcome is verifiable from CEX data, THE System SHALL identify it as a resolution farming opportunity
3. WHEN executing resolution farming, THE System SHALL only buy positions where the outcome matches current CEX price direction
4. THE System SHALL skip resolution farming opportunities when the market has ambiguous resolution criteria
5. THE System SHALL limit resolution farming position size to 2% of total bankroll per trade

### Requirement 6: Risk-Free Order Execution

**User Story:** As a trader, I want all arbitrage orders to execute atomically, so that I never hold unhedged positions that could result in losses.

#### Acceptance Criteria

1. WHEN submitting arbitrage orders, THE System SHALL use FOK_Order type exclusively
2. WHEN a FOK_Order is submitted, THE System SHALL set a maximum slippage tolerance of 0.1%
3. IF any order in an arbitrage pair fails to fill completely, THEN THE System SHALL not execute the trade
4. WHEN both orders fill, THE System SHALL verify the fill prices match expected prices within tolerance
5. THE System SHALL maintain a pending transaction limit of 5 maximum to prevent nonce conflicts
6. WHEN gas prices exceed 800 gwei, THE System SHALL halt all trading until gas prices normalize

### Requirement 7: AI Safety Guardrails

**User Story:** As a trader, I want AI-powered safety checks to prevent trading during abnormal market conditions, so that the system avoids unpredictable scenarios.

#### Acceptance Criteria

1. WHEN evaluating a trade opportunity, THE AI_Safety_Guard SHALL query the NVIDIA AI API with market context
2. WHEN the AI_Safety_Guard receives a response, THE System SHALL parse multilingual YES/NO responses (yes, no, да, нет, oui, non, sí, no)
3. IF the AI_Safety_Guard returns NO or fails to respond within 2 seconds, THEN THE System SHALL skip the trade
4. WHEN the AI_Safety_Guard is unavailable, THE System SHALL use fallback heuristics: balance > $10, gas < 800 gwei, pending_tx < 5
5. WHEN BTC/ETH/SOL/XRP moves more than 5% in 1 minute, THE AI_Safety_Guard SHALL halt trading for 5 minutes
6. THE AI_Safety_Guard SHALL skip markets with ambiguous resolution criteria based on keyword detection (e.g., "approximately", "around", "roughly")

### Requirement 8: Automated Fund Management

**User Story:** As a trader, I want automated deposit and withdrawal management, so that the system maintains optimal trading balance without manual intervention.

#### Acceptance Criteria

1. WHEN the Proxy_Wallet balance falls below $50, THE Fund_Manager SHALL initiate an auto-deposit from the EOA wallet
2. WHEN initiating auto-deposit, THE Fund_Manager SHALL approve USDC to the CTF_Exchange contract and deposit the configured amount
3. WHEN the Proxy_Wallet balance exceeds $500 (configurable WITHDRAW_LIMIT), THE Fund_Manager SHALL initiate an auto-withdrawal
4. WHEN withdrawing, THE Fund_Manager SHALL transfer USDC from Proxy_Wallet to EOA wallet
5. THE Fund_Manager SHALL support multi-chain deposits from Ethereum, Polygon, Arbitrum, and Optimism
6. WHEN depositing from non-Polygon chains, THE Fund_Manager SHALL use 1inch API to swap any token to USDC and bridge to Polygon
7. THE Fund_Manager SHALL log all deposit and withdrawal transactions with timestamps and amounts

### Requirement 9: 24/7 Autonomous Operation

**User Story:** As a trader, I want the system to run continuously without manual intervention, so that it captures arbitrage opportunities around the clock.

#### Acceptance Criteria

1. WHEN the system is deployed, THE System SHALL run as a systemd service with auto-restart on failure
2. WHEN a network error occurs, THE System SHALL retry with exponential backoff (1s, 2s, 4s, 8s, max 60s)
3. WHEN the system restarts, THE System SHALL resume operation from the last known state without data loss
4. THE System SHALL log all errors, trades, and balance changes to AWS CloudWatch
5. WHEN critical errors occur (balance < $10, repeated failures), THE System SHALL send SNS alerts to configured endpoints
6. THE System SHALL perform a heartbeat check every 60 seconds verifying: balance > $10, gas < 800 gwei, pending_tx < 5, API connectivity
7. WHEN the heartbeat check fails 3 consecutive times, THE System SHALL halt trading and send an alert

### Requirement 10: Performance Optimization

**User Story:** As a trader, I want sub-150ms execution latency, so that the system can capture time-sensitive arbitrage opportunities before they disappear.

#### Acceptance Criteria

1. WHEN scanning markets, THE Arbitrage_Engine SHALL use the Rust core module for fee calculations and opportunity detection
2. WHEN processing market data, THE System SHALL scan all active markets in parallel using async/await patterns
3. WHEN an opportunity is detected, THE System SHALL submit orders within 150ms of detection
4. THE System SHALL maintain WebSocket connections to Polymarket CLOB for real-time market updates
5. THE System SHALL cache market metadata (token IDs, contract addresses) to avoid repeated API calls
6. THE System SHALL use connection pooling for HTTP requests with a pool size of 10

### Requirement 11: Position Sizing with Kelly Criterion

**User Story:** As a trader, I want dynamic position sizing based on bankroll, so that the system maximizes long-term growth while limiting risk.

#### Acceptance Criteria

1. WHEN calculating position size, THE System SHALL apply the Kelly_Criterion formula: f = (bp - q) / b, where b = odds, p = win probability, q = 1 - p
2. WHEN the Kelly_Criterion suggests a position size > 5% of bankroll, THE System SHALL cap it at 5%
3. WHEN the bankroll is below $100, THE System SHALL use fixed position sizes of $0.10 to $1.00
4. WHEN the bankroll is above $100, THE System SHALL scale position sizes proportionally up to $5.00 maximum
5. THE System SHALL recalculate bankroll after every 10 trades to adjust position sizing

### Requirement 12: Backtesting Framework

**User Story:** As a developer, I want to backtest strategies against historical data, so that I can validate 99.5%+ win rates before live trading.

#### Acceptance Criteria

1. WHEN running in backtest mode, THE System SHALL load historical market data from CSV or database
2. WHEN processing historical data, THE System SHALL simulate order execution with realistic fill rates and slippage
3. WHEN backtesting completes, THE System SHALL generate a report with: total trades, win rate, average profit, maximum drawdown, Sharpe ratio
4. THE Backtesting_Framework SHALL support DRY_RUN mode that uses live market data but doesn't submit real orders
5. WHEN DRY_RUN mode is enabled, THE System SHALL log all simulated trades with expected profits and actual market outcomes

### Requirement 13: Monitoring and Observability

**User Story:** As an operator, I want real-time monitoring and alerts, so that I can track system performance and respond to issues quickly.

#### Acceptance Criteria

1. WHEN the system is running, THE System SHALL expose Prometheus metrics on port 9090 including: trades_total, trades_successful, trades_failed, profit_usd, balance_usd, latency_ms
2. WHEN metrics are exposed, THE System SHALL update them in real-time after each trade
3. THE System SHALL integrate with Grafana for dashboard visualization of key metrics
4. WHEN deploying to AWS, THE System SHALL send all logs to CloudWatch with structured JSON format
5. THE System SHALL send SNS alerts for: balance < $10, win_rate < 95% over last 100 trades, system downtime > 5 minutes, gas_price > 800 gwei for > 10 minutes

### Requirement 14: Security and Key Management

**User Story:** As an operator, I want secure private key storage, so that funds are protected from unauthorized access.

#### Acceptance Criteria

1. WHEN deploying to AWS, THE System SHALL retrieve private keys from AWS Secrets Manager, not environment variables
2. WHEN accessing Secrets Manager, THE System SHALL use IAM roles with least-privilege permissions
3. THE System SHALL never log private keys or mnemonic phrases
4. WHEN the system starts, THE System SHALL verify the private key corresponds to the expected wallet address
5. THE System SHALL use separate wallets for trading (hot wallet) and profit storage (cold wallet)

### Requirement 15: Deployment Automation

**User Story:** As an operator, I want automated deployment to AWS, so that I can launch the system quickly and consistently.

#### Acceptance Criteria

1. THE System SHALL provide Terraform or CloudFormation templates for AWS infrastructure provisioning
2. WHEN deploying, THE Deployment_Automation SHALL create: EC2 instance (t3.micro or c7i.large), security groups, IAM roles, CloudWatch log groups, SNS topics
3. THE Deployment_Automation SHALL install dependencies: Python 3.11+, Rust toolchain, systemd service configuration
4. THE Deployment_Automation SHALL configure the systemd service to start on boot and restart on failure
5. WHEN deployment completes, THE System SHALL perform a health check and report deployment status

### Requirement 16: Error Recovery and Resilience

**User Story:** As a trader, I want the system to recover gracefully from errors, so that temporary issues don't cause extended downtime.

#### Acceptance Criteria

1. WHEN a network request fails, THE System SHALL retry with exponential backoff up to 5 attempts
2. WHEN the RPC endpoint is unavailable, THE System SHALL failover to backup RPC endpoints automatically
3. WHEN a transaction fails due to insufficient gas, THE System SHALL increase gas price by 10% and retry
4. WHEN a transaction is pending for more than 60 seconds, THE System SHALL check if it was mined and resubmit if necessary
5. WHEN the system encounters an unrecoverable error, THE System SHALL log the full stack trace, send an alert, and attempt to restart
6. THE System SHALL maintain a circuit breaker that halts trading after 10 consecutive failed trades and requires manual reset

### Requirement 17: Market Data Parsing and Validation

**User Story:** As a trader, I want accurate market data parsing, so that the system makes decisions based on correct information.

#### Acceptance Criteria

1. WHEN fetching markets from CLOB_API, THE System SHALL parse JSON responses into structured Market objects
2. WHEN parsing market data, THE System SHALL validate required fields: market_id, question, outcomes, prices, volume, end_time
3. IF any required field is missing or invalid, THEN THE System SHALL skip that market and log a warning
4. THE System SHALL filter markets to only 15-minute crypto markets (BTC, ETH, SOL, XRP) based on question text and duration
5. THE System SHALL parse price data as Decimal types to avoid floating-point precision errors
6. WHEN market end_time is in the past, THE System SHALL exclude it from arbitrage scanning

### Requirement 18: Transaction Management and Nonce Handling

**User Story:** As a trader, I want reliable transaction submission, so that orders execute without nonce conflicts or stuck transactions.

#### Acceptance Criteria

1. WHEN submitting a transaction, THE System SHALL fetch the current nonce from the blockchain
2. WHEN multiple transactions are pending, THE System SHALL track pending nonces to avoid conflicts
3. IF a transaction is stuck (pending > 60 seconds), THEN THE System SHALL resubmit with 10% higher gas price and same nonce
4. THE System SHALL limit pending transactions to 5 maximum to prevent nonce queue buildup
5. WHEN a transaction is confirmed, THE System SHALL update the nonce tracker and remove it from pending queue

### Requirement 19: Profit Tracking and Reporting

**User Story:** As a trader, I want detailed profit tracking, so that I can analyze system performance over time.

#### Acceptance Criteria

1. WHEN a trade completes, THE System SHALL record: timestamp, market_id, strategy_type, position_size, entry_cost, exit_value, profit_usd, profit_percentage, gas_cost
2. THE System SHALL maintain a running total of: total_trades, successful_trades, failed_trades, total_profit_usd, total_gas_cost_usd
3. WHEN generating reports, THE System SHALL calculate: win_rate, average_profit_per_trade, profit_factor, maximum_drawdown, Sharpe_ratio
4. THE System SHALL store trade history in a SQLite database for persistence across restarts
5. THE System SHALL provide a CLI command to generate daily/weekly/monthly profit reports

### Requirement 20: Configuration Management

**User Story:** As an operator, I want flexible configuration, so that I can adjust system parameters without code changes.

#### Acceptance Criteria

1. THE System SHALL load configuration from environment variables and a config.yaml file
2. THE Configuration SHALL support parameters: PRIVATE_KEY, RPC_URLS, STAKE_AMOUNT, MIN_PROFIT_THRESHOLD, WITHDRAW_LIMIT, MAX_POSITION_SIZE, GAS_LIMIT, DRY_RUN
3. WHEN configuration is invalid (e.g., negative stake amount), THE System SHALL fail to start and log a clear error message
4. THE System SHALL validate configuration on startup and log all active settings
5. WHEN DRY_RUN is enabled, THE System SHALL log "DRY RUN MODE" prominently and skip all real transactions

### Requirement 21: Comprehensive Real-Time Monitoring and Debug Output

**User Story:** As an operator, I want detailed real-time monitoring with verbose debug logs, so that I can verify the system is working correctly and troubleshoot issues immediately.

#### Acceptance Criteria

1. WHEN the system is running, THE System SHALL display a continuously updating console dashboard showing: system status, balances, portfolio performance, current scan details, gas prices, recent activity, fund management status, safety checks, and errors
2. THE Dashboard SHALL update in real-time showing: EOA wallet balance, Proxy wallet balance, total assets, current gas price, pending transaction count, RPC endpoint status, and block number
3. THE Dashboard SHALL display portfolio metrics including: total trades, win rate, successful trades, failed trades, total profit, average profit per trade, total gas cost, net profit, profit factor, Sharpe ratio, and maximum drawdown
4. WHEN scanning for opportunities, THE System SHALL display: number of markets scanned, opportunities found, scan latency, and detailed information for each opportunity including prices, fees, profit, AI safety status, gas price, and volatility
5. THE Dashboard SHALL show the last 5 trades with: timestamp, market ID, strategy type, profit amount, gas cost, net profit, and success/failure status with reasons
6. THE System SHALL log verbose debug output for every operation including: market scanning, fee calculations, AI safety checks, order creation, transaction submission, position merging, and balance updates
7. WHEN in debug mode, THE System SHALL log: exact timestamps (milliseconds), operation names, input parameters, calculated values, API response times, transaction hashes, and success/failure indicators
8. THE System SHALL display fund management status including: auto-deposit enabled/disabled, trigger thresholds, last deposit/withdrawal time and amount, and countdown to next balance check
9. THE System SHALL show safety check status including: AI Safety Guard status, API response times, volatility levels for all assets, number of filtered ambiguous markets, and recent errors with auto-recovery status
10. THE Dashboard SHALL display "Bot Running. Waiting for Arbs..." message with full context showing what the system is actively doing, not just idle waiting
11. THE System SHALL provide interactive controls: Ctrl+C to stop, 'h' for help, 'd' to toggle debug verbosity, 's' for statistics summary
12. WHEN errors occur, THE System SHALL log: full error message, stack trace, context data, recovery action taken, and whether alert was sent
13. THE System SHALL maintain error counters for the last hour showing: network errors, API timeouts, failed trades, and alerts sent
14. THE Heartbeat log SHALL include: timestamp, overall health status, detailed balance breakdown, network status (gas, pending TXs, RPC latency, block number), performance metrics, safety status, and any detected issues
15. THE System SHALL use color coding in console output: green for success, yellow for warnings, red for errors, blue for info, to improve readability
