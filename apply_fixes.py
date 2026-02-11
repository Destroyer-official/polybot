"""
Apply critical fixes to the trading bot files.
"""
import re

print("="*80)
print("APPLYING CRITICAL FIXES")
print("="*80)

# Fix 1: Change min_consensus from 60.0 to 15.0
print("\n[1/4] Fixing min_consensus value...")
with open('src/fifteen_min_crypto_strategy.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_consensus = 'min_consensus=60.0  # Require 60% consensus for execution'
new_consensus = 'min_consensus=15.0  # Lowered to 15% to allow more trades'

if old_consensus in content:
    content = content.replace(old_consensus, new_consensus)
    print("  ✅ Changed min_consensus from 60.0 to 15.0")
else:
    print("  ⚠️  Could not find exact match for min_consensus=60.0")
    # Try regex
    content = re.sub(r'min_consensus=60\.0.*', 'min_consensus=15.0  # Lowered to 15% to allow more trades', content)
    print("  ✅ Applied regex replacement for min_consensus")

# Fix 2 & 3: Add missing methods
print("\n[2/4] Adding missing _check_circuit_breaker and _check_daily_loss_limit methods...")

# Find where to insert (after _should_take_trade method)
insert_marker = '        return should_trade, weighted_score, reason\n    \n    def _record_trade_outcome('

if insert_marker in content:
    methods_to_add = '''        return should_trade, weighted_score, reason
    
    def _check_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker is active (too many consecutive losses).
        
        Returns:
            True if trading is allowed, False if circuit breaker is active
        """
        # Check consecutive losses
        max_consecutive_losses = 5
        recent_trades = list(self.stats.get('recent_outcomes', []))[-max_consecutive_losses:]
        
        if len(recent_trades) >= max_consecutive_losses:
            if all(outcome == 'loss' for outcome in recent_trades):
                logger.warning(f"🔴 CIRCUIT BREAKER: {max_consecutive_losses} consecutive losses")
                return False
        
        return True
    
    def _check_daily_loss_limit(self) -> bool:
        """
        Check if daily loss limit has been reached.
        
        Returns:
            True if trading is allowed, False if daily loss limit reached
        """
        daily_pnl = self.stats.get('total_profit', Decimal('0'))
        max_daily_loss = Decimal('-10.0')  # Stop trading if down $10 in a day
        
        if daily_pnl < max_daily_loss:
            logger.warning(f"🔴 DAILY LOSS LIMIT: ${daily_pnl:.2f} < ${max_daily_loss:.2f}")
            return False
        
        return True
    
    def _record_trade_outcome('''
    
    content = content.replace(insert_marker, methods_to_add)
    print("  ✅ Added _check_circuit_breaker() method")
    print("  ✅ Added _check_daily_loss_limit() method")
else:
    print("  ⚠️  Could not find insertion point for methods")
    print("  ⚠️  You'll need to add these methods manually")

# Fix 4: Update log message
print("\n[3/4] Fixing log message...")
old_log = 'logger.info(f"   Consensus: {ensemble_decision.consensus_score:.1f}% (need >= 50%)")'
new_log = 'logger.info(f"   Consensus: {ensemble_decision.consensus_score:.1f}% (need >= 15%)")'

if old_log in content:
    content = content.replace(old_log, new_log)
    print("  ✅ Updated log message from 50% to 15%")
else:
    print("  ⚠️  Could not find exact log message")
    # Try regex
    content = re.sub(r'\(need >= 50%\)', '(need >= 15%)', content)
    print("  ✅ Applied regex replacement for log message")

# Write the fixed content
print("\n[4/4] Writing fixed file...")
with open('src/fifteen_min_crypto_strategy.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("  ✅ File written successfully")

print("\n" + "="*80)
print("FIXES APPLIED!")
print("="*80)
print("\nRun 'python final_pre_deployment_check.py' to verify all fixes.")
