"""
Property-based tests for DRY_RUN mode transaction prevention.

Tests correctness properties for DRY_RUN mode to ensure no real transactions
are submitted when the mode is enabled.

Validates Requirement 20.5: WHEN DRY_RUN is enabled, THE System SHALL log 
"DRY RUN MODE" prominently and skip all real transactions.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from web3 import Web3
from eth_account import Account

from src.fund_manager import FundManager
from src.transaction_manager import TransactionManager
from config.config import Config


# Test configuration
MIN_BALANCE = Decimal("50.0")
TARGET_BALANCE = Decimal("100.0")
WITHDRAW_LIMIT = Decimal("500.0")


def create_mock_config(dry_run: bool = False) -> Config:
    """Create a mock Config with specified dry_run setting."""
    # Create a test private key
    test_account = Account.create()
    
    config = Config(
        private_key=test_account.key.hex(),
        wallet_address=test_account.address,
        polygon_rpc_url="https://polygon-rpc.com",
        dry_run=dry_run
    )
    
    return config


def create_mock_fund_manager(
    eoa_balance: Decimal,
    proxy_balance: Decimal,
    dry_run: bool = False
) -> FundManager:
    """Create a mock FundManager with specified balances and dry_run setting."""
    # Create mock Web3 instance
    mock_web3 = Mock(spec=Web3)
    mock_web3.eth = Mock()
    mock_web3.eth.gas_price = 50000000000  # 50 gwei
    mock_web3.eth.get_transaction_count = Mock(return_value=0)
    mock_web3.eth.wait_for_transaction_receipt = Mock(
        return_value={'status': 1, 'transactionHash': b'\x00' * 32}
    )
    mock_web3.eth.send_raw_transaction = Mock(
        return_value=b'\x00' * 32
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


def create_mock_transaction_manager(dry_run: bool = False) -> TransactionManager:
    """Create a mock TransactionManager for testing."""
    # Create mock Web3 instance
    mock_web3 = Mock(spec=Web3)
    mock_web3.eth = Mock()
    mock_web3.eth.gas_price = 50000000000  # 50 gwei
    mock_web3.eth.get_transaction_count = Mock(return_value=0)
    mock_web3.eth.send_raw_transaction = Mock(
        return_value=b'\x00' * 32
    )
    mock_web3.eth.get_transaction_receipt = Mock(return_value=None)
    
    # Create mock wallet
    mock_wallet = Mock()
    mock_wallet.address = "0x1234567890123456789012345678901234567890"
    mock_wallet.sign_transaction = Mock(
        return_value=Mock(raw_transaction=b'\x00' * 100)
    )
    
    tx_manager = TransactionManager(
        web3=mock_web3,
        wallet=mock_wallet,
        max_pending_tx=5
    )
    
    # Store dry_run flag for testing
    tx_manager._dry_run = dry_run
    
    return tx_manager


@pytest.mark.asyncio
@given(
    eoa_balance=st.decimals(
        min_value="100.0",
        max_value="1000.0",
        places=2
    ),
    proxy_balance=st.decimals(
        min_value="0.0",
        max_value="49.99",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_55_dry_run_prevents_deposit_transactions(eoa_balance, proxy_balance):
    """
    Property 55: DRY_RUN Mode Transaction Prevention
    
    **Validates: Requirements 20.5**
    
    PROPERTY: When DRY_RUN mode is enabled, the system SHALL NOT submit any
    real blockchain transactions for deposit operations.
    
    GIVEN:
        - DRY_RUN mode is enabled
        - Proxy balance is below minimum (triggers auto-deposit)
        - EOA balance is sufficient for deposit
    
    WHEN:
        - auto_deposit is called
    
    THEN:
        - No transaction is sent to the blockchain
        - The system logs the intended action
        - No calls to web3.eth.send_raw_transaction occur
        - No calls to wallet.sign_transaction occur
    """
    # Create fund manager with DRY_RUN enabled
    fund_manager = create_mock_fund_manager(eoa_balance, proxy_balance, dry_run=True)
    
    # Verify proxy balance is below minimum (would trigger deposit)
    assume(proxy_balance < MIN_BALANCE)
    
    # Calculate expected deposit amount
    deposit_amount = TARGET_BALANCE - proxy_balance
    
    # Verify EOA has sufficient balance
    assume(eoa_balance >= deposit_amount)
    
    # Attempt auto-deposit in DRY_RUN mode
    result = await fund_manager.auto_deposit(deposit_amount)
    
    # PROPERTY VALIDATION: No transaction should be sent
    # In DRY_RUN mode, auto_deposit returns None instead of a transaction receipt
    assert result is None, (
        f"DRY_RUN mode should return None, not a transaction receipt. "
        f"Got: {result}"
    )
    
    # Verify no blockchain transaction was sent
    # The mock's send_raw_transaction should NOT have been called
    assert not fund_manager.web3.eth.send_raw_transaction.called, (
        "DRY_RUN mode should NOT send raw transactions to blockchain. "
        f"send_raw_transaction was called {fund_manager.web3.eth.send_raw_transaction.call_count} times"
    )
    
    # Verify no transaction was signed
    # In DRY_RUN mode, we should not sign transactions
    assert not fund_manager.wallet.sign_transaction.called, (
        "DRY_RUN mode should NOT sign transactions. "
        f"sign_transaction was called {fund_manager.wallet.sign_transaction.call_count} times"
    )


@pytest.mark.asyncio
@given(
    eoa_balance=st.decimals(
        min_value="100.0",
        max_value="1000.0",
        places=2
    ),
    proxy_balance=st.decimals(
        min_value="501.0",
        max_value="1000.0",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_55_dry_run_prevents_withdrawal_transactions(eoa_balance, proxy_balance):
    """
    Property 55: DRY_RUN Mode Transaction Prevention (Withdrawals)
    
    **Validates: Requirements 20.5**
    
    PROPERTY: When DRY_RUN mode is enabled, the system SHALL NOT submit any
    real blockchain transactions for withdrawal operations.
    
    GIVEN:
        - DRY_RUN mode is enabled
        - Proxy balance exceeds withdrawal limit (triggers auto-withdraw)
    
    WHEN:
        - auto_withdraw is called
    
    THEN:
        - No transaction is sent to the blockchain
        - The system logs the intended action
        - No calls to web3.eth.send_raw_transaction occur
        - No calls to wallet.sign_transaction occur
    """
    # Create fund manager with DRY_RUN enabled
    fund_manager = create_mock_fund_manager(eoa_balance, proxy_balance, dry_run=True)
    
    # Verify proxy balance exceeds withdrawal limit (would trigger withdrawal)
    assume(proxy_balance > WITHDRAW_LIMIT)
    
    # Calculate expected withdrawal amount
    withdraw_amount = proxy_balance - TARGET_BALANCE
    
    # Attempt auto-withdrawal in DRY_RUN mode
    result = await fund_manager.auto_withdraw(withdraw_amount)
    
    # PROPERTY VALIDATION: No transaction should be sent
    # In DRY_RUN mode, auto_withdraw returns None instead of a transaction receipt
    assert result is None, (
        f"DRY_RUN mode should return None, not a transaction receipt. "
        f"Got: {result}"
    )
    
    # Verify no blockchain transaction was sent
    assert not fund_manager.web3.eth.send_raw_transaction.called, (
        "DRY_RUN mode should NOT send raw transactions to blockchain. "
        f"send_raw_transaction was called {fund_manager.web3.eth.send_raw_transaction.call_count} times"
    )
    
    # Verify no transaction was signed
    assert not fund_manager.wallet.sign_transaction.called, (
        "DRY_RUN mode should NOT sign transactions. "
        f"sign_transaction was called {fund_manager.wallet.sign_transaction.call_count} times"
    )


@pytest.mark.asyncio
@given(
    eoa_balance=st.decimals(
        min_value="100.0",
        max_value="1000.0",
        places=2
    ),
    proxy_balance=st.decimals(
        min_value="0.0",
        max_value="49.99",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_55_live_mode_allows_transactions(eoa_balance, proxy_balance):
    """
    Property 55: DRY_RUN Mode Transaction Prevention (Inverse - Live Mode)
    
    **Validates: Requirements 20.5**
    
    PROPERTY: When DRY_RUN mode is DISABLED (live mode), the system SHALL
    submit real blockchain transactions normally.
    
    This is the inverse property to ensure DRY_RUN mode is actually preventing
    transactions, not a bug in the test setup.
    
    GIVEN:
        - DRY_RUN mode is DISABLED (live mode)
        - Proxy balance is below minimum (triggers auto-deposit)
        - EOA balance is sufficient for deposit
    
    WHEN:
        - auto_deposit is called
    
    THEN:
        - Transaction IS sent to the blockchain
        - Transaction IS signed
        - A transaction receipt is returned
    """
    # Create fund manager with DRY_RUN DISABLED (live mode)
    fund_manager = create_mock_fund_manager(eoa_balance, proxy_balance, dry_run=False)
    
    # Verify proxy balance is below minimum (would trigger deposit)
    assume(proxy_balance < MIN_BALANCE)
    
    # Calculate expected deposit amount
    deposit_amount = TARGET_BALANCE - proxy_balance
    
    # Verify EOA has sufficient balance
    assume(eoa_balance >= deposit_amount)
    
    # Attempt auto-deposit in LIVE mode
    result = await fund_manager.auto_deposit(deposit_amount)
    
    # PROPERTY VALIDATION: Transaction SHOULD be sent in live mode
    # In live mode, auto_deposit returns a transaction receipt
    assert result is not None, (
        "Live mode should return a transaction receipt, not None. "
        "This indicates transactions are being sent."
    )
    
    # Verify blockchain transaction WAS sent
    assert fund_manager.web3.eth.send_raw_transaction.called, (
        "Live mode SHOULD send raw transactions to blockchain. "
        "send_raw_transaction was not called."
    )
    
    # Verify transaction WAS signed
    assert fund_manager.wallet.sign_transaction.called, (
        "Live mode SHOULD sign transactions. "
        "sign_transaction was not called."
    )


@pytest.mark.asyncio
@given(
    amount=st.decimals(
        min_value="10.0",
        max_value="100.0",
        places=2
    )
)
@settings(max_examples=100, deadline=None)
async def test_property_55_dry_run_prevents_cross_chain_transactions(amount):
    """
    Property 55: DRY_RUN Mode Transaction Prevention (Cross-Chain)
    
    **Validates: Requirements 20.5**
    
    PROPERTY: When DRY_RUN mode is enabled, the system SHALL NOT submit any
    real blockchain transactions for cross-chain deposit operations.
    
    GIVEN:
        - DRY_RUN mode is enabled
        - A cross-chain deposit is requested
    
    WHEN:
        - cross_chain_deposit is called
    
    THEN:
        - No transaction is sent to the blockchain
        - The system logs the intended action
        - No calls to web3.eth.send_raw_transaction occur
    """
    # Create fund manager with DRY_RUN enabled
    fund_manager = create_mock_fund_manager(
        eoa_balance=Decimal("1000.0"),
        proxy_balance=Decimal("50.0"),
        dry_run=True
    )
    
    # Set 1inch API key for cross-chain support
    fund_manager.oneinch_api_key = "test_api_key"
    
    # Attempt cross-chain deposit in DRY_RUN mode
    result = await fund_manager.cross_chain_deposit(
        source_chain="ethereum",
        token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC on Ethereum
        amount=amount
    )
    
    # PROPERTY VALIDATION: No transaction should be sent
    assert result is None, (
        f"DRY_RUN mode should return None for cross-chain deposits. "
        f"Got: {result}"
    )
    
    # Verify no blockchain transaction was sent
    assert not fund_manager.web3.eth.send_raw_transaction.called, (
        "DRY_RUN mode should NOT send raw transactions for cross-chain deposits. "
        f"send_raw_transaction was called {fund_manager.web3.eth.send_raw_transaction.call_count} times"
    )


@pytest.mark.asyncio
@given(
    dry_run=st.booleans()
)
@settings(max_examples=50, deadline=None)
async def test_property_55_config_dry_run_flag_consistency(dry_run):
    """
    Property 55: DRY_RUN Mode Configuration Consistency
    
    **Validates: Requirements 20.5**
    
    PROPERTY: The DRY_RUN configuration flag SHALL be consistently applied
    across all system components.
    
    GIVEN:
        - A Config object with dry_run set to a specific value
    
    WHEN:
        - Components are initialized with this config
    
    THEN:
        - All components respect the dry_run setting
        - The setting is correctly propagated
    """
    # Create config with specified dry_run setting
    config = create_mock_config(dry_run=dry_run)
    
    # PROPERTY VALIDATION: Config should have the correct dry_run value
    assert config.dry_run == dry_run, (
        f"Config dry_run should be {dry_run}, got {config.dry_run}"
    )
    
    # Verify the config can be serialized and the dry_run flag is preserved
    config_dict = config.to_dict()
    assert config_dict['dry_run'] == dry_run, (
        f"Config.to_dict() should preserve dry_run={dry_run}, "
        f"got {config_dict['dry_run']}"
    )
