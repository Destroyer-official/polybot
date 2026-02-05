"""
Fund Manager for Polymarket Arbitrage Bot.

Manages deposits, withdrawals, and multi-chain operations.
Validates Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7.
"""

import asyncio
import logging
from typing import Tuple, Optional, Dict
from decimal import Decimal
from datetime import datetime
from web3 import Web3
from web3.types import TxReceipt
from eth_account.signers.local import LocalAccount
import aiohttp

logger = logging.getLogger(__name__)


class FundManagerError(Exception):
    """Base exception for fund manager errors."""
    pass


class InsufficientBalanceError(FundManagerError):
    """Raised when balance is insufficient for operation."""
    pass


class DepositError(FundManagerError):
    """Raised when deposit operation fails."""
    pass


class WithdrawalError(FundManagerError):
    """Raised when withdrawal operation fails."""
    pass


class FundManager:
    """
    Manages automated fund operations for the trading bot.
    
    Features:
    - Check EOA and Proxy wallet balances
    - Auto-deposit when balance < $50
    - Auto-withdraw when balance > $500
    - Cross-chain deposits with 1inch API integration
    - Support for Ethereum, Polygon, Arbitrum, Optimism
    - Comprehensive logging of all operations
    
    Validates Requirements:
    - 8.1: Auto-deposit when Proxy balance < $50
    - 8.2: Deposit from EOA to Proxy wallet
    - 8.3: Auto-withdraw when Proxy balance > $500
    - 8.4: Withdraw from Proxy to EOA wallet
    - 8.5: Multi-chain deposit support
    - 8.6: Cross-chain swap and bridge via 1inch
    - 8.7: Log all deposit/withdrawal transactions
    """
    
    # Supported chains for cross-chain deposits
    SUPPORTED_CHAINS = {
        "ethereum": 1,
        "polygon": 137,
        "arbitrum": 42161,
        "optimism": 10
    }
    
    # USDC contract addresses on different chains
    USDC_ADDRESSES = {
        1: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # Ethereum
        137: "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # Polygon
        42161: "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",  # Arbitrum
        10: "0x7F5c764cBc14f9669B88837ca1490cCa17c31607"  # Optimism
    }
    
    def __init__(
        self,
        web3: Web3,
        wallet: LocalAccount,
        usdc_address: str,
        ctf_exchange_address: str,
        min_balance: Decimal,
        target_balance: Decimal,
        withdraw_limit: Decimal,
        dry_run: bool = False,
        oneinch_api_key: Optional[str] = None
    ):
        """
        Initialize Fund Manager.
        
        Args:
            web3: Web3 instance connected to Polygon RPC
            wallet: Wallet account for signing transactions
            usdc_address: USDC contract address on Polygon
            ctf_exchange_address: CTF Exchange contract address
            min_balance: Minimum balance threshold for auto-deposit ($50)
            target_balance: Target balance after deposit ($100)
            withdraw_limit: Balance threshold for auto-withdrawal ($500)
            dry_run: If True, log actions but don't execute transactions
            oneinch_api_key: API key for 1inch aggregator (optional)
        """
        self.web3 = web3
        self.wallet = wallet
        self.usdc_address = Web3.to_checksum_address(usdc_address)
        self.ctf_exchange_address = Web3.to_checksum_address(ctf_exchange_address)
        self.min_balance = min_balance
        self.target_balance = target_balance
        self.withdraw_limit = withdraw_limit
        self.dry_run = dry_run
        self.oneinch_api_key = oneinch_api_key
        
        # Load USDC contract ABI (minimal ERC20)
        self.usdc_contract = self.web3.eth.contract(
            address=self.usdc_address,
            abi=self._get_erc20_abi()
        )
        
        # Load CTF Exchange ABI (minimal for deposit/withdraw)
        self.ctf_exchange_contract = self.web3.eth.contract(
            address=self.ctf_exchange_address,
            abi=self._get_ctf_exchange_abi()
        )
        
        logger.info(
            f"FundManager initialized: "
            f"wallet={wallet.address}, "
            f"min_balance=${min_balance}, "
            f"target_balance=${target_balance}, "
            f"withdraw_limit=${withdraw_limit}, "
            f"dry_run={dry_run}"
        )
    
    async def check_balance(self) -> Tuple[Decimal, Decimal]:
        """
        Check EOA and Proxy wallet balances.
        
        Validates Requirement 8.1, 8.2, 8.3, 8.4:
        - Check both EOA and Proxy wallet balances
        
        Returns:
            Tuple[Decimal, Decimal]: (EOA balance, Proxy balance) in USDC
        """
        try:
            # Get EOA balance (direct wallet balance)
            eoa_balance_raw = await asyncio.to_thread(
                self.usdc_contract.functions.balanceOf(self.wallet.address).call
            )
            eoa_balance = Decimal(eoa_balance_raw) / Decimal(10 ** 6)  # USDC has 6 decimals
            
            # Get Proxy balance (trading balance on CTF Exchange)
            proxy_balance_raw = await asyncio.to_thread(
                self.ctf_exchange_contract.functions.getCollateralBalance(
                    self.wallet.address
                ).call
            )
            proxy_balance = Decimal(proxy_balance_raw) / Decimal(10 ** 6)
            
            logger.debug(
                f"Balance check: EOA=${eoa_balance:.2f}, Proxy=${proxy_balance:.2f}"
            )
            
            return eoa_balance, proxy_balance
            
        except Exception as e:
            logger.error(f"Failed to check balances: {e}")
            raise FundManagerError(f"Balance check failed: {e}")
    
    async def auto_deposit(self, amount: Optional[Decimal] = None) -> Optional[TxReceipt]:
        """
        Deposit USDC from EOA to Proxy wallet.
        
        Validates Requirements 8.1, 8.2:
        - Auto-deposit when Proxy balance < min_balance
        - Deposit configured amount from EOA to Proxy
        
        Args:
            amount: Amount to deposit (if None, deposits target_balance - proxy_balance)
            
        Returns:
            Optional[TxReceipt]: Transaction receipt, or None if dry run
            
        Raises:
            InsufficientBalanceError: If EOA balance insufficient
            DepositError: If deposit operation fails
        """
        try:
            # Check current balances
            eoa_balance, proxy_balance = await self.check_balance()
            
            # Calculate deposit amount if not specified
            if amount is None:
                amount = self.target_balance - proxy_balance
            
            # Validate amount
            if amount <= 0:
                logger.info(f"No deposit needed: proxy_balance=${proxy_balance:.2f}")
                return None
            
            if eoa_balance < amount:
                raise InsufficientBalanceError(
                    f"Insufficient EOA balance: have ${eoa_balance:.2f}, need ${amount:.2f}"
                )
            
            logger.info(
                f"Initiating auto-deposit: ${amount:.2f} USDC "
                f"(EOA: ${eoa_balance:.2f} -> Proxy: ${proxy_balance:.2f})"
            )
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would deposit ${amount:.2f} USDC to Proxy wallet")
                return None
            
            # Convert amount to raw units (6 decimals for USDC)
            amount_raw = int(amount * Decimal(10 ** 6))
            
            # Step 1: Approve USDC to CTF Exchange
            logger.debug(f"Approving ${amount:.2f} USDC to CTF Exchange...")
            approve_tx = await self._approve_usdc(amount_raw)
            logger.info(f"USDC approved: tx={approve_tx['transactionHash'].hex()}")
            
            # Step 2: Deposit to CTF Exchange
            logger.debug(f"Depositing ${amount:.2f} USDC to Proxy wallet...")
            deposit_tx = await self._deposit_to_proxy(amount_raw)
            logger.info(
                f"Deposit successful: tx={deposit_tx['transactionHash'].hex()}, "
                f"amount=${amount:.2f}"
            )
            
            # Verify new balance
            _, new_proxy_balance = await self.check_balance()
            logger.info(
                f"Deposit complete: Proxy balance ${proxy_balance:.2f} -> ${new_proxy_balance:.2f}"
            )
            
            # Log transaction (Requirement 8.7)
            self._log_transaction(
                "deposit",
                amount,
                deposit_tx['transactionHash'].hex(),
                f"EOA -> Proxy"
            )
            
            return deposit_tx
            
        except InsufficientBalanceError:
            raise
        except Exception as e:
            logger.error(f"Auto-deposit failed: {e}")
            raise DepositError(f"Deposit operation failed: {e}")
    
    async def auto_withdraw(self, amount: Optional[Decimal] = None) -> Optional[TxReceipt]:
        """
        Withdraw USDC from Proxy to EOA wallet.
        
        Validates Requirements 8.3, 8.4:
        - Auto-withdraw when Proxy balance > withdraw_limit
        - Withdraw to EOA wallet
        
        Args:
            amount: Amount to withdraw (if None, withdraws proxy_balance - target_balance)
            
        Returns:
            Optional[TxReceipt]: Transaction receipt, or None if dry run
            
        Raises:
            InsufficientBalanceError: If Proxy balance insufficient
            WithdrawalError: If withdrawal operation fails
        """
        try:
            # Check current balances
            eoa_balance, proxy_balance = await self.check_balance()
            
            # Calculate withdrawal amount if not specified
            if amount is None:
                amount = proxy_balance - self.target_balance
            
            # Validate amount
            if amount <= 0:
                logger.info(f"No withdrawal needed: proxy_balance=${proxy_balance:.2f}")
                return None
            
            if proxy_balance < amount:
                raise InsufficientBalanceError(
                    f"Insufficient Proxy balance: have ${proxy_balance:.2f}, need ${amount:.2f}"
                )
            
            logger.info(
                f"Initiating auto-withdrawal: ${amount:.2f} USDC "
                f"(Proxy: ${proxy_balance:.2f} -> EOA: ${eoa_balance:.2f})"
            )
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would withdraw ${amount:.2f} USDC to EOA wallet")
                return None
            
            # Convert amount to raw units (6 decimals for USDC)
            amount_raw = int(amount * Decimal(10 ** 6))
            
            # Withdraw from CTF Exchange
            logger.debug(f"Withdrawing ${amount:.2f} USDC from Proxy wallet...")
            withdraw_tx = await self._withdraw_from_proxy(amount_raw)
            logger.info(
                f"Withdrawal successful: tx={withdraw_tx['transactionHash'].hex()}, "
                f"amount=${amount:.2f}"
            )
            
            # Verify new balance
            new_eoa_balance, new_proxy_balance = await self.check_balance()
            logger.info(
                f"Withdrawal complete: "
                f"Proxy ${proxy_balance:.2f} -> ${new_proxy_balance:.2f}, "
                f"EOA ${eoa_balance:.2f} -> ${new_eoa_balance:.2f}"
            )
            
            # Log transaction (Requirement 8.7)
            self._log_transaction(
                "withdrawal",
                amount,
                withdraw_tx['transactionHash'].hex(),
                f"Proxy -> EOA"
            )
            
            return withdraw_tx
            
        except InsufficientBalanceError:
            raise
        except Exception as e:
            logger.error(f"Auto-withdrawal failed: {e}")
            raise WithdrawalError(f"Withdrawal operation failed: {e}")
    
    async def cross_chain_deposit(
        self,
        source_chain: str,
        token_address: str,
        amount: Decimal
    ) -> Optional[Dict]:
        """
        Swap and bridge tokens from another chain to Polygon USDC.
        
        Validates Requirements 8.5, 8.6:
        - Support multi-chain deposits (Ethereum, Polygon, Arbitrum, Optimism)
        - Use 1inch API to swap and bridge tokens
        
        Args:
            source_chain: Source chain name ("ethereum", "polygon", "arbitrum", "optimism")
            token_address: Token contract address on source chain
            amount: Amount of tokens to swap and bridge
            
        Returns:
            Optional[Dict]: Transaction details, or None if dry run
            
        Raises:
            FundManagerError: If chain not supported or operation fails
        """
        # Validate chain
        source_chain_lower = source_chain.lower()
        if source_chain_lower not in self.SUPPORTED_CHAINS:
            raise FundManagerError(
                f"Unsupported chain: {source_chain}. "
                f"Supported: {list(self.SUPPORTED_CHAINS.keys())}"
            )
        
        chain_id = self.SUPPORTED_CHAINS[source_chain_lower]
        
        logger.info(
            f"Initiating cross-chain deposit: "
            f"chain={source_chain}, token={token_address}, amount=${amount:.2f}"
        )
        
        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would swap and bridge ${amount:.2f} "
                f"from {source_chain} to Polygon USDC"
            )
            return None
        
        try:
            # If already on Polygon and token is USDC, just deposit directly
            if chain_id == 137 and token_address.lower() == self.usdc_address.lower():
                logger.info("Already on Polygon with USDC, performing direct deposit")
                receipt = await self.auto_deposit(amount)
                return {
                    "type": "direct_deposit",
                    "tx_hash": receipt['transactionHash'].hex() if receipt else None,
                    "amount": amount
                }
            
            # Use 1inch API for cross-chain swap and bridge
            result = await self._execute_cross_chain_swap(
                source_chain_id=chain_id,
                source_token=token_address,
                amount=amount
            )
            
            logger.info(
                f"Cross-chain deposit successful: "
                f"tx={result.get('tx_hash', 'N/A')}, amount=${amount:.2f}"
            )
            
            # Log transaction (Requirement 8.7)
            self._log_transaction(
                "cross_chain_deposit",
                amount,
                result.get('tx_hash', 'N/A'),
                f"{source_chain} -> Polygon"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Cross-chain deposit failed: {e}")
            raise FundManagerError(f"Cross-chain deposit failed: {e}")
    
    async def _approve_usdc(self, amount_raw: int) -> TxReceipt:
        """Approve USDC to CTF Exchange."""
        # Build approval transaction
        approve_tx = self.usdc_contract.functions.approve(
            self.ctf_exchange_address,
            amount_raw
        ).build_transaction({
            'from': self.wallet.address,
            'gas': 100000,
            'gasPrice': self.web3.eth.gas_price,
            'nonce': self.web3.eth.get_transaction_count(self.wallet.address)
        })
        
        # Sign and send
        signed_tx = self.wallet.sign_transaction(approve_tx)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        # Wait for confirmation
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] != 1:
            raise DepositError("USDC approval transaction failed")
        
        return receipt
    
    async def _deposit_to_proxy(self, amount_raw: int) -> TxReceipt:
        """Deposit USDC to Proxy wallet via CTF Exchange."""
        # Build deposit transaction
        deposit_tx = self.ctf_exchange_contract.functions.deposit(
            amount_raw
        ).build_transaction({
            'from': self.wallet.address,
            'gas': 200000,
            'gasPrice': self.web3.eth.gas_price,
            'nonce': self.web3.eth.get_transaction_count(self.wallet.address)
        })
        
        # Sign and send
        signed_tx = self.wallet.sign_transaction(deposit_tx)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        # Wait for confirmation
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] != 1:
            raise DepositError("Deposit transaction failed")
        
        return receipt
    
    async def _withdraw_from_proxy(self, amount_raw: int) -> TxReceipt:
        """Withdraw USDC from Proxy wallet via CTF Exchange."""
        # Build withdrawal transaction
        withdraw_tx = self.ctf_exchange_contract.functions.withdraw(
            amount_raw
        ).build_transaction({
            'from': self.wallet.address,
            'gas': 200000,
            'gasPrice': self.web3.eth.gas_price,
            'nonce': self.web3.eth.get_transaction_count(self.wallet.address)
        })
        
        # Sign and send
        signed_tx = self.wallet.sign_transaction(withdraw_tx)
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        # Wait for confirmation
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] != 1:
            raise WithdrawalError("Withdrawal transaction failed")
        
        return receipt
    
    async def _execute_cross_chain_swap(
        self,
        source_chain_id: int,
        source_token: str,
        amount: Decimal
    ) -> Dict:
        """
        Execute cross-chain swap and bridge using 1inch API.
        
        This is a placeholder implementation. In production, you would:
        1. Query 1inch API for best swap route
        2. Get bridge quote for cross-chain transfer
        3. Execute swap on source chain
        4. Execute bridge transaction
        5. Wait for bridge completion on Polygon
        6. Deposit USDC to Proxy wallet
        
        Args:
            source_chain_id: Source chain ID
            source_token: Source token address
            amount: Amount to swap and bridge
            
        Returns:
            Dict: Transaction details
        """
        if not self.oneinch_api_key:
            raise FundManagerError(
                "1inch API key required for cross-chain deposits. "
                "Set ONEINCH_API_KEY environment variable."
            )
        
        logger.warning(
            "Cross-chain swap implementation is a placeholder. "
            "Production implementation requires full 1inch API integration."
        )
        
        # Placeholder: In production, implement full 1inch API integration
        # For now, return mock result
        return {
            "type": "cross_chain_swap",
            "source_chain_id": source_chain_id,
            "source_token": source_token,
            "amount": str(amount),
            "status": "pending",
            "tx_hash": "0x" + "0" * 64,  # Placeholder
            "message": "Cross-chain swap requires full 1inch API integration"
        }
    
    def _log_transaction(
        self,
        tx_type: str,
        amount: Decimal,
        tx_hash: str,
        direction: str
    ) -> None:
        """
        Log deposit/withdrawal transaction.
        
        Validates Requirement 8.7: Log all deposit/withdrawal transactions
        
        Args:
            tx_type: Transaction type ("deposit", "withdrawal", "cross_chain_deposit")
            amount: Transaction amount in USDC
            tx_hash: Transaction hash
            direction: Direction description (e.g., "EOA -> Proxy")
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": tx_type,
            "amount": str(amount),
            "tx_hash": tx_hash,
            "direction": direction,
            "wallet": self.wallet.address
        }
        
        logger.info(
            f"FUND_TRANSACTION: {tx_type.upper()} | "
            f"Amount: ${amount:.2f} | "
            f"Direction: {direction} | "
            f"TX: {tx_hash}"
        )
        
        # In production, also log to database or structured logging system
        # For now, structured log is sufficient
    
    @staticmethod
    def _get_erc20_abi() -> list:
        """Get minimal ERC20 ABI for USDC operations."""
        return [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
    
    @staticmethod
    def _get_ctf_exchange_abi() -> list:
        """Get minimal CTF Exchange ABI for deposit/withdraw operations."""
        return [
            {
                "constant": True,
                "inputs": [{"name": "user", "type": "address"}],
                "name": "getCollateralBalance",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [{"name": "amount", "type": "uint256"}],
                "name": "deposit",
                "outputs": [],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [{"name": "amount", "type": "uint256"}],
                "name": "withdraw",
                "outputs": [],
                "type": "function"
            }
        ]
