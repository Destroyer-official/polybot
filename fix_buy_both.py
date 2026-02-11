#!/usr/bin/env python3
"""
Fix buy_both handling in ensemble integration
"""

def fix_buy_both_handling():
    """Add handling for buy_both action in directional trade."""
    
    file_path = "src/fifteen_min_crypto_strategy.py"
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and replace the buggy section
    old_code = """                # Execute trade based on ensemble decision
                if ensemble_decision.action == "buy_yes":
                    shares = float(adjusted_size / market.up_price)
                    await self._place_order(market, "UP", market.up_price, shares, strategy="directional")
                    return True
                elif ensemble_decision.action == "buy_no":
                    shares = float(adjusted_size / market.down_price)
                    await self._place_order(market, "DOWN", market.down_price, shares, strategy="directional")
                    return True
            else:"""
    
    new_code = """                # Execute trade based on ensemble decision
                if ensemble_decision.action == "buy_yes":
                    shares = float(adjusted_size / market.up_price)
                    await self._place_order(market, "UP", market.up_price, shares, strategy="directional")
                    return True
                elif ensemble_decision.action == "buy_no":
                    shares = float(adjusted_size / market.down_price)
                    await self._place_order(market, "DOWN", market.down_price, shares, strategy="directional")
                    return True
                elif ensemble_decision.action == "buy_both":
                    # buy_both is for arbitrage, not directional - treat as skip
                    logger.info(f"🎯 ENSEMBLE: buy_both not applicable for directional trade - skipping")
                    return False
            else:"""
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Fixed buy_both handling in fifteen_min_crypto_strategy.py")
        print("   - Added elif for buy_both action")
        print("   - buy_both now treated as skip for directional trades")
        return True
    else:
        print("❌ Could not find the old code pattern")
        print("   The file may already be fixed or have different formatting")
        return False

if __name__ == "__main__":
    success = fix_buy_both_handling()
    exit(0 if success else 1)
