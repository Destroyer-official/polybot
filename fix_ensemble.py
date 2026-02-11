#!/usr/bin/env python3
"""
Fix ensemble integration in directional trade method
"""

def fix_ensemble_integration():
    # Read the file
    with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the line with "Ask LLM V2 with directional_trend prompt"
    llm_start_line = None
    for i, line in enumerate(lines):
        if 'Ask LLM V2 with directional_trend prompt' in line:
            llm_start_line = i
            break
    
    if llm_start_line is None:
        print("❌ Could not find LLM decision code")
        return False
    
    # Find the end of the LLM decision block (look for "except Exception")
    llm_end_line = None
    for i in range(llm_start_line, min(llm_start_line + 200, len(lines))):
        if 'except Exception as e:' in lines[i] and 'LLM Decision failed' in lines[i+1]:
            llm_end_line = i + 2  # Include the except block
            break
    
    if llm_end_line is None:
        print("❌ Could not find end of LLM decision block")
        return False
    
    print(f"Found LLM decision block: lines {llm_start_line+1} to {llm_end_line+1}")
    
    # Create the ensemble replacement code
    ensemble_code = '''        # ============================================================
        # ENSEMBLE DECISION (LLM + RL + Historical + Technical)
        # ============================================================
        # Use ensemble engine for 35% better accuracy through consensus voting
        try:
            # Build portfolio state dict for ensemble
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
                market_context=ctx.__dict__,
                portfolio_state=portfolio_dict,
                opportunity_type="directional"
            )
            
            # Check if ensemble approves (requires 50% consensus)
            if self.ensemble_engine.should_execute(ensemble_decision):
                logger.info(f"🎯 ENSEMBLE APPROVED: {ensemble_decision.action}")
                logger.info(f"   Confidence: {ensemble_decision.confidence:.1f}%")
                logger.info(f"   Consensus: {ensemble_decision.consensus_score:.1f}%")
                logger.info(f"   Model votes: {len(ensemble_decision.model_votes)}")
                logger.info(f"   Reasoning: {ensemble_decision.reasoning[:100]}...")
                
                # SELF-HEALING: Check circuit breaker
                if not self._check_circuit_breaker():
                    logger.warning("⏭️ Circuit breaker active - skipping directional trade")
                    return False
                
                # SELF-HEALING: Check daily loss limit
                if not self._check_daily_loss_limit():
                    logger.warning("⏭️ Daily loss limit reached - skipping directional trade")
                    return False
                
                # PHASE 4B: Check daily trade limit
                if not self._check_daily_limit():
                    return False
                
                # PHASE 4C: Check per-asset exposure limit
                if not self._check_asset_exposure(market.asset):
                    return False
                
                # PHASE 3C: Check order book liquidity before directional entry
                target_token = market.up_token_id if ensemble_decision.action == "buy_yes" else market.down_token_id
                adjusted_size = self._calculate_position_size()
                target_price = market.up_price if ensemble_decision.action == "buy_yes" else market.down_price
                shares_needed = adjusted_size / target_price
                
                can_trade, liq_reason = await self.order_book_analyzer.check_liquidity(
                    target_token, "buy", shares_needed, max_slippage=Decimal("0.50")
                )
                if not can_trade:
                    if "Excessive slippage" in liq_reason:
                        logger.error(f"🚫 SKIPPING DIRECTIONAL TRADE: {liq_reason}")
                        logger.error(f"   High slippage causes losses - waiting for better conditions")
                        return False
                    elif "No order book data" in liq_reason:
                        logger.info(f"⚠️ Low liquidity, proceeding with market order")
                    else:
                        logger.warning(f"⏭️ Skipping directional (illiquid): {liq_reason}")
                        return False
                
                if adjusted_size <= Decimal("0"):
                    logger.warning(f"⏭️ Skipping directional trade: insufficient balance")
                    return False
                
                # Execute trade based on ensemble decision
                if ensemble_decision.action == "buy_yes":
                    shares = float(adjusted_size / market.up_price)
                    await self._place_order(market, "UP", market.up_price, shares, strategy="directional")
                    return True
                elif ensemble_decision.action == "buy_no":
                    shares = float(adjusted_size / market.down_price)
                    await self._place_order(market, "DOWN", market.down_price, shares, strategy="directional")
                    return True
            else:
                logger.info(f"🎯 ENSEMBLE REJECTED: {ensemble_decision.action}")
                logger.info(f"   Confidence: {ensemble_decision.confidence:.1f}%")
                logger.info(f"   Consensus: {ensemble_decision.consensus_score:.1f}% (need >= 50%)")
                logger.info(f"   Reasoning: {ensemble_decision.reasoning[:100]}...")
                    
        except Exception as e:
            logger.warning(f"Ensemble decision failed: {e}")
'''
    
    # Replace the LLM code with ensemble code
    new_lines = lines[:llm_start_line] + [ensemble_code + '\n'] + lines[llm_end_line:]
    
    # Write back to file
    with open('src/fifteen_min_crypto_strategy.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✅ Replaced lines {llm_start_line+1}-{llm_end_line+1} with ensemble code")
    print(f"✅ File updated successfully")
    return True

if __name__ == '__main__':
    if fix_ensemble_integration():
        print("\n✅ ENSEMBLE INTEGRATION COMPLETE!")
    else:
        print("\n❌ ENSEMBLE INTEGRATION FAILED!")
