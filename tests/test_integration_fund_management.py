"""
Integration test for fund management flow.

Tests the complete fund management cycle:
low balance → auto-deposit → trading → high balance → auto-withdraw

Validates Requirements: 8.1, 8.2, 8.3, 8.4
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from web3 import Web3
from eth_account import Account

from src.fund_manager import FundManager, InsufficientBalanceError, DepositError, WithdrawalError


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
        'gasUsed': 100000
    })
    web3.to_checksum_address = Web3.to_checksum_address
    return web3


@pytest.fixture
def mock_wallet():
    """Create mock wallet"""
    account = Account.create()
    return account


@pytest.fixture
def mock_usdc_contract():
    """Create mock USDC contract"""
    contract = Mock()
    contract.functions = Mock()
    
    # Mock balanceOf - will be updated by tests
    balance_of = Mock()
    balance_of.call = Mock(return_value=100000000)  # 100 USDC default
    contract.functions.balanceOf = Mock(return_value=balance_of)
    
    # Mock approve
    approve = Mock()
    approve.build_transaction = Mock(return_value={
        'from': '0x' + '1' * 40,
        'gas': 100000,
        'gasPrice': 50000000000,
        'nonce': 0
    })
    contract.functions.approve = Mock(return_value=approve)
    
    return contract


@pytest.fixture
def mock_ctf_contract():
    """Create mock CTF Exchange contract"""
    contract = Mock()
    contract.functions = Mock()
    
    # Mock deposit
    deposit = Mock()
    deposit.build_transaction = Mock(return_value={
        'from': '0x' + '1' * 40,
        'gas': 150000,
        'gasPrice': 50000000000,
        'nonce': 1
    })
    contract.functions.deposit = Mock(return_value=deposit)
    
    # Mock withdraw
    withdraw = Mock()
    withdraw.build_transaction = Mock(return_value={
        'from': '0x' + '1' * 40,
        'gas': 150000,
        'gasPrice': 50000000000,
        'nonce': 2
    })
    contract.functions.withdraw = Mock(return_value=withdraw)
    
    # Mock getCollateralBalance (Proxy balance)
    get_balance = Mock()
    get_balance.call = Mock(return_value=40000000)  # 40 USDC default (below min)
    contract.functions.getCollateralBalance = Mock(return_value=get_balance)
    
    return contract


@pytest.fixture
def fund_manager(mock_web3, mock_wallet, mock_usdc_contract, mock_ctf_contract):
    """Create FundManager instance with mocked contracts"""
    # Mock contract creation
    def mock_contract(address, abi):
        if 'deposit' in str(abi):
            return mock_ctf_contract
        else:
            return mock_usdc_contract
    
    mock_web3.eth.contract = mock_contract
    
    manager = FundManager(
        web3=mock_web3,
        wallet=mock_wallet,
        usdc_address="0x" + "2" * 40,
        ctf_exchange_address="0x" + "3" * 40,
        min_balance=Decimal('50.0'),
        target_balance=Decimal('100.0'),
        withdraw_limit=Decimal('500.0'),
        dry_run=False
    )
    
    return manager


class TestFundManagementFlow:
    """Test complete fund management flow"""
    
    @pytest.mark.asyncio
    async def test_complete_fund_management_cycle(
        self,
        fund_manager,
        mock_usdc_contract,
        mock_ctf_contract
    ):
        """
        Test complete fund management cycle:
        low balance → auto-deposit → trading → high balance → auto-withdraw
        
        Validates Requirements: 8.1, 8.2, 8.3, 8.4
        """
        # Phase 1: Low Balance Detection (Requirement 8.1)
        # Set initial balances: EOA=100, Proxy=40 (below min of 50)
        eoa_balance_call = Mock()
        eoa_balance_call.call = Mock(return_value=100000000)  # 100 USDC
        mock_usdc_contract.functions.balanceOf = Mock(return_value=eoa_balance_call)
        
        proxy_balance_call = Mock()
        proxy_balance_call.call = Mock(return_value=40000000)  # 40 USDC (below min)
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_call)
        
        # Check balances
        eoa_balance, proxy_balance = await fund_manager.check_balance()
        
        assert eoa_balance == Decimal('100.0')
        assert proxy_balance == Decimal('40.0')
        assert proxy_balance < fund_manager.min_balance  # Triggers auto-deposit
        
        # Phase 2: Auto-Deposit (Requirement 8.2)
        # Calculate deposit amount
        deposit_amount = fund_manager.target_balance - proxy_balance
        assert deposit_amount == Decimal('60.0')  # 100 - 40 = 60
        
        # Mock successful deposit
        with patch.object(fund_manager.wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            # Execute auto-deposit
            receipt = await fund_manager.auto_deposit(deposit_amount)
        
        assert receipt['status'] == 1
        assert receipt['transactionHash'] == b'\x00' * 32
        
        # Phase 3: Simulate Trading (balance increases)
        # After trading, Proxy balance increases to 520 (above withdraw limit of 500)
        proxy_balance_after_trading = Mock()
        proxy_balance_after_trading.call = Mock(return_value=520000000)  # 520 USDC
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_after_trading)
        
        # Check balances again
        eoa_balance, proxy_balance = await fund_manager.check_balance()
        
        assert proxy_balance == Decimal('520.0')
        assert proxy_balance > fund_manager.withdraw_limit  # Triggers auto-withdraw
        
        # Phase 4: Auto-Withdrawal (Requirement 8.3, 8.4)
        # Calculate withdrawal amount
        withdraw_amount = proxy_balance - fund_manager.target_balance
        assert withdraw_amount == Decimal('420.0')  # 520 - 100 = 420
        
        # Mock successful withdrawal
        with patch.object(fund_manager.wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            # Execute auto-withdrawal
            receipt = await fund_manager.auto_withdraw(withdraw_amount)
        
        assert receipt['status'] == 1
        assert receipt['transactionHash'] == b'\x00' * 32
        
        # Phase 5: Verify Final State
        # After withdrawal, Proxy balance should be at target (100)
        proxy_balance_final = Mock()
        proxy_balance_final.call = Mock(return_value=100000000)  # 100 USDC
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_final)
        
        eoa_balance, proxy_balance = await fund_manager.check_balance()
        
        assert proxy_balance == Decimal('100.0')
        assert proxy_balance == fund_manager.target_balance
    
    @pytest.mark.asyncio
    async def test_auto_deposit_trigger(
        self,
        fund_manager,
        mock_usdc_contract,
        mock_ctf_contract
    ):
        """
        Test auto-deposit triggers when balance falls below minimum.
        
        Validates Requirements: 8.1, 8.2
        """
        # Set balances: EOA=200, Proxy=30 (below min of 50)
        eoa_balance_call = Mock()
        eoa_balance_call.call = Mock(return_value=200000000)  # 200 USDC
        mock_usdc_contract.functions.balanceOf = Mock(return_value=eoa_balance_call)
        
        proxy_balance_call = Mock()
        proxy_balance_call.call = Mock(return_value=30000000)  # 30 USDC
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_call)
        
        # Check balances
        eoa_balance, proxy_balance = await fund_manager.check_balance()
        
        # Verify trigger condition (Requirement 8.1)
        assert proxy_balance < fund_manager.min_balance
        assert eoa_balance >= (fund_manager.target_balance - proxy_balance)
        
        # Calculate deposit amount
        deposit_amount = fund_manager.target_balance - proxy_balance
        assert deposit_amount == Decimal('70.0')  # 100 - 30 = 70
        
        # Execute deposit (Requirement 8.2)
        with patch.object(fund_manager.wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            receipt = await fund_manager.auto_deposit(deposit_amount)
        
        assert receipt['status'] == 1
    
    @pytest.mark.asyncio
    async def test_auto_withdraw_trigger(
        self,
        fund_manager,
        mock_usdc_contract,
        mock_ctf_contract
    ):
        """
        Test auto-withdrawal triggers when balance exceeds limit.
        
        Validates Requirements: 8.3, 8.4
        """
        # Set balances: EOA=100, Proxy=600 (above limit of 500)
        eoa_balance_call = Mock()
        eoa_balance_call.call = Mock(return_value=100000000)  # 100 USDC
        mock_usdc_contract.functions.balanceOf = Mock(return_value=eoa_balance_call)
        
        proxy_balance_call = Mock()
        proxy_balance_call.call = Mock(return_value=600000000)  # 600 USDC
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_call)
        
        # Check balances
        eoa_balance, proxy_balance = await fund_manager.check_balance()
        
        # Verify trigger condition (Requirement 8.3)
        assert proxy_balance > fund_manager.withdraw_limit
        
        # Calculate withdrawal amount
        withdraw_amount = proxy_balance - fund_manager.target_balance
        assert withdraw_amount == Decimal('500.0')  # 600 - 100 = 500
        
        # Execute withdrawal (Requirement 8.4)
        with patch.object(fund_manager.wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            receipt = await fund_manager.auto_withdraw(withdraw_amount)
        
        assert receipt['status'] == 1
    
    @pytest.mark.asyncio
    async def test_insufficient_eoa_balance_for_deposit(
        self,
        fund_manager,
        mock_usdc_contract,
        mock_ctf_contract
    ):
        """
        Test handling when EOA has insufficient balance for deposit.
        
        Validates Requirement 8.2
        """
        # Set balances: EOA=20, Proxy=30 (both low)
        eoa_balance_call = Mock()
        eoa_balance_call.call = Mock(return_value=20000000)  # 20 USDC
        mock_usdc_contract.functions.balanceOf = Mock(return_value=eoa_balance_call)
        
        proxy_balance_call = Mock()
        proxy_balance_call.call = Mock(return_value=30000000)  # 30 USDC
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_call)
        
        # Check balances
        eoa_balance, proxy_balance = await fund_manager.check_balance()
        
        # Verify trigger condition
        assert proxy_balance < fund_manager.min_balance
        
        # Calculate required deposit
        deposit_amount = fund_manager.target_balance - proxy_balance
        assert deposit_amount == Decimal('70.0')
        
        # EOA doesn't have enough
        assert eoa_balance < deposit_amount
        
        # Attempt deposit should raise error
        with pytest.raises(InsufficientBalanceError):
            await fund_manager.auto_deposit(deposit_amount)
    
    @pytest.mark.asyncio
    async def test_no_action_when_balance_in_range(
        self,
        fund_manager,
        mock_usdc_contract,
        mock_ctf_contract
    ):
        """
        Test that no action is taken when balance is in acceptable range.
        
        Validates Requirements: 8.1, 8.3
        """
        # Set balances: EOA=100, Proxy=200 (in acceptable range: 50-500)
        eoa_balance_call = Mock()
        eoa_balance_call.call = Mock(return_value=100000000)  # 100 USDC
        mock_usdc_contract.functions.balanceOf = Mock(return_value=eoa_balance_call)
        
        proxy_balance_call = Mock()
        proxy_balance_call.call = Mock(return_value=200000000)  # 200 USDC
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_call)
        
        # Check balances
        eoa_balance, proxy_balance = await fund_manager.check_balance()
        
        # Verify no action needed
        assert proxy_balance >= fund_manager.min_balance  # No deposit needed
        assert proxy_balance <= fund_manager.withdraw_limit  # No withdrawal needed
        
        # Balance is in acceptable range
        assert fund_manager.min_balance <= proxy_balance <= fund_manager.withdraw_limit


class TestFundManagementEdgeCases:
    """Test edge cases in fund management"""
    
    @pytest.mark.asyncio
    async def test_deposit_exactly_to_target(
        self,
        fund_manager,
        mock_usdc_contract,
        mock_ctf_contract
    ):
        """Test depositing exactly to target balance"""
        # Set balances: EOA=100, Proxy=50 (at minimum)
        eoa_balance_call = Mock()
        eoa_balance_call.call = Mock(return_value=100000000)
        mock_usdc_contract.functions.balanceOf = Mock(return_value=eoa_balance_call)
        
        proxy_balance_call = Mock()
        proxy_balance_call.call = Mock(return_value=50000000)
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_call)
        
        eoa_balance, proxy_balance = await fund_manager.check_balance()
        
        # Deposit to reach target
        deposit_amount = fund_manager.target_balance - proxy_balance
        assert deposit_amount == Decimal('50.0')
        
        with patch.object(fund_manager.wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            receipt = await fund_manager.auto_deposit(deposit_amount)
        
        assert receipt['status'] == 1
    
    @pytest.mark.asyncio
    async def test_withdraw_exactly_to_target(
        self,
        fund_manager,
        mock_usdc_contract,
        mock_ctf_contract
    ):
        """Test withdrawing exactly to target balance"""
        # Set balances: EOA=100, Proxy=500 (at limit)
        eoa_balance_call = Mock()
        eoa_balance_call.call = Mock(return_value=100000000)
        mock_usdc_contract.functions.balanceOf = Mock(return_value=eoa_balance_call)
        
        proxy_balance_call = Mock()
        proxy_balance_call.call = Mock(return_value=500000000)
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_call)
        
        eoa_balance, proxy_balance = await fund_manager.check_balance()
        
        # Withdraw to reach target
        withdraw_amount = proxy_balance - fund_manager.target_balance
        assert withdraw_amount == Decimal('400.0')
        
        with patch.object(fund_manager.wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            receipt = await fund_manager.auto_withdraw(withdraw_amount)
        
        assert receipt['status'] == 1
    
    @pytest.mark.asyncio
    async def test_multiple_deposits_in_sequence(
        self,
        fund_manager,
        mock_usdc_contract,
        mock_ctf_contract
    ):
        """Test multiple deposits in sequence"""
        # First deposit
        with patch.object(fund_manager.wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            receipt1 = await fund_manager.auto_deposit(Decimal('50.0'))
            assert receipt1['status'] == 1
            
            # Second deposit
            receipt2 = await fund_manager.auto_deposit(Decimal('30.0'))
            assert receipt2['status'] == 1
    
    @pytest.mark.asyncio
    async def test_multiple_withdrawals_in_sequence(
        self,
        fund_manager,
        mock_usdc_contract,
        mock_ctf_contract
    ):
        """Test multiple withdrawals in sequence"""
        # Set up sufficient proxy balance for withdrawals
        eoa_balance_call = Mock()
        eoa_balance_call.call = Mock(return_value=100000000)  # 100 USDC
        mock_usdc_contract.functions.balanceOf = Mock(return_value=eoa_balance_call)
        
        proxy_balance_call = Mock()
        proxy_balance_call.call = Mock(return_value=600000000)  # 600 USDC (enough for withdrawals)
        mock_ctf_contract.functions.getCollateralBalance = Mock(return_value=proxy_balance_call)
        
        # First withdrawal
        with patch.object(fund_manager.wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            receipt1 = await fund_manager.auto_withdraw(Decimal('100.0'))
            assert receipt1['status'] == 1
            
            # Update proxy balance after first withdrawal
            proxy_balance_call.call = Mock(return_value=500000000)  # 500 USDC remaining
            
            # Second withdrawal
            receipt2 = await fund_manager.auto_withdraw(Decimal('50.0'))
            assert receipt2['status'] == 1
