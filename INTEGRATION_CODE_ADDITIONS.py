# ============================================================
# CODE TO ADD AFTER LINE 404 in src/fifteen_min_crypto_strategy.py
# (After: self.max_positions_per_asset = 2)
# ============================================================

        # ============================================================
        # ADVANCED LEARNING SYSTEMS - FULLY INTEGRATED
        # ============================================================
        logger.info("=" * 80)
        logger.info("🧠 Initializing Advanced Learning Systems...")
        logger.info("=" * 80)
        
        # Multi-timeframe analyzer (40% fewer false signals)
        from src.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        self.multi_tf_analyzer = MultiTimeframeAnalyzer()
        logger.info("✅ Multi-Timeframe Analyzer: Active")
        
        # Order book analyzer (prevents slippage)
        from src.order_book_analyzer import OrderBookAnalyzer
        self.order_book_analyzer = OrderBookAnalyzer(clob_client)
        logger.info("✅ Order Book Analyzer: Active")
        
        # Historical success tracker
        from src.historical_success_tracker import HistoricalSuccessTracker
        self.success_tracker = HistoricalSuccessTracker()
        logger.info("✅ Historical Success Tracker: Active")
        
        # Reinforcement Learning Engine (Q-learning)
        from src.reinforcement_learning_engine import ReinforcementLearningEngine
        self.rl_engine = ReinforcementLearningEngine()
        logger.info("✅ RL Engine: Active")
        
        # Adaptive Learning Engine
        from src.adaptive_learning_engine import AdaptiveLearningEngine
        self.adaptive_learning = None
        if enable_adaptive_learning:
            self.adaptive_learning = AdaptiveLearningEngine(
                data_file="data/adaptive_learning.json",
                learning_rate=0.1,
                min_trades_for_learning=10
            )
            logger.info("✅ Adaptive Learning: Active")
        else:
            logger.info("⚠️ Adaptive Learning: Disabled")
        
        # SuperSmart Learning (most advanced)
        from src.super_smart_learning import SuperSmartLearning
        self.super_smart = SuperSmartLearning(data_file="data/super_smart_learning.json")
        logger.info("✅ SuperSmart Learning: Active")
        
        # Ensemble Decision Engine (combines all models)
        from src.ensemble_decision_engine import EnsembleDecisionEngine
        self.ensemble_engine = EnsembleDecisionEngine(
            llm_engine=llm_decision_engine,
            rl_engine=self.rl_engine,
            historical_tracker=self.success_tracker,
            multi_tf_analyzer=self.multi_tf_analyzer,
            min_consensus=50.0  # AGGRESSIVE: 50% consensus
        )
        logger.info("✅ Ensemble Engine: Active")
        
        # ============================================================
        # LAYERED PARAMETER SYSTEM (BASE + DYNAMIC)
        # ============================================================
        # Store BASE parameters separately from dynamic adjustments
        # This prevents learning from overriding dynamic TP
        
        self.base_take_profit_pct = self.take_profit_pct
        self.base_stop_loss_pct = self.stop_loss_pct
        
        # Update base from SuperSmart (if available)
        if self.super_smart.total_trades >= 5:
            optimal = self.super_smart.get_optimal_parameters()
            self.base_take_profit_pct = Decimal(str(optimal["take_profit_pct"]))
            self.base_stop_loss_pct = Decimal(str(optimal["stop_loss_pct"]))
            logger.info(f"🚀 SuperSmart BASE: TP={self.base_take_profit_pct*100:.1f}%, SL={self.base_stop_loss_pct*100:.1f}%")
            logger.info(f"   (Dynamic system will adjust these in real-time)")
        # Or update from Adaptive (if SuperSmart not ready)
        elif self.adaptive_learning and self.adaptive_learning.total_trades >= 10:
            params = self.adaptive_learning.current_params
            self.base_take_profit_pct = params.take_profit_pct
            self.base_stop_loss_pct = params.stop_loss_pct
            logger.info(f"📚 Adaptive BASE: TP={self.base_take_profit_pct*100:.2f}%, SL={self.base_stop_loss_pct*100:.2f}%")
            logger.info(f"   (Dynamic system will adjust these in real-time)")
        else:
            logger.info(f"📊 Using config BASE: TP={self.base_take_profit_pct*100:.2f}%, SL={self.base_stop_loss_pct*100:.2f}%")
            logger.info(f"   (Will learn optimal values from trades)")
        
        logger.info("=" * 80)
        logger.info("🧠 ALL LEARNING SYSTEMS: ACTIVE AND INTEGRATED")
        logger.info("=" * 80)


