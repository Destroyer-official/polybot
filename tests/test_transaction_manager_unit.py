"""
Unit tests for Transaction Manager.

Tests stuck transaction handling, gas escalation, and timeout behavior.
Validates Requirements 16.4, 18.3.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.transaction_manager import (
    TransactionManager,
    TransactionError,
    TransactionTimeoutError,
    PendingTransaction
)


# Mock Web3 and Account for testing
class MockWeb3:
    """Mock Web3 instance for testing."""
    
    def __init__(self, initial_nonce=0):
        self.eth = MockEth(initial_nonce)
        self._nonce = initial_nonce
        self._tx_counter = 0
    
    def set_nonce(self, nonce):
        """Set the blockchain nonce."""
        self._nonce = nonce
        self.eth.set_nonce(nonce)


class MockEth:
    """Mock eth interface."""
    
    def __init__(self, initial_nonce=0):
        self._nonce = initial_nonce
        self._receipts = {}
        self.gas_price = 50_000_000_000  # 50 gwei
        self._tx_counter = 0
    
    def get_transaction_count(self, address, block='latest'):
        """Mock get_transaction_count."""
        return self._nonce
    
    def set_nonce(self, nonce):
        """Set the blockchain nonce."""
        self._nonce = nonce
    
    def send_raw_transaction(self, raw_tx):
        """Mock send_raw_transaction with unique hashes."""
        self._tx_counter += 1
        tx_hash = f"0x{'a' * 63}{self._tx_counter:x}"
        return bytes.fromhex(tx_hash[2:])
    
    def get_transaction_receipt(self, tx_hash):
        """Mock get_transaction_receipt."""
        return self._receipts.get(tx_hash)
    
    def add_receipt(self, tx_hash, status=1):
        """Add a mock receipt."""
        self._receipts[tx_hash] = {
            'transactionHash': tx_hash,
            'status': status,
            'blockNumber': 12345,
            'gasUsed': 100000
        }


class MockAccount:
    """Mock account for testing."""
    
    def __init__(self, address="0x1234567890123456789012345678901234567890"):
        self.address = address
        self._sign_counter = 0
    
    def sign_transaction(self, tx_params):
        """Mock sign_transaction."""
        self._sign_counter += 1
        mock_signed = Mock()
        # Create unique raw transaction based on counter
        mock_signed.raw_transaction = bytes([self._sign_counter % 256]) + b'\x00' * 31
        return mock_signed


@pytest.mark.asyncio
async def test_resubmit_stuck_transaction_with_10_percent_higher_gas():
    """
    Test resubmission with 10% higher gas.
    
    Validates Requirement 16.4:
    - When a transaction is stuck (pending > 60s), resubmit with 10% higher gas
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, stuck_tx_timeout=1)  # 1 second for testing
    
    # Send initial transaction
    tx_params = {
        'to': '0x' + '0' * 40,
        'value': 0,
        'gas': 100000,
        'gasPrice': 50_000_000_000  # 50 gwei
    }
    
    original_tx_hash = await tx_manager.send_transaction(tx_params)
    
    # Verify transaction is pending
    assert original_tx_hash in tx_manager._pending_transactions
    original_pending = tx_manager._pending_transactions[original_tx_hash]
    original_gas_price = original_pending.gas_price
    
    # Wait for transaction to become stuck
    await asyncio.sleep(1.5)
    
    # Resubmit stuck transaction
    new_tx_hash = await tx_manager.resubmit_stuck_transaction(original_tx_hash)
    
    # Verify new transaction was created
    assert new_tx_hash != original_tx_hash
    assert new_tx_hash in tx_manager._pending_transactions
    
    # Verify gas price increased by 10%
    new_pending = tx_manager._pending_transactions[new_tx_hash]
    expected_gas_price = int(original_gas_price * 1.1)
    assert new_pending.gas_price == expected_gas_price, \
        f"Gas price should be 10% higher: expected {expected_gas_price}, got {new_pending.gas_price}"
    
    # Verify old transaction removed from pending
    assert original_tx_hash not in tx_manager._pending_transactions
    
    # Verify same nonce used
    assert new_pending.nonce == original_pending.nonce, \
        "Resubmitted transaction should use same nonce"


