"""
Integration test for full arbitrage flow.

Tests the complete end-to-end arbitrage execution:
detection → AI safety → order execution → merge → profit

Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from web3 import Web3
from eth_account import Account

from src.internal_arbitrage_engine import InternalArbitrageEngine
from src.ai_safety_guard import AISafetyGuard
from src.kelly_position_sizer import KellyPositionSizer
from src.order_manager import OrderManager
from src.position_merger import PositionMerger
from src.transaction_manager import TransactionManager
from src.models import Market, Opportunity, TradeResult, SafetyDecision


@pytest.fixture
def mock_web3():
    """Create mock Web3 instance"""
    web3 = Mock(spec=Web3)
    web3.eth = Mock()
    web3.eth.gas_price = 50000000000  # 50 gwei
    web3.eth.get_transaction_count = Mock(return_value=0)
    web3.eth.send_raw_transaction = Mock(return_value=b'\x00' * 32)
    web3.eth.wait_for_transaction_receipt = Mock(return_value={
        'status': 1,
        'transactionHash': b'\x00' * 32,
        'gasUsed': 200000
    })
    web3.eth.contract = Mock()
    return web3


@pytest.fixture
def mock_wallet():
    """Create mock wallet"""
    # Create a real account for signing (but won't be used in mocked tests)
    account = Account.create()
    return account


@pytest.fixture
def mock_clob_client():
    """Create mock CLOB client"""
    return Mock()


@pytest.fixture
def mock_tx_manager():
    """Create mock transaction manager"""
    mock = Mock(spec=TransactionManager)
    mock.get_pending_count = Mock(return_value=0)
    mock.send_transaction = AsyncMock(return_value="0x" + "a" * 64)
    mock.wait_for_confirmation = AsyncMock(return_value={
        'status': 1,
        'transactionHash': "0x" + "a" * 64
    })
    return mock


@pytest.fixture
def mock_ctf_contract():
    """Create mock CTF contract"""
    contract = Mock()
    contract.functions = Mock()
    
    # Mock balanceOf
    balance_of = Mock()
    balance_of.call = Mock(return_value=2000000)  # 2.0 tokens (6 decimals)
    contract.functions.balanceOf = Mock(return_value=balance_of)
    
    # Mock mergePositions
    merge_positions = Mock()
    merge_positions.estimate_gas = Mock(return_value=250000)
    merge_positions.build_transaction = Mock(return_value={
        'from': '0x' + '1' * 40,
        'gas': 300000,
        'gasPrice': 50000000000,
        'nonce': 0,
        'to': '0x' + '2' * 40,
        'data': '0x' + 'a' * 128
    })
    contract.functions.mergePositions = Mock(return_value=merge_positions)
    
    return contract


@pytest.fixture
def mock_usdc_contract():
    """Create mock USDC contract"""
    contract = Mock()
    contract.functions = Mock()
    
    # Mock balanceOf - will return different values for before/after merge
    balance_of = Mock()
    balance_of.call = Mock(side_effect=[
        100000000,  # 100 USDC before merge
        101000000   # 101 USDC after merge (redeemed 1 USDC)
    ])
    contract.functions.balanceOf = Mock(return_value=balance_of)
    
    return contract


@pytest.fixture
def position_merger(mock_web3, mock_wallet, mock_ctf_contract, mock_usdc_contract):
    """Create PositionMerger instance with mocked contracts"""
    # Mock contract creation
    def mock_contract(address, abi):
        if 'mergePositions' in abi:
            return mock_ctf_contract
        else:
            return mock_usdc_contract
    
    mock_web3.eth.contract = mock_contract
    mock_web3.to_checksum_address = Web3.to_checksum_address
    
    merger = PositionMerger(
        web3=mock_web3,
        ctf_contract_address="0x" + "2" * 40,
        usdc_address="0x" + "3" * 40,
        wallet=mock_wallet
    )
    
    return merger


@pytest.fixture
def order_manager(mock_clob_client, mock_tx_manager):
    """Create OrderManager instance"""
    return OrderManager(
        clob_client=mock_clob_client,
        tx_manager=mock_tx_manager
    )


@pytest.fixture
def ai_safety_guard():
    """Create AISafetyGuard instance"""
    return AISafetyGuard(
        nvidia_api_key="test_key",
        nvidia_api_url="https://test.nvidia.com/api"
    )


@pytest.fixture
def kelly_sizer():
    """Create KellyPositionSizer instance"""
    from src.kelly_position_sizer import PositionSizingConfig
    config = PositionSizingConfig(
        max_kelly_fraction=Decimal('0.05'),
        small_bankroll_threshold=Decimal('100'),
        small_bankroll_min=Decimal('0.10'),
        small_bankroll_max=Decimal('1.00'),
        large_bankroll_max=Decimal('5.00')
    )
    return KellyPositionSizer(config=config)


@pytest.fixture
def arbitrage_engine(
    mock_clob_client,
    order_manager,
    position_merger,
    ai_safety_guard,
    kelly_sizer
):
    """Create InternalArbitrageEngine instance"""
    return InternalArbitrageEngine(
        clob_client=mock_clob_client,
        order_manager=order_manager,
        position_merger=position_merger,
        ai_safety_guard=ai_safety_guard,
        kelly_sizer=kelly_sizer,
        current_balance_getter=lambda: Decimal('100.0'),
        current_gas_price_getter=lambda: 50,
        pending_tx_count_getter=lambda: 0
    )


@pytest.fixture
def sample_market():
    """Create sample market for testing"""
    return Market(
        market_id="market_btc_15min",
        question="Will BTC be above $95,000 in 15 minutes?",
        asset="BTC",
        outcomes=["YES", "NO"],
        yes_price=Decimal('0.48'),
        no_price=Decimal('0.47'),
        yes_token_id="0x" + "1" * 64,
        no_token_id="0x" + "2" * 64,
        volume=Decimal('10000'),
        liquidity=Decimal('5000'),
        end_time=datetime.now() + timedelta(minutes=15),
        resolution_source="CEX"
    )


class TestFullArbitrageFlow:
    """Test complete arbitrage flow from detection to profit"""
    
    @pytest.mark.asyncio
    async def test_successful_arbitrage_flow(
        self,
        arbitrage_engine,
        sample_market,
        order_manager,
        position_merger
    ):
        """
        Test successful end-to-end arbitrage execution.
        
        Flow: detection → AI safety → order execution → merge → profit
        
        Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
        """
        # Step 1: Detection (Requirements 1.1, 1.2)
        opportunities = await arbitrage_engine.scan_opportunities([sample_market])
        
        assert len(opportunities) > 0, "Should detect arbitrage opportunity"
        opportunity = opportunities[0]
        
        assert opportunity.market_id == sample_market.market_id
        assert opportunity.strategy == "internal_arbitrage"
        assert opportunity.expected_profit > 0
        assert opportunity.profit_percentage >= Decimal('0.005')  # >= 0.5%
        
        # Step 2: Mock AI Safety Check (Requirement 7.1-7.6)
        with patch.object(
            arbitrage_engine.ai_safety_guard,
            'validate_trade',
            new=AsyncMock(return_value=SafetyDecision(
                approved=True,
                reason="All safety checks passed",
                timestamp=datetime.now(),
                checks_performed={'nvidia_api': True},
                fallback_used=False
            ))
        ):
            # Step 3: Mock Order Submission (Requirements 1.3, 1.4, 6.1, 6.3)
            with patch.object(
                order_manager,
                '_submit_order',
                new=AsyncMock(side_effect=lambda order: {
                    'filled': True,
                    'fill_price': order.price,
                    'tx_hash': f"0x{'a' * 64}"
                })
            ):
                # Step 4: Mock Position Merge (Requirements 1.5, 1.6)
                # Note: The engine calls with market_id and amount
                async def mock_merge(market_id=None, condition_id=None, yes_token_id=None, 
                                   no_token_id=None, amount=None):
                    return {
                        'status': 1,
                        'transactionHash': bytes.fromhex('b' * 64),
                        'gasUsed': 250000
                    }
                
                with patch.object(
                    position_merger,
                    'merge_positions',
                    new=AsyncMock(side_effect=mock_merge)
                ):
                    # Execute the trade
                    result = await arbitrage_engine.execute(
                        opportunity=opportunity,
                        market=sample_market,
                        bankroll=Decimal('100.0')
                    )
        
        # Verify trade result
        assert result.status == "success"
        assert result.yes_filled is True
        assert result.no_filled is True
        assert result.yes_fill_price == opportunity.yes_price
        assert result.no_fill_price == opportunity.no_price
        assert result.actual_profit > 0
        assert result.net_profit > 0  # After gas costs
        
        # Verify both orders were created and filled (Requirement 1.3, 1.4)
        assert result.yes_order_id is not None
        assert result.no_order_id is not None
        assert result.yes_tx_hash is not None
        assert result.no_tx_hash is not None
        
        # Verify merge occurred (Requirement 1.5, 1.6)
        assert result.merge_tx_hash is not None
    
    @pytest.mark.asyncio
    async def test_arbitrage_flow_ai_safety_rejection(
        self,
        arbitrage_engine,
        sample_market
    ):
        """
        Test arbitrage flow when AI safety guard rejects trade.
        
        Validates Requirements: 7.1-7.6
        """
        # Scan for opportunities
        opportunities = await arbitrage_engine.scan_opportunities([sample_market])
        assert len(opportunities) > 0
        opportunity = opportunities[0]
        
        # Mock AI Safety rejection
        with patch.object(
            arbitrage_engine.ai_safety_guard,
            'validate_trade',
            new=AsyncMock(return_value=SafetyDecision(
                approved=False,
                reason="High volatility detected",
                timestamp=datetime.now(),
                checks_performed={'volatility_check': True},
                fallback_used=False
            ))
        ):
            # Execute the trade
            result = await arbitrage_engine.execute(
                opportunity=opportunity,
                market=sample_market,
                bankroll=Decimal('100.0')
            )
        
        # Verify trade was rejected
        assert result.status == "failed"
        assert "AI safety check failed" in result.error_message
        assert result.yes_filled is False
        assert result.no_filled is False
        assert result.actual_profit == 0
    
    @pytest.mark.asyncio
    async def test_arbitrage_flow_fok_order_failure(
        self,
        arbitrage_engine,
        sample_market,
        order_manager
    ):
        """
        Test arbitrage flow when FOK orders fail to fill.
        
        Validates Requirements: 1.4, 6.1, 6.3 (atomic execution)
        """
        # Scan for opportunities
        opportunities = await arbitrage_engine.scan_opportunities([sample_market])
        assert len(opportunities) > 0
        opportunity = opportunities[0]
        
        # Mock AI Safety approval
        with patch.object(
            arbitrage_engine.ai_safety_guard,
            'validate_trade',
            new=AsyncMock(return_value=SafetyDecision(
                approved=True,
                reason="All safety checks passed",
                timestamp=datetime.now(),
                checks_performed={'nvidia_api': True},
                fallback_used=False
            ))
        ):
            # Mock order submission - neither order fills
            with patch.object(
                order_manager,
                '_submit_order',
                new=AsyncMock(return_value={
                    'filled': False,
                    'fill_price': None,
                    'tx_hash': None
                })
            ):
                # Execute the trade
                result = await arbitrage_engine.execute(
                    opportunity=opportunity,
                    market=sample_market,
                    bankroll=Decimal('100.0')
                )
        
        # Verify trade failed atomically (neither filled)
        assert result.status == "failed"
        assert result.yes_filled is False
        assert result.no_filled is False
        assert "FOK orders failed to fill" in result.error_message
        assert result.actual_profit == 0
    
    @pytest.mark.asyncio
    async def test_arbitrage_flow_with_kelly_sizing(
        self,
        arbitrage_engine,
        sample_market,
        order_manager,
        position_merger
    ):
        """
        Test arbitrage flow with Kelly Criterion position sizing.
        
        Validates Requirements: 11.1-11.4
        """
        # Scan for opportunities
        opportunities = await arbitrage_engine.scan_opportunities([sample_market])
        assert len(opportunities) > 0
        opportunity = opportunities[0]
        
        # Test with small bankroll (< $100)
        small_bankroll = Decimal('50.0')
        
        # Mock AI Safety approval
        with patch.object(
            arbitrage_engine.ai_safety_guard,
            'validate_trade',
            new=AsyncMock(return_value=SafetyDecision(
                approved=True,
                reason="All safety checks passed",
                timestamp=datetime.now(),
                checks_performed={'nvidia_api': True},
                fallback_used=False
            ))
        ):
            # Mock order submission
            with patch.object(
                order_manager,
                '_submit_order',
                new=AsyncMock(side_effect=lambda order: {
                    'filled': True,
                    'fill_price': order.price,
                    'tx_hash': f"0x{'a' * 64}"
                })
            ):
                # Mock position merge
                async def mock_merge(market_id=None, condition_id=None, yes_token_id=None, 
                                   no_token_id=None, amount=None):
                    return {
                        'status': 1,
                        'transactionHash': bytes.fromhex('b' * 64),
                        'gasUsed': 250000
                    }
                
                with patch.object(
                    position_merger,
                    'merge_positions',
                    new=AsyncMock(side_effect=mock_merge)
                ):
                    # Execute with small bankroll
                    result = await arbitrage_engine.execute(
                        opportunity=opportunity,
                        market=sample_market,
                        bankroll=small_bankroll
                    )
        
        # Verify position size was calculated and applied
        assert result.status == "success"
        assert opportunity.position_size > 0
        # For small bankroll, position size should be between $0.10 and $1.00
        assert Decimal('0.10') <= opportunity.position_size <= Decimal('1.00')
    
    @pytest.mark.asyncio
    async def test_arbitrage_flow_profit_calculation(
        self,
        arbitrage_engine,
        sample_market,
        order_manager,
        position_merger
    ):
        """
        Test accurate profit calculation throughout arbitrage flow.
        
        Validates Requirements: 2.4, 1.6
        """
        # Scan for opportunities
        opportunities = await arbitrage_engine.scan_opportunities([sample_market])
        assert len(opportunities) > 0
        opportunity = opportunities[0]
        
        # Record expected profit
        expected_profit = opportunity.expected_profit
        
        # Mock AI Safety approval
        with patch.object(
            arbitrage_engine.ai_safety_guard,
            'validate_trade',
            new=AsyncMock(return_value=SafetyDecision(
                approved=True,
                reason="All safety checks passed",
                timestamp=datetime.now(),
                checks_performed={'nvidia_api': True},
                fallback_used=False
            ))
        ):
            # Mock order submission with exact prices
            with patch.object(
                order_manager,
                '_submit_order',
                new=AsyncMock(side_effect=lambda order: {
                    'filled': True,
                    'fill_price': order.price,  # Fill at exact order price
                    'tx_hash': f"0x{'a' * 64}"
                })
            ):
                # Mock position merge
                async def mock_merge(market_id=None, condition_id=None, yes_token_id=None, 
                                   no_token_id=None, amount=None):
                    return {
                        'status': 1,
                        'transactionHash': bytes.fromhex('b' * 64),
                        'gasUsed': 250000
                    }
                
                with patch.object(
                    position_merger,
                    'merge_positions',
                    new=AsyncMock(side_effect=mock_merge)
                ):
                    # Execute the trade
                    result = await arbitrage_engine.execute(
                        opportunity=opportunity,
                        market=sample_market,
                        bankroll=Decimal('100.0')
                    )
        
        # Verify profit calculation
        assert result.status == "success"
        
        # Actual profit should be close to expected profit
        # (may differ slightly due to position sizing)
        position_size = opportunity.position_size
        expected_profit_scaled = expected_profit * position_size
        
        # Allow 1% tolerance for rounding
        tolerance = expected_profit_scaled * Decimal('0.01')
        assert abs(result.actual_profit - expected_profit_scaled) <= tolerance
        
        # Net profit should be actual profit minus gas costs
        assert result.net_profit == result.actual_profit - result.gas_cost
        assert result.net_profit > 0


class TestArbitrageDetection:
    """Test arbitrage opportunity detection"""
    
    @pytest.mark.asyncio
    async def test_detect_profitable_opportunity(self, arbitrage_engine):
        """
        Test detection of profitable arbitrage opportunity.
        
        Validates Requirements: 1.1, 1.2
        """
        # Create market with profitable arbitrage
        market = Market(
            market_id="market_test",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.48'),  # YES at 48¢
            no_price=Decimal('0.47'),   # NO at 47¢
            yes_token_id="0x" + "1" * 64,
            no_token_id="0x" + "2" * 64,
            # Total cost ~0.95 + fees ~0.03 = ~0.98 < $1.00
            volume=Decimal('1000'),
            liquidity=Decimal('500'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        opportunities = await arbitrage_engine.scan_opportunities([market])
        
        assert len(opportunities) == 1
        opp = opportunities[0]
        
        # Verify opportunity details
        assert opp.market_id == market.market_id
        assert opp.strategy == "internal_arbitrage"
        assert opp.yes_price == Decimal('0.48')
        assert opp.no_price == Decimal('0.47')
        assert opp.expected_profit > 0
        assert opp.profit_percentage >= Decimal('0.005')  # >= 0.5%
    
    @pytest.mark.asyncio
    async def test_skip_unprofitable_opportunity(self, arbitrage_engine):
        """
        Test that unprofitable opportunities are skipped.
        
        Validates Requirements: 1.2, 2.4
        """
        # Create market with no arbitrage (prices too high)
        market = Market(
            market_id="market_test",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.52'),  # YES at 52¢
            no_price=Decimal('0.51'),   # NO at 51¢
            yes_token_id="0x" + "1" * 64,
            no_token_id="0x" + "2" * 64,
            # Total cost ~1.03 + fees > $1.00 (not profitable)
            volume=Decimal('1000'),
            liquidity=Decimal('500'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        opportunities = await arbitrage_engine.scan_opportunities([market])
        
        # Should not detect any opportunities
        assert len(opportunities) == 0
    
    @pytest.mark.asyncio
    async def test_skip_below_threshold_opportunity(self, arbitrage_engine):
        """
        Test that opportunities below profit threshold are skipped.
        
        Validates Requirements: 2.4
        """
        # Create market with very small profit (< 0.5%)
        market = Market(
            market_id="market_test",
            question="Will BTC be above $95,000 in 15 minutes?",
            asset="BTC",
            outcomes=["YES", "NO"],
            yes_price=Decimal('0.495'),  # YES at 49.5¢
            no_price=Decimal('0.495'),   # NO at 49.5¢
            yes_token_id="0x" + "1" * 64,
            no_token_id="0x" + "2" * 64,
            # Total cost ~0.99 + fees ~0.03 = ~1.02 (loss)
            volume=Decimal('1000'),
            liquidity=Decimal('500'),
            end_time=datetime.now() + timedelta(minutes=15),
            resolution_source="CEX"
        )
        
        opportunities = await arbitrage_engine.scan_opportunities([market])
        
        # Should not detect any opportunities
        assert len(opportunities) == 0
