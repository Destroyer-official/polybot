# Polybot - AI Coding Agent Instructions

## Project Overview
Polybot is a Python-based bot for interacting with Polymarket's CLOB (Central Limit Order Book) trading system. It integrates with the OpenAI API for intelligent decision-making and uses the py-clob-client library for market interactions.

## Core Dependencies
- **py-clob-client**: Polymarket CLOB client for trading operations
- **openai**: GPT-based intelligence for decision-making
- **requests**: HTTP operations for API interactions
- **python-dotenv**: Secure environment configuration (API keys, credentials)

## Essential Architecture Patterns

### Environment Configuration
- Use `.env` file (gitignored) for:
  - OpenAI API key
  - Polymarket credentials
  - Private keys (`.pem` files are gitignored)
- Load via `python-dotenv` before initializing clients
- Never hardcode credentials; always use environment variables

### Expected Module Structure
When creating modules, follow this pattern:
```
polybot/
├── core/          # CLOB client initialization and core market logic
├── agents/        # AI-driven decision making (OpenAI integration)
├── strategies/    # Trading strategies and algorithms
├── utils/         # Helpers (API wrappers, validators)
└── main.py        # Entry point
```

### Key Integration Points
1. **Polymarket CLOB Integration**: Use `py-clob-client` to place orders, query markets, check balances
2. **OpenAI Integration**: Use OpenAI API for analysis/decision-making on trading opportunities
3. **Rate Limiting**: Both APIs have rate limits - implement backoff and queuing
4. **Error Handling**: Network failures are common; use retry logic with exponential backoff

## Development Workflow

### Setup
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configuration
1. Create `.env` file with API credentials
2. Initialize CLOB client with network/environment config
3. Authenticate with Polymarket

### Testing Strategy
- Mock CLOB client responses for unit tests
- Use test networks when available (Polymarket may have testnet)
- Log all trades for audit trails

## Code Patterns & Conventions

### Async Considerations
- Polymarket operations may be blocking; consider `asyncio` or threading for concurrent market monitoring
- OpenAI API calls should have timeout handling

### Type Hints
- Use Python type hints for clarity (requests are welcome for any new modules)
- Important types: `Dict` for market data, `List` for orders, `float` for prices/amounts

### Error Handling
- Wrap CLOB operations in try-catch blocks
- Log failures before retrying
- Preserve order state for recovery/debugging

## Critical Files to Reference
- `requirements.txt`: Define all dependencies here with versions for reproducibility
- `.env`: Never commit; create template as `.env.example` if helpful
- Main entry point: Will be created as `main.py` or `polybot/__main__.py`

## Common Tasks

### Adding a New Trading Strategy
1. Create module in `strategies/`
2. Implement risk checks and order validation
3. Integrate with CLOB client
4. Add comprehensive logging

### Integrating New OpenAI Feature
1. Create function in `agents/` module
2. Handle API errors and rate limits
3. Cache responses when appropriate to reduce costs
4. Log prompts and responses for debugging

### Debugging Market Issues
- Enable verbose logging in CLOB client
- Check `.env` configuration
- Verify network connectivity to Polymarket
- Review recent logs for failed orders