@pytest.mark.asyncio
async def test_resubmit_checks_if_transaction_was_mined():
    """
    Test that resubmit checks if transaction was already mined.
    
    Validates Requirement 18.3:
    - Check if transaction was mined before resubmitting
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, stuck_tx_timeout=1)
    
    # Send transaction
    tx_params = {
        'to': '0x' + '0' * 40,
        'value': 0,
        'gas': 100000,
        'gasPrice': 50_000_000_000
    }
    
    tx_hash = await tx_manager.send_transaction(tx_params)
    
    # Simulate transaction being mined
    web3.eth.add_receipt(tx_hash, status=1)
    
    # Wait for stuck timeout
    await asyncio.sleep(1.5)
    
    # Try to resubmit - should detect it was already mined
    result_hash = await tx_manager.resubmit_stuck_transaction(tx_hash)
    
    # Should return original hash (already mined)
    assert result_hash == tx_hash
    
    # Transaction should be removed from pending
    assert tx_hash not in tx_manager._pending_transactions


@pytest.mark.asyncio
async def test_wait_for_confirmation_timeout():
    """
    Test timeout handling in wait_for_confirmation.
    
    Validates Requirement 16.4:
    - Handle transaction confirmation timeout
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, confirmation_timeout=2)
    
    # Send transaction
    tx_params = {
        'to': '0x' + '0' * 40,
        'value': 0,
        'gas': 100000,
        'gasPrice': 50_000_000_000
    }
    
    tx_hash = await tx_manager.send_transaction(tx_params)
    
    # Don't add receipt - transaction will never confirm
    
    # Wait for confirmation with short timeout
    with pytest.raises(TransactionTimeoutError) as exc_info:
        await tx_manager.wait_for_confirmation(tx_hash, timeout=1)
    
    # Verify error message mentions timeout
    assert "timeout" in str(exc_info.value).lower()
    assert tx_hash in str(exc_info.value)


@pytest.mark.asyncio
async def test_wait_for_confirmation_success():
    """
    Test successful transaction confirmation.
    
    Validates Requirements 18.5:
    - Update nonce tracker when transaction confirms
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet)
    
    # Send transaction
    tx_params = {
        'to': '0x' + '0' * 40,
        'value': 0,
        'gas': 100000,
        'gasPrice': 50_000_000_000
    }
    
    tx_hash = await tx_manager.send_transaction(tx_params)
    nonce = tx_manager._pending_transactions[tx_hash].nonce
    
    # Verify transaction is pending
    assert tx_hash in tx_manager._pending_transactions
    assert nonce in tx_manager._pending_nonces
    
    # Add receipt after a short delay
    async def add_receipt_delayed():
        await asyncio.sleep(0.5)
        web3.eth.add_receipt(tx_hash, status=1)
    
    # Start adding receipt in background
    asyncio.create_task(add_receipt_delayed())
    
    # Wait for confirmation
    receipt = await tx_manager.wait_for_confirmation(tx_hash, timeout=5)
    
    # Verify receipt returned
    assert receipt is not None
    assert receipt['status'] == 1
    
    # Verify transaction removed from pending
    assert tx_hash not in tx_manager._pending_transactions
    
    # Verify nonce released
    assert nonce not in tx_manager._pending_nonces


@pytest.mark.asyncio
async def test_get_stuck_transactions():
    """
    Test identification of stuck transactions.
    
    Validates Requirement 16.4:
    - Identify transactions stuck for > 60 seconds
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, stuck_tx_timeout=1)
    
    # Send multiple transactions
    tx_hashes = []
    for i in range(3):
        tx_params = {
            'to': '0x' + '0' * 40,
            'value': 0,
            'gas': 100000,
            'gasPrice': 50_000_000_000
        }
        tx_hash = await tx_manager.send_transaction(tx_params)
        tx_hashes.append(tx_hash)
        
        # Add small delay between transactions
        if i < 2:
            await asyncio.sleep(0.3)
    
    # Wait for first two to become stuck
    await asyncio.sleep(1.2)
    
    # Get stuck transactions
    stuck = await tx_manager.get_stuck_transactions()
    
    # First two should be stuck, third should not
    assert len(stuck) >= 2, f"Expected at least 2 stuck transactions, got {len(stuck)}"
    
    # Verify stuck transactions are the older ones
    stuck_hashes = [tx.tx_hash for tx in stuck]
    assert tx_hashes[0] in stuck_hashes
    assert tx_hashes[1] in stuck_hashes


