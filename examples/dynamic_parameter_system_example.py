"""
Example usage of DynamicParameterSystem for adaptive position sizing.

This demonstrates:
1. Initializing the system
2. Calculating position sizes with Kelly Criterion
3. Recording trade results
4. Monitoring performance and adaptive adjustments
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from decimal import Decimal
from src.dynamic_parameter_system import DynamicParameterSystem


def main():
    """Demonstrate DynamicParameterSystem usage."""
    
    # Initialize the system
    print("=" * 60)
    print("Dynamic Parameter System Example")
    print("=" * 60)
    
    system = DynamicParameterSystem(
        min_fractional_kelly=0.25,
        max_fractional_kelly=0.50,
        performance_window=20,
        transaction_cost_pct=Decimal('0.02'),  # 2% fees + slippage
        min_edge_threshold=Decimal('0.025'),   # 2.5% minimum edge
        max_position_pct=Decimal('0.20'),      # 20% max position
        min_position_size=Decimal('0.10')      # $0.10 minimum
    )
    
    print(f"\nInitial Configuration:")
    print(f"  Fractional Kelly: {system.current_fractional_kelly:.2%}")
    print(f"  Transaction Costs: {system.transaction_cost_pct:.2%}")
    print(f"  Min Edge Threshold: {system.min_edge_threshold:.2%}")
    print(f"  Max Position: {system.max_position_pct:.2%} of bankroll")
    
    # Simulate trading with different scenarios
    bankroll = Decimal('100.00')
    
    print(f"\n{'='*60}")
    print(f"Scenario 1: Good Arbitrage Opportunity")
    print(f"{'='*60}")
    
    profit_pct = Decimal('0.05')  # 5% profit
    cost = Decimal('10.00')
    
    # Calculate edge
    edge = system.calculate_edge(profit_pct)
    print(f"\nProfit: {profit_pct:.2%}")
    print(f"Edge (after costs): {edge:.2%}")
    
    # Calculate position size
    position_size, details = system.calculate_position_size(
        bankroll=bankroll,
        profit_pct=profit_pct,
        cost=cost
    )
    
    print(f"\nPosition Sizing:")
    print(f"  Bankroll: ${bankroll:.2f}")
    print(f"  Kelly Fraction: {details['kelly_fraction']:.2%}")
    print(f"  Fractional Kelly: {details['fractional_kelly']:.2%}")
    print(f"  Adjusted Kelly: {details['adjusted_kelly']:.2%}")
    print(f"  Position Size: ${position_size:.2f}")
    print(f"  Was Capped: {details['was_capped']}")
    
    # Record successful trade
    system.record_trade(
        position_size=position_size,
        profit=position_size * profit_pct,
        was_successful=True,
        edge=edge,
        odds=profit_pct
    )
    
    print(f"\n{'='*60}")
    print(f"Scenario 2: Low Profit Opportunity (Below Threshold)")
    print(f"{'='*60}")
    
    low_profit_pct = Decimal('0.025')  # 2.5% profit
    edge_low = system.calculate_edge(low_profit_pct)
    
    print(f"\nProfit: {low_profit_pct:.2%}")
    print(f"Edge (after costs): {edge_low:.2%}")
    
    position_size_low, details_low = system.calculate_position_size(
        bankroll=bankroll,
        profit_pct=low_profit_pct,
        cost=cost
    )
    
    print(f"\nPosition Size: ${position_size_low:.2f}")
    if position_size_low == Decimal('0'):
        print(f"Trade Skipped: {details_low['reason']}")
    
    print(f"\n{'='*60}")
    print(f"Scenario 3: High Profit Opportunity (Capped)")
    print(f"{'='*60}")
    
    high_profit_pct = Decimal('0.50')  # 50% profit
    edge_high = system.calculate_edge(high_profit_pct)
    
    print(f"\nProfit: {high_profit_pct:.2%}")
    print(f"Edge (after costs): {edge_high:.2%}")
    
    position_size_high, details_high = system.calculate_position_size(
        bankroll=bankroll,
        profit_pct=high_profit_pct,
        cost=cost
    )
    
    print(f"\nPosition Sizing:")
    print(f"  Kelly Fraction: {details_high['kelly_fraction']:.2%}")
    print(f"  Position Size: ${position_size_high:.2f}")
    print(f"  Max Position: ${details_high['max_position']:.2f}")
    print(f"  Was Capped: {details_high['was_capped']}")
    
    # Simulate 20 trades to show adaptive behavior
    print(f"\n{'='*60}")
    print(f"Scenario 4: Adaptive Behavior (20 Trades)")
    print(f"{'='*60}")
    
    print("\nSimulating 20 trades with 95% win rate...")
    
    for i in range(20):
        # 95% win rate
        is_win = i < 19
        
        position_size, _ = system.calculate_position_size(
            bankroll=bankroll,
            profit_pct=Decimal('0.05'),
            cost=Decimal('10.00')
        )
        
        if position_size > Decimal('0'):
            profit = position_size * Decimal('0.05') if is_win else -position_size * Decimal('0.02')
            system.record_trade(
                position_size=position_size,
                profit=profit,
                was_successful=is_win,
                edge=Decimal('0.03'),
                odds=Decimal('0.05')
            )
    
    # Show performance metrics
    metrics = system.get_performance_metrics()
    state = system.get_current_state()
    
    print(f"\nPerformance Metrics:")
    print(f"  Total Trades: {metrics.total_trades}")
    print(f"  Profitable Trades: {metrics.profitable_trades}")
    print(f"  Win Rate: {metrics.win_rate:.1%}")
    print(f"  Avg Profit: ${metrics.avg_profit:.4f}")
    print(f"  Avg Edge: {metrics.avg_edge:.2%}")
    
    print(f"\nAdaptive Adjustment:")
    print(f"  Initial Fractional Kelly: 37.5%")
    print(f"  Current Fractional Kelly: {state['fractional_kelly']:.2%}")
    print(f"  Adjustment: {'Increased' if state['fractional_kelly'] > 0.375 else 'Decreased'}")
    
    print(f"\n{'='*60}")
    print(f"Summary")
    print(f"{'='*60}")
    print(f"\nThe DynamicParameterSystem:")
    print(f"  ✓ Calculates edge with transaction costs")
    print(f"  ✓ Uses Kelly Criterion for optimal sizing")
    print(f"  ✓ Applies fractional Kelly (25-50%) for safety")
    print(f"  ✓ Tracks performance over last 20 trades")
    print(f"  ✓ Adapts fractional Kelly based on win rate")
    print(f"  ✓ Enforces position size bounds (min/max)")
    print(f"\nWith 95% win rate, fractional Kelly increased to {state['fractional_kelly']:.2%}")
    print(f"This allows larger positions while maintaining risk control.")


if __name__ == '__main__':
    main()
