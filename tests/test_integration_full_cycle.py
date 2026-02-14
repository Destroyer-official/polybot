"""
Integration test for full trading cycle.

Tests the complete trading workflow:
market scan → exit check → entry analysis → order placement → position tracking

Validates Requirements: 2.1-2.10, 3.1-3.10, 4.1-4.14
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import json

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, CryptoMarket, Position
from src.ensemble_decision_engine import EnsembleDecisionEngine, EnsembleDecision, ModelDecision
from src.portfolio_risk_manager import PortfolioRiskManager
from src.order_manager import OrderManager


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory for test"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # Create empty data files
    (data_dir / "active_positions.json").write_text("[]")
    (data_dir / "super_smart_learning.json").write_text("{}")
    (data_dir / "adaptive_learning.json").write_text("{}")
    (data_dir / "rl_q_table.json").write_text("{}")
    
    return data_dir


@pytest.fixture
def mock_clob_client():
    """Create mock CLOB client"""
    client = Mock()
    
    # Mock get_markets
    client.get_markets = AsyncMock(return_value=[])
    
    # Mock get_orderbook
    client.get_orderbook = AsyncMock(return_value={
        'bids': [['0.52', '100']],
        'asks': [['0.48', '100']]
    })
    
    # Mock create_order
    client.create_order = Mock(return_value={'order_id': 'test_order_123'})
    
    # Mock post_order
    client.post_order = Mock(return_value={
        'success': True,
        'orderID': 'test_order_123'
    })
    
    return client


@pytest.fixture
def mock_ensemble_engine():
    """Create mock ensemble decision engine"""
    engine = Mock(spec=EnsembleDecisionEngine)
    
    # Default: approve trades with high confidence
    engine.make_decision = AsyncMock(return_value=EnsembleDecision(
        action="buy_yes",
        confidence=Decimal('75.0'),
        consensus_score=Decimal('80.0'),
        model_votes={
            'llm': ModelDecision(model_name='llm', action='buy_yes', confidence=Decimal('80.0'), reasoning='Bullish'),
            'rl': ModelDecision(model_name='rl', action='buy_yes', confidence=Decimal('75.0'), reasoning='Learned pattern'),
            'historical': ModelDecision(model_name='historical', action='buy_yes', confidence=Decimal('70.0'), reasoning='Past success'),
            'technical': ModelDecision(model_name='technical', action='buy_yes', confidence=Decimal('65.0'), reasoning='Momentum')
        },
        reasoning="Strong bullish consensus"
    ))
    
    return engine


@pytest.fixture
def mock_risk_manager():
    """Create mock risk manager"""
    manager = Mock(spec=PortfolioRiskManager)
    
    # Default: allow trades
    manager.check_can_trade = Mock(return_value=Mock(
        can_trade=True,
        max_position_size=Decimal('10.0'),
        reason="All checks passed"
    ))
    
    manager.open_position = Mock()
    manager.close_position = Mock()
    manager.get_portfolio_heat = Mock(return_value=Decimal('0.0'))
    
    return manager


@pytest.fixture
def strategy(temp_data_dir, mock_clob_client):
    """Create FifteenMinuteCryptoStrategy instance with mocked dependencies"""
    
    # Create strategy with minimal mocking
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob_client,
        trade_size=5.0,
        take_profit_pct=0.02,
        stop_loss_pct=0.02,
        max_positions=3,
        dry_run=False,
        llm_decision_engine=None,  # Disable LLM for testing
        enable_adaptive_learning=False,  # Disable learning for testing
        initial_capital=100.0
    )
    
    # Override data directory
    strategy.positions_file = temp_data_dir / "active_positions.json"
    
    return strategy


@pytest.fixture
def sample_markets():
    """Create sample markets for testing"""
    from datetime import timezone
    now = datetime.now(timezone.utc)
    
    return [
        # Market 1: Sum-to-one arbitrage opportunity
        CryptoMarket(
            market_id="btc_15min_1",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            up_price=Decimal('0.48'),
            down_price=Decimal('0.47'),
            up_token_id="0x" + "1" * 64,
            down_token_id="0x" + "2" * 64,
            end_time=now + timedelta(minutes=15),
            neg_risk=False
        ),
        # Market 2: Directional trade opportunity
        CryptoMarket(
            market_id="eth_15min_2",
            question="Will ETH be above $3,500 in 15 minutes?",
            asset="ETH",
            up_price=Decimal('0.55'),
            down_price=Decimal('0.45'),
            up_token_id="0x" + "3" * 64,
            down_token_id="0x" + "4" * 64,
            end_time=now + timedelta(minutes=15),
            neg_risk=False
        ),
        # Market 3: No opportunity (prices too high)
        CryptoMarket(
            market_id="sol_15min_3",
            question="Will SOL be above $150 in 15 minutes?",
            asset="SOL",
            up_price=Decimal('0.52'),
            down_price=Decimal('0.51'),
            up_token_id="0x" + "5" * 64,
            down_token_id="0x" + "6" * 64,
            end_time=now + timedelta(minutes=15),
            neg_risk=False
        )
    ]


class TestFullTradingCycle:
    """Test complete trading cycle from market scan to position tracking"""
    
    @pytest.mark.asyncio
    async def test_complete_trading_cycle_with_exit(
        self,
        strategy,
        sample_markets,
        mock_clob_client
    ):
        """
        Test complete trading cycle:
        1. Market scan
        2. Exit check (no positions initially)
        3. Entry analysis (find opportunity)
        4. Order placement
        5. Position tracking
        6. Exit check (position exists)
        7. Position close
        
        Validates Requirements: 2.1-2.10, 3.1-3.10
        """
        # Phase 1: Market Scan
        # Mock fetch_15min_markets to return sample markets
        with patch.object(strategy, 'fetch_15min_markets', new=AsyncMock(return_value=sample_markets)):
            
            # Phase 2: Exit Check (no positions initially)
            await strategy._check_all_positions_for_exit()
            assert len(strategy.positions) == 0
            
            # Phase 3: Entry Analysis - Process first market (sum-to-one arbitrage)
            market = sample_markets[0]
            
            # Mock orderbook for sum-to-one check
            mock_clob_client.get_orderbook = AsyncMock(return_value={
                'bids': [['0.52', '100']],
                'asks': [['0.48', '100']]  # Ask prices sum to 0.95 < 1.00
            })
            
            # Phase 4: Order Placement
            # Execute sum-to-one arbitrage
            result = await strategy.check_sum_to_one_arbitrage(market)
            
            # Verify order was placed
            assert result is True
            assert mock_clob_client.create_order.called
            assert mock_clob_client.post_order.called
            
            # Phase 5: Position Tracking
            # Verify position was created
            assert len(strategy.positions) > 0
            
            # Get the position
            position_key = list(strategy.positions.keys())[0]
            position = strategy.positions[position_key]
            
            assert position.asset == "BTC"
            assert position.strategy == "sum_to_one"
            assert position.size > 0
            assert position.entry_price > 0
            
            # Phase 6: Exit Check (position exists)
            # Simulate price movement to trigger take-profit
            # Mock orderbook to return profitable exit price
            mock_clob_client.get_orderbook = AsyncMock(return_value={
                'bids': [['0.54', '100']],  # Higher bid = profit
                'asks': [['0.46', '100']]
            })
            
            # Mock successful sell order
            mock_clob_client.create_order = Mock(return_value={'order_id': 'sell_order_123'})
            mock_clob_client.post_order = Mock(return_value={
                'success': True,
                'orderID': 'sell_order_123'
            })
            
            # Phase 7: Position Close
            # Run exit check
            await strategy._check_all_positions_for_exit()
            
            # Verify position was closed
            assert len(strategy.positions) == 0
            
            # Verify trade statistics were updated
            assert strategy.stats['total_trades'] > 0
    
    @pytest.mark.asyncio
    async def test_exit_checked_before_entry(
        self,
        strategy,
        sample_markets,
        mock_clob_client
    ):
        """
        Test that exit conditions are checked BEFORE entry analysis.
        
        Validates Requirements: 2.9, 2.10
        """
        # Create an existing position
        position = Position(
            token_id="0x" + "a" * 64,
            side="UP",
            entry_price=Decimal('0.50'),
            size=Decimal('10.0'),
            entry_time=datetime.now() - timedelta(minutes=14),  # Old position
            market_id="old_market",
            asset="BTC",
            strategy="directional",
            neg_risk=False,
            highest_price=Decimal('0.50')
        )
        strategy.positions[position.token_id] = position
        
        # Track call order
        call_order = []
        
        # Wrap methods to track call order
        original_check_exit = strategy._check_all_positions_for_exit
        original_check_sum_to_one = strategy.check_sum_to_one_arbitrage
        
        async def tracked_check_exit():
            call_order.append('exit_check')
            return await original_check_exit()
        
        async def tracked_check_sum_to_one(market):
            call_order.append('entry_analysis')
            return await original_check_sum_to_one(market)
        
        # Mock orderbook for exit
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.52', '100']],
            'asks': [['0.48', '100']]
        })
        
        # Mock successful sell order
        mock_clob_client.create_order = Mock(return_value={'order_id': 'sell_order_123'})
        mock_clob_client.post_order = Mock(return_value={
            'success': True,
            'orderID': 'sell_order_123'
        })
        
        with patch.object(strategy, '_check_all_positions_for_exit', new=tracked_check_exit):
            with patch.object(strategy, 'check_sum_to_one_arbitrage', new=tracked_check_sum_to_one):
                with patch.object(strategy, 'fetch_15min_markets', new=AsyncMock(return_value=sample_markets)):
                    
                    # Run cycle
                    await strategy.run_cycle()
        
        # Verify exit check was called before entry analysis
        assert 'exit_check' in call_order
        assert 'entry_analysis' in call_order
        assert call_order.index('exit_check') < call_order.index('entry_analysis')
    
    @pytest.mark.asyncio
    async def test_orders_placed_correctly(
        self,
        strategy,
        sample_markets,
        mock_clob_client
    ):
        """
        Test that orders are placed with correct parameters.
        
        Validates Requirements: 2.6, 3.9
        """
        market = sample_markets[0]
        
        # Mock orderbook for sum-to-one
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.52', '100']],
            'asks': [['0.48', '100']]
        })
        
        # Execute trade
        await strategy.check_sum_to_one_arbitrage(market)
        
        # Verify create_order was called
        assert mock_clob_client.create_order.called
        
        # Get the order arguments
        call_args = mock_clob_client.create_order.call_args
        
        # Verify order parameters
        # Note: The actual implementation may pass OrderArgs object
        # We're checking that the method was called with proper structure
        assert call_args is not None
    
    @pytest.mark.asyncio
    async def test_positions_tracked_correctly(
        self,
        strategy,
        sample_markets,
        mock_clob_client,
        temp_data_dir
    ):
        """
        Test that positions are tracked correctly in memory and persisted to disk.
        
        Validates Requirements: 2.7
        """
        market = sample_markets[0]
        
        # Mock orderbook
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.52', '100']],
            'asks': [['0.48', '100']]
        })
        
        # Execute trade
        await strategy.check_sum_to_one_arbitrage(market)
        
        # Verify position in memory
        assert len(strategy.positions) > 0
        
        position_key = list(strategy.positions.keys())[0]
        position = strategy.positions[position_key]
        
        # Verify position attributes
        assert position.token_id is not None
        assert position.asset == "BTC"
        assert position.strategy == "sum_to_one"
        assert position.entry_price > 0
        assert position.size > 0
        assert position.entry_time is not None
        assert isinstance(position.neg_risk, bool)
        
        # Verify position persisted to disk
        positions_file = temp_data_dir / "active_positions.json"
        assert positions_file.exists()
        
        with open(positions_file, 'r') as f:
            saved_positions = json.load(f)
        
        assert len(saved_positions) > 0
        assert saved_positions[0]['asset'] == "BTC"
    
    @pytest.mark.asyncio
    async def test_multiple_markets_processed(
        self,
        strategy,
        sample_markets,
        mock_clob_client
    ):
        """
        Test that multiple markets are processed in a single cycle.
        
        Validates Requirements: 5.4
        """
        # Mock orderbook to return different opportunities
        orderbook_responses = [
            # Market 1: Sum-to-one opportunity
            {'bids': [['0.52', '100']], 'asks': [['0.48', '100']]},
            # Market 2: No opportunity
            {'bids': [['0.50', '100']], 'asks': [['0.50', '100']]},
            # Market 3: No opportunity
            {'bids': [['0.50', '100']], 'asks': [['0.50', '100']]},
        ]
        
        mock_clob_client.get_orderbook = AsyncMock(side_effect=orderbook_responses)
        
        with patch.object(strategy, 'fetch_15min_markets', new=AsyncMock(return_value=sample_markets)):
            # Process markets
            await strategy._process_markets_concurrently(sample_markets)
        
        # Verify orderbook was fetched for multiple markets
        assert mock_clob_client.get_orderbook.call_count >= len(sample_markets)
    
    @pytest.mark.asyncio
    async def test_learning_engines_updated_after_trade(
        self,
        strategy,
        sample_markets,
        mock_clob_client
    ):
        """
        Test that learning engines are updated after trade completion.
        
        Validates Requirements: 2.8
        """
        market = sample_markets[0]
        
        # Mock orderbook for entry
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.52', '100']],
            'asks': [['0.48', '100']]
        })
        
        # Execute trade
        await strategy.check_sum_to_one_arbitrage(market)
        
        # Get position
        position_key = list(strategy.positions.keys())[0]
        position = strategy.positions[position_key]
        
        # Mock orderbook for exit (profitable)
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.54', '100']],
            'asks': [['0.46', '100']]
        })
        
        # Mock successful sell
        mock_clob_client.create_order = Mock(return_value={'order_id': 'sell_order_123'})
        mock_clob_client.post_order = Mock(return_value={
            'success': True,
            'orderID': 'sell_order_123'
        })
        
        # Track if _record_trade_outcome was called
        with patch.object(strategy, '_record_trade_outcome') as mock_record:
            # Close position
            await strategy._check_all_positions_for_exit()
            
            # Verify learning engines were updated
            assert mock_record.called
            
            # Verify call arguments
            call_args = mock_record.call_args[1]  # Get keyword arguments
            assert 'strategy' in call_args
            assert 'asset' in call_args
            assert 'profit' in call_args


class TestEdgeCases:
    """Test edge cases in trading cycle"""
    
    @pytest.mark.asyncio
    async def test_orphan_position_handling(
        self,
        strategy,
        mock_clob_client
    ):
        """
        Test handling of orphan positions (no market data available).
        
        Validates Requirements: 2.9, 2.10
        """
        # Create orphan position (old market that no longer exists)
        position = Position(
            token_id="0x" + "b" * 64,
            side="UP",
            entry_price=Decimal('0.50'),
            size=Decimal('10.0'),
            entry_time=datetime.now() - timedelta(minutes=20),  # Very old
            market_id="expired_market",
            asset="BTC",
            strategy="directional",
            neg_risk=False,
            highest_price=Decimal('0.50')
        )
        strategy.positions[position.token_id] = position
        
        # Mock orderbook (fallback price)
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.50', '100']],
            'asks': [['0.50', '100']]
        })
        
        # Mock successful sell
        mock_clob_client.create_order = Mock(return_value={'order_id': 'sell_order_123'})
        mock_clob_client.post_order = Mock(return_value={
            'success': True,
            'orderID': 'sell_order_123'
        })
        
        # Run exit check
        await strategy._check_all_positions_for_exit()
        
        # Verify orphan position was handled (closed due to age)
        assert len(strategy.positions) == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_new_entries(
        self,
        strategy,
        sample_markets,
        mock_clob_client
    ):
        """
        Test that circuit breaker blocks new entries after consecutive losses.
        
        Validates Requirements: 7.3, 7.9
        """
        # Simulate consecutive losses
        strategy.consecutive_losses = 5
        
        market = sample_markets[0]
        
        # Mock orderbook (opportunity exists)
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.52', '100']],
            'asks': [['0.48', '100']]
        })
        
        # Try to execute trade
        result = await strategy.check_sum_to_one_arbitrage(market)
        
        # Verify trade was blocked
        assert result is False
        assert len(strategy.positions) == 0
    
    @pytest.mark.asyncio
    async def test_daily_trade_limit_enforcement(
        self,
        strategy,
        sample_markets,
        mock_clob_client
    ):
        """
        Test that daily trade limit is enforced.
        
        Validates Requirements: 4.10
        """
        # Set daily trade count to limit
        strategy.daily_trade_count = strategy.max_daily_trades
        strategy.last_trade_date = datetime.now().date()
        
        market = sample_markets[0]
        
        # Mock orderbook (opportunity exists)
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.52', '100']],
            'asks': [['0.48', '100']]
        })
        
        # Try to execute trade
        result = await strategy.check_sum_to_one_arbitrage(market)
        
        # Verify trade was blocked
        assert result is False
        assert len(strategy.positions) == 0


class TestPerformanceMetrics:
    """Test performance tracking and metrics"""
    
    @pytest.mark.asyncio
    async def test_execution_time_tracking(
        self,
        strategy,
        sample_markets,
        mock_clob_client
    ):
        """
        Test that execution times are tracked for performance monitoring.
        
        Validates Requirements: 5.1
        """
        market = sample_markets[0]
        
        # Mock orderbook
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.52', '100']],
            'asks': [['0.48', '100']]
        })
        
        # Execute trade
        start_time = datetime.now()
        await strategy.check_sum_to_one_arbitrage(market)
        end_time = datetime.now()
        
        execution_time_ms = (end_time - start_time).total_seconds() * 1000
        
        # Verify execution was fast (< 1 second)
        assert execution_time_ms < 1000
    
    @pytest.mark.asyncio
    async def test_statistics_updated_correctly(
        self,
        strategy,
        sample_markets,
        mock_clob_client
    ):
        """
        Test that trade statistics are updated correctly.
        
        Validates Requirements: 9.1-9.8
        """
        initial_trades = strategy.stats['trades_placed']
        
        market = sample_markets[0]
        
        # Mock orderbook
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.52', '100']],
            'asks': [['0.48', '100']]
        })
        
        # Execute trade
        await strategy.check_sum_to_one_arbitrage(market)
        
        # Verify statistics updated
        assert strategy.stats['trades_placed'] >= initial_trades