@pytest.mark.asyncio
async def test_resubmit_multiple_times_escalates_gas():
    """
    Test that multiple resubmissions continue to escalate gas price.
    
    Validates Requirement 16.4:
    - Gas price escalation on repeated resubmissions
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, stuck_tx_timeout=0.5)
    
    # Send initial transaction
    tx_params = {
        'to': '0x' + '0' * 40,
        'value': 0,
        'gas': 100000,
        'gasPrice': 100_000_000_000  # 100 gwei
    }
    
    tx_hash = await tx_manager.send_transaction(tx_params)
    original_gas = 100_000_000_000
    
    # Resubmit multiple times
    gas_prices = [original_gas]
    current_hash = tx_hash
    
    for i in range(3):
        await asyncio.sleep(0.6)  # Wait for stuck timeout
        current_hash = await tx_manager.resubmit_stuck_transaction(current_hash)
        current_pending = tx_manager._pending_transactions[current_hash]
        gas_prices.append(current_pending.gas_price)
    
    # Verify gas price escalated each time
    for i in range(1, len(gas_prices)):
        expected_gas = int(gas_prices[i-1] * 1.1)
        assert gas_prices[i] == expected_gas, \
            f"Gas price should escalate by 10%: iteration {i}, expected {expected_gas}, got {gas_prices[i]}"
    
    # Verify final gas price is significantly higher
    final_gas = gas_prices[-1]
    expected_final = int(original_gas * (1.1 ** 3))
    assert final_gas == expected_final, \
        f"Final gas should be {expected_final}, got {final_gas}"


@pytest.mark.asyncio
async def test_cleanup_confirmed_transactions():
    """
    Test cleanup of confirmed transactions from pending queue.
    
    Validates Requirement 18.5:
    - Periodic cleanup of confirmed transactions
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet)
    
    # Send multiple transactions
    tx_hashes = []
    for i in range(5):
        tx_params = {
            'to': '0x' + '0' * 40,
            'value': 0,
            'gas': 100000,
            'gasPrice': 50_000_000_000
        }
        tx_hash = await tx_manager.send_transaction(tx_params)
        tx_hashes.append(tx_hash)
    
    # Verify all pending
    assert tx_manager.get_pending_count() == 5
    
    # Confirm 3 transactions externally (without notifying tx_manager)
    for i in range(3):
        web3.eth.add_receipt(tx_hashes[i], status=1)
    
    # Pending count should still be 5 (not updated yet)
    assert tx_manager.get_pending_count() == 5
    
    # Run cleanup
    cleaned = await tx_manager.cleanup_confirmed_transactions()
    
    # Verify 3 transactions were cleaned up
    assert cleaned == 3, f"Expected 3 cleaned, got {cleaned}"
    
    # Verify pending count updated
    assert tx_manager.get_pending_count() == 2
    
    # Verify correct transactions remain
    for i in range(3):
        assert tx_hashes[i] not in tx_manager._pending_transactions
    for i in range(3, 5):
        assert tx_hashes[i] in tx_manager._pending_transactions


@pytest.mark.asyncio
async def test_transaction_revert_handling():
    """
    Test handling of reverted transactions.
    
    Validates Requirement 16.4:
    - Handle transaction reverts appropriately
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet)
    
    # Send transaction
    tx_params = {
        'to': '0x' + '0' * 40,
        'value': 0,
        'gas': 100000,
        'gasPrice': 50_000_000_000
    }
    
    tx_hash = await tx_manager.send_transaction(tx_params)
    
    # Add receipt with status=0 (reverted) immediately
    web3.eth.add_receipt(tx_hash, status=0)
    
    # Wait for confirmation - should raise error for reverted transaction
    with pytest.raises(TransactionError) as exc_info:
        await tx_manager.wait_for_confirmation(tx_hash, timeout=5)
    
    # Verify error mentions revert
    assert "revert" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
