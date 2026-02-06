"""
Token Allowance Manager for Polymarket Trading.

Manages USDC and Conditional Token approvals for EOA wallets.
Required before trading with MetaMask or hardware wallets.
"""

import logging
from decimal import Decimal
from typing import Dict, List
from web3 import Web3
from web3.contract import Contract

logger = logging.getLogger(__name__)

# Polygon Mainnet Addresses
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKEN_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# Polymarket Exchange Contracts
EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

# ERC20 ABI (minimal for approve/allowance)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

# ERC1155 ABI (minimal for setApprovalForAll/isApprovedForAll)
ERC1155_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "operator", "type": "address"}
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function"
    }
]


class TokenAllowanceManager:
    """
    Manages token allowances for Polymarket trading.
    
    Required for EOA wallets (MetaMask, hardware wallets) before trading.
    Email/Magic wallets have allowances set automatically.
    """
    
    def __init__(self, web3: Web3, account):
        """
        Initialize allowance manager.
        
        Args:
            web3: Web3 instance connected to Polygon
            account: Account object with address and private key
        """
        self.web3 = web3
        self.account = account
        
        # Initialize contracts
        self.usdc = web3.eth.contract(
            address=Web3.to_checksum_address(USDC_ADDRESS),
            abi=ERC20_ABI
        )
        
        self.conditional_token = web3.eth.contract(
            address=Web3.to_checksum_address(CONDITIONAL_TOKEN_ADDRESS),
            abi=ERC1155_ABI
        )
        
        self.spenders = [
            Web3.to_checksum_address(EXCHANGE_ADDRESS),
            Web3.to_checksum_address(NEG_RISK_EXCHANGE),
            Web3.to_checksum_address(NEG_RISK_ADAPTER)
        ]
    
    def check_all_allowances(self) -> Dict[str, Dict[str, bool]]:
        """
        Check all required allowances.
        
        Returns:
            Dict with allowance status for each token and spender
        """
        results = {
            "usdc": {},
            "conditional_token": {},
            "all_approved": True
        }
        
        # Check USDC allowances
        for spender in self.spenders:
            try:
                allowance = self.usdc.functions.allowance(
                    self.account.address,
                    spender
                ).call()
                
                # Consider approved if allowance > 1M USDC (6 decimals)
                is_approved = allowance > 1_000_000 * 10**6
                results["usdc"][spender] = is_approved
                
                if not is_approved:
                    results["all_approved"] = False
                    
            except Exception as e:
                logger.error(f"Failed to check USDC allowance for {spender}: {e}")
                results["usdc"][spender] = False
                results["all_approved"] = False
        
        # Check Conditional Token allowances
        for spender in self.spenders:
            try:
                is_approved = self.conditional_token.functions.isApprovedForAll(
                    self.account.address,
                    spender
                ).call()
                
                results["conditional_token"][spender] = is_approved
                
                if not is_approved:
                    results["all_approved"] = False
                    
            except Exception as e:
                logger.error(f"Failed to check CT allowance for {spender}: {e}")
                results["conditional_token"][spender] = False
                results["all_approved"] = False
        
        return results
    
    def approve_usdc(self, spender: str, amount: int = 2**256 - 1, dry_run: bool = False) -> bool:
        """
        Approve USDC spending.
        
        Args:
            spender: Address to approve
            amount: Amount to approve (default: unlimited)
            dry_run: If True, don't actually send transaction
            
        Returns:
            True if successful
        """
        try:
            spender = Web3.to_checksum_address(spender)
            
            if dry_run:
                logger.info(f"[DRY RUN] Would approve USDC for {spender}")
                return True
            
            # Build transaction
            tx = self.usdc.functions.approve(spender, amount).build_transaction({
                'from': self.account.address,
                'nonce': self.web3.eth.get_transaction_count(self.account.address),
                'gas': 100000,
                'gasPrice': self.web3.eth.gas_price
            })
            
            # Sign and send
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"USDC approval sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                logger.info(f"✅ USDC approved for {spender}")
                return True
            else:
                logger.error(f"❌ USDC approval failed for {spender}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to approve USDC for {spender}: {e}")
            return False
    
    def approve_conditional_token(self, spender: str, dry_run: bool = False) -> bool:
        """
        Approve Conditional Token spending.
        
        Args:
            spender: Address to approve
            dry_run: If True, don't actually send transaction
            
        Returns:
            True if successful
        """
        try:
            spender = Web3.to_checksum_address(spender)
            
            if dry_run:
                logger.info(f"[DRY RUN] Would approve Conditional Token for {spender}")
                return True
            
            # Build transaction
            tx = self.conditional_token.functions.setApprovalForAll(
                spender,
                True
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.web3.eth.get_transaction_count(self.account.address),
                'gas': 100000,
                'gasPrice': self.web3.eth.gas_price
            })
            
            # Sign and send
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Conditional Token approval sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                logger.info(f"✅ Conditional Token approved for {spender}")
                return True
            else:
                logger.error(f"❌ Conditional Token approval failed for {spender}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to approve Conditional Token for {spender}: {e}")
            return False
    
    def approve_all(self, dry_run: bool = False) -> bool:
        """
        Approve all required tokens for all spenders.
        
        Args:
            dry_run: If True, don't actually send transactions
            
        Returns:
            True if all approvals successful
        """
        logger.info("=" * 80)
        logger.info("SETTING UP TOKEN ALLOWANCES")
        logger.info("=" * 80)
        
        if dry_run:
            logger.info("[DRY RUN MODE] No actual transactions will be sent")
        
        all_success = True
        
        # Approve USDC for all spenders
        logger.info("\n1. Approving USDC...")
        for spender in self.spenders:
            success = self.approve_usdc(spender, dry_run=dry_run)
            if not success:
                all_success = False
        
        # Approve Conditional Token for all spenders
        logger.info("\n2. Approving Conditional Tokens...")
        for spender in self.spenders:
            success = self.approve_conditional_token(spender, dry_run=dry_run)
            if not success:
                all_success = False
        
        logger.info("\n" + "=" * 80)
        if all_success:
            logger.info("✅ ALL ALLOWANCES SET SUCCESSFULLY")
        else:
            logger.error("❌ SOME ALLOWANCES FAILED")
        logger.info("=" * 80)
        
        return all_success
    
    def check_and_approve_if_needed(self, dry_run: bool = False) -> bool:
        """
        Check allowances and approve if needed.
        
        Args:
            dry_run: If True, don't actually send transactions
            
        Returns:
            True if all allowances are set (or were set successfully)
        """
        logger.info("Checking token allowances...")
        
        results = self.check_all_allowances()
        
        if results["all_approved"]:
            logger.info("✅ All allowances already set")
            return True
        
        logger.warning("⚠️ Some allowances missing, setting them now...")
        
        # Approve missing allowances
        all_success = True
        
        # USDC
        for spender, is_approved in results["usdc"].items():
            if not is_approved:
                logger.info(f"Approving USDC for {spender}...")
                success = self.approve_usdc(spender, dry_run=dry_run)
                if not success:
                    all_success = False
        
        # Conditional Token
        for spender, is_approved in results["conditional_token"].items():
            if not is_approved:
                logger.info(f"Approving Conditional Token for {spender}...")
                success = self.approve_conditional_token(spender, dry_run=dry_run)
                if not success:
                    all_success = False
        
        return all_success
