#!/usr/bin/env python3
"""
Fix ensemble integration bug in fifteen_min_crypto_strategy.py
"""

def fix_ensemble_integration():
    """Remove portfolio_dict building and pass objects directly."""
    
    file_path = "src/fifteen_min_crypto_strategy.py"
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the buggy section
    old_code = """            # Build portfolio state dict for ensemble
            portfolio_dict = {
                'available_balance': float(p_state.available_balance),
                'total_balance': float(p_state.total_balance),
                'open_positions': p_state.open_positions,
                'daily_pnl': float(p_state.daily_pnl),
                'win_rate_today': p_state.win_rate_today,
                'trades_today': p_state.trades_today,
                'max_position_size': float(p_state.max_position_size)
            }
            
            # Get ensemble decision (combines all models)
            ensemble_decision = await self.ensemble_engine.make_decision(
                asset=market.asset,
                market_context=ctx,
                portfolio_state=portfolio_dict,
                opportunity_type="directional"
            )"""
    
    new_code = """            # Get ensemble decision (combines all models)
            # Pass objects directly - ensemble handles both Dict and object types
            ensemble_decision = await self.ensemble_engine.make_decision(
                asset=market.asset,
                market_context=ctx,
                portfolio_state=p_state,
                opportunity_type="directional"
            )"""
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Fixed ensemble integration in fifteen_min_crypto_strategy.py")
        print("   - Removed portfolio_dict building")
        print("   - Changed portfolio_state=portfolio_dict to portfolio_state=p_state")
        print("   - Changed market_context=ctx (already correct)")
        return True
    else:
        print("❌ Could not find the old code pattern")
        print("   The file may already be fixed or have different formatting")
        return False

if __name__ == "__main__":
    success = fix_ensemble_integration()
    exit(0 if success else 1)
