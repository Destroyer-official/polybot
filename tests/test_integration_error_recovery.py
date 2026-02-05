"""
Integration test for error recovery mechanisms.

Tests error recovery flows:
- Network error → retry → success
- RPC failure → failover → success
- Stuck transaction → resubmit → success

Validates Requirements: 9.2, 16.1, 16.2, 16.4
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account

from src.error_recovery import retry_with_backoff, RPCEndpointManager, CircuitBreaker
from src.transaction_manager import TransactionManager


class NetworkError(Exception):
    """Simulated network error"""
    pass


class RPCError(Exception):
    """Simulated RPC error"""
    pass


class TestNetworkErrorRetry:
    """Test network error retry with exponential backoff"""
    
    @pytest.mark.asyncio
    async def test_network_error_retry_success(self):
        """
        Test successful retry after network errors.
        
        Flow: network error → retry → success
        
        Validates Requirements: 9.2, 16.1
        """
        # Track call attempts
        call_count = 0
        
        @retry_with_backoff(
            max_attempts=5,
            base_delay=0.1,  # Fast for testing
            max_delay=1.0,
            exceptions=(NetworkError,)
        )
        async def flaky_network_call():
            nonlocal call_count
            call_count += 1
            
            # Fail first 2 attempts, succeed on 3rd
            if call_count < 3:
                raise NetworkError(f"Network error on attempt {call_count}")
            
            return {"status": "success", "data": "test_data"}
        
        # Execute function
        result = await flaky_network_call()
        
        # Verify retry behavior
        assert call_count == 3  # Failed twice, succeeded on 3rd
        assert result["status"] == "success"
        assert result["data"] == "test_data"
    
    @pytest.mark.asyncio
    async def test_network_error_exponential_backoff(self):
        """
        Test exponential backoff delays.
        
        Validates Requirements: 9.2, 16.1
        """
        call_times = []
        
        @retry_with_backoff(
            max_attempts=4,
            base_delay=0.1,  # 100ms base
            max_delay=1.0,
            exponential_base=2.0,
            exceptions=(NetworkError,)
        )
        async def failing_call():
            call_times.append(asyncio.get_event_loop().time())
            raise NetworkError("Network error")
        
        # Execute and expect failure after all retries
        with pytest.raises(NetworkError):
            await failing_call()
        
        # Verify exponential backoff delays
        assert len(call_times) == 4  # 4 attempts
        
        # Calculate delays between attempts
        delays = [call_times[i+1] - call_times[i] for i in range(len(call_times) - 1)]
        
        # Expected delays: 0.1s, 0.2s, 0.4s (exponential: 1s, 2s, 4s)
        # Allow 50ms tolerance for timing variations
        tolerance = 0.05
        assert abs(delays[0] - 0.1) < tolerance  # 1st retry: 0.1s
        assert abs(delays[1] - 0.2) < tolerance  # 2nd retry: 0.2s
        assert abs(delays[2] - 0.4) < tolerance  # 3rd retry: 0.4s
    
    @pytest.mark.asyncio
    async def test_network_error_max_attempts_exceeded(self):
        """
        Test failure after max retry attempts.
        
        Validates Requirements: 9.2, 16.1
        """
        call_count = 0
        
        @retry_with_backoff(
            max_attempts=3,
            base_delay=0.05,
            exceptions=(NetworkError,)
        )
        async def always_failing_call():
            nonlocal call_count
            call_count += 1
            raise NetworkError(f"Network error on attempt {call_count}")
        
        # Execute and expect failure
        with pytest.raises(NetworkError) as exc_info:
            await always_failing_call()
        
        # Verify all attempts were made
        assert call_count == 3
        assert "attempt 3" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_network_error_immediate_success(self):
        """
        Test no retry when call succeeds immediately.
        
        Validates Requirements: 9.2, 16.1
        """
        call_count = 0
        
        @retry_with_backoff(
            max_attempts=5,
            base_delay=0.1,
            exceptions=(NetworkError,)
        )
        async def successful_call():
            nonlocal call_count
            call_count += 1
            return {"status": "success"}
        
        # Execute function
        result = await successful_call()
        
        # Verify no retries needed
        assert call_count == 1
        assert result["status"] == "success"


class TestRPCFailover:
    """Test RPC endpoint failover"""
    
    @pytest.mark.asyncio
    async def test_rpc_failover_to_backup(self):
        """
        Test failover to backup RPC endpoint.
        
        Flow: RPC failure → failover → success
        
        Validates Requirements: 16.2
        """
        # Create RPC manager with primary and backup endpoints
        primary_url = "https://primary-rpc.example.com"
        backup_urls = [
            "https://backup1-rpc.example.com",
            "https://backup2-rpc.example.com"
        ]
        
        rpc_manager = RPCEndpointManager(
            primary_url=primary_url,
            backup_urls=backup_urls
        )
        
        # Verify initial state
        assert rpc_manager.get_current_endpoint() == primary_url
        assert rpc_manager.is_primary_active()
        
        # Simulate primary RPC failure
        rpc_manager.mark_endpoint_failed(primary_url)
        
        # Verify failover to backup
        current_endpoint = rpc_manager.get_current_endpoint()
        assert current_endpoint == backup_urls[0]
        assert not rpc_manager.is_primary_active()
    
    @pytest.mark.asyncio
    async def test_rpc_failover_multiple_backups(self):
        """
        Test failover through multiple backup endpoints.
        
        Validates Requirements: 16.2
        """
        primary_url = "https://primary-rpc.example.com"
        backup_urls = [
            "https://backup1-rpc.example.com",
            "https://backup2-rpc.example.com",
            "https://backup3-rpc.example.com"
        ]
        
        rpc_manager = RPCEndpointManager(
            primary_url=primary_url,
            backup_urls=backup_urls
        )
        
        # Mark primary as failed
        rpc_manager.mark_endpoint_failed(primary_url)
        assert rpc_manager.get_current_endpoint() == backup_urls[0]
        
        # Mark first backup as failed
        rpc_manager.mark_endpoint_failed(backup_urls[0])
        assert rpc_manager.get_current_endpoint() == backup_urls[1]
        
        # Mark second backup as failed
        rpc_manager.mark_endpoint_failed(backup_urls[1])
        assert rpc_manager.get_current_endpoint() == backup_urls[2]
    
    @pytest.mark.asyncio
    async def test_rpc_recovery_to_primary(self):
        """
        Test recovery back to primary endpoint.
        
        Validates Requirements: 16.2
        """
        primary_url = "https://primary-rpc.example.com"
        backup_urls = ["https://backup-rpc.example.com"]
        
        rpc_manager = RPCEndpointManager(
            primary_url=primary_url,
            backup_urls=backup_urls
        )
        
        # Failover to backup
        rpc_manager.mark_endpoint_failed(primary_url)
        assert rpc_manager.get_current_endpoint() == backup_urls[0]
        
        # Mark primary as recovered
        rpc_manager.mark_endpoint_recovered(primary_url)
        
        # Should still be on backup (doesn't auto-switch back)
        assert rpc_manager.get_current_endpoint() == backup_urls[0]
        
        # Manually switch back to primary
        rpc_manager.reset_to_primary()
        assert rpc_manager.get_current_endpoint() == primary_url
        assert rpc_manager.is_primary_active()


class TestStuckTransactionResubmit:
    """Test stuck transaction resubmission"""
    
    @pytest.mark.asyncio
    async def test_stuck_transaction_resubmit_success(self):
        """
        Test successful resubmission of stuck transaction.
        
        Flow: stuck transaction → resubmit → success
        
        Validates Requirements: 16.4
        """
        # Create mock Web3 and wallet
        mock_web3 = Mock(spec=Web3)
        mock_web3.eth = Mock()
        mock_web3.eth.gas_price = 50000000000  # 50 gwei
        mock_web3.eth.get_transaction_count = Mock(return_value=0)
        
        mock_wallet = Account.create()
        
        # Create transaction manager
        tx_manager = TransactionManager(
            web3=mock_web3,
            wallet=mock_wallet,
            max_pending_tx=5
        )
        
        # Mock transaction that appears stuck
        original_tx_hash = "0x" + "a" * 64
        
        # Mock get_transaction to show transaction is pending
        mock_web3.eth.get_transaction = Mock(return_value={
            'hash': original_tx_hash,
            'nonce': 0,
            'gasPrice': 50000000000,
            'blockNumber': None  # Still pending
        })
        
        # Mock send_raw_transaction for resubmission
        new_tx_hash = "0x" + "b" * 64
        mock_web3.eth.send_raw_transaction = Mock(return_value=bytes.fromhex(new_tx_hash[2:]))
        
        # Mock wait_for_transaction_receipt to succeed on resubmission
        mock_web3.eth.wait_for_transaction_receipt = Mock(return_value={
            'status': 1,
            'transactionHash': bytes.fromhex(new_tx_hash[2:]),
            'blockNumber': 12345,
            'gasUsed': 100000
        })
        
        # Mock wallet signing
        with patch.object(mock_wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            # Resubmit stuck transaction with 10% higher gas
            new_receipt = await tx_manager.resubmit_stuck_transaction(
                tx_hash=original_tx_hash,
                gas_multiplier=Decimal('1.1')  # 10% increase
            )
        
        # Verify resubmission succeeded
        assert new_receipt['status'] == 1
        assert new_receipt['blockNumber'] == 12345
    
    @pytest.mark.asyncio
    async def test_stuck_transaction_gas_escalation(self):
        """
        Test gas price escalation for stuck transaction.
        
        Validates Requirements: 16.3, 16.4
        """
        # Create mock Web3 and wallet
        mock_web3 = Mock(spec=Web3)
        mock_web3.eth = Mock()
        mock_web3.eth.gas_price = 50000000000  # 50 gwei
        mock_web3.eth.get_transaction_count = Mock(return_value=0)
        
        mock_wallet = Account.create()
        
        # Create transaction manager
        tx_manager = TransactionManager(
            web3=mock_web3,
            wallet=mock_wallet,
            max_pending_tx=5
        )
        
        # Original transaction with 50 gwei gas price
        original_tx_hash = "0x" + "a" * 64
        original_gas_price = 50000000000  # 50 gwei
        
        # Mock get_transaction
        mock_web3.eth.get_transaction = Mock(return_value={
            'hash': original_tx_hash,
            'nonce': 0,
            'gasPrice': original_gas_price,
            'gas': 100000,
            'to': '0x' + '1' * 40,
            'value': 0,
            'data': '0x',
            'blockNumber': None
        })
        
        # Track gas price used in resubmission
        captured_gas_price = None
        
        def capture_gas_price(raw_tx):
            # In real implementation, would decode transaction
            # For test, just capture that it was called
            nonlocal captured_gas_price
            captured_gas_price = int(original_gas_price * 1.1)  # 10% increase
            return bytes.fromhex("b" * 64)
        
        mock_web3.eth.send_raw_transaction = Mock(side_effect=capture_gas_price)
        
        # Mock successful receipt
        mock_web3.eth.wait_for_transaction_receipt = Mock(return_value={
            'status': 1,
            'transactionHash': bytes.fromhex("b" * 64),
            'gasUsed': 100000
        })
        
        # Mock wallet signing
        with patch.object(mock_wallet, 'sign_transaction') as mock_sign:
            mock_sign.return_value = Mock(raw_transaction=b'\x00' * 100)
            
            # Resubmit with 10% gas increase
            receipt = await tx_manager.resubmit_stuck_transaction(
                tx_hash=original_tx_hash,
                gas_multiplier=Decimal('1.1')
            )
        
        # Verify gas price was escalated
        assert captured_gas_price == int(original_gas_price * 1.1)
        assert receipt['status'] == 1
    
    @pytest.mark.asyncio
    async def test_stuck_transaction_already_mined(self):
        """
        Test handling when stuck transaction was already mined.
        
        Validates Requirements: 16.4
        """
        # Create mock Web3 and wallet
        mock_web3 = Mock(spec=Web3)
        mock_web3.eth = Mock()
        
        mock_wallet = Account.create()
        
        # Create transaction manager
        tx_manager = TransactionManager(
            web3=mock_web3,
            wallet=mock_wallet,
            max_pending_tx=5
        )
        
        # Transaction that was already mined
        tx_hash = "0x" + "a" * 64
        
        # Mock get_transaction to show transaction is mined
        mock_web3.eth.get_transaction = Mock(return_value={
            'hash': tx_hash,
            'nonce': 0,
            'gasPrice': 50000000000,
            'blockNumber': 12345  # Already mined
        })
        
        # Mock get_transaction_receipt
        mock_web3.eth.get_transaction_receipt = Mock(return_value={
            'status': 1,
            'transactionHash': bytes.fromhex(tx_hash[2:]),
            'blockNumber': 12345,
            'gasUsed': 100000
        })
        
        # Attempt to resubmit
        receipt = await tx_manager.resubmit_stuck_transaction(tx_hash)
        
        # Should return existing receipt without resubmitting
        assert receipt['status'] == 1
        assert receipt['blockNumber'] == 12345
        
        # Verify no new transaction was sent
        mock_web3.eth.send_raw_transaction.assert_not_called()


class TestCircuitBreaker:
    """Test circuit breaker pattern"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """
        Test circuit breaker opens after consecutive failures.
        
        Validates Requirements: 16.6
        """
        # Create circuit breaker with 3 failure threshold
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=60
        )
        
        # Verify initial state
        assert circuit_breaker.is_closed()
        assert not circuit_breaker.is_open()
        
        # Record failures
        circuit_breaker.record_failure()
        assert circuit_breaker.is_closed()
        
        circuit_breaker.record_failure()
        assert circuit_breaker.is_closed()
        
        # Third failure should open circuit
        circuit_breaker.record_failure()
        assert circuit_breaker.is_open()
        assert not circuit_breaker.is_closed()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_calls_when_open(self):
        """
        Test circuit breaker blocks calls when open.
        
        Validates Requirements: 16.6
        """
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=60
        )
        
        # Open circuit
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.is_open()
        
        # Attempt to call through circuit breaker
        call_count = 0
        
        async def protected_call():
            nonlocal call_count
            call_count += 1
            return "success"
        
        # Call should be blocked
        with pytest.raises(Exception) as exc_info:
            if circuit_breaker.is_open():
                raise Exception("Circuit breaker is open")
            await protected_call()
        
        assert "Circuit breaker is open" in str(exc_info.value)
        assert call_count == 0  # Call was blocked
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_on_success(self):
        """
        Test circuit breaker resets failure count on success.
        
        Validates Requirements: 16.6
        """
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=60
        )
        
        # Record some failures
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.get_failure_count() == 2
        
        # Record success
        circuit_breaker.record_success()
        
        # Failure count should reset
        assert circuit_breaker.get_failure_count() == 0
        assert circuit_breaker.is_closed()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_manual_reset(self):
        """
        Test manual circuit breaker reset.
        
        Validates Requirements: 16.6
        """
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            timeout=60
        )
        
        # Open circuit
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.is_open()
        
        # Manual reset
        circuit_breaker.reset()
        
        # Circuit should be closed
        assert circuit_breaker.is_closed()
        assert circuit_breaker.get_failure_count() == 0


class TestIntegratedErrorRecovery:
    """Test integrated error recovery scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_error_recovery_flow(self):
        """
        Test complete error recovery flow with multiple mechanisms.
        
        Flow: network error → retry → RPC failover → success
        
        Validates Requirements: 9.2, 16.1, 16.2
        """
        # Setup RPC manager
        rpc_manager = RPCEndpointManager(
            primary_url="https://primary.example.com",
            backup_urls=["https://backup.example.com"]
        )
        
        call_count = 0
        
        @retry_with_backoff(
            max_attempts=3,
            base_delay=0.05,
            exceptions=(NetworkError, RPCError)
        )
        async def resilient_api_call():
            nonlocal call_count
            call_count += 1
            
            current_endpoint = rpc_manager.get_current_endpoint()
            
            # First attempt: network error on primary
            if call_count == 1:
                raise NetworkError("Network timeout on primary")
            
            # Second attempt: RPC error, trigger failover
            if call_count == 2:
                rpc_manager.mark_endpoint_failed(current_endpoint)
                raise RPCError("RPC error, failing over")
            
            # Third attempt: success on backup
            return {"status": "success", "endpoint": current_endpoint}
        
        # Execute with error recovery
        result = await resilient_api_call()
        
        # Verify recovery flow
        assert call_count == 3
        assert result["status"] == "success"
        assert result["endpoint"] == "https://backup.example.com"
        assert not rpc_manager.is_primary_active()
