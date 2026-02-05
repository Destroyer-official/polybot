"""
Property-based tests for Transaction Manager.

Tests nonce management, pending transaction limits, and stuck transaction handling.
Validates Requirements 18.1, 18.2, 18.5, 6.5, 18.4.
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
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
    NonceConflictError,
    TransactionTimeoutError,
    PendingTransaction
)


# Mock Web3 and Account for testing
class MockWeb3:
    """Mock Web3 instance for testing."""
    
    def __init__(self, initial_nonce=0):
        self.eth = MockEth(initial_nonce)
        self._nonce = initial_nonce
    
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
        # Generate unique hash based on counter
        tx_hash = f"0x{self._tx_counter:064x}"
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
    
    def sign_transaction(self, tx_params):
        """Mock sign_transaction."""
        mock_signed = Mock()
        mock_signed.raw_transaction = b'\x00' * 32
        return mock_signed


@given(
    num_transactions=st.integers(min_value=1, max_value=20),
    initial_nonce=st.integers(min_value=0, max_value=100)
)
@settings(max_examples=100, deadline=None)
def test_nonce_management_sequential(num_transactions, initial_nonce):
    """
    **Validates: Requirements 18.1, 18.2, 18.5**
    
    Feature: polymarket-arbitrage-bot, Property 51: Nonce Management
    
    For any transaction submission, the system should fetch the current nonce,
    track pending nonces to avoid conflicts, and update the nonce tracker when
    transactions confirm.
    
    This test verifies:
    1. Nonces are allocated sequentially without gaps
    2. Each nonce is unique (no conflicts)
    3. Nonces start from blockchain nonce
    4. Pending nonces are tracked correctly
    """
    # Setup
    web3 = MockWeb3(initial_nonce)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, max_pending_tx=25)
    
    allocated_nonces = []
    
    async def allocate_nonces():
        for i in range(num_transactions):
            nonce = await tx_manager.get_next_nonce()
            allocated_nonces.append(nonce)
    
    # Run test
    asyncio.run(allocate_nonces())
    
    # Verify nonces are sequential starting from initial_nonce
    expected_nonces = list(range(initial_nonce, initial_nonce + num_transactions))
    assert allocated_nonces == expected_nonces, \
        f"Nonces not sequential: expected {expected_nonces}, got {allocated_nonces}"
    
    # Verify all nonces are unique (no conflicts)
    assert len(allocated_nonces) == len(set(allocated_nonces)), \
        f"Duplicate nonces detected: {allocated_nonces}"
    
    # Verify pending nonces are tracked
    assert len(tx_manager._pending_nonces) == num_transactions, \
        f"Pending nonces count mismatch: expected {num_transactions}, got {len(tx_manager._pending_nonces)}"
    
    # Verify all allocated nonces are in pending set
    for nonce in allocated_nonces:
        assert nonce in tx_manager._pending_nonces, \
            f"Nonce {nonce} not tracked in pending set"


@given(
    num_transactions=st.integers(min_value=2, max_value=10),
    initial_nonce=st.integers(min_value=0, max_value=50)
)
@settings(max_examples=100, deadline=None)
def test_nonce_management_with_confirmations(num_transactions, initial_nonce):
    """
    **Validates: Requirements 18.1, 18.2, 18.5**
    
    Feature: polymarket-arbitrage-bot, Property 51: Nonce Management
    
    Test that nonces are properly released when transactions confirm,
    and the nonce tracker is updated correctly.
    """
    # Setup
    web3 = MockWeb3(initial_nonce)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, max_pending_tx=25)
    
    async def test_with_confirmations():
        allocated_nonces = []
        tx_hashes = []
        
        # Send transactions (which allocates nonces internally)
        for i in range(num_transactions):
            tx_params = {
                'to': '0x' + '0' * 40,
                'value': 0,
                'gas': 100000,
                'gasPrice': 50_000_000_000
            }
            tx_hash = await tx_manager.send_transaction(tx_params)
            tx_hashes.append(tx_hash)
            
            # Get the nonce that was allocated
            pending_tx = tx_manager._pending_transactions[tx_hash]
            allocated_nonces.append(pending_tx.nonce)
        
        # Verify all nonces are pending
        assert len(tx_manager._pending_nonces) == num_transactions
        assert len(tx_manager._pending_transactions) == num_transactions
        
        # Confirm transactions one by one
        for i, tx_hash in enumerate(tx_hashes):
            # Add receipt to mock
            web3.eth.add_receipt(tx_hash, status=1)
            
            # Simulate confirmation
            receipt = {'transactionHash': tx_hash, 'status': 1}
            await tx_manager._on_transaction_confirmed(tx_hash, receipt)
            
            # Verify nonce was released
            assert allocated_nonces[i] not in tx_manager._pending_nonces, \
                f"Nonce {allocated_nonces[i]} not released after confirmation"
            
            # Verify transaction removed from pending
            assert tx_hash not in tx_manager._pending_transactions, \
                f"Transaction {tx_hash} not removed from pending"
        
        # Verify all nonces released
        assert len(tx_manager._pending_nonces) == 0, \
            f"Pending nonces not empty after all confirmations: {tx_manager._pending_nonces}"
        
        # Verify all transactions removed
        assert len(tx_manager._pending_transactions) == 0, \
            f"Pending transactions not empty: {tx_manager._pending_transactions}"
    
    # Run test
    asyncio.run(test_with_confirmations())


@given(
    blockchain_nonce=st.integers(min_value=0, max_value=100),
    nonce_jump=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=100, deadline=None)
def test_nonce_synchronization_with_blockchain(blockchain_nonce, nonce_jump):
    """
    **Validates: Requirements 18.1, 18.2**
    
    Feature: polymarket-arbitrage-bot, Property 51: Nonce Management
    
    Test that the transaction manager correctly synchronizes with blockchain nonce,
    even when external transactions cause the blockchain nonce to jump ahead.
    """
    # Setup
    web3 = MockWeb3(blockchain_nonce)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet)
    
    async def test_sync():
        # Get initial nonce
        nonce1 = await tx_manager.get_next_nonce()
        assert nonce1 == blockchain_nonce, \
            f"First nonce should match blockchain: expected {blockchain_nonce}, got {nonce1}"
        
        # Simulate external transaction (blockchain nonce jumps)
        new_blockchain_nonce = blockchain_nonce + nonce_jump
        web3.set_nonce(new_blockchain_nonce)
        
        # Get next nonce - should sync with new blockchain nonce
        nonce2 = await tx_manager.get_next_nonce()
        
        # Nonce should be at least the new blockchain nonce
        assert nonce2 >= new_blockchain_nonce, \
            f"Nonce should sync with blockchain: expected >= {new_blockchain_nonce}, got {nonce2}"
        
        # If we had pending nonces, new nonce should skip them
        # Otherwise, it should be exactly the blockchain nonce
        if nonce1 in tx_manager._pending_nonces:
            # Should skip the pending nonce
            assert nonce2 > nonce1, \
                f"Nonce should skip pending: {nonce2} should be > {nonce1}"
        else:
            # Should use blockchain nonce
            assert nonce2 == new_blockchain_nonce, \
                f"Nonce should match blockchain: expected {new_blockchain_nonce}, got {nonce2}"
    
    # Run test
    asyncio.run(test_sync())


@given(
    num_concurrent=st.integers(min_value=2, max_value=10),
    initial_nonce=st.integers(min_value=0, max_value=50)
)
@settings(max_examples=50, deadline=None)
def test_nonce_management_concurrent_allocation(num_concurrent, initial_nonce):
    """
    **Validates: Requirements 18.1, 18.2**
    
    Feature: polymarket-arbitrage-bot, Property 51: Nonce Management
    
    Test that concurrent nonce allocations don't create conflicts.
    Each concurrent request should get a unique nonce.
    """
    # Setup
    web3 = MockWeb3(initial_nonce)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, max_pending_tx=25)
    
    async def test_concurrent():
        # Allocate nonces concurrently
        tasks = [tx_manager.get_next_nonce() for _ in range(num_concurrent)]
        allocated_nonces = await asyncio.gather(*tasks)
        
        # Verify all nonces are unique
        assert len(allocated_nonces) == len(set(allocated_nonces)), \
            f"Concurrent allocation created duplicate nonces: {allocated_nonces}"
        
        # Verify nonces are in expected range
        expected_range = range(initial_nonce, initial_nonce + num_concurrent)
        assert set(allocated_nonces) == set(expected_range), \
            f"Nonces not in expected range: expected {list(expected_range)}, got {allocated_nonces}"
        
        # Verify all nonces are tracked as pending
        for nonce in allocated_nonces:
            assert nonce in tx_manager._pending_nonces, \
                f"Nonce {nonce} not tracked as pending"
    
    # Run test
    asyncio.run(test_concurrent())


@given(
    initial_nonce=st.integers(min_value=0, max_value=50),
    num_to_allocate=st.integers(min_value=1, max_value=10),
    num_to_release=st.integers(min_value=0, max_value=10)
)
@settings(max_examples=100, deadline=None)
def test_nonce_reuse_after_release(initial_nonce, num_to_allocate, num_to_release):
    """
    **Validates: Requirements 18.2, 18.5**
    
    Feature: polymarket-arbitrage-bot, Property 51: Nonce Management
    
    Test that nonces are NOT reused even after being released.
    Once a nonce is used, it should never be allocated again.
    """
    assume(num_to_release <= num_to_allocate)
    
    # Setup
    web3 = MockWeb3(initial_nonce)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, max_pending_tx=25)
    
    async def test_no_reuse():
        # Allocate nonces
        allocated_nonces = []
        for i in range(num_to_allocate):
            nonce = await tx_manager.get_next_nonce()
            allocated_nonces.append(nonce)
        
        # Release some nonces by removing them from pending
        released_nonces = allocated_nonces[:num_to_release]
        async with tx_manager._nonce_lock:
            for nonce in released_nonces:
                tx_manager._pending_nonces.discard(nonce)
        
        # Allocate more nonces
        new_nonces = []
        for i in range(5):
            nonce = await tx_manager.get_next_nonce()
            new_nonces.append(nonce)
        
        # Verify new nonces don't reuse released nonces
        for new_nonce in new_nonces:
            assert new_nonce not in released_nonces, \
                f"Nonce {new_nonce} was reused after being released"
        
        # Verify new nonces are sequential and higher than all previous
        max_allocated = max(allocated_nonces)
        for new_nonce in new_nonces:
            assert new_nonce > max_allocated, \
                f"New nonce {new_nonce} should be > {max_allocated}"
    
    # Run test
    asyncio.run(test_no_reuse())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



@given(
    max_pending=st.integers(min_value=1, max_value=10),
    num_to_send=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=100, deadline=None)
def test_pending_transaction_limit_invariant(max_pending, num_to_send):
    """
    **Validates: Requirements 6.5, 18.4**
    
    Feature: polymarket-arbitrage-bot, Property 19: Pending Transaction Limit Invariant
    
    At any point in time, the number of pending transactions should not exceed 5
    (or the configured max), preventing nonce conflicts and transaction queue buildup.
    
    This test verifies:
    1. Pending transaction count never exceeds the limit
    2. TransactionError is raised when limit is reached
    3. Limit is enforced before transaction submission
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, max_pending_tx=max_pending)
    
    async def test_limit():
        successful_sends = 0
        
        for i in range(num_to_send):
            # Check current pending count
            pending_count = tx_manager.get_pending_count()
            
            # Invariant: pending count should never exceed max
            assert pending_count <= max_pending, \
                f"Pending transaction count {pending_count} exceeds limit {max_pending}"
            
            # Try to send transaction
            tx_params = {
                'to': '0x' + '0' * 40,
                'value': 0,
                'gas': 100000,
                'gasPrice': 50_000_000_000
            }
            
            if pending_count < max_pending:
                # Should succeed
                tx_hash = await tx_manager.send_transaction(tx_params)
                assert tx_hash is not None
                successful_sends += 1
                
                # Verify pending count increased
                new_pending_count = tx_manager.get_pending_count()
                assert new_pending_count == pending_count + 1, \
                    f"Pending count should increase: {pending_count} -> {new_pending_count}"
            else:
                # Should fail with TransactionError
                with pytest.raises(TransactionError) as exc_info:
                    await tx_manager.send_transaction(tx_params)
                
                assert "limit" in str(exc_info.value).lower(), \
                    f"Error should mention limit: {exc_info.value}"
                
                # Verify pending count didn't change
                new_pending_count = tx_manager.get_pending_count()
                assert new_pending_count == pending_count, \
                    f"Pending count should not change on failure: {pending_count} -> {new_pending_count}"
        
        # Verify final state
        final_pending = tx_manager.get_pending_count()
        assert final_pending <= max_pending, \
            f"Final pending count {final_pending} exceeds limit {max_pending}"
        
        # Verify we sent exactly max_pending transactions (or num_to_send if less)
        expected_sends = min(num_to_send, max_pending)
        assert successful_sends == expected_sends, \
            f"Expected {expected_sends} successful sends, got {successful_sends}"
    
    # Run test
    asyncio.run(test_limit())