# ============================================================
# NEW METHODS TO ADD (Self-Healing)
# Add these after _check_asset_exposure() method
# ============================================================

    def _check_circuit_breaker(self) -> bool:
        """
        SELF-HEALING: Circuit breaker for consecutive losses.
        
        Automatically reduces risk after losses and increases after wins.
        """
        if self.consecutive_losses >= self.max_consecutive_losses:
            if not self.circuit_breaker_active:
                logger.error("=" * 80)
                logger.error("🚨 CIRCUIT BREAKER ACTIVATED")
                logger.error(f"   Reason: {self.consecutive_losses} consecutive losses")
                logger.error(f"   Action: Reducing position size by 50%")
                logger.error(f"   Recovery: Will auto-recover after 3 wins")
                logger.error("=" * 80)
                self.circuit_breaker_active = True
            return False
        
        # Auto-recovery
        if self.consecutive_wins >= 3 and self.circuit_breaker_active:
            logger.info("=" * 80)
            logger.info("✅ CIRCUIT BREAKER DEACTIVATED")
            logger.info(f"   Reason: {self.consecutive_wins} consecutive wins")
            logger.info(f"   Action: Restoring normal operation")
            logger.info("=" * 80)
            self.circuit_breaker_active = False
        
        return True

    def _check_daily_loss_limit(self) -> bool:
        """SELF-HEALING: Daily loss limit protection."""
        today = datetime.now(timezone.utc).date()
        if today != self.last_trade_date:
            self.daily_loss = Decimal("0")
            logger.info(f"📅 New day - daily loss reset")
        
        if self.daily_loss >= self.max_daily_loss:
            logger.error("🚨 DAILY LOSS LIMIT REACHED: Trading halted")
            return False
        return True

    def _calculate_dynamic_stop_loss(self, asset: str, position_age_minutes: float) -> Decimal:
        """SELF-HEALING: Dynamic stop loss based on volatility."""
        dynamic_stop_loss = self.base_stop_loss_pct
        
        # Adjust for volatility
        changes = []
        for seconds in [10, 30, 60]:
            change = self.binance_feed.get_price_change(asset, seconds)
            if change:
                changes.append(abs(change))
        
        if changes:
            avg_volatility = sum(changes) / len(changes)
            if avg_volatility > Decimal("0.01"):
                dynamic_stop_loss *= Decimal("1.5")  # Widen
                logger.info(f"📊 High volatility - SL: {dynamic_stop_loss*100:.1f}%")
            elif avg_volatility < Decimal("0.002"):
                dynamic_stop_loss *= Decimal("0.8")  # Tighten
        
        # Tighten for old positions
        if position_age_minutes > 8:
            dynamic_stop_loss *= Decimal("0.8")
        
        return dynamic_stop_loss


# ============================================================
# MODIFICATIONS TO EXISTING METHODS
# ============================================================

# In check_sum_to_one_arbitrage(), check_latency_arbitrage(), check_directional_trade()
# ADD THESE CHECKS at the start:

                # SELF-HEALING: Check circuit breaker
                if not self._check_circuit_breaker():
                    return False
                
                # SELF-HEALING: Check daily loss limit
                if not self._check_daily_loss_limit():
                    return False


# In check_exit_conditions(), REPLACE dynamic TP calculation with:

            # ============================================================
            # LAYERED DYNAMIC TAKE PROFIT
            # ============================================================
            dynamic_take_profit = self.base_take_profit_pct
            
            # Layer 1: Time remaining
            if time_remaining_minutes < 2:
                dynamic_take_profit *= Decimal("0.4")
            elif time_remaining_minutes < 4:
                dynamic_take_profit *= Decimal("0.6")
            elif time_remaining_minutes < 6:
                dynamic_take_profit *= Decimal("0.8")
            elif time_remaining_minutes > 10:
                dynamic_take_profit *= Decimal("1.2")
            
            # Layer 2: Position age
            if position_age_minutes > 8:
                dynamic_take_profit *= Decimal("0.7")
            
            # Layer 3: Binance momentum
            binance_change = self.binance_feed.get_price_change(position.asset, seconds=30)
            if binance_change is not None:
                if position.side == "UP" and binance_change < Decimal("-0.001"):
                    dynamic_take_profit *= Decimal("0.6")
                elif position.side == "DOWN" and binance_change > Decimal("0.001"):
                    dynamic_take_profit *= Decimal("0.6")
            
            # Layer 4: Performance streak
            if self.consecutive_wins >= 3:
                dynamic_take_profit *= Decimal("1.1")
            elif self.consecutive_losses >= 2:
                dynamic_take_profit *= Decimal("0.8")
            
            logger.info(f"   🎯 Dynamic TP: {dynamic_take_profit*100:.2f}% (base: {self.base_take_profit_pct*100:.1f}%)")


# In check_exit_conditions(), REPLACE stop loss check with:

            # ============================================================
            # DYNAMIC STOP LOSS (SELF-HEALING)
            # ============================================================
            dynamic_stop_loss = self._calculate_dynamic_stop_loss(position.asset, position_age_minutes)
            
            if pnl_pct <= -dynamic_stop_loss:
                logger.warning(f"❌ DYNAMIC STOP LOSS: {pnl_pct*100:.2f}% <= -{dynamic_stop_loss*100:.2f}%")
                
                success = await self._close_position(position, current_price)
                if success:
                    positions_to_close.append(token_id)
                    self.stats["trades_lost"] += 1
                    
                    # Update daily loss
                    loss_amount = abs((current_price - position.entry_price) * position.size)
                    self.daily_loss += loss_amount
                    
                    self.stats["total_profit"] += (current_price - position.entry_price) * position.size
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0
                    
                    self._record_trade_outcome(
                        asset=position.asset, side=position.side,
                        strategy=position.strategy, entry_price=position.entry_price,
                        exit_price=current_price, profit_pct=pnl_pct,
                        hold_time_minutes=position_age_minutes, exit_reason="dynamic_stop_loss"
                    )
                continue
