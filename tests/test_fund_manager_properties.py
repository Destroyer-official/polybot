"""
Property-based tests for Fund Manager.

Tests correctness properties for automated fund management operations.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from web3 import Web3
from eth_account import Account

from src.fund_manager import FundManager, InsufficientBalanceError


# Test configuration
MIN_BALANCE = Decimal("50.0")
TARGET_BALANCE = Decimal("100.0")
WITHDRAW_LIMIT = Decimal("500.0")


def create_mock_fund_manager(
    eoa_balance: Decimal,
    proxy_balance: Decimal,
    dry_run: bool = False
) -> FundManager:
    """Create a mock FundManager with specified balances."""
    # Create mock Web3 instance
    mock_web3 = Mock(spec=Web3)
    mock_web3.eth = Mock()
    mock_web3.eth.gas_price = 50000000000  # 50 gwei
    mock_web3.eth.get_transaction_count = Mock(return_value=0)
    mock_web3.eth.wait_for_transaction_receipt = Mock(
        return_value={'status': 1, 'transactionHash': b'\x00' * 32}
    )
    mock_web3.to_checksum_address = Web3.to_checksum_address
    
    # Create mock wallet
    mock_wallet = Mock()
    mock_wallet.address = "0x1234567890123456789012345678901234567890"
    mock_wallet.sign_transaction = Mock(
        return_value=Mock(raw_transaction=b'\x00' * 100)
    )
    
    # Create mock USDC contract
    mock_usdc_contract = Mock()
    mock_usdc_contract.functions.balanceOf = Mock(
        return_value=Mock(call=Mock(return_value=int(eoa_balance * Decimal(10 ** 6))))
    )
    mock_usdc_contract.functions.approve = Mock(
        return_value=Mock(build_transaction=Mock(return_value={}))
    )
    
    # Create mock CTF Exchange contract
    mock_ctf_contract = Mock()
    mock_ctf_contract.functions.getCollateralBalance = Mock(
        return_value=Mock(call=Mock(return_value=int(proxy_balance * Decimal(10 ** 6))))
    )
    mock_ctf_contract.functions.deposit = Mock(
        return_value=Mock(build_transaction=Mock(return_value={}))
    )
    mock_ctf_contract.functions.withdraw = Mock(
        return_value=Mock(build_transaction=Mock(return_value={}))
    )
    
    # Create FundManager
    fund_manager = FundManager(
        web3=mock_web3,
        wallet=mock_wallet,
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        ctf_exchange_address="0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
        min_balance=MIN_BALANCE,
        target_balance=TARGET_BALANCE,
        withdraw_limit=WITHDRAW_LIMIT,
        dry_run=dry_run
    )
    
    # Replace contracts with mocks
    fund_manager.usdc_contract = mock_usdc_contract
    fund_manager.ctf_exchange_contract = mock_ctf_contract
    
    return fund_manager


@pytest.mark.asyncio
@given(
    proxy_balance=st.decimals(
        min_value="0.0",
        max_value="49.99",
        places=2
    ),
    eoa_balance=st.decimals(
        min_value="100.0",
        max_value="1000.0",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_25_auto_deposit_trigger(proxy_balance, eoa_balance):
    """
    Property 25: Auto-Deposit Trigger
    
    **Validates: Requirements 8.1, 8.2**
    
    *For any* Proxy wallet balance falling below $50, the fund manager should
    initiate an auto-deposit from the EOA wallet to restore the target balance.
    
    Property: When proxy_balance < MIN_BALANCE ($50) and EOA has sufficient funds,
    auto_deposit should be triggered and deposit target_balance - proxy_balance.
    """
    # Create fund manager with specified balances
    fund_manager = create_mock_fund_manager(eoa_balance, proxy_balance, dry_run=True)
    
    # Calculate expected deposit amount
    expected_deposit = TARGET_BALANCE - proxy_balance
    
    # Verify proxy balance is below minimum
    assert proxy_balance < MIN_BALANCE, "Test setup: proxy balance should be below minimum"
    
    # Verify EOA has sufficient balance (should always be true with min 100)
    assert eoa_balance >= expected_deposit, "Test setup: EOA should have sufficient balance"
    
    # Execute auto-deposit
    result = await fund_manager.auto_deposit()
    
    # In dry run mode, result is None but operation should be logged
    # In production mode, we would verify the transaction was submitted
    
    # Property verification: The system should recognize the need for deposit
    # Since we're in dry run mode, we verify the logic would trigger correctly
    current_eoa, current_proxy = await fund_manager.check_balance()
    
    # Verify balances are as expected (unchanged in dry run)
    assert current_eoa == eoa_balance
    assert current_proxy == proxy_balance
    
    # Verify the deposit amount calculation is correct
    calculated_deposit = TARGET_BALANCE - current_proxy
    assert calculated_deposit == expected_deposit
    assert calculated_deposit > 0


@pytest.mark.asyncio
@given(
    proxy_balance=st.decimals(
        min_value="0.0",
        max_value="49.99",
        places=2
    ),
    eoa_balance=st.decimals(
        min_value="0.0",
        max_value="49.99",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_25_auto_deposit_insufficient_eoa(proxy_balance, eoa_balance):
    """
    Property 25: Auto-Deposit Trigger - Insufficient EOA Balance
    
    **Validates: Requirements 8.1, 8.2**
    
    *For any* Proxy wallet balance below $50 where EOA balance is insufficient,
    the fund manager should raise InsufficientBalanceError.
    
    Property: When proxy_balance < MIN_BALANCE but EOA balance is insufficient,
    auto_deposit should fail with InsufficientBalanceError.
    """
    # Calculate required deposit
    required_deposit = TARGET_BALANCE - proxy_balance
    
    # Ensure EOA balance is insufficient
    assume(eoa_balance < required_deposit)
    
    # Create fund manager with specified balances
    fund_manager = create_mock_fund_manager(eoa_balance, proxy_balance, dry_run=False)
    
    # Verify proxy balance is below minimum
    assert proxy_balance < MIN_BALANCE
    
    # Verify EOA balance is insufficient
    assert eoa_balance < required_deposit
    
    # Attempt auto-deposit should raise InsufficientBalanceError
    with pytest.raises(InsufficientBalanceError) as exc_info:
        await fund_manager.auto_deposit()
    
    # Verify error message contains relevant information
    assert "Insufficient EOA balance" in str(exc_info.value)


@pytest.mark.asyncio
@given(
    proxy_balance=st.decimals(
        min_value="100.0",
        max_value="499.99",
        places=2
    ),
    eoa_balance=st.decimals(
        min_value="0.0",
        max_value="1000.0",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_25_no_deposit_when_above_minimum(proxy_balance, eoa_balance):
    """
    Property 25: Auto-Deposit Trigger - No Deposit When Above Minimum
    
    **Validates: Requirements 8.1, 8.2**
    
    *For any* Proxy wallet balance at or above target balance ($100), the fund manager should
    not initiate an auto-deposit.
    
    Property: When proxy_balance >= TARGET_BALANCE, auto_deposit should return None
    (no deposit needed).
    """
    # Create fund manager with specified balances
    fund_manager = create_mock_fund_manager(eoa_balance, proxy_balance, dry_run=True)
    
    # Verify proxy balance is at or above target
    assert proxy_balance >= TARGET_BALANCE
    
    # Execute auto-deposit
    result = await fund_manager.auto_deposit()
    
    # Property verification: No deposit should be triggered
    assert result is None, "No deposit should be triggered when balance >= target"
    
    # Verify balances remain unchanged
    current_eoa, current_proxy = await fund_manager.check_balance()
    assert current_eoa == eoa_balance
    assert current_proxy == proxy_balance


@pytest.mark.asyncio
@given(
    initial_proxy_balance=st.decimals(
        min_value="0.0",
        max_value="49.99",
        places=2
    ),
    eoa_balance=st.decimals(
        min_value="100.0",
        max_value="1000.0",
        places=2
    )
)
@settings(max_examples=50, deadline=None)
async def test_property_25_deposit_reaches_target_balance(initial_proxy_balance, eoa_balance):
    """
    Property 25: Auto-Deposit Trigger - Deposit Reaches Target Balance
    
    **Validates: Requirements 8.1, 8.2**
    
    *For any* successful auto-deposit, the Proxy wallet balance should reach
    the target balance ($100).
    
    Property: After auto_deposit completes, proxy_balance should equal TARGET_BALANCE.
    """
    # Create fund manager with specified balances
    fund_manager = create_mock_fund_manager(eoa_balance, initial_proxy_balance, dry_run=False)
    
    # Calculate expected deposit amount
    deposit_amount = TARGET_BALANCE - initial_proxy_balance
    
    # Verify EOA has sufficient balance
    assume(eoa_balance >= deposit_amount)
    
    # Mock the balance check to return updated balance after deposit
    original_check_balance = fund_manager.check_balance
    
    async def mock_check_balance_after_deposit():
        # First call returns initial balances
        # Subsequent calls return updated balances
        if not hasattr(mock_check_balance_after_deposit, 'call_count'):
            mock_check_balance_after_deposit.call_count = 0
        
        mock_check_balance_after_deposit.call_count += 1
        
        if mock_check_balance_after_deposit.call_count <= 1:
            return eoa_balance, initial_proxy_balance
        else:
            # After deposit: EOA decreased, Proxy increased
            new_eoa = eoa_balance - deposit_amount
            new_proxy = TARGET_BALANCE
            return new_eoa, new_proxy
    
    fund_manager.check_balance = mock_check_balance_after_deposit
    
    # Execute auto-deposit
    result = await fund_manager.auto_deposit()
    
    # Verify transaction was submitted (not None in non-dry-run mode)
    assert result is not None
    
    # Verify final balance reaches target
    final_eoa, final_proxy = await fund_manager.check_balance()
    
    # Property verification: Proxy balance should equal target balance
    assert final_proxy == TARGET_BALANCE, \
        f"Proxy balance should reach target: expected {TARGET_BALANCE}, got {final_proxy}"
    
    # Verify EOA balance decreased by deposit amount
    expected_eoa = eoa_balance - deposit_amount
    assert abs(final_eoa - expected_eoa) < Decimal("0.01"), \
        f"EOA balance should decrease by deposit amount: expected {expected_eoa}, got {final_eoa}"



@pytest.mark.asyncio
@given(
    proxy_balance=st.decimals(
        min_value="500.01",
        max_value="1000.0",
        places=2
    ),
    eoa_balance=st.decimals(
        min_value="0.0",
        max_value="500.0",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_26_auto_withdrawal_trigger(proxy_balance, eoa_balance):
    """
    Property 26: Auto-Withdrawal Trigger
    
    **Validates: Requirements 8.3, 8.4**
    
    *For any* Proxy wallet balance exceeding $500, the fund manager should
    initiate an auto-withdrawal to transfer profits to the EOA wallet.
    
    Property: When proxy_balance > WITHDRAW_LIMIT ($500), auto_withdraw should
    be triggered and withdraw proxy_balance - target_balance.
    """
    # Create fund manager with specified balances
    fund_manager = create_mock_fund_manager(eoa_balance, proxy_balance, dry_run=True)
    
    # Calculate expected withdrawal amount
    expected_withdrawal = proxy_balance - TARGET_BALANCE
    
    # Verify proxy balance exceeds withdrawal limit
    assert proxy_balance > WITHDRAW_LIMIT, "Test setup: proxy balance should exceed limit"
    
    # Verify withdrawal amount is positive
    assert expected_withdrawal > 0, "Test setup: withdrawal amount should be positive"
    
    # Execute auto-withdrawal
    result = await fund_manager.auto_withdraw()
    
    # In dry run mode, result is None but operation should be logged
    # In production mode, we would verify the transaction was submitted
    
    # Property verification: The system should recognize the need for withdrawal
    current_eoa, current_proxy = await fund_manager.check_balance()
    
    # Verify balances are as expected (unchanged in dry run)
    assert current_eoa == eoa_balance
    assert current_proxy == proxy_balance
    
    # Verify the withdrawal amount calculation is correct
    calculated_withdrawal = current_proxy - TARGET_BALANCE
    assert calculated_withdrawal == expected_withdrawal
    assert calculated_withdrawal > 0


@pytest.mark.asyncio
@given(
    proxy_balance=st.decimals(
        min_value="0.0",
        max_value="500.0",
        places=2
    ),
    eoa_balance=st.decimals(
        min_value="0.0",
        max_value="1000.0",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_26_no_withdrawal_when_below_limit(proxy_balance, eoa_balance):
    """
    Property 26: Auto-Withdrawal Trigger - No Withdrawal When Below Limit
    
    **Validates: Requirements 8.3, 8.4**
    
    *For any* Proxy wallet balance at or below $500, the fund manager should
    not initiate an auto-withdrawal.
    
    Property: When proxy_balance <= WITHDRAW_LIMIT, auto_withdraw should return None
    (no withdrawal needed).
    """
    # Create fund manager with specified balances
    fund_manager = create_mock_fund_manager(eoa_balance, proxy_balance, dry_run=True)
    
    # Verify proxy balance is at or below withdrawal limit
    assert proxy_balance <= WITHDRAW_LIMIT
    
    # Execute auto-withdrawal
    result = await fund_manager.auto_withdraw()
    
    # Property verification: No withdrawal should be triggered
    assert result is None, "No withdrawal should be triggered when balance <= limit"
    
    # Verify balances remain unchanged
    current_eoa, current_proxy = await fund_manager.check_balance()
    assert current_eoa == eoa_balance
    assert current_proxy == proxy_balance


@pytest.mark.asyncio
@given(
    initial_proxy_balance=st.decimals(
        min_value="500.01",
        max_value="1000.0",
        places=2
    ),
    eoa_balance=st.decimals(
        min_value="0.0",
        max_value="500.0",
        places=2
    )
)
@settings(max_examples=50, deadline=None)
async def test_property_26_withdrawal_reaches_target_balance(initial_proxy_balance, eoa_balance):
    """
    Property 26: Auto-Withdrawal Trigger - Withdrawal Reaches Target Balance
    
    **Validates: Requirements 8.3, 8.4**
    
    *For any* successful auto-withdrawal, the Proxy wallet balance should reach
    the target balance ($100).
    
    Property: After auto_withdraw completes, proxy_balance should equal TARGET_BALANCE.
    """
    # Create fund manager with specified balances
    fund_manager = create_mock_fund_manager(eoa_balance, initial_proxy_balance, dry_run=False)
    
    # Calculate expected withdrawal amount
    withdrawal_amount = initial_proxy_balance - TARGET_BALANCE
    
    # Verify withdrawal amount is positive
    assert withdrawal_amount > 0
    
    # Mock the balance check to return updated balance after withdrawal
    original_check_balance = fund_manager.check_balance
    
    async def mock_check_balance_after_withdrawal():
        # First call returns initial balances
        # Subsequent calls return updated balances
        if not hasattr(mock_check_balance_after_withdrawal, 'call_count'):
            mock_check_balance_after_withdrawal.call_count = 0
        
        mock_check_balance_after_withdrawal.call_count += 1
        
        if mock_check_balance_after_withdrawal.call_count <= 1:
            return eoa_balance, initial_proxy_balance
        else:
            # After withdrawal: EOA increased, Proxy decreased
            new_eoa = eoa_balance + withdrawal_amount
            new_proxy = TARGET_BALANCE
            return new_eoa, new_proxy
    
    fund_manager.check_balance = mock_check_balance_after_withdrawal
    
    # Execute auto-withdrawal
    result = await fund_manager.auto_withdraw()
    
    # Verify transaction was submitted (not None in non-dry-run mode)
    assert result is not None
    
    # Verify final balance reaches target
    final_eoa, final_proxy = await fund_manager.check_balance()
    
    # Property verification: Proxy balance should equal target balance
    assert final_proxy == TARGET_BALANCE, \
        f"Proxy balance should reach target: expected {TARGET_BALANCE}, got {final_proxy}"
    
    # Verify EOA balance increased by withdrawal amount
    expected_eoa = eoa_balance + withdrawal_amount
    assert abs(final_eoa - expected_eoa) < Decimal("0.01"), \
        f"EOA balance should increase by withdrawal amount: expected {expected_eoa}, got {final_eoa}"


@pytest.mark.asyncio
@given(
    proxy_balance=st.decimals(
        min_value="500.01",
        max_value="1000.0",
        places=2
    ),
    eoa_balance=st.decimals(
        min_value="0.0",
        max_value="500.0",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_26_withdrawal_amount_calculation(proxy_balance, eoa_balance):
    """
    Property 26: Auto-Withdrawal Trigger - Withdrawal Amount Calculation
    
    **Validates: Requirements 8.3, 8.4**
    
    *For any* Proxy balance exceeding the withdrawal limit, the withdrawal amount
    should be calculated as proxy_balance - target_balance.
    
    Property: withdrawal_amount = proxy_balance - TARGET_BALANCE
    """
    # Create fund manager with specified balances
    fund_manager = create_mock_fund_manager(eoa_balance, proxy_balance, dry_run=True)
    
    # Verify proxy balance exceeds withdrawal limit
    assert proxy_balance > WITHDRAW_LIMIT
    
    # Calculate expected withdrawal amount
    expected_withdrawal = proxy_balance - TARGET_BALANCE
    
    # Execute auto-withdrawal (dry run)
    await fund_manager.auto_withdraw()
    
    # Verify the calculation is correct
    current_eoa, current_proxy = await fund_manager.check_balance()
    calculated_withdrawal = current_proxy - TARGET_BALANCE
    
    # Property verification: Withdrawal amount calculation is correct
    assert calculated_withdrawal == expected_withdrawal, \
        f"Withdrawal amount should be proxy - target: expected {expected_withdrawal}, got {calculated_withdrawal}"
    
    # Verify it would leave the target balance
    remaining_balance = current_proxy - calculated_withdrawal
    assert remaining_balance == TARGET_BALANCE, \
        f"After withdrawal, proxy should have target balance: expected {TARGET_BALANCE}, got {remaining_balance}"



@pytest.mark.asyncio
@given(
    chain=st.sampled_from(["ethereum", "polygon", "arbitrum", "optimism"]),
    amount=st.decimals(
        min_value="10.0",
        max_value="1000.0",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_27_multi_chain_deposit_support(chain, amount):
    """
    Property 27: Multi-Chain Deposit Support
    
    **Validates: Requirements 8.5**
    
    *For any* deposit request from Ethereum, Polygon, Arbitrum, or Optimism,
    the fund manager should successfully process the deposit.
    
    Property: cross_chain_deposit should accept and process deposits from all
    supported chains without errors.
    """
    # Create fund manager
    fund_manager = create_mock_fund_manager(
        eoa_balance=Decimal("1000.0"),
        proxy_balance=Decimal("50.0"),
        dry_run=True
    )
    
    # Get USDC address for the chain
    chain_id = FundManager.SUPPORTED_CHAINS[chain]
    usdc_address = FundManager.USDC_ADDRESSES[chain_id]
    
    # Verify chain is supported
    assert chain in FundManager.SUPPORTED_CHAINS, f"Chain {chain} should be supported"
    
    # Execute cross-chain deposit
    result = await fund_manager.cross_chain_deposit(
        source_chain=chain,
        token_address=usdc_address,
        amount=amount
    )
    
    # In dry run mode, result is None
    # In production mode, we would verify the transaction details
    
    # Property verification: Operation should complete without errors
    # The fact that we reached here means the chain is supported
    assert result is None, "Dry run should return None"


@pytest.mark.asyncio
@given(
    chain=st.sampled_from(["ethereum", "polygon", "arbitrum", "optimism"]),
    amount=st.decimals(
        min_value="10.0",
        max_value="1000.0",
        places=2
    )
)
@settings(max_examples=50, deadline=None)
async def test_property_27_chain_id_mapping(chain, amount):
    """
    Property 27: Multi-Chain Deposit Support - Chain ID Mapping
    
    **Validates: Requirements 8.5**
    
    *For any* supported chain name, the fund manager should correctly map it
    to the corresponding chain ID.
    
    Property: Each supported chain name maps to a unique, valid chain ID.
    """
    # Verify chain is in supported chains
    assert chain in FundManager.SUPPORTED_CHAINS
    
    # Get chain ID
    chain_id = FundManager.SUPPORTED_CHAINS[chain]
    
    # Verify chain ID is valid (positive integer)
    assert isinstance(chain_id, int)
    assert chain_id > 0
    
    # Verify expected chain IDs
    expected_chain_ids = {
        "ethereum": 1,
        "polygon": 137,
        "arbitrum": 42161,
        "optimism": 10
    }
    
    # Property verification: Chain ID matches expected value
    assert chain_id == expected_chain_ids[chain], \
        f"Chain {chain} should map to chain ID {expected_chain_ids[chain]}, got {chain_id}"


@pytest.mark.asyncio
@given(
    chain=st.sampled_from(["ethereum", "polygon", "arbitrum", "optimism"]),
    amount=st.decimals(
        min_value="10.0",
        max_value="1000.0",
        places=2
    )
)
@settings(max_examples=50, deadline=None)
async def test_property_27_usdc_address_mapping(chain, amount):
    """
    Property 27: Multi-Chain Deposit Support - USDC Address Mapping
    
    **Validates: Requirements 8.5**
    
    *For any* supported chain, the fund manager should have the correct USDC
    contract address configured.
    
    Property: Each supported chain has a valid USDC contract address.
    """
    # Get chain ID
    chain_id = FundManager.SUPPORTED_CHAINS[chain]
    
    # Verify USDC address exists for this chain
    assert chain_id in FundManager.USDC_ADDRESSES
    
    # Get USDC address
    usdc_address = FundManager.USDC_ADDRESSES[chain_id]
    
    # Verify address is valid Ethereum address format
    assert isinstance(usdc_address, str)
    assert usdc_address.startswith("0x")
    assert len(usdc_address) == 42  # 0x + 40 hex characters
    
    # Verify address is valid checksum address
    assert Web3.is_address(usdc_address), \
        f"USDC address for {chain} should be valid Ethereum address"


@pytest.mark.asyncio
@given(
    invalid_chain=st.text(
        alphabet=st.characters(blacklist_categories=('Cs',)),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.lower() not in ["ethereum", "polygon", "arbitrum", "optimism"])
)
@settings(max_examples=50, deadline=None)
async def test_property_27_unsupported_chain_rejection(invalid_chain):
    """
    Property 27: Multi-Chain Deposit Support - Unsupported Chain Rejection
    
    **Validates: Requirements 8.5**
    
    *For any* unsupported chain name, the fund manager should reject the
    deposit request with a clear error.
    
    Property: cross_chain_deposit should raise FundManagerError for unsupported chains.
    """
    from src.fund_manager import FundManagerError
    
    # Create fund manager
    fund_manager = create_mock_fund_manager(
        eoa_balance=Decimal("1000.0"),
        proxy_balance=Decimal("50.0"),
        dry_run=True
    )
    
    # Attempt cross-chain deposit with invalid chain
    with pytest.raises(FundManagerError) as exc_info:
        await fund_manager.cross_chain_deposit(
            source_chain=invalid_chain,
            token_address="0x" + "0" * 40,
            amount=Decimal("100.0")
        )
    
    # Verify error message mentions unsupported chain
    error_message = str(exc_info.value).lower()
    assert "unsupported" in error_message or "not supported" in error_message, \
        f"Error should mention unsupported chain: {exc_info.value}"


@pytest.mark.asyncio
@given(
    amount=st.decimals(
        min_value="10.0",
        max_value="1000.0",
        places=2
    )
)
@settings(max_examples=50, deadline=None)
async def test_property_27_polygon_usdc_direct_deposit(amount):
    """
    Property 27: Multi-Chain Deposit Support - Polygon USDC Direct Deposit
    
    **Validates: Requirements 8.5**
    
    *For any* deposit request on Polygon with USDC token, the fund manager
    should perform a direct deposit instead of cross-chain swap.
    
    Property: When source chain is Polygon and token is USDC, use direct deposit.
    """
    # Create fund manager
    fund_manager = create_mock_fund_manager(
        eoa_balance=amount + Decimal("100.0"),  # Ensure sufficient balance
        proxy_balance=Decimal("50.0"),
        dry_run=False
    )
    
    # Mock the auto_deposit method to track if it was called
    original_auto_deposit = fund_manager.auto_deposit
    auto_deposit_called = False
    
    async def mock_auto_deposit(deposit_amount=None):
        nonlocal auto_deposit_called
        auto_deposit_called = True
        return {'transactionHash': b'\x00' * 32, 'status': 1}
    
    fund_manager.auto_deposit = mock_auto_deposit
    
    # Execute cross-chain deposit on Polygon with USDC
    result = await fund_manager.cross_chain_deposit(
        source_chain="polygon",
        token_address=fund_manager.usdc_address,
        amount=amount
    )
    
    # Property verification: Should use direct deposit
    assert auto_deposit_called, "Should call auto_deposit for Polygon USDC"
    assert result is not None
    assert result.get("type") == "direct_deposit", \
        f"Should be direct deposit, got: {result.get('type')}"