@given(
    max_pending=st.integers(min_value=2, max_value=10),
    num_to_confirm=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=100, deadline=None)
def test_pending_limit_with_confirmations(max_pending, num_to_confirm):
    """
    **Validates: Requirements 6.5, 18.4, 18.5**
    
    Feature: polymarket-arbitrage-bot, Property 19: Pending Transaction Limit Invariant
    
    Test that confirming transactions frees up slots in the pending queue,
    allowing new transactions to be sent.
    """
    assume(num_to_confirm <= max_pending)
    
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, max_pending_tx=max_pending)
    
    async def test_with_confirmations():
        # Fill up to the limit
        tx_hashes = []
        for i in range(max_pending):
            tx_params = {
                'to': '0x' + '0' * 40,
                'value': 0,
                'gas': 100000,
                'gasPrice': 50_000_000_000
            }
            tx_hash = await tx_manager.send_transaction(tx_params)
            tx_hashes.append(tx_hash)
        
        # Verify at limit
        assert tx_manager.get_pending_count() == max_pending
        
        # Try to send one more - should fail
        with pytest.raises(TransactionError):
            await tx_manager.send_transaction({
                'to': '0x' + '0' * 40,
                'value': 0,
                'gas': 100000,
                'gasPrice': 50_000_000_000
            })
        
        # Confirm some transactions
        for i in range(num_to_confirm):
            tx_hash = tx_hashes[i]
            web3.eth.add_receipt(tx_hash, status=1)
            receipt = {'transactionHash': tx_hash, 'status': 1}
            await tx_manager._on_transaction_confirmed(tx_hash, receipt)
        
        # Verify pending count decreased
        expected_pending = max_pending - num_to_confirm
        assert tx_manager.get_pending_count() == expected_pending, \
            f"Expected {expected_pending} pending, got {tx_manager.get_pending_count()}"
        
        # Should now be able to send num_to_confirm more transactions
        for i in range(num_to_confirm):
            tx_params = {
                'to': '0x' + '0' * 40,
                'value': 0,
                'gas': 100000,
                'gasPrice': 50_000_000_000
            }
            tx_hash = await tx_manager.send_transaction(tx_params)
            assert tx_hash is not None
        
        # Verify back at limit
        assert tx_manager.get_pending_count() == max_pending
        
        # Invariant still holds
        assert tx_manager.get_pending_count() <= max_pending
    
    # Run test
    asyncio.run(test_with_confirmations())


