"""
Wallet address verification for security.

Implements Requirement 14.4:
- Verify private key matches expected address on startup
"""

import logging
from web3 import Web3
from eth_account import Account

logger = logging.getLogger(__name__)


class WalletVerifier:
    """
    Verifies that private keys match expected wallet addresses.
    
    Responsibilities:
    - Derive wallet address from private key
    - Compare with expected address
    - Prevent startup if mismatch detected
    
    Validates Requirement 14.4: Wallet address verification
    """
    
    @staticmethod
    def verify_wallet_address(private_key: str, expected_address: str) -> bool:
        """
        Verify that a private key corresponds to the expected wallet address.
        
        Args:
            private_key: Private key (with or without 0x prefix)
            expected_address: Expected Ethereum address
            
        Returns:
            True if private key matches expected address, False otherwise
            
        Raises:
            ValueError: If private key or address format is invalid
        """
        try:
            # Normalize private key (ensure 0x prefix)
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            
            # Derive address from private key
            account = Account.from_key(private_key)
            derived_address = account.address
            
            # Normalize addresses to checksum format for comparison
            expected_checksum = Web3.to_checksum_address(expected_address)
            derived_checksum = Web3.to_checksum_address(derived_address)
            
            # Compare addresses
            matches = expected_checksum == derived_checksum
            
            if matches:
                logger.info(f"[OK] Wallet address verified: {derived_checksum}")
            else:
                logger.error(
                    f"[FAIL] Wallet address mismatch!\n"
                    f"  Expected: {expected_checksum}\n"
                    f"  Derived:  {derived_checksum}"
                )
            
            return matches
            
        except ValueError as e:
            logger.error(f"Invalid private key or address format: {e}")
            raise ValueError(f"Wallet verification failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during wallet verification: {e}")
            raise ValueError(f"Wallet verification failed: {e}")
    
    @staticmethod
    def derive_address_from_private_key(private_key: str) -> str:
        """
        Derive Ethereum address from private key.
        
        Args:
            private_key: Private key (with or without 0x prefix)
            
        Returns:
            Checksum Ethereum address
            
        Raises:
            ValueError: If private key format is invalid
        """
        try:
            # Normalize private key
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            
            # Derive address
            account = Account.from_key(private_key)
            address = Web3.to_checksum_address(account.address)
            
            logger.debug(f"Derived address: {address}")
            return address
            
        except Exception as e:
            logger.error(f"Failed to derive address from private key: {e}")
            raise ValueError(f"Invalid private key: {e}")
    
    @staticmethod
    def verify_or_derive_address(private_key: str, expected_address: str = None) -> str:
        """
        Verify wallet address if provided, or derive it from private key.
        
        This is useful when the expected address might not be configured.
        
        Args:
            private_key: Private key
            expected_address: Optional expected address to verify against
            
        Returns:
            Verified or derived wallet address
            
        Raises:
            ValueError: If verification fails or private key is invalid
        """
        # Derive address from private key
        derived_address = WalletVerifier.derive_address_from_private_key(private_key)
        
        # If expected address provided, verify it matches
        if expected_address:
            if not WalletVerifier.verify_wallet_address(private_key, expected_address):
                raise ValueError(
                    f"Private key does not match expected wallet address. "
                    f"Expected: {expected_address}, Derived: {derived_address}"
                )
        else:
            logger.info(f"No expected address provided. Using derived address: {derived_address}")
        
        return derived_address


def verify_wallet(private_key: str, expected_address: str) -> bool:
    """
    Convenience function to verify wallet address.
    
    Args:
        private_key: Private key
        expected_address: Expected wallet address
        
    Returns:
        True if verification succeeds, False otherwise
    """
    return WalletVerifier.verify_wallet_address(private_key, expected_address)
