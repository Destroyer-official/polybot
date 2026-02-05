"""
Transaction Manager for Polymarket Arbitrage Bot.

Manages transaction submission, nonce tracking, and retry logic.
Validates Requirements 18.1, 18.2, 18.4, 18.5, 16.4, 18.3.
"""

import asyncio
import time
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from web3 import Web3
from web3.types import TxReceipt, TxParams
from eth_account.signers.local import LocalAccount
import logging

logger = logging.getLogger(__name__)


@dataclass
class PendingTransaction:
    """Represents a pending transaction."""
    tx_hash: str
    nonce: int
    submitted_at: float
    gas_price: int
    tx_params: Dict


class TransactionError(Exception):
    """Base exception for transaction errors."""
    pass


class NonceConflictError(TransactionError):
    """Raised when a nonce conflict is detected."""
    pass


class InsufficientGasError(TransactionError):
    """Raised when transaction fails due to insufficient gas."""
    pass


class TransactionTimeoutError(TransactionError):
    """Raised when transaction confirmation times out."""
    pass


class TransactionManager:
    """
    Manages transaction submission with nonce tracking and retry logic.
    
    Features:
    - Nonce tracking with pending queue
    - Automatic nonce conflict resolution
    - Stuck transaction resubmission with gas escalation
    - Pending transaction limit enforcement (max 5)
    - Exponential backoff for network errors
    
    Validates Requirements:
    - 18.1: Fetch current nonce from blockchain
    - 18.2: Track pending nonces to avoid conflicts
    - 18.4: Limit pending transactions to 5 maximum
    - 18.5: Update nonce tracker when transactions confirm
    - 16.4: Resubmit stuck transactions (pending > 60s) with 10% higher gas
    - 18.3: Check if transaction was mined before resubmitting
    """
    
    def __init__(
        self,
        web3: Web3,
        wallet: LocalAccount,
        max_pending_tx: int = 5,
        stuck_tx_timeout: int = 60,
        confirmation_timeout: int = 120
    ):
        """
        Initialize Transaction Manager.
        
        Args:
            web3: Web3 instance connected to Polygon RPC
            wallet: Wallet account for signing transactions
            max_pending_tx: Maximum number of pending transactions (default 5)
            stuck_tx_timeout: Seconds before considering transaction stuck (default 60)
            confirmation_timeout: Seconds to wait for confirmation (default 120)
        """
        self.web3 = web3
        self.wallet = wallet
        self.max_pending_tx = max_pending_tx
        self.stuck_tx_timeout = stuck_tx_timeout
        self.confirmation_timeout = confirmation_timeout
        
        # Nonce tracking
        self._current_nonce: Optional[int] = None
        self._pending_nonces: Set[int] = set()
        self._pending_transactions: Dict[str, PendingTransaction] = {}
        
        # Lock for thread-safe nonce management
        self._nonce_lock = asyncio.Lock()
        
        logger.info(
            f"TransactionManager initialized: "
            f"wallet={wallet.address}, max_pending={max_pending_tx}"
        )
    
    async def get_next_nonce(self) -> int:
        """
        Get the next available nonce for transaction submission.
        
        Validates Requirements 18.1, 18.2:
        - Fetches current nonce from blockchain
        - Tracks pending nonces to avoid conflicts
        
        Returns:
            int: Next available nonce
        """
        async with self._nonce_lock:
            # Fetch current nonce from blockchain
            blockchain_nonce = await asyncio.to_thread(
                self.web3.eth.get_transaction_count,
                self.wallet.address,
                'pending'
            )
            
            # If we have no cached nonce, use blockchain nonce
            if self._current_nonce is None:
                self._current_nonce = blockchain_nonce
            
            # Use the maximum of blockchain nonce and our tracked nonce
            # This handles cases where transactions confirmed externally
            self._current_nonce = max(self._current_nonce, blockchain_nonce)
            
            # Find next available nonce not in pending set
            nonce = self._current_nonce
            while nonce in self._pending_nonces:
                nonce += 1
            
            # Mark this nonce as pending
            self._pending_nonces.add(nonce)
            
            # Update current nonce for next call
            self._current_nonce = nonce + 1
            
            logger.debug(
                f"Allocated nonce {nonce} "
                f"(blockchain: {blockchain_nonce}, pending: {len(self._pending_nonces)})"
            )
            
            return nonce
    
    def get_pending_count(self) -> int:
        """
        Get count of pending transactions.
        
        Validates Requirement 18.4: Track pending transaction count
        
        Returns:
            int: Number of pending transactions
        """
        return len(self._pending_transactions)
    
    async def send_transaction(self, tx_params: TxParams) -> str:
        """
        Send transaction with nonce management.
        
        Validates Requirements 18.1, 18.2, 18.4:
        - Manages nonce allocation
        - Enforces pending transaction limit
        - Tracks pending transactions
        
        Args:
            tx_params: Transaction parameters (without nonce)
            
        Returns:
            str: Transaction hash (hex string with 0x prefix)
            
        Raises:
            TransactionError: If pending transaction limit exceeded
            NonceConflictError: If nonce conflict detected
        """
        # Check pending transaction limit (Requirement 18.4)
        if self.get_pending_count() >= self.max_pending_tx:
            raise TransactionError(
                f"Pending transaction limit reached: "
                f"{self.get_pending_count()}/{self.max_pending_tx}"
            )
        
        # Get next available nonce
        nonce = await self.get_next_nonce()
        
        # Add nonce to transaction params
        tx_params_with_nonce = dict(tx_params)
        tx_params_with_nonce['nonce'] = nonce
        tx_params_with_nonce['from'] = self.wallet.address
        
        # Ensure gas price is set
        if 'gasPrice' not in tx_params_with_nonce:
            gas_price = await asyncio.to_thread(self.web3.eth.gas_price)
            tx_params_with_nonce['gasPrice'] = gas_price
        
        try:
            # Sign transaction
            signed_tx = await asyncio.to_thread(
                self.wallet.sign_transaction,
                tx_params_with_nonce
            )
            
            # Send raw transaction
            tx_hash = await asyncio.to_thread(
                self.web3.eth.send_raw_transaction,
                signed_tx.raw_transaction
            )
            
            tx_hash_hex = tx_hash.hex()
            
            # Track pending transaction
            pending_tx = PendingTransaction(
                tx_hash=tx_hash_hex,
                nonce=nonce,
                submitted_at=time.time(),
                gas_price=tx_params_with_nonce['gasPrice'],
                tx_params=tx_params_with_nonce
            )
            self._pending_transactions[tx_hash_hex] = pending_tx
            
            logger.info(
                f"Transaction sent: hash={tx_hash_hex}, nonce={nonce}, "
                f"gas_price={tx_params_with_nonce['gasPrice']}"
            )
            
            return tx_hash_hex
            
        except Exception as e:
            # Release nonce on failure
            async with self._nonce_lock:
                self._pending_nonces.discard(nonce)
            
            logger.error(f"Failed to send transaction: {e}")
            raise TransactionError(f"Transaction submission failed: {e}")
    
    async def wait_for_confirmation(
        self,
        tx_hash: str,
        timeout: Optional[int] = None
    ) -> TxReceipt:
        """
        Wait for transaction confirmation with timeout.
        
        Validates Requirements 18.5, 16.4:
        - Updates nonce tracker when transaction confirms
        - Handles stuck transactions
        
        Args:
            tx_hash: Transaction hash to wait for
            timeout: Timeout in seconds (uses default if None)
            
        Returns:
            TxReceipt: Transaction receipt
            
        Raises:
            TransactionTimeoutError: If confirmation times out
        """
        if timeout is None:
            timeout = self.confirmation_timeout
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check if transaction is mined
                receipt = await asyncio.to_thread(
                    self.web3.eth.get_transaction_receipt,
                    tx_hash
                )
                
                if receipt is not None:
                    # Transaction confirmed
                    await self._on_transaction_confirmed(tx_hash, receipt)
                    
                    if receipt['status'] == 1:
                        logger.info(f"Transaction confirmed: {tx_hash}")
                        return receipt
                    else:
                        logger.error(f"Transaction reverted: {tx_hash}")
                        raise TransactionError(f"Transaction reverted: {tx_hash}")
                
            except TransactionError:
                # Re-raise transaction errors (like reverts)
                raise
            except Exception as e:
                if "not found" not in str(e).lower():
                    logger.warning(f"Error checking transaction: {e}")
            
            # Check if transaction is stuck (Requirement 16.4)
            if tx_hash in self._pending_transactions:
                pending_tx = self._pending_transactions[tx_hash]
                elapsed = time.time() - pending_tx.submitted_at
                
                if elapsed > self.stuck_tx_timeout:
                    logger.warning(
                        f"Transaction stuck for {elapsed:.0f}s: {tx_hash}"
                    )
                    # Note: Caller should handle resubmission
            
            await asyncio.sleep(2)
        
        raise TransactionTimeoutError(
            f"Transaction confirmation timeout after {timeout}s: {tx_hash}"
        )
    
    async def resubmit_stuck_transaction(self, tx_hash: str) -> str:
        """
        Resubmit stuck transaction with 10% higher gas price.
        
        Validates Requirements 16.4, 18.3:
        - Checks if transaction was mined before resubmitting
        - Increases gas price by 10% and resubmits with same nonce
        
        Args:
            tx_hash: Hash of stuck transaction
            
        Returns:
            str: New transaction hash
            
        Raises:
            TransactionError: If transaction not found or already mined
        """
        if tx_hash not in self._pending_transactions:
            raise TransactionError(f"Transaction not found: {tx_hash}")
        
        pending_tx = self._pending_transactions[tx_hash]
        
        # Check if transaction was already mined (Requirement 18.3)
        try:
            receipt = await asyncio.to_thread(
                self.web3.eth.get_transaction_receipt,
                tx_hash
            )
            if receipt is not None:
                logger.info(f"Transaction already mined: {tx_hash}")
                await self._on_transaction_confirmed(tx_hash, receipt)
                return tx_hash
        except Exception:
            pass  # Transaction not mined yet
        
        # Increase gas price by 10% (Requirement 16.4)
        new_gas_price = int(pending_tx.gas_price * 1.1)
        
        # Create new transaction with same nonce but higher gas
        new_tx_params = dict(pending_tx.tx_params)
        new_tx_params['gasPrice'] = new_gas_price
        
        logger.info(
            f"Resubmitting transaction with 10% higher gas: "
            f"nonce={pending_tx.nonce}, "
            f"old_gas={pending_tx.gas_price}, new_gas={new_gas_price}"
        )
        
        try:
            # Sign and send new transaction
            signed_tx = await asyncio.to_thread(
                self.wallet.sign_transaction,
                new_tx_params
            )
            
            new_tx_hash = await asyncio.to_thread(
                self.web3.eth.send_raw_transaction,
                signed_tx.raw_transaction
            )
            
            new_tx_hash_hex = new_tx_hash.hex()
            
            # Remove old transaction from pending
            del self._pending_transactions[tx_hash]
            
            # Add new transaction to pending
            new_pending_tx = PendingTransaction(
                tx_hash=new_tx_hash_hex,
                nonce=pending_tx.nonce,  # Same nonce
                submitted_at=time.time(),
                gas_price=new_gas_price,
                tx_params=new_tx_params
            )
            self._pending_transactions[new_tx_hash_hex] = new_pending_tx
            
            logger.info(f"Transaction resubmitted: {new_tx_hash_hex}")
            
            return new_tx_hash_hex
            
        except Exception as e:
            logger.error(f"Failed to resubmit transaction: {e}")
            raise TransactionError(f"Transaction resubmission failed: {e}")
    
    async def _on_transaction_confirmed(
        self,
        tx_hash: str,
        receipt: TxReceipt
    ) -> None:
        """
        Handle transaction confirmation.
        
        Validates Requirement 18.5: Update nonce tracker when transactions confirm
        
        Args:
            tx_hash: Confirmed transaction hash
            receipt: Transaction receipt
        """
        if tx_hash in self._pending_transactions:
            pending_tx = self._pending_transactions[tx_hash]
            
            # Remove from pending
            del self._pending_transactions[tx_hash]
            
            # Release nonce
            async with self._nonce_lock:
                self._pending_nonces.discard(pending_tx.nonce)
            
            logger.debug(
                f"Transaction confirmed and removed from pending: "
                f"hash={tx_hash}, nonce={pending_tx.nonce}"
            )
    
    async def get_stuck_transactions(self) -> list[PendingTransaction]:
        """
        Get list of stuck transactions (pending > stuck_tx_timeout).
        
        Returns:
            list: List of stuck PendingTransaction objects
        """
        current_time = time.time()
        stuck = []
        
        for tx_hash, pending_tx in self._pending_transactions.items():
            elapsed = current_time - pending_tx.submitted_at
            if elapsed > self.stuck_tx_timeout:
                stuck.append(pending_tx)
        
        return stuck
    
    async def cleanup_confirmed_transactions(self) -> int:
        """
        Check all pending transactions and remove confirmed ones.
        
        This is useful for periodic cleanup to ensure the pending queue
        stays accurate even if confirmations were missed.
        
        Returns:
            int: Number of transactions cleaned up
        """
        cleaned = 0
        tx_hashes = list(self._pending_transactions.keys())
        
        for tx_hash in tx_hashes:
            try:
                receipt = await asyncio.to_thread(
                    self.web3.eth.get_transaction_receipt,
                    tx_hash
                )
                if receipt is not None:
                    await self._on_transaction_confirmed(tx_hash, receipt)
                    cleaned += 1
            except Exception:
                pass  # Transaction not found or error
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} confirmed transactions")
        
        return cleaned
