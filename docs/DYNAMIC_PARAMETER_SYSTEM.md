# Dynamic Parameter System

## Overview

The `DynamicParameterSystem` is an adaptive position sizing system that uses the Kelly Criterion with intelligent adjustments based on recent trading performance. It's designed for the Polymarket arbitrage bot to optimize position sizes while managing risk.

## Key Features

### 1. Kelly Criterion Position Sizing
- **Formula**: `f = edge / odds`
- Calculates optimal position size to maximize long-term growth
- Accounts for win probability and profit potential

### 2. Fractional Kelly (25-50%)
- Uses 25-50% of full Kelly to reduce variance
- Starts at 37.5% (midpoint)
- Dynamically adjusts based on performance

### 3. Edge Calculation with Transaction Costs
- **Formula**: `edge = (win_prob × profit_pct) - transaction_costs`
- Default transaction costs: 2% (fees + slippage)
- Minimum edge threshold: 2.5%
- Skips trades when edge is too low

### 4. Performance Tracking (Last 20 Trades)
- Tracks win rate, average profit, average edge
- Uses rolling window of 20 trades
- Provides real-time performance metrics

### 5. Dynamic Threshold Adjustments
- **High win rate (≥95%)**: Increase fractional Kelly to 50%
- **Medium win rate (85-95%)**: Keep fractional Kelly at 37.5%
- **Low win rate (<85%)**: Decrease fractional Kelly to 25%

## Requirements Validation

This implementation validates the following requirements:

- **4.1**: Kelly Criterion formula implementation
- **4.2**: Fractional Kelly (25-50%) for risk management
- **4.3**: Edge calculation with transaction costs
- **4.4**: Performance tracking over last 20 trades
- **4.5**: Dynamic adjustment of fractional Kelly
- **4.6**: Position size bounds enforcement
- **4.9**: Minimum edge threshold (2.5%)
- **4.12**: Maximum position limit (20% of bankroll)
- **4.13**: Minimum position size ($0.10) & Cost-benefit analysis (transaction costs < 50% of profit)
- **4.14**: Transaction cost accounting (2%) & Slippage check (< 25% of profit)

## Usage

### Basic Usage

```python
from decimal import Decimal
from src.dynamic_parameter_system import DynamicParameterSystem

# Initialize the system
system = DynamicParameterSystem(
    min_fractional_kelly=0.25,      # 25% minimum
    max_fractional_kelly=0.50,      # 50% maximum
    performance_window=20,          # Track last 20 trades
    transaction_cost_pct=Decimal('0.02'),  # 2% costs
    min_edge_threshold=Decimal('0.025'),   # 2.5% min edge
    max_position_pct=Decimal('0.20'),      # 20% max position
    min_position_size=Decimal('0.10')      # $0.10 minimum
)

# Calculate position size
bankroll = Decimal('100.00')
profit_pct = Decimal('0.05')  # 5% profit
cost = Decimal('10.00')

position_size, details = system.calculate_position_size(
    bankroll=bankroll,
    profit_pct=profit_pct,
    cost=cost
)

print(f"Position Size: ${position_size:.2f}")
print(f"Edge: {details['edge']:.2%}")
print(f"Kelly Fraction: {details['kelly_fraction']:.2%}")
```

### Cost-Benefit Analysis

Before executing a trade, perform cost-benefit analysis to ensure profitability:

```python
# Analyze cost-benefit
expected_profit = Decimal('1.00')
transaction_costs = Decimal('0.30')  # Fees, gas, etc.
estimated_slippage = Decimal('0.10')  # Price impact

should_trade, details = system.analyze_cost_benefit(
    expected_profit=expected_profit,
    transaction_costs=transaction_costs,
    estimated_slippage=estimated_slippage
)

if should_trade:
    print(f"✅ Trade approved")
    print(f"Net Profit: ${details['net_profit']:.4f}")
    print(f"Transaction Costs: {details['transaction_cost_pct']:.1f}%")
    print(f"Slippage: {details['slippage_pct']:.1f}%")
else:
    print(f"❌ Trade rejected: {details['reason']}")
```

The cost-benefit analysis validates:
- **Requirement 4.13**: Transaction costs must be ≤ 50% of expected profit
- **Requirement 4.14**: Estimated slippage must be ≤ 25% of expected profit
- Net profit must be > 0 after all costs

### Recording Trades

```python
# Record a successful trade
system.record_trade(
    position_size=Decimal('10.00'),
    profit=Decimal('0.50'),
    was_successful=True,
    edge=Decimal('0.03'),
    odds=Decimal('0.05')
)

# Get performance metrics
metrics = system.get_performance_metrics()
print(f"Win Rate: {metrics.win_rate:.1%}")
print(f"Avg Profit: ${metrics.avg_profit:.4f}")
```

### Monitoring System State