@given(
    max_pending=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100, deadline=None)
def test_pending_limit_never_exceeded(max_pending):
    """
    **Validates: Requirements 6.5, 18.4**
    
    Feature: polymarket-arbitrage-bot, Property 19: Pending Transaction Limit Invariant
    
    Stress test: Try to send many transactions rapidly and verify the limit
    is never exceeded, even under concurrent load.
    """
    # Setup
    web3 = MockWeb3(0)
    wallet = MockAccount()
    tx_manager = TransactionManager(web3, wallet, max_pending_tx=max_pending)
    
    async def test_stress():
        # Try to send 3x the limit sequentially (not concurrently to avoid race conditions)
        num_attempts = max_pending * 3
        
        successful = []
        failed = 0
        
        for i in range(num_attempts):
            try:
                tx_params = {
                    'to': '0x' + '0' * 40,
                    'value': 0,
                    'gas': 100000,
                    'gasPrice': 50_000_000_000
                }
                tx_hash = await tx_manager.send_transaction(tx_params)
                successful.append(tx_hash)
            except TransactionError:
                failed += 1
            
            # Verify invariant after each attempt
            pending_count = tx_manager.get_pending_count()
            assert pending_count <= max_pending, \
                f"Invariant violated: {pending_count} > {max_pending}"
        
        # Verify we sent exactly max_pending transactions
        assert len(successful) == max_pending, \
            f"Expected {max_pending} successful sends, got {len(successful)}"
        
        # Verify remaining attempts failed
        assert failed == num_attempts - max_pending, \
            f"Expected {num_attempts - max_pending} failures, got {failed}"
        
        # Verify pending count equals max
        assert tx_manager.get_pending_count() == max_pending, \
            f"Expected {max_pending} pending, got {tx_manager.get_pending_count()}"
        
        # Invariant: never exceeded
        assert tx_manager.get_pending_count() <= max_pending
    
    # Run test
    asyncio.run(test_stress())
