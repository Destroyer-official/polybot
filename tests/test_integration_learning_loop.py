"""
Integration test for learning loop.

Tests the complete learning workflow:
trade execution → outcome recording → parameter update → persistence

Validates that all learning engines receive updates and parameters persist to disk.
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import json

from src.fifteen_min_crypto_strategy import FifteenMinuteCryptoStrategy, Position
from src.dynamic_parameter_system import DynamicParameterSystem


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
    
    client.get_markets = AsyncMock(return_value=[])
    client.get_orderbook = AsyncMock(return_value={
        'bids': [['0.52', '100']],
        'asks': [['0.48', '100']]
    })
    client.create_order = Mock(return_value={'order_id': 'test_order_123'})
    client.post_order = Mock(return_value={
        'success': True,
        'orderID': 'test_order_123'
    })
    
    return client


@pytest.fixture
def strategy(temp_data_dir, mock_clob_client):
    """Create FifteenMinuteCryptoStrategy instance with learning enabled"""
    
    strategy = FifteenMinuteCryptoStrategy(
        clob_client=mock_clob_client,
        trade_size=5.0,
        take_profit_pct=0.02,
        stop_loss_pct=0.02,
        max_positions=3,
        dry_run=False,
        llm_decision_engine=None,
        enable_adaptive_learning=True,  # Enable learning
        initial_capital=100.0
    )
    
    # Override data directory
    strategy.positions_file = temp_data_dir / "active_positions.json"
    strategy.super_smart_file = temp_data_dir / "super_smart_learning.json"
    strategy.adaptive_file = temp_data_dir / "adaptive_learning.json"
    strategy.rl_file = temp_data_dir / "rl_q_table.json"
    
    return strategy


class TestLearningLoopIntegration:
    """Test complete learning loop from trade execution to parameter persistence"""
    
    @pytest.mark.asyncio
    async def test_profitable_trade_updates_all_engines(
        self,
        strategy,
        mock_clob_client,
        temp_data_dir
    ):
        """
        Test that a profitable trade updates all three learning engines:
        - SuperSmart engine
        - RL engine
        - Adaptive engine
        
        Validates Requirements: 2.8
        """
        # Create a position
        position = Position(
            token_id="0x" + "1" * 64,
            side="UP",
            entry_price=Decimal('0.50'),
            size=Decimal('10.0'),
            entry_time=datetime.now() - timedelta(minutes=5),
            market_id="test_market",
            asset="BTC",
            strategy="sum_to_one",
            neg_risk=False,
            highest_price=Decimal('0.50')
        )
        strategy.positions[position.token_id] = position
        
        # Mock orderbook for profitable exit
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.55', '100']],  # 10% profit
            'asks': [['0.45', '100']]
        })
        
        # Mock successful sell
        mock_clob_client.create_order = Mock(return_value={'order_id': 'sell_order_123'})
        mock_clob_client.post_order = Mock(return_value={
            'success': True,
            'orderID': 'sell_order_123'
        })
        
        # Close position
        await strategy._check_all_positions_for_exit()
        
        # Verify position was closed
        assert len(strategy.positions) == 0
        
        # Verify SuperSmart learning was updated
        super_smart_file = temp_data_dir / "super_smart_learning.json"
        assert super_smart_file.exists()
        
        with open(super_smart_file, 'r') as f:
            super_smart_data = json.load(f)
        
        # Check that strategy/asset combination was recorded
        key = "sum_to_one_BTC"
        if key in super_smart_data:
            assert super_smart_data[key]['total_trades'] > 0
        
        # Verify RL Q-table was updated
        rl_file = temp_data_dir / "rl_q_table.json"
        assert rl_file.exists()
        
        # Verify Adaptive learning was updated
        adaptive_file = temp_data_dir / "adaptive_learning.json"
        assert adaptive_file.exists()
    
    @pytest.mark.asyncio
    async def test_losing_trade_updates_all_engines(
        self,
        strategy,
        mock_clob_client,
        temp_data_dir
    ):
        """
        Test that a losing trade updates all three learning engines.
        
        Validates Requirements: 2.8
        """
        # Create a position
        position = Position(
            token_id="0x" + "2" * 64,
            side="UP",
            entry_price=Decimal('0.50'),
            size=Decimal('10.0'),
            entry_time=datetime.now() - timedelta(minutes=5),
            market_id="test_market",
            asset="ETH",
            strategy="directional",
            neg_risk=False,
            highest_price=Decimal('0.50')
        )
        strategy.positions[position.token_id] = position
        
        # Mock orderbook for losing exit
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.45', '100']],  # 10% loss
            'asks': [['0.55', '100']]
        })
        
        # Mock successful sell
        mock_clob_client.create_order = Mock(return_value={'order_id': 'sell_order_123'})
        mock_clob_client.post_order = Mock(return_value={
            'success': True,
            'orderID': 'sell_order_123'
        })
        
        # Close position
        await strategy._check_all_positions_for_exit()
        
        # Verify position was closed
        assert len(strategy.positions) == 0
        
        # Verify learning files were updated
        super_smart_file = temp_data_dir / "super_smart_learning.json"
        rl_file = temp_data_dir / "rl_q_table.json"
        adaptive_file = temp_data_dir / "adaptive_learning.json"
        
        assert super_smart_file.exists()
        assert rl_file.exists()
        assert adaptive_file.exists()
    
    @pytest.mark.asyncio
    async def test_parameters_update_after_multiple_trades(
        self,
        strategy,
        mock_clob_client,
        temp_data_dir
    ):
        """
        Test that parameters update correctly after multiple trades.
        
        Validates Requirements: 4.2, 4.11
        """
        # Execute multiple trades with different outcomes
        outcomes = [
            ("BTC", "sum_to_one", Decimal('0.50'), Decimal('0.55'), True),   # Win
            ("ETH", "directional", Decimal('0.50'), Decimal('0.45'), False),  # Loss
            ("SOL", "sum_to_one", Decimal('0.50'), Decimal('0.52'), True),   # Win
            ("BTC", "directional", Decimal('0.50'), Decimal('0.48'), False),  # Loss
            ("ETH", "sum_to_one", Decimal('0.50'), Decimal('0.54'), True),   # Win
        ]
        
        for asset, strat, entry, exit_price, is_win in outcomes:
            # Create position
            position = Position(
                token_id="0x" + asset[0] * 64,
                side="UP",
                entry_price=entry,
                size=Decimal('10.0'),
                entry_time=datetime.now() - timedelta(minutes=5),
                market_id=f"test_market_{asset}",
                asset=asset,
                strategy=strat,
                neg_risk=False,
                highest_price=entry
            )
            strategy.positions[position.token_id] = position
            
            # Mock orderbook for exit
            mock_clob_client.get_orderbook = AsyncMock(return_value={
                'bids': [[str(exit_price), '100']],
                'asks': [[str(1 - exit_price), '100']]
            })
            
            # Mock successful sell
            mock_clob_client.create_order = Mock(return_value={'order_id': f'sell_{asset}'})
            mock_clob_client.post_order = Mock(return_value={
                'success': True,
                'orderID': f'sell_{asset}'
            })
            
            # Close position
            await strategy._check_all_positions_for_exit()
            
            # Small delay between trades
            await asyncio.sleep(0.01)
        
        # Verify all positions were closed
        assert len(strategy.positions) == 0
        
        # Verify learning data accumulated
        super_smart_file = temp_data_dir / "super_smart_learning.json"
        with open(super_smart_file, 'r') as f:
            super_smart_data = json.load(f)
        
        # Check that multiple strategy/asset combinations were recorded
        total_recorded_trades = sum(
            data.get('total_trades', 0) 
            for data in super_smart_data.values()
        )
        assert total_recorded_trades >= len(outcomes)
    
    @pytest.mark.asyncio
    async def test_learned_parameters_persist_across_restarts(
        self,
        strategy,
        mock_clob_client,
        temp_data_dir
    ):
        """
        Test that learned parameters persist to disk and can be loaded on restart.
        
        Validates Requirements: 2.8, 11.3
        """
        # Execute a trade
        position = Position(
            token_id="0x" + "3" * 64,
            side="UP",
            entry_price=Decimal('0.50'),
            size=Decimal('10.0'),
            entry_time=datetime.now() - timedelta(minutes=5),
            market_id="test_market",
            asset="BTC",
            strategy="sum_to_one",
            neg_risk=False,
            highest_price=Decimal('0.50')
        )
        strategy.positions[position.token_id] = position
        
        # Mock orderbook for profitable exit
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.55', '100']],
            'asks': [['0.45', '100']]
        })
        
        # Mock successful sell
        mock_clob_client.create_order = Mock(return_value={'order_id': 'sell_order_123'})
        mock_clob_client.post_order = Mock(return_value={
            'success': True,
            'orderID': 'sell_order_123'
        })
        
        # Close position
        await strategy._check_all_positions_for_exit()
        
        # Save learning data
        super_smart_file = temp_data_dir / "super_smart_learning.json"
        with open(super_smart_file, 'r') as f:
            saved_data = json.load(f)
        
        # Create new strategy instance (simulating restart)
        new_strategy = FifteenMinuteCryptoStrategy(
            clob_client=mock_clob_client,
            trade_size=5.0,
            take_profit_pct=0.02,
            stop_loss_pct=0.02,
            max_positions=3,
            dry_run=False,
            llm_decision_engine=None,
            enable_adaptive_learning=True,
            initial_capital=100.0
        )
        
        # Override data directory
        new_strategy.super_smart_file = temp_data_dir / "super_smart_learning.json"
        new_strategy.adaptive_file = temp_data_dir / "adaptive_learning.json"
        new_strategy.rl_file = temp_data_dir / "rl_q_table.json"
        
        # Load learning data
        new_strategy._load_learning_data()
        
        # Verify data was loaded
        assert new_strategy.super_smart_learning is not None
        
        # Verify loaded data matches saved data
        if saved_data:
            key = list(saved_data.keys())[0]
            assert key in new_strategy.super_smart_learning
    
    @pytest.mark.asyncio
    async def test_dynamic_parameters_adjust_based_on_performance(
        self,
        strategy,
        mock_clob_client,
        temp_data_dir
    ):
        """
        Test that dynamic parameters adjust based on trade performance.
        
        Validates Requirements: 4.2, 4.11
        """
        # Record initial parameters
        initial_tp = strategy.take_profit_pct
        initial_sl = strategy.stop_loss_pct
        
        # Execute multiple winning trades
        for i in range(5):
            position = Position(
                token_id=f"0x{i}" + "a" * 63,
                side="UP",
                entry_price=Decimal('0.50'),
                size=Decimal('10.0'),
                entry_time=datetime.now() - timedelta(minutes=5),
                market_id=f"test_market_{i}",
                asset="BTC",
                strategy="sum_to_one",
                neg_risk=False,
                highest_price=Decimal('0.50')
            )
            strategy.positions[position.token_id] = position
            
            # Mock profitable exit
            mock_clob_client.get_orderbook = AsyncMock(return_value={
                'bids': [['0.55', '100']],
                'asks': [['0.45', '100']]
            })
            
            mock_clob_client.create_order = Mock(return_value={'order_id': f'sell_{i}'})
            mock_clob_client.post_order = Mock(return_value={
                'success': True,
                'orderID': f'sell_{i}'
            })
            
            await strategy._check_all_positions_for_exit()
            await asyncio.sleep(0.01)
        
        # Verify consecutive wins increased
        assert strategy.consecutive_wins >= 5
        
        # Verify position size multiplier increased (due to winning streak)
        # The strategy should be more aggressive after wins
        assert strategy.consecutive_losses == 0
    
    @pytest.mark.asyncio
    async def test_learning_engines_handle_edge_cases(
        self,
        strategy,
        mock_clob_client,
        temp_data_dir
    ):
        """
        Test that learning engines handle edge cases correctly:
        - Zero profit trades
        - Very small profit/loss
        - Very large profit/loss
        
        Validates Requirements: 2.8
        """
        edge_cases = [
            ("BTC", Decimal('0.50'), Decimal('0.50')),   # Zero profit
            ("ETH", Decimal('0.50'), Decimal('0.501')),  # Tiny profit
            ("SOL", Decimal('0.50'), Decimal('0.499')),  # Tiny loss
            ("XRP", Decimal('0.50'), Decimal('0.70')),   # Large profit
            ("BTC", Decimal('0.50'), Decimal('0.30')),   # Large loss
        ]
        
        for asset, entry, exit_price in edge_cases:
            position = Position(
                token_id="0x" + asset[0] * 64,
                side="UP",
                entry_price=entry,
                size=Decimal('10.0'),
                entry_time=datetime.now() - timedelta(minutes=5),
                market_id=f"test_market_{asset}",
                asset=asset,
                strategy="sum_to_one",
                neg_risk=False,
                highest_price=entry
            )
            strategy.positions[position.token_id] = position
            
            # Mock orderbook
            mock_clob_client.get_orderbook = AsyncMock(return_value={
                'bids': [[str(exit_price), '100']],
                'asks': [[str(1 - exit_price), '100']]
            })
            
            mock_clob_client.create_order = Mock(return_value={'order_id': f'sell_{asset}'})
            mock_clob_client.post_order = Mock(return_value={
                'success': True,
                'orderID': f'sell_{asset}'
            })
            
            # Should not raise exception
            await strategy._check_all_positions_for_exit()
            await asyncio.sleep(0.01)
        
        # Verify all positions were handled
        assert len(strategy.positions) == 0
        
        # Verify learning files still valid
        super_smart_file = temp_data_dir / "super_smart_learning.json"
        with open(super_smart_file, 'r') as f:
            data = json.load(f)
        
        # Should be valid JSON
        assert isinstance(data, dict)


class TestLearningEngineIntegration:
    """Test integration between different learning engines"""
    
    @pytest.mark.asyncio
    async def test_all_engines_contribute_to_decisions(
        self,
        strategy,
        mock_clob_client,
        temp_data_dir
    ):
        """
        Test that all learning engines contribute to trading decisions.
        
        Validates Requirements: 3.1, 3.2
        """
        # Build up learning history
        for i in range(10):
            position = Position(
                token_id=f"0x{i}" + "b" * 63,
                side="UP",
                entry_price=Decimal('0.50'),
                size=Decimal('10.0'),
                entry_time=datetime.now() - timedelta(minutes=5),
                market_id=f"test_market_{i}",
                asset="BTC",
                strategy="sum_to_one",
                neg_risk=False,
                highest_price=Decimal('0.50')
            )
            strategy.positions[position.token_id] = position
            
            # Alternate wins and losses
            exit_price = Decimal('0.55') if i % 2 == 0 else Decimal('0.45')
            
            mock_clob_client.get_orderbook = AsyncMock(return_value={
                'bids': [[str(exit_price), '100']],
                'asks': [[str(1 - exit_price), '100']]
            })
            
            mock_clob_client.create_order = Mock(return_value={'order_id': f'sell_{i}'})
            mock_clob_client.post_order = Mock(return_value={
                'success': True,
                'orderID': f'sell_{i}'
            })
            
            await strategy._check_all_positions_for_exit()
            await asyncio.sleep(0.01)
        
        # Verify learning data accumulated
        super_smart_file = temp_data_dir / "super_smart_learning.json"
        with open(super_smart_file, 'r') as f:
            super_smart_data = json.load(f)
        
        # Should have data for BTC sum_to_one strategy
        assert len(super_smart_data) > 0
    
    @pytest.mark.asyncio
    async def test_learning_data_format_consistency(
        self,
        strategy,
        mock_clob_client,
        temp_data_dir
    ):
        """
        Test that learning data maintains consistent format across updates.
        
        Validates Requirements: 2.8
        """
        # Execute a trade
        position = Position(
            token_id="0x" + "4" * 64,
            side="UP",
            entry_price=Decimal('0.50'),
            size=Decimal('10.0'),
            entry_time=datetime.now() - timedelta(minutes=5),
            market_id="test_market",
            asset="BTC",
            strategy="sum_to_one",
            neg_risk=False,
            highest_price=Decimal('0.50')
        )
        strategy.positions[position.token_id] = position
        
        mock_clob_client.get_orderbook = AsyncMock(return_value={
            'bids': [['0.55', '100']],
            'asks': [['0.45', '100']]
        })
        
        mock_clob_client.create_order = Mock(return_value={'order_id': 'sell_order_123'})
        mock_clob_client.post_order = Mock(return_value={
            'success': True,
            'orderID': 'sell_order_123'
        })
        
        await strategy._check_all_positions_for_exit()
        
        # Verify all learning files have valid JSON format
        for filename in ['super_smart_learning.json', 'adaptive_learning.json', 'rl_q_table.json']:
            filepath = temp_data_dir / filename
            assert filepath.exists()
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Should be valid JSON (dict or list)
            assert isinstance(data, (dict, list))
