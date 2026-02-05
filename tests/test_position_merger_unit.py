"""
Unit tests for Position Merger.

Tests error handling for insufficient balance and contract reverts.
Validates Requirement 1.5.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.position_merger import (
    PositionMerger,
    PositionMergerError,
    InsufficientBalanceError,
    MergeRedemptionError
)


# Mock Web3 and Contract for testing
class MockWeb3:
    """Mock Web3 instance for testing."""
    
    def __init__(self):
        self.eth = MockEth()
    
    @staticmethod
    def to_checksum_address(address):
        """Mock checksum address conversion."""
        if isinstance(address, str) and address.startswith('0x') and len(address) == 42:
            return address
        return address


class MockEth:
    """Mock eth interface."""
    
    def __init__(self):
        self._gas_price = 50_000_000_000  # 50 gwei
        self._nonce = 0
        self._tx_counter = 0
        self._receipts = {}
    
    @property
    def gas_price(self):
        """Mock gas_price property."""
        return self._gas_price
    
    def get_transaction_count(self, address, block='latest'):
        """Mock get_transaction_count."""
        return self._nonce
    
    def send_raw_transaction(self, raw_tx):
        """Mock send_raw_transaction."""
        self._tx_counter += 1
        tx_hash = f"0x{self._tx_counter:064x}"
        return bytes.fromhex(tx_hash[2:])
    
    def wait_for_transaction_receipt(self, tx_hash, timeout=120):
        """Mock wait_for_transaction_receipt."""
        tx_hash_hex = tx_hash.hex() if isinstance(tx_hash, bytes) else tx_hash
        if tx_hash_hex in self._receipts:
            return self._receipts[tx_hash_hex]
        return {
            'transactionHash': tx_hash_hex,
            'status': 1,
            'blockNumber': 12345,
            'gasUsed': 100000
        }
    
    def add_receipt(self, tx_hash, status=1):
        """Add a mock receipt."""
        self._receipts[tx_hash] = {
            'transactionHash': tx_hash,
            'status': status,
            'blockNumber': 12345,
            'gasUsed': 100000
        }
    
    def contract(self, address, abi):
        """Mock contract creation."""
        return MockContract(address, abi)


class MockContract:
    """Mock contract for testing."""
    
    def __init__(self, address, abi):
        self.address = address
        self.abi = abi
        self.functions = MockContractFunctions(address)


class MockContractFunctions:
    """Mock contract functions."""
    
    def __init__(self, address):
        self.address = address
        # Track balances: {(owner, token_id): balance_wei}
        self._position_balances = {}
        # Track USDC balances: {owner: balance_wei}
        self._usdc_balances = {}
        # Control merge behavior
        self._merge_should_revert = False
        self._merge_revert_message = ""
    
    def set_position_balance(self, owner, token_id, balance_wei):
        """Set position balance for testing."""
        self._position_balances[(owner, token_id)] = balance_wei
    
    def set_usdc_balance(self, owner, balance_wei):
        """Set USDC balance for testing."""
        self._usdc_balances[owner] = balance_wei
    
    def set_merge_revert(self, should_revert, message=""):
        """Configure merge to revert."""
        self._merge_should_revert = should_revert
        self._merge_revert_message = message
    
    def balanceOf(self, owner, token_id=None):
        """Mock balanceOf function."""
        if token_id is not None:
            # CTF position balance
            balance = self._position_balances.get((owner, token_id), 0)
            return MockCall(balance)
        else:
            # USDC balance
            balance = self._usdc_balances.get(owner, 0)
            return MockCall(balance)
    
    def mergePositions(self, collateral_token, parent_collection_id, 
                      condition_id, partition, amount):
        """Mock mergePositions function."""
        return MockMergeFunction(
            self, collateral_token, parent_collection_id,
            condition_id, partition, amount
        )


class MockCall:
    """Mock contract call result."""
    
    def __init__(self, return_value):
        self.return_value = return_value
    
    def call(self):
        """Execute mock call."""
        return self.return_value


class MockMergeFunction:
    """Mock merge function for building and estimating."""
    
    def __init__(self, functions, collateral_token, parent_collection_id,
                 condition_id, partition, amount):
        self.functions = functions
        self.collateral_token = collateral_token
        self.parent_collection_id = parent_collection_id
        self.condition_id = condition_id
        self.partition = partition
        self.amount = amount
    
    def estimate_gas(self, tx_params):
        """Mock gas estimation."""
        if self.functions._merge_should_revert:
            raise Exception(self.functions._merge_revert_message or "execution reverted")
        return 200000
    
    def build_transaction(self, tx_params):
        """Mock transaction building."""
        if self.functions._merge_should_revert:
            raise Exception(self.functions._merge_revert_message or "execution reverted")
        return {
            'from': tx_params['from'],
            'gas': tx_params.get('gas', 200000),
            'gasPrice': tx_params.get('gasPrice', 50_000_000_000),
            'nonce': tx_params.get('nonce', 0),
            'to': self.functions.address,
            'data': '0x' + '0' * 64
        }


class MockAccount:
    """Mock account for testing."""
    
    def __init__(self, address="0x1234567890123456789012345678901234567890"):
        self.address = address
    
    def sign_transaction(self, tx_params):
        """Mock sign_transaction."""
        mock_signed = Mock()
        mock_signed.raw_transaction = b'\x00' * 32
        return mock_signed


@pytest.mark.asyncio
async def test_insufficient_yes_balance_error():
    """
    Test that InsufficientBalanceError is raised when YES balance is insufficient.
    
    Validates Requirement 1.5: Balance verification before merge
    """
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    merge_amount = Decimal('10.0')
    
    # Set insufficient YES balance, sufficient NO balance
    yes_balance_wei = int(Decimal('5.0') * Decimal(10 ** 6))  # Only 5.0
    no_balance_wei = int(Decimal('20.0') * Decimal(10 ** 6))  # 20.0
    
    ctf_contract = position_merger.ctf_contract
    ctf_contract.functions.set_position_balance(
        wallet.address, int(yes_token_id, 16), yes_balance_wei
    )
    ctf_contract.functions.set_position_balance(
        wallet.address, int(no_token_id, 16), no_balance_wei
    )
    
    # Attempt merge - should raise InsufficientBalanceError
    with pytest.raises(InsufficientBalanceError) as exc_info:
        await position_merger.merge_positions(
            condition_id=condition_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            amount=merge_amount
        )
    
    # Verify error message mentions YES balance
    assert "YES" in str(exc_info.value)
    assert "5" in str(exc_info.value)  # Current balance
    assert "10" in str(exc_info.value)  # Required amount


@pytest.mark.asyncio
async def test_insufficient_no_balance_error():
    """
    Test that InsufficientBalanceError is raised when NO balance is insufficient.
    
    Validates Requirement 1.5: Balance verification before merge
    """
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    merge_amount = Decimal('10.0')
    
    # Set sufficient YES balance, insufficient NO balance
    yes_balance_wei = int(Decimal('20.0') * Decimal(10 ** 6))  # 20.0
    no_balance_wei = int(Decimal('3.0') * Decimal(10 ** 6))  # Only 3.0
    
    ctf_contract = position_merger.ctf_contract
    ctf_contract.functions.set_position_balance(
        wallet.address, int(yes_token_id, 16), yes_balance_wei
    )
    ctf_contract.functions.set_position_balance(
        wallet.address, int(no_token_id, 16), no_balance_wei
    )
    
    # Attempt merge - should raise InsufficientBalanceError
    with pytest.raises(InsufficientBalanceError) as exc_info:
        await position_merger.merge_positions(
            condition_id=condition_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            amount=merge_amount
        )
    
    # Verify error message mentions NO balance
    assert "NO" in str(exc_info.value)
    assert "3" in str(exc_info.value)  # Current balance
    assert "10" in str(exc_info.value)  # Required amount


@pytest.mark.asyncio
async def test_both_balances_insufficient():
    """
    Test error when both YES and NO balances are insufficient.
    
    Should fail on YES check first (checked before NO).
    
    Validates Requirement 1.5: Balance verification before merge
    """
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    merge_amount = Decimal('10.0')
    
    # Set both balances insufficient
    yes_balance_wei = int(Decimal('2.0') * Decimal(10 ** 6))
    no_balance_wei = int(Decimal('3.0') * Decimal(10 ** 6))
    
    ctf_contract = position_merger.ctf_contract
    ctf_contract.functions.set_position_balance(
        wallet.address, int(yes_token_id, 16), yes_balance_wei
    )
    ctf_contract.functions.set_position_balance(
        wallet.address, int(no_token_id, 16), no_balance_wei
    )
    
    # Attempt merge - should raise InsufficientBalanceError for YES (checked first)
    with pytest.raises(InsufficientBalanceError) as exc_info:
        await position_merger.merge_positions(
            condition_id=condition_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            amount=merge_amount
        )
    
    # Should fail on YES check
    assert "YES" in str(exc_info.value)


@pytest.mark.asyncio
async def test_contract_revert_during_gas_estimation():
    """
    Test handling of contract revert during gas estimation.
    
    Validates Requirement 1.5: Contract revert handling
    """
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    merge_amount = Decimal('10.0')
    
    # Set sufficient balances
    yes_balance_wei = int(Decimal('20.0') * Decimal(10 ** 6))
    no_balance_wei = int(Decimal('20.0') * Decimal(10 ** 6))
    
    ctf_contract = position_merger.ctf_contract
    usdc_contract = position_merger.usdc_contract
    
    ctf_contract.functions.set_position_balance(
        wallet.address, int(yes_token_id, 16), yes_balance_wei
    )
    ctf_contract.functions.set_position_balance(
        wallet.address, int(no_token_id, 16), no_balance_wei
    )
    usdc_contract.functions.set_usdc_balance(
        wallet.address, int(Decimal('100.0') * Decimal(10 ** 6))
    )
    
    # Configure merge to revert
    ctf_contract.functions.set_merge_revert(True, "Merge not allowed")
    
    # Gas estimation should use default when it fails
    gas_estimate = position_merger.estimate_gas(
        condition_id, yes_token_id, no_token_id, merge_amount
    )
    
    # Should return default gas limit
    assert gas_estimate == position_merger.gas_limit_default


@pytest.mark.asyncio
async def test_contract_revert_during_transaction():
    """
    Test handling of contract revert during transaction execution.
    
    Validates Requirement 1.5: Contract revert handling
    """
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    merge_amount = Decimal('10.0')
    
    # Set sufficient balances
    yes_balance_wei = int(Decimal('20.0') * Decimal(10 ** 6))
    no_balance_wei = int(Decimal('20.0') * Decimal(10 ** 6))
    
    ctf_contract = position_merger.ctf_contract
    usdc_contract = position_merger.usdc_contract
    
    ctf_contract.functions.set_position_balance(
        wallet.address, int(yes_token_id, 16), yes_balance_wei
    )
    ctf_contract.functions.set_position_balance(
        wallet.address, int(no_token_id, 16), no_balance_wei
    )
    usdc_contract.functions.set_usdc_balance(
        wallet.address, int(Decimal('100.0') * Decimal(10 ** 6))
    )
    
    # Configure merge to revert during transaction building
    ctf_contract.functions.set_merge_revert(True, "Insufficient allowance")
    
    # Attempt merge - should raise PositionMergerError
    with pytest.raises(PositionMergerError) as exc_info:
        await position_merger.merge_positions(
            condition_id=condition_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            amount=merge_amount
        )
    
    # Verify error message mentions the failure
    assert "failed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_transaction_reverted_status():
    """
    Test handling of transaction with reverted status (status=0).
    
    Validates Requirement 1.5: Contract revert handling
    """
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    merge_amount = Decimal('10.0')
    
    # Set sufficient balances
    yes_balance_wei = int(Decimal('20.0') * Decimal(10 ** 6))
    no_balance_wei = int(Decimal('20.0') * Decimal(10 ** 6))
    initial_usdc_wei = int(Decimal('100.0') * Decimal(10 ** 6))
    
    ctf_contract = position_merger.ctf_contract
    usdc_contract = position_merger.usdc_contract
    
    ctf_contract.functions.set_position_balance(
        wallet.address, int(yes_token_id, 16), yes_balance_wei
    )
    ctf_contract.functions.set_position_balance(
        wallet.address, int(no_token_id, 16), no_balance_wei
    )
    usdc_contract.functions.set_usdc_balance(
        wallet.address, initial_usdc_wei
    )
    
    # Configure transaction to return reverted status
    # We'll need to intercept the wait_for_transaction_receipt call
    original_wait = web3.eth.wait_for_transaction_receipt
    
    def mock_wait_reverted(tx_hash, timeout=120):
        return {
            'transactionHash': tx_hash.hex() if isinstance(tx_hash, bytes) else tx_hash,
            'status': 0,  # Reverted
            'blockNumber': 12345,
            'gasUsed': 100000
        }
    
    web3.eth.wait_for_transaction_receipt = mock_wait_reverted
    
    # Attempt merge - should raise PositionMergerError
    with pytest.raises(PositionMergerError) as exc_info:
        await position_merger.merge_positions(
            condition_id=condition_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            amount=merge_amount
        )
    
    # Verify error message mentions revert
    assert "revert" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_zero_balance():
    """
    Test error when trying to merge with zero balance.
    
    Validates Requirement 1.5: Balance verification
    """
    # Setup
    web3 = MockWeb3()
    wallet = MockAccount()
    
    position_merger = PositionMerger(
        web3=web3,
        ctf_contract_address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wallet=wallet
    )
    
    # Setup test data
    condition_id = "0x" + "c" * 64
    yes_token_id = "0x" + "1" * 64
    no_token_id = "0x" + "2" * 64
    merge_amount = Decimal('10.0')
    
    # Set zero balances (default)
    ctf_contract = position_merger.ctf_contract
    
    # Attempt merge - should raise InsufficientBalanceError
    with pytest.raises(InsufficientBalanceError) as exc_info:
        await position_merger.merge_positions(
            condition_id=condition_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            amount=merge_amount
        )
    
    # Should fail on YES balance check (checked first)
    assert "YES" in str(exc_info.value)
    assert "0" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
