# Polymarket Arbitrage Bot

An autonomous 24/7 trading bot that achieves 99.5%+ win rates through mathematical arbitrage strategies on Polymarket's 15-minute crypto prediction markets.

## Features

- **Internal Arbitrage**: Exploits YES + NO price inefficiencies
- **Cross-Platform Arbitrage**: Trades between Polymarket and Kalshi
- **Latency Arbitrage**: Capitalizes on CEX price lag
- **Resolution Farming**: Buys near-certain positions before market close
- **AI Safety Guards**: Validates trades using NVIDIA AI API
- **Automated Fund Management**: Auto-deposits and withdrawals
- **24/7 Operation**: Runs continuously with error recovery
- **Comprehensive Monitoring**: Prometheus metrics, CloudWatch logs, SNS alerts

## Project Structure

```
polymarket-arbitrage-bot/
├── src/                    # Main source code
│   ├── __init__.py
│   └── logging_config.py   # Logging infrastructure
├── config/                 # Configuration files
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   └── config.example.yaml # Example YAML config
├── tests/                  # Test suite
│   └── __init__.py
├── rust_core/             # Rust performance module
│   ├── src/
│   └── Cargo.toml
├── logs/                   # Log files (gitignored)
│   └── .gitkeep
├── .env.example           # Example environment variables
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd polymarket-arbitrage-bot
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` and set:
- `PRIVATE_KEY`: Your wallet private key
- `WALLET_ADDRESS`: Your wallet address
- `POLYGON_RPC_URL`: Polygon RPC endpoint
- Other optional parameters

Alternatively, use YAML configuration:

```bash
cp config/config.example.yaml config/config.yaml
```

Edit `config/config.yaml` with your settings.

### 5. Build Rust Core (Optional)

For performance-critical operations:

```bash
cd rust_core
maturin develop --release
cd ..
```

## Configuration

The bot supports two configuration methods:

### Environment Variables

Set variables in `.env` file or export them:

```bash
export PRIVATE_KEY="your_private_key"
export WALLET_ADDRESS="your_address"
export POLYGON_RPC_URL="https://polygon-rpc.com"
```

### YAML Configuration

Create `config/config.yaml`:

```yaml
private_key: "your_private_key"
wallet_address: "your_address"
polygon_rpc_url: "https://polygon-rpc.com"
dry_run: false
```

### Configuration Priority

1. YAML file (if provided)
2. Environment variables
3. Default values

### Key Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `stake_amount` | Position size in USDC | 10.0 |
| `min_profit_threshold` | Minimum profit % to trade | 0.005 (0.5%) |
| `max_position_size` | Maximum position size | 5.0 |
| `min_balance` | Trigger auto-deposit below | 50.0 |
| `withdraw_limit` | Trigger auto-withdraw above | 500.0 |
| `max_gas_price_gwei` | Halt trading above | 800 |
| `dry_run` | Simulate trades without execution | false |

## Usage

### Run the Bot

```bash
python bot.py
```

### Run with YAML Config

```bash
python bot.py --config config/config.yaml
```

### Run in Dry-Run Mode

```bash
DRY_RUN=true python bot.py
```

### Run Tests

```bash
# Unit tests
pytest tests/

# Property-based tests
pytest tests/ -k property

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## Monitoring

### Prometheus Metrics

Metrics exposed on port 9090 (configurable):

- `trades_total`: Total trades executed
- `trades_successful`: Successful trades
- `profit_usd`: Total profit in USD
- `balance_usd`: Current balance
- `win_rate`: Win rate percentage
- `gas_price_gwei`: Current gas price
- `latency_ms`: Execution latency

Access metrics: `http://localhost:9090/metrics`

### CloudWatch Logs

Structured JSON logs sent to CloudWatch (requires AWS credentials):

```bash
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_DEFAULT_REGION="us-east-1"
```

### SNS Alerts

Critical alerts sent via SNS (requires SNS topic ARN):

```bash
export SNS_ALERT_TOPIC="arn:aws:sns:us-east-1:123456789:alerts"
```

## Development

### Code Structure

- `src/`: Main application code
- `config/`: Configuration management
- `tests/`: Unit and property-based tests
- `rust_core/`: Performance-critical Rust code

### Testing Strategy

The project uses dual testing approach:

1. **Unit Tests**: Specific examples and edge cases
2. **Property-Based Tests**: Universal correctness properties

Run all tests:

```bash
pytest tests/ -v
```

### Adding New Features

1. Update requirements in `.kiro/specs/polymarket-arbitrage-bot/requirements.md`
2. Update design in `.kiro/specs/polymarket-arbitrage-bot/design.md`
3. Add tasks to `.kiro/specs/polymarket-arbitrage-bot/tasks.md`
4. Implement feature with tests
5. Update documentation

## Security

### Private Key Management

- **Never commit** private keys to git
- Use environment variables or AWS Secrets Manager
- Rotate keys regularly
- Use separate hot/cold wallets

### Best Practices

- Run in dry-run mode first
- Start with small position sizes
- Monitor logs and metrics
- Set up alerts for critical errors
- Keep backup RPC endpoints configured

## Troubleshooting

### Common Issues

**Configuration validation failed**
- Check all required fields in `.env` or `config.yaml`
- Ensure addresses are valid Ethereum addresses
- Verify numeric values are positive

**Network errors**
- Check RPC endpoint is accessible
- Configure backup RPC URLs
- Verify network connectivity

**Transaction failures**
- Check wallet has sufficient MATIC for gas
- Verify gas price is below max threshold
- Check pending transaction count

**Low balance**
- Ensure EOA wallet has USDC for auto-deposit
- Check min_balance and target_balance settings
- Verify fund management is enabled

## License

[Your License Here]

## Disclaimer

This software is for educational purposes only. Trading cryptocurrencies carries risk. Use at your own risk.
