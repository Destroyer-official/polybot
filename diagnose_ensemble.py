"""
Diagnostic script to understand why ensemble is rejecting all trades.
"""
import asyncio
import sys
from decimal import Decimal
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, 'src')

from ensemble_decision_engine import EnsembleDecisionEngine
from llm_decision_engine_v2 import LLMDecisionEngineV2, MarketContext as MarketContextV2, PortfolioState as PortfolioStateV2
from reinforcement_learning_engine import ReinforcementLearningEngine
from historical_success_tracker import HistoricalSuccessTracker
from multi_timeframe_analyzer import MultiTimeframeAnalyzer
from binance_price_feed import BinancePriceFeed

async def test_ensemble():
    """Test ensemble with realistic market data."""
    
    # Initialize components
    print("Initializing components...")
    llm_engine = LLMDecisionEngineV2()
    rl_engine = ReinforcementLearningEngine()
    success_tracker = HistoricalSuccessTracker()
    binance_feed = BinancePriceFeed()
    multi_tf_analyzer = MultiTimeframeAnalyzer(binance_feed)
    
    # Start Binance feed
    print("Starting Binance feed...")
    await binance_feed.start()
    await asyncio.sleep(2)  # Wait for initial prices
    
    # Initialize ensemble
    ensemble = EnsembleDecisionEngine(
        llm_engine=llm_engine,
        rl_engine=rl_engine,
        historical_tracker=success_tracker,
        multi_tf_analyzer=multi_tf_analyzer,
        min_consensus=30.0
    )
    
    # Test with BTC market
    print("\n" + "="*80)
    print("Testing BTC market...")
    print("="*80)
    
    btc_price = binance_feed.prices.get("BTC", Decimal("0"))
    print(f"Current BTC price: ${btc_price}")
    
    # Build realistic market context
    ctx = MarketContextV2(
        market_id="test_btc_market",
        question="Will BTC be above $95,000 at 15:15:00 UTC?",
        asset="BTC",
        yes_price=Decimal("0.52"),  # 52% probability
        no_price=Decimal("0.48"),   # 48% probability
        yes_liquidity=Decimal("1000"),
        no_liquidity=Decimal("1000"),
        volume_24h=Decimal("10000"),
        time_to_resolution=10.0,  # 10 minutes to close
        spread=Decimal("0.00"),
        volatility_1h=None,
        recent_price_changes=[Decimal("0.002")],  # 0.2% up
        binance_price=btc_price,
        binance_momentum="bullish"
    )
    
    # Build portfolio state
    p_state = PortfolioStateV2(
        available_balance=Decimal("3.0"),
        total_balance=Decimal("6.0"),
        open_positions=[],
        daily_pnl=Decimal("0"),
        win_rate_today=0.5,
        trades_today=0,
        max_position_size=Decimal("3.0")
    )
    
    # Get ensemble decision
    print("\nGetting ensemble decision...")
    decision = await ensemble.make_decision(
        asset="BTC",
        market_context=ctx,
        portfolio_state=p_state,
        opportunity_type="directional"
    )
    
    print(f"\n{'='*80}")
    print("ENSEMBLE DECISION")
    print(f"{'='*80}")
    print(f"Action: {decision.action}")
    print(f"Confidence: {decision.confidence:.1f}%")
    print(f"Consensus: {decision.consensus_score:.1f}%")
    print(f"Reasoning: {decision.reasoning}")
    print(f"\nModel Votes:")
    for model_name, vote in decision.model_votes.items():
        print(f"  {model_name}: {vote.action} ({vote.confidence:.1f}%) - {vote.reasoning}")
    
    print(f"\nShould Execute: {ensemble.should_execute(decision)}")
    print(f"  - Action is not skip: {decision.action != 'skip'}")
    print(f"  - Consensus >= 30%: {decision.consensus_score >= 30.0}")
    print(f"  - Confidence >= 25%: {decision.confidence >= 25.0}")
    
    # Stop Binance feed
    await binance_feed.stop()

if __name__ == "__main__":
    asyncio.run(test_ensemble())