```python
# Get current state
state = system.get_current_state()
print(f"Current Fractional Kelly: {state['fractional_kelly']:.2%}")
print(f"Win Rate: {state['performance']['win_rate']:.1%}")
print(f"Total Trades: {state['performance']['total_trades']}")
```

## Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_fractional_kelly` | 0.25 | Minimum fractional Kelly (25%) |
| `max_fractional_kelly` | 0.50 | Maximum fractional Kelly (50%) |
| `performance_window` | 20 | Number of trades to track |
| `transaction_cost_pct` | 0.02 | Transaction costs (2%) |
| `min_edge_threshold` | 0.025 | Minimum edge to trade (2.5%) |
| `max_position_pct` | 0.20 | Maximum position (20% of bankroll) |
| `min_position_size` | 0.10 | Minimum position size ($0.10) |

## Position Sizing Logic

### Step 1: Calculate Edge
```
edge = (win_probability × profit_pct) - transaction_costs
```

### Step 2: Check Edge Threshold
```
if edge < min_edge_threshold:
    return 0  # Skip trade
```

### Step 3: Calculate Kelly Fraction
```
kelly_fraction = edge / odds
```

### Step 4: Apply Fractional Kelly
```
adjusted_kelly = kelly_fraction × fractional_kelly
```

### Step 5: Calculate Position Size
```
position_size = bankroll × adjusted_kelly
```

### Step 6: Apply Bounds
```
position_size = min(position_size, bankroll × max_position_pct)
position_size = max(position_size, min_position_size)
position_size = min(position_size, bankroll)
```

## Adaptive Behavior

The system automatically adjusts the fractional Kelly multiplier based on recent performance:

### High Performance (≥95% win rate)
- Increases fractional Kelly to **50%** (maximum)
- Allows larger positions with proven success
- Maximizes returns during winning streaks

### Medium Performance (85-95% win rate)
- Maintains fractional Kelly at **37.5%** (midpoint)
- Balanced approach for normal operations
- Standard risk management

### Low Performance (<85% win rate)
- Decreases fractional Kelly to **25%** (minimum)
- Reduces position sizes to limit losses
- Conservative approach during losing periods

## Example Scenarios

### Scenario 1: Good Arbitrage Opportunity
```
Profit: 5.00%
Transaction Costs: 2.00%
Edge: 2.98%
Kelly Fraction: 59.50%
Fractional Kelly: 37.50%
Position Size: $20.00 (capped at 20% of $100 bankroll)
```

### Scenario 2: Low Profit (Below Threshold)
```
Profit: 2.50%
Transaction Costs: 2.00%
Edge: 0.49%
Result: Trade skipped (edge below 2.5% threshold)
```

### Scenario 3: High Profit (Capped)
```
Profit: 50.00%
Transaction Costs: 2.00%
Edge: 47.75%
Kelly Fraction: 95.50%
Position Size: $20.00 (capped at 20% of bankroll)
```

## Performance Metrics

The system tracks the following metrics:

- **Win Rate**: Percentage of profitable trades
- **Average Profit**: Mean profit per trade
- **Average Edge**: Mean edge across trades
- **Total Trades**: Number of trades recorded
- **Profitable Trades**: Number of winning trades

## Testing

Comprehensive unit tests are provided in `tests/test_dynamic_parameter_system.py`:

```bash
# Run tests
python -m pytest tests/test_dynamic_parameter_system.py -v

# Expected: 20 tests, all passing
```

## Integration Example

See `examples/dynamic_parameter_system_example.py` for a complete demonstration:

```bash
python examples/dynamic_parameter_system_example.py
```

## Best Practices

1. **Start Conservative**: Begin with default parameters
2. **Monitor Performance**: Track win rate and adjust if needed
3. **Respect Bounds**: Never override position size limits
4. **Account for Costs**: Always include transaction costs in edge calculation
5. **Track History**: Record all trades for accurate performance metrics
6. **Review Regularly**: Check system state periodically

## Mathematical Foundation

### Kelly Criterion
The Kelly Criterion is a formula for optimal bet sizing that maximizes long-term growth:

```
f* = (bp - q) / b
```

Where:
- `f*` = optimal fraction of bankroll to bet
- `b` = odds (profit/cost)
- `p` = win probability
- `q` = loss probability (1 - p)

For arbitrage with edge calculation:
```
f* = edge / odds
```

### Fractional Kelly
Full Kelly can be aggressive, so we use fractional Kelly:

```
f_fractional = f* × fractional_multiplier
```

This reduces variance while maintaining most of the growth rate.

## References

- Kelly, J. L. (1956). "A New Interpretation of Information Rate"
- Thorp, E. O. (2006). "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market"
- MacLean, L. C., Thorp, E. O., & Ziemba, W. T. (2011). "The Kelly Capital Growth Investment Criterion"

## License

Part of the Polymarket Arbitrage Bot project.
