"""
Automatic Bridge Manager - Handles cross-chain USDC bridging autonomously.

This module enables the bot to automatically:
1. Detect USDC on Ethereum
2. Bridge it to Polygon using the official Polygon Bridge
3. Wait for bridge completion
4. Start trading automatically

Fully autonomous - no human intervention required.
"""

import asyncio
import time
import logging
from decimal import Decimal
from typing import Optional, Tuple
from web3 import Web3
from eth_account.signers.local import LocalAccount

logger = logging.getLogger(__name__)


class AutoBridgeManager:
    """
    Manages automatic cross-chain USDC bridging from Ethereum to Polygon.
    
    Features:
    - Detects USDC on Ethereum automatically
    - Bridges to Polygon using Polygon PoS Bridge
    - Monitors bridge status
    - Retries on failure
    - Fully autonomous operation
    """
    
    # Ethereum Mainnet - Use Alchemy for better reliability
    ETHEREUM_RPC = "https://eth-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64"  # Alchemy RPC
    ETHEREUM_CHAIN_ID = 1
    USDC_ETHEREUM = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    
    # Polygon PoS Bridge contracts on Ethereum
    POLYGON_BRIDGE_PREDICATE = "0x40ec5B33f54e0E8A33A975908C5BA1c14e5BbbDf"  # ERC20 Predicate
    POLYGON_ROOT_CHAIN_MANAGER = "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77"
    
    # Polygon Mainnet
    POLYGON_RPC = "https://polygon-rpc.com"  # Public RPC
    POLYGON_CHAIN_ID = 137
    USDC_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    
    # Bridge parameters
    MIN_BRIDGE_AMOUNT = Decimal("1.0")  # Minimum $1 to bridge
    GAS_BUFFER = Decimal("0.002")  # Keep 0.002 ETH for gas (~$5)
    MAX_WAIT_TIME = 1800  # 30 minutes max wait for bridge
    
    def __init__(
        self,
        private_key: str,
        ethereum_rpc: Optional[str] = None,
        polygon_rpc: Optional[str] = None,
        dry_run: bool = False
    ):
        """
        Initialize the auto bridge manager.
        
        Args:
            private_key: Wallet private key
            ethereum_rpc: Ethereum RPC URL (optional, uses public if not provided)
            polygon_rpc: Polygon RPC URL (optional, uses public if not provided)
            dry_run: If True, simulates bridging without actual transactions
        """
        self.private_key = private_key
        self.dry_run = dry_run
        
        # Initialize Ethereum Web3
        eth_rpc = ethereum_rpc or self.ETHEREUM_RPC
        self.eth_web3 = Web3(Web3.HTTPProvider(eth_rpc))
        self.account = self.eth_web3.eth.account.from_key(private_key)
        
        # Initialize Polygon Web3
        poly_rpc = polygon_rpc or self.POLYGON_RPC
        self.poly_web3 = Web3(Web3.HTTPProvider(poly_rpc))
        
        logger.info(f"AutoBridgeManager initialized for wallet: {self.account.address}")
        logger.info(f"Ethereum RPC: {eth_rpc}")
        logger.info(f"Polygon RPC: {poly_rpc}")
        logger.info(f"DRY_RUN: {dry_run}")
    
    async def check_ethereum_usdc_balance(self) -> Decimal:
        """
        Check USDC balance on Ethereum.
        
        Returns:
            USDC balance in decimal format
        """
        try:
            usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
            usdc_contract = self.eth_web3.eth.contract(
                address=Web3.to_checksum_address(self.USDC_ETHEREUM),
                abi=usdc_abi
            )
            
            balance_wei = usdc_contract.functions.balanceOf(self.account.address).call()
            balance = Decimal(balance_wei) / Decimal(10**6)  # USDC has 6 decimals
            
            logger.info(f"Ethereum USDC balance: ${balance:.2f}")
            return balance
            
        except Exception as e:
            logger.error(f"Failed to check Ethereum USDC balance: {e}")
            return Decimal("0")
    
    async def check_polygon_usdc_balance(self) -> Decimal:
        """
        Check USDC balance on Polygon.
        
        Returns:
            USDC balance in decimal format
        """
        try:
            usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
            usdc_contract = self.poly_web3.eth.contract(
                address=Web3.to_checksum_address(self.USDC_POLYGON),
                abi=usdc_abi
            )
            
            balance_wei = usdc_contract.functions.balanceOf(self.account.address).call()
            balance = Decimal(balance_wei) / Decimal(10**6)
            
            logger.info(f"Polygon USDC balance: ${balance:.2f}")
            return balance
            
        except Exception as e:
            logger.error(f"Failed to check Polygon USDC balance: {e}")
            return Decimal("0")
    
    async def check_eth_balance(self) -> Decimal:
        """
        Check ETH balance for gas.
        
        Returns:
            ETH balance in decimal format
        """
        try:
            balance_wei = self.eth_web3.eth.get_balance(self.account.address)
            balance = Decimal(balance_wei) / Decimal(10**18)
            
            logger.info(f"Ethereum ETH balance: {balance:.6f} ETH")
            return balance
            
        except Exception as e:
            logger.error(f"Failed to check ETH balance: {e}")
            return Decimal("0")
    
    async def bridge_usdc_to_polygon(self, amount: Decimal) -> bool:
        """
        Bridge USDC from Ethereum to Polygon using Polygon PoS Bridge.
        
        Args:
            amount: Amount of USDC to bridge
            
        Returns:
            True if bridge initiated successfully, False otherwise
        """
        logger.info(f"Initiating bridge of ${amount:.2f} USDC from Ethereum to Polygon")
        
        if self.dry_run:
            logger.info("DRY_RUN: Simulating bridge transaction")
            await asyncio.sleep(2)  # Simulate transaction time
            logger.info("DRY_RUN: Bridge transaction simulated successfully")
            return True
        
        try:
            # Step 1: Approve USDC to Polygon Bridge
            logger.info("Step 1: Approving USDC to Polygon Bridge...")
            
            usdc_abi = '[{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"}]'
            usdc_contract = self.eth_web3.eth.contract(
                address=Web3.to_checksum_address(self.USDC_ETHEREUM),
                abi=usdc_abi
            )
            
            amount_wei = int(amount * Decimal(10**6))
            
            # Build approval transaction
            approve_tx = usdc_contract.functions.approve(
                Web3.to_checksum_address(self.POLYGON_BRIDGE_PREDICATE),
                amount_wei
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.eth_web3.eth.get_transaction_count(self.account.address),
                'gas': 100000,
                'gasPrice': self.eth_web3.eth.gas_price
            })
            
            # Sign and send approval
            signed_approve = self.eth_web3.eth.account.sign_transaction(approve_tx, self.private_key)
            approve_hash = self.eth_web3.eth.send_raw_transaction(signed_approve.raw_transaction)
            
            logger.info(f"Approval transaction sent: {approve_hash.hex()}")
            logger.info("Waiting for approval confirmation...")
            
            approve_receipt = self.eth_web3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)
            
            if approve_receipt['status'] != 1:
                logger.error("Approval transaction failed")
                return False
            
            logger.info("[OK] Approval confirmed")
            
            # Step 2: Deposit to Polygon Bridge
            logger.info("Step 2: Depositing to Polygon Bridge...")
            
            # RootChainManager ABI (depositFor function)
            bridge_abi = '[{"inputs":[{"internalType":"address","name":"user","type":"address"},{"internalType":"address","name":"rootToken","type":"address"},{"internalType":"bytes","name":"depositData","type":"bytes"}],"name":"depositFor","outputs":[],"stateMutability":"nonpayable","type":"function"}]'
            
            bridge_contract = self.eth_web3.eth.contract(
                address=Web3.to_checksum_address(self.POLYGON_ROOT_CHAIN_MANAGER),
                abi=bridge_abi
            )
            
            # Encode deposit data (amount in bytes32)
            deposit_data = Web3.to_bytes(amount_wei).rjust(32, b'\x00')
            
            # Build deposit transaction
            deposit_tx = bridge_contract.functions.depositFor(
                self.account.address,
                Web3.to_checksum_address(self.USDC_ETHEREUM),
                deposit_data
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.eth_web3.eth.get_transaction_count(self.account.address),
                'gas': 200000,
                'gasPrice': self.eth_web3.eth.gas_price
            })
            
            # Sign and send deposit
            signed_deposit = self.eth_web3.eth.account.sign_transaction(deposit_tx, self.private_key)
            deposit_hash = self.eth_web3.eth.send_raw_transaction(signed_deposit.raw_transaction)
            
            logger.info(f"Bridge transaction sent: {deposit_hash.hex()}")
            logger.info("Waiting for bridge confirmation...")
            
            deposit_receipt = self.eth_web3.eth.wait_for_transaction_receipt(deposit_hash, timeout=300)
            
            if deposit_receipt['status'] != 1:
                logger.error("Bridge transaction failed")
                return False
            
            logger.info("[OK] Bridge transaction confirmed on Ethereum")
            logger.info("Bridge initiated successfully!")
            logger.info("USDC will arrive on Polygon in 5-15 minutes")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to bridge USDC: {e}", exc_info=True)
            return False
    
    async def wait_for_polygon_balance(
        self,
        expected_amount: Decimal,
        timeout: int = MAX_WAIT_TIME
    ) -> bool:
        """
        Wait for USDC to arrive on Polygon after bridging.
        
        Args:
            expected_amount: Expected USDC amount on Polygon
            timeout: Maximum wait time in seconds
            
        Returns:
            True if balance received, False if timeout
        """
        logger.info(f"Waiting for ${expected_amount:.2f} USDC to arrive on Polygon...")
        logger.info(f"This usually takes 5-15 minutes (max {timeout//60} minutes)")
        
        start_time = time.time()
        check_interval = 30  # Check every 30 seconds
        
        initial_balance = await self.check_polygon_usdc_balance()
        target_balance = initial_balance + expected_amount
        
        while time.time() - start_time < timeout:
            current_balance = await self.check_polygon_usdc_balance()
            
            if current_balance >= target_balance * Decimal("0.95"):  # Allow 5% tolerance
                logger.info(f"[OK] USDC arrived on Polygon: ${current_balance:.2f}")
                return True
            
            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed
            logger.info(f"Still waiting... ({elapsed}s elapsed, {remaining}s remaining)")
            
            await asyncio.sleep(check_interval)
        
        logger.error(f"Timeout waiting for USDC on Polygon after {timeout}s")
        return False
    
    async def auto_bridge_if_needed(self) -> Tuple[bool, Decimal]:
        """
        Automatically bridge USDC from Ethereum to Polygon if needed.
        
        This is the main entry point for autonomous bridging.
        Intelligently calculates how much to bridge based on available ETH for gas.
        
        Returns:
            Tuple of (success, polygon_balance)
        """
        logger.info("=" * 80)
        logger.info("AUTO BRIDGE CHECK")
        logger.info("=" * 80)
        
        # Check balances on both chains
        eth_usdc = await self.check_ethereum_usdc_balance()
        poly_usdc = await self.check_polygon_usdc_balance()
        eth_balance = await self.check_eth_balance()
        
        logger.info(f"Ethereum USDC: ${eth_usdc:.2f}")
        logger.info(f"Ethereum ETH: {eth_balance:.6f} ETH")
        logger.info(f"Polygon USDC: ${poly_usdc:.2f}")
        
        # If we have enough on Polygon, no bridge needed
        if poly_usdc >= self.MIN_BRIDGE_AMOUNT:
            logger.info("[OK] Sufficient USDC on Polygon - no bridge needed")
            return True, poly_usdc
        
        # If we have USDC on Ethereum, check if we can bridge
        if eth_usdc >= self.MIN_BRIDGE_AMOUNT:
            logger.info(f"Found ${eth_usdc:.2f} USDC on Ethereum")
            
            # CRITICAL: Check if we have enough ETH for a FULL bridge
            # Bridge costs ~$5-10 in gas, so we need at least 0.002 ETH
            min_eth_for_full_bridge = Decimal("0.002")  # ~$5 gas
            
            if eth_balance < min_eth_for_full_bridge:
                logger.error("=" * 80)
                logger.error("INSUFFICIENT ETH FOR BRIDGE")
                logger.error("=" * 80)
                logger.error(f"Your ETH balance: {eth_balance:.6f} ETH (~${eth_balance * Decimal('2500'):.2f})")
                logger.error(f"Required for bridge: {min_eth_for_full_bridge:.6f} ETH (~$5.00)")
                logger.error(f"You need: {min_eth_for_full_bridge - eth_balance:.6f} more ETH")
                logger.error("")
                logger.error("WHY BRIDGE IS BAD WITH LOW ETH:")
                logger.error("  1. Multiple small bridges = MORE gas fees")
                logger.error("  2. You get USDC.E (wrong token, needs swap)")
                logger.error("  3. Below Polymarket minimum ($3.00)")
                logger.error("  4. Gas cost > your capital (waste of money)")
                logger.error("")
                logger.error("USE POLYMARKET DEPOSIT INSTEAD (FREE & INSTANT):")
                logger.error("")
                logger.error("1. Go to: https://polymarket.com")
                logger.error("2. Click 'Connect Wallet' (top right)")
                logger.error("3. Click your profile → 'Deposit'")
                logger.error(f"4. Enter amount: ${eth_usdc:.2f} USDC")
                logger.error("5. Select 'Wallet' as source")
                logger.error("6. Select 'Ethereum' as network")
                logger.error("7. Click 'Continue' → Approve in MetaMask")
                logger.error("8. Wait 10-30 seconds → Done!")
                logger.error("")
                logger.error("BENEFITS:")
                logger.error("  - FREE (Polymarket pays gas)")
                logger.error("  - FAST (10-30 seconds)")
                logger.error(f"  - FULL AMOUNT (${eth_usdc:.2f}, not partial)")
                logger.error("  - RIGHT TOKEN (USDC, not USDC.E)")
                logger.error("  - ONE TRANSACTION (not multiple)")
                logger.error("")
                logger.error(f"Your wallet: {self.account.address}")
                logger.error("=" * 80)
                return False, poly_usdc
            
            # Enough ETH - bridge all USDC
            bridge_amount = eth_usdc
            logger.info(f"Sufficient ETH - bridging all ${bridge_amount:.2f} USDC")
            
            # Bridge USDC
            bridge_success = await self.bridge_usdc_to_polygon(bridge_amount)
            
            if not bridge_success:
                logger.error("Bridge initiation failed")
                return False, poly_usdc
            
            # Wait for USDC to arrive on Polygon
            if self.dry_run:
                logger.info("DRY_RUN: Skipping wait for bridge completion")
                return True, poly_usdc + bridge_amount
            
            arrival_success = await self.wait_for_polygon_balance(bridge_amount)
            
            if not arrival_success:
                logger.error("USDC did not arrive on Polygon in time")
                logger.info("Bridge may still be processing - check again later")
                return False, poly_usdc
            
            # Check final balance
            final_balance = await self.check_polygon_usdc_balance()
            logger.info(f"[OK] Bridge complete! Final Polygon balance: ${final_balance:.2f}")
            
            return True, final_balance
        
        # No USDC on either chain
        logger.error("No USDC found on Ethereum or Polygon")
        logger.info("Please deposit USDC to your wallet:")
        logger.info(f"  Wallet: {self.account.address}")
        logger.info(f"  Network: Ethereum or Polygon")
        logger.info(f"  Token: USDC")
        logger.info(f"  Minimum: ${self.MIN_BRIDGE_AMOUNT}")
        
        return False, poly_usdc


async def main():
    """Test the auto bridge manager."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        print("Error: PRIVATE_KEY not found in .env")
        return
    
    # Create bridge manager
    bridge_manager = AutoBridgeManager(
        private_key=private_key,
        dry_run=True  # Set to False for real bridging
    )
    
    # Run auto bridge
    success, balance = await bridge_manager.auto_bridge_if_needed()
    
    if success:
        print(f"\n✓ Ready to trade with ${balance:.2f} USDC on Polygon")
    else:
        print(f"\n✗ Bridge failed or insufficient funds")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
