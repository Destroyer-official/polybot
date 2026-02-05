"""
Position Merger for Polymarket Arbitrage Bot.

Merges YES and NO positions to redeem $1.00 USDC per position pair.
Validates Requirements 1.5, 1.6.
"""

import asyncio
import logging
from typing import Optional
from decimal import Decimal
from web3 import Web3
from web3.contract import Contract
from web3.types import TxReceipt, TxParams
from eth_account.signers.local import LocalAccount

logger = logging.getLogger(__name__)


class PositionMergerError(Exception):
    """Base exception for position merger errors."""
    pass


class InsufficientBalanceError(PositionMergerError):
    """Raised when wallet has insufficient position balance."""
    pass


class MergeRedemptionError(PositionMergerError):
    """Raised when merge doesn't redeem expected $1.00 USDC."""
    pass


class PositionMerger:
    """
    Manages merging of YES and NO positions to redeem USDC.
    
    Features:
    - Balance verification before merge
    - Gas estimation for merge operations
    - Verification of $1.00 USDC redemption after merge
    - Support for CTF (Conditional Token Framework) contract
    
    Validates Requirements:
    - 1.5: Merge YES and NO positions with balance verification
    - 1.6: Verify $1.00 USDC redemption per position pair
    """
    
    # CTF Exchange ABI (minimal interface for mergePositions)
    CTF_ABI = '''[
        {
            "constant": false,
            "inputs": [
                {"name": "collateralToken", "type": "address"},
                {"name": "parentCollectionId", "type": "bytes32"},
                {"name": "conditionId", "type": "bytes32"},
                {"name": "partition", "type": "uint256[]"},
                {"name": "amount", "type": "uint256"}
            ],
            "name": "mergePositions",
            "outputs": [],
            "payable": false,
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "constant": true,
            "inputs": [
                {"name": "owner", "type": "address"},
                {"name": "id", "type": "uint256"}
            ],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": false,
            "stateMutability": "view",
            "type": "function"
        }
    ]'''
    
    # USDC ABI (minimal interface for balance checking)
    USDC_ABI = '''[
        {
            "constant": true,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        }
    ]'''
    
    # Zero bytes32 for parent collection ID (no parent)
    ZERO_BYTES32 = "0x" + "0" * 64
    
    def __init__(
        self,
        web3: Web3,
        ctf_contract_address: str,
        usdc_address: str,
        wallet: LocalAccount,
        gas_limit_default: int = 300000
    ):
        """
        Initialize Position Merger.
        
        Args:
            web3: Web3 instance connected to Polygon RPC
            ctf_contract_address: Address of CTF Exchange contract
            usdc_address: Address of USDC token contract
            wallet: Wallet account for signing transactions
            gas_limit_default: Default gas limit for merge operations
        """
        self.web3 = web3
        self.wallet = wallet
        self.gas_limit_default = gas_limit_default
        
        # Initialize CTF contract
        self.ctf_contract = web3.eth.contract(
            address=Web3.to_checksum_address(ctf_contract_address),
            abi=self.CTF_ABI
        )
        
        # Initialize USDC contract
        self.usdc_contract = web3.eth.contract(
            address=Web3.to_checksum_address(usdc_address),
            abi=self.USDC_ABI
        )
        
        self.usdc_address = Web3.to_checksum_address(usdc_address)
        
        logger.info(
            f"PositionMerger initialized: "
            f"wallet={wallet.address}, "
            f"ctf={ctf_contract_address}, "
            f"usdc={usdc_address}"
        )
    
    def _get_token_id(self, condition_id: str, outcome_index: int) -> int:
        """
        Calculate token ID for a specific outcome.
        
        Token ID = keccak256(abi.encodePacked(collateralToken, collectionId))
        where collectionId = keccak256(abi.encodePacked(parentCollectionId, conditionId, indexSet))
        
        For simplicity, we assume token IDs are provided by the market data.
        This is a placeholder for the actual calculation.
        
        Args:
            condition_id: Condition ID of the market
            outcome_index: Outcome index (0 for YES, 1 for NO)
            
        Returns:
            int: Token ID
        """
        # In production, this would calculate the actual token ID
        # For now, we'll rely on token IDs being provided by market data
        raise NotImplementedError(
            "Token ID calculation not implemented. "
            "Use merge_positions_with_token_ids instead."
        )
    
    async def get_position_balance(
        self,
        token_id: str,
        owner: Optional[str] = None
    ) -> Decimal:
        """
        Get position balance for a specific token.
        
        Args:
            token_id: Token ID to check balance for
            owner: Owner address (defaults to wallet address)
            
        Returns:
            Decimal: Position balance (in whole tokens, not wei)
        """
        if owner is None:
            owner = self.wallet.address
        
        # Convert token_id to int if it's a hex string
        if isinstance(token_id, str) and token_id.startswith('0x'):
            token_id_int = int(token_id, 16)
        else:
            token_id_int = int(token_id)
        
        # Get balance from CTF contract
        balance_wei = await asyncio.to_thread(
            self.ctf_contract.functions.balanceOf(owner, token_id_int).call
        )
        
        # Convert from wei (6 decimals for USDC-based tokens)
        balance = Decimal(balance_wei) / Decimal(10 ** 6)
        
        return balance
    
    async def get_usdc_balance(self, owner: Optional[str] = None) -> Decimal:
        """
        Get USDC balance for an address.
        
        Args:
            owner: Owner address (defaults to wallet address)
            
        Returns:
            Decimal: USDC balance (in whole tokens, not wei)
        """
        if owner is None:
            owner = self.wallet.address
        
        # Get balance from USDC contract
        balance_wei = await asyncio.to_thread(
            self.usdc_contract.functions.balanceOf(owner).call
        )
        
        # Convert from wei (6 decimals for USDC)
        balance = Decimal(balance_wei) / Decimal(10 ** 6)
        
        return balance
    
    def estimate_gas(
        self,
        condition_id: str,
        yes_token_id: str,
        no_token_id: str,
        amount: Decimal
    ) -> int:
        """
        Estimate gas cost for merge operation.
        
        Validates Requirement 1.5: Implement gas estimation
        
        Args:
            condition_id: Condition ID of the market
            yes_token_id: Token ID for YES outcome
            no_token_id: Token ID for NO outcome
            amount: Amount to merge (in whole tokens)
            
        Returns:
            int: Estimated gas units
        """
        try:
            # Convert amount to wei (6 decimals)
            amount_wei = int(amount * Decimal(10 ** 6))
            
            # Build merge transaction
            merge_func = self.ctf_contract.functions.mergePositions(
                self.usdc_address,
                self.ZERO_BYTES32,
                condition_id,
                [1, 2],  # Partition: [YES, NO]
                amount_wei
            )
            
            # Estimate gas
            gas_estimate = merge_func.estimate_gas({'from': self.wallet.address})
            
            # Add 20% buffer for safety
            gas_with_buffer = int(gas_estimate * 1.2)
            
            logger.debug(
                f"Gas estimate for merge: {gas_estimate} "
                f"(with buffer: {gas_with_buffer})"
            )
            
            return gas_with_buffer
            
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}, using default")
            return self.gas_limit_default
    
    async def merge_positions(
        self,
        condition_id: str,
        yes_token_id: str,
        no_token_id: str,
        amount: Decimal
    ) -> TxReceipt:
        """
        Merge YES and NO positions to redeem USDC.
        
        Validates Requirements:
        - 1.5: Merge positions with balance verification
        - 1.6: Verify $1.00 USDC redemption after merge
        
        Args:
            condition_id: Condition ID of the market
            yes_token_id: Token ID for YES outcome
            no_token_id: Token ID for NO outcome
            amount: Amount to merge (in whole tokens)
            
        Returns:
            TxReceipt: Transaction receipt
            
        Raises:
            InsufficientBalanceError: If insufficient YES or NO balance
            MergeRedemptionError: If redemption doesn't yield expected USDC
            PositionMergerError: If merge transaction fails
        """
        logger.info(
            f"Merging positions: condition={condition_id}, amount={amount}"
        )
        
        # 1. Verify balances (Requirement 1.5)
        yes_balance = await self.get_position_balance(yes_token_id)
        no_balance = await self.get_position_balance(no_token_id)
        
        if yes_balance < amount:
            raise InsufficientBalanceError(
                f"Insufficient YES balance: have {yes_balance}, need {amount}"
            )
        
        if no_balance < amount:
            raise InsufficientBalanceError(
                f"Insufficient NO balance: have {no_balance}, need {amount}"
            )
        
        logger.debug(
            f"Balance check passed: YES={yes_balance}, NO={no_balance}"
        )
        
        # 2. Get USDC balance before merge (Requirement 1.6)
        usdc_before = await self.get_usdc_balance()
        logger.debug(f"USDC balance before merge: {usdc_before}")
        
        # 3. Estimate gas
        gas_limit = self.estimate_gas(
            condition_id, yes_token_id, no_token_id, amount
        )
        
        # 4. Build merge transaction
        amount_wei = int(amount * Decimal(10 ** 6))
        
        merge_func = self.ctf_contract.functions.mergePositions(
            self.usdc_address,
            self.ZERO_BYTES32,
            condition_id,
            [1, 2],  # Partition: [YES, NO]
            amount_wei
        )
        
        # Get current gas price
        gas_price = self.web3.eth.gas_price
        
        # Get current nonce
        nonce = await asyncio.to_thread(
            self.web3.eth.get_transaction_count,
            self.wallet.address,
            'pending'
        )
        
        # Build transaction
        try:
            tx_params = merge_func.build_transaction({
                'from': self.wallet.address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce
            })
        except Exception as e:
            logger.error(f"Failed to build merge transaction: {e}")
            raise PositionMergerError(f"Failed to build merge transaction: {e}")
        
        # 5. Sign and send transaction
        try:
            signed_tx = await asyncio.to_thread(
                self.wallet.sign_transaction,
                tx_params
            )
            
            tx_hash = await asyncio.to_thread(
                self.web3.eth.send_raw_transaction,
                signed_tx.raw_transaction
            )
            
            tx_hash_hex = tx_hash.hex()
            logger.info(f"Merge transaction sent: {tx_hash_hex}")
            
            # 6. Wait for confirmation
            receipt = await asyncio.to_thread(
                self.web3.eth.wait_for_transaction_receipt,
                tx_hash,
                timeout=120
            )
            
            if receipt['status'] != 1:
                raise PositionMergerError(
                    f"Merge transaction reverted: {tx_hash_hex}"
                )
            
            logger.info(f"Merge transaction confirmed: {tx_hash_hex}")
            
        except Exception as e:
            logger.error(f"Merge transaction failed: {e}")
            raise PositionMergerError(f"Merge transaction failed: {e}")
        
        # 7. Verify USDC redemption (Requirement 1.6)
        usdc_after = await self.get_usdc_balance()
        usdc_redeemed = usdc_after - usdc_before
        
        logger.debug(
            f"USDC balance after merge: {usdc_after} "
            f"(redeemed: {usdc_redeemed})"
        )
        
        # Expected redemption: $1.00 per position pair
        expected_redemption = amount
        
        # Allow small tolerance for rounding (0.01 USDC)
        tolerance = Decimal('0.01')
        
        if abs(usdc_redeemed - expected_redemption) > tolerance:
            raise MergeRedemptionError(
                f"Unexpected redemption amount: "
                f"expected {expected_redemption}, got {usdc_redeemed}"
            )
        
        logger.info(
            f"Merge successful: redeemed {usdc_redeemed} USDC "
            f"(expected {expected_redemption})"
        )
        
        return receipt
    
    async def merge_positions_with_token_ids(
        self,
        condition_id: str,
        yes_token_id: str,
        no_token_id: str,
        amount: Decimal
    ) -> TxReceipt:
        """
        Convenience method that wraps merge_positions.
        
        This is the primary method to use when token IDs are known.
        
        Args:
            condition_id: Condition ID of the market
            yes_token_id: Token ID for YES outcome
            no_token_id: Token ID for NO outcome
            amount: Amount to merge (in whole tokens)
            
        Returns:
            TxReceipt: Transaction receipt
        """
        return await self.merge_positions(
            condition_id, yes_token_id, no_token_id, amount
        )
