#!/usr/bin/env python3
"""
Test script to verify ensemble integration fix.
Tests that ensemble can accept both Dict and object types.
"""
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from src.llm_decision_engine_v2 import MarketContext, PortfolioState
from src.ensemble_decision_engine import EnsembleDecisionEngine

async def test_ensemble_with_objects():
    """Test ensemble with proper object types (the fix)."""
    print("=" * 60)
    print("TEST 1: Ensemble with Objects (FIXED)")
    print("=" * 60)
    
    # Create ensemble (without actual engines for quick test)
    ensemble = EnsembleDecisionEngine(
        llm_engine=None,  # Skip LLM for quick test
        rl_engine=None,
        historical_tracker=None,
        multi_tf_analyzer=None
    )
    
    # Create proper objects
    market_ctx = MarketContext(
        market_id="test123",
        question="Will BTC go up?",
        asset="BTC",
        yes_price=Decimal("0.55"),
        no_price=Decimal("0.45"),
        yes_liquidity=Decimal("1000"),
        no_liquidity=Decimal("1000"),
        volume_24h=Decimal("10000"),
        time_to_resolution=60.0,
        spread=Decimal("0.00"),
        volatility_1h=None,
        recent_price_changes=None,
        binance_price=Decimal("50000"),
        binance_momentum="bullish"
    )
    
    portfolio_state = PortfolioState(
        available_balance=Decimal("100"),
        total_balance=Decimal("200"),
        open_positions=[],
        daily_pnl=Decimal("5.50"),
        win_rate_today=0.65,
        trades_today=10,
        max_position_size=Decimal("20")
    )
    
    try:
        # This should work now with the fix
        decision = await ensemble.make_decision(
            asset="BTC",
            market_context=market_ctx,
            portfolio_state=portfolio_state,
            opportunity_type="directional"
        )
        print(f"✅ SUCCESS: Ensemble accepted objects!")
        print(f"   Decision: {decision.action}")
        print(f"   Confidence: {decision.confidence:.1f}%")
        print(f"   Consensus: {decision.consensus_score:.1f}%")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_ensemble_with_dicts():
    """Test ensemble with dict types (backward compatibility)."""
    print("\n" + "=" * 60)
    print("TEST 2: Ensemble with Dicts (Backward Compatibility)")
    print("=" * 60)
    
    # Create ensemble
    ensemble = EnsembleDecisionEngine(
        llm_engine=None,
        rl_engine=None,
        historical_tracker=None,
        multi_tf_analyzer=None
    )
    
    # Create dicts
    market_dict = {
        "market_id": "test123",
        "asset": "BTC",
        "volatility": 0.05,
        "trend": "bullish",
        "liquidity": 1000
    }
    
    portfolio_dict = {
        "available_balance": 100,
        "total_balance": 200,
        "open_positions": [],
        "daily_pnl": 5.50,
        "win_rate_today": 0.65,
        "trades_today": 10
    }
    
    try:
        # This should also work (backward compatibility)
        decision = await ensemble.make_decision(
            asset="BTC",
            market_context=market_dict,
            portfolio_state=portfolio_dict,
            opportunity_type="directional"
        )
        print(f"✅ SUCCESS: Ensemble accepted dicts!")
        print(f"   Decision: {decision.action}")
        print(f"   Confidence: {decision.confidence:.1f}%")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests."""
    print("\n🧪 Testing Ensemble Integration Fix\n")
    
    test1 = await test_ensemble_with_objects()
    test2 = await test_ensemble_with_dicts()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Test 1 (Objects): {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"Test 2 (Dicts):   {'✅ PASS' if test2 else '❌ FAIL'}")
    
    if test1 and test2:
        print("\n🎉 ALL TESTS PASSED! Ensemble fix is working!")
        print("\nNext steps:")
        print("1. Deploy to AWS")
        print("2. Restart polybot.service")
        print("3. Monitor logs for '🎯 ENSEMBLE APPROVED' with 4 model votes")
    else:
        print("\n⚠️ SOME TESTS FAILED - Review errors above")
    
    return test1 and test2

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
