"""
Unit tests for Fund Manager.

Tests specific scenarios and edge cases for fund management operations.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from web3 import Web3

from src.fund_manager import (
    FundManager,
    InsufficientBalanceError,
    DepositError,
    WithdrawalError,
    FundManagerError
)


def create_test_fund_manager(dry_run=False):
    """Create a FundManager instance for testing."""
    mock_web3 = Mock(spec=Web3)
    mock_web3.eth = Mock()
    mock_web3.eth.gas_price = 50000000000
    mock_web3.eth.get_transaction_count = Mock(return_value=0)
    mock_web3.eth.wait_for_transaction_receipt = Mock(
        return_value={'status': 1, 'transactionHash': b'\x00' * 32}
    )
    mock_web3.to_checksum_address = Web3.to_checksum_address
    
    mock_wallet = Mock()
    mock_wallet.address = "0x1234567890123456789012345678901234567890"
    mock_wallet.sign_transaction = Mock(
        return_value=Mock(raw_transaction=b'\x00' * 100)
    )
    
    fund_manager = FundManager(
        web3=mock_web3,
        wallet=mock_wallet,
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        ctf_exchange_address="0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
        min_balance=Decimal("50.0"),
        target_balance=Decimal("100.0"),
        withdraw_limit=Decimal("500.0"),
        dry_run=dry_run
    )
    
    return fund_manager


def _setup_balance_mocks(fund_manager, eoa_raw, polymarket_usdc):
    """
    Helper to mock both balance sources.
    
    Args:
        fund_manager: FundManager instance
        eoa_raw: Raw USDC balance in smallest units (6 decimals)
        polymarket_usdc: Polymarket balance as Decimal (already in USDC units)
    """
    # Mock EOA balance (usdc_contract.functions.balanceOf)
    fund_manager.usdc_contract.functions.balanceOf = Mock(
        return_value=Mock(call=Mock(return_value=eoa_raw))
    )
    # Mock Polymarket balance (replaces old ctf_exchange mock)
    fund_manager._get_polymarket_balance_from_api = AsyncMock(return_value=polymarket_usdc)


@pytest.mark.asyncio
async def test_check_balance_success():
    """Test successful balance check."""
    fund_manager = create_test_fund_manager()
    
    # Mock balance sources
    _setup_balance_mocks(fund_manager, 100_000_000, Decimal("50.0"))  # EOA=100, Poly=50
    
    eoa_balance, proxy_balance = await fund_manager.check_balance()
    
    assert eoa_balance == Decimal("100.0")
    assert proxy_balance == Decimal("50.0")


@pytest.mark.asyncio
async def test_auto_deposit_dry_run():
    """Test auto-deposit in dry run mode."""
    fund_manager = create_test_fund_manager(dry_run=True)
    
    # Mock balances: EOA=200, Proxy=30 (below minimum)
    _setup_balance_mocks(fund_manager, 200_000_000, Decimal("30.0"))
    
    result = await fund_manager.auto_deposit()
    
    # In dry run, should return None
    assert result is None


@pytest.mark.asyncio
async def test_auto_deposit_insufficient_balance():
    """Test auto-deposit with insufficient EOA balance."""
    fund_manager = create_test_fund_manager(dry_run=False)
    
    # Mock balances: EOA=20, Proxy=30 (need 70 to reach target 100)
    _setup_balance_mocks(fund_manager, 20_000_000, Decimal("30.0"))
    
    with pytest.raises(InsufficientBalanceError) as exc_info:
        await fund_manager.auto_deposit()
    
    assert "Insufficient EOA balance" in str(exc_info.value)


@pytest.mark.asyncio
async def test_auto_deposit_no_deposit_needed():
    """Test auto-deposit when balance is already sufficient."""
    fund_manager = create_test_fund_manager()
    
    # Mock balances: EOA=200, Proxy=150 (above target)
    _setup_balance_mocks(fund_manager, 200_000_000, Decimal("150.0"))
    
    result = await fund_manager.auto_deposit()
    
    # Should return None (no deposit needed)
    assert result is None


@pytest.mark.asyncio
async def test_auto_withdraw_dry_run():
    """Test auto-withdrawal in dry run mode."""
    fund_manager = create_test_fund_manager(dry_run=True)
    
    # Mock balances: EOA=100, Proxy=600 (above withdrawal limit)
    _setup_balance_mocks(fund_manager, 100_000_000, Decimal("600.0"))
    
    result = await fund_manager.auto_withdraw()
    
    # In dry run, should return None
    assert result is None


@pytest.mark.asyncio
async def test_auto_withdraw_no_withdrawal_needed():
    """Test auto-withdrawal when balance is below or at target."""
    fund_manager = create_test_fund_manager()
    
    # Mock balances: EOA=100, Proxy=100 (at target, no withdrawal needed)
    _setup_balance_mocks(fund_manager, 100_000_000, Decimal("100.0"))
    
    result = await fund_manager.auto_withdraw()
    
    # Should return None (no withdrawal needed)
    assert result is None


@pytest.mark.asyncio
async def test_cross_chain_deposit_unsupported_chain():
    """Test cross-chain deposit with unsupported chain."""
    fund_manager = create_test_fund_manager()
    
    with pytest.raises(FundManagerError) as exc_info:
        await fund_manager.cross_chain_deposit(
            source_chain="bitcoin",
            token_address="0x" + "0" * 40,
            amount=Decimal("100.0")
        )
    
    assert "Unsupported chain" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cross_chain_deposit_supported_chains():
    """Test that all supported chains are recognized."""
    fund_manager = create_test_fund_manager(dry_run=True)
    
    supported_chains = ["ethereum", "polygon", "arbitrum", "optimism"]
    
    for chain in supported_chains:
        # Should not raise error
        result = await fund_manager.cross_chain_deposit(
            source_chain=chain,
            token_address="0x" + "0" * 40,
            amount=Decimal("100.0")
        )
        
        # In dry run, should return None
        assert result is None


@pytest.mark.asyncio
async def test_cross_chain_deposit_polygon_usdc_direct():
    """Test that Polygon USDC uses direct deposit."""
    fund_manager = create_test_fund_manager(dry_run=False)
    
    # Mock balances
    _setup_balance_mocks(fund_manager, 200_000_000, Decimal("30.0"))
    
    # Mock auto_deposit
    original_auto_deposit = fund_manager.auto_deposit
    auto_deposit_called = False
    
    async def mock_auto_deposit(amount=None):
        nonlocal auto_deposit_called
        auto_deposit_called = True
        return {'transactionHash': b'\x00' * 32, 'status': 1}
    
    fund_manager.auto_deposit = mock_auto_deposit
    
    result = await fund_manager.cross_chain_deposit(
        source_chain="polygon",
        token_address=fund_manager.usdc_address,
        amount=Decimal("50.0")
    )
    
    # Should call auto_deposit
    assert auto_deposit_called
    assert result is not None
    assert result.get("type") == "direct_deposit"


@pytest.mark.asyncio
async def test_cross_chain_deposit_no_1inch_api_key():
    """Test cross-chain deposit without 1inch API key."""
    fund_manager = create_test_fund_manager(dry_run=False)
    fund_manager.oneinch_api_key = None
    
    # Mock balances
    _setup_balance_mocks(fund_manager, 200_000_000, Decimal("30.0"))
    
    # Try cross-chain deposit from Ethereum (not Polygon)
    with pytest.raises(FundManagerError) as exc_info:
        await fund_manager.cross_chain_deposit(
            source_chain="ethereum",
            token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            amount=Decimal("100.0")
        )
    
    assert "1inch API key required" in str(exc_info.value)


def test_supported_chains_configuration():
    """Test that supported chains are correctly configured."""
    assert "ethereum" in FundManager.SUPPORTED_CHAINS
    assert "polygon" in FundManager.SUPPORTED_CHAINS
    assert "arbitrum" in FundManager.SUPPORTED_CHAINS
    assert "optimism" in FundManager.SUPPORTED_CHAINS
    
    assert FundManager.SUPPORTED_CHAINS["ethereum"] == 1
    assert FundManager.SUPPORTED_CHAINS["polygon"] == 137
    assert FundManager.SUPPORTED_CHAINS["arbitrum"] == 42161
    assert FundManager.SUPPORTED_CHAINS["optimism"] == 10


def test_usdc_addresses_configuration():
    """Test that USDC addresses are configured for all chains."""
    for chain_name, chain_id in FundManager.SUPPORTED_CHAINS.items():
        assert chain_id in FundManager.USDC_ADDRESSES
        usdc_address = FundManager.USDC_ADDRESSES[chain_id]
        assert Web3.is_address(usdc_address)
        assert usdc_address.startswith("0x")
        assert len(usdc_address) == 42


@pytest.mark.asyncio
async def test_balance_check_decimal_precision():
    """Test that balance check maintains decimal precision."""
    fund_manager = create_test_fund_manager()
    
    # Mock balances with precise values
    _setup_balance_mocks(fund_manager, 123_456_789, Decimal("987.654321"))
    
    eoa_balance, proxy_balance = await fund_manager.check_balance()
    
    # Verify precision is maintained
    assert eoa_balance == Decimal("123.456789")
    assert proxy_balance == Decimal("987.654321")


@pytest.mark.asyncio
async def test_deposit_amount_calculation():
    """Test deposit amount calculation."""
    fund_manager = create_test_fund_manager(dry_run=True)
    
    # Mock balances: Proxy=25 (need 75 to reach target 100)
    _setup_balance_mocks(fund_manager, 200_000_000, Decimal("25.0"))
    
    # Execute deposit
    await fund_manager.auto_deposit()
    
    # Verify calculation
    eoa, proxy = await fund_manager.check_balance()
    expected_deposit = fund_manager.target_balance - proxy
    assert expected_deposit == Decimal("75.0")


@pytest.mark.asyncio
async def test_withdrawal_amount_calculation():
    """Test withdrawal amount calculation."""
    fund_manager = create_test_fund_manager(dry_run=True)
    
    # Mock balances: Proxy=600 (withdraw 500 to reach target 100)
    _setup_balance_mocks(fund_manager, 100_000_000, Decimal("600.0"))
    
    # Execute withdrawal
    await fund_manager.auto_withdraw()
    
    # Verify calculation
    eoa, proxy = await fund_manager.check_balance()
    expected_withdrawal = proxy - fund_manager.target_balance
    assert expected_withdrawal == Decimal("500.0")
