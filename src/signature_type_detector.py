"""
Signature Type Detector for Polymarket Wallets.

Automatically detects the correct signature type (EOA, POLY_PROXY, or GNOSIS_SAFE)
for a given private key by attempting to derive API credentials.
"""

import logging
from typing import Optional, Tuple
from py_clob_client.client import ClobClient

logger = logging.getLogger(__name__)


class SignatureTypeDetector:
    """
    Detects the correct signature type for Polymarket authentication.
    
    Signature Types:
    - 0: EOA (Externally Owned Account) - Standard Ethereum wallet
    - 1: POLY_PROXY - Polymarket proxy wallet (most common for web users)
    - 2: GNOSIS_SAFE - Gnosis Safe multisig wallet
    """
    
    SIGNATURE_TYPES = {
        0: "EOA",
        1: "POLY_PROXY",
        2: "GNOSIS_SAFE"
    }
    
    @staticmethod
    def detect(
        private_key: str,
        host: str = "https://clob.polymarket.com",
        chain_id: int = 137
    ) -> Tuple[int, Optional[dict]]:
        """
        Detect the correct signature type for the wallet.
        
        Tries signature types in order of likelihood:
        1. POLY_PROXY (1) - Most common for users who deposited via website
        2. GNOSIS_SAFE (2) - Common for new users
        3. EOA (0) - Standard wallets
        
        Args:
            private_key: Wallet private key
            host: CLOB API host
            chain_id: Chain ID (137 for Polygon)
            
        Returns:
            Tuple of (signature_type, api_credentials)
            
        Raises:
            ValueError: If no valid signature type found
        """
        logger.info("Detecting wallet signature type...")
        
        # Try signature types in order of likelihood
        for sig_type in [1, 2, 0]:  # POLY_PROXY, GNOSIS_SAFE, EOA
            try:
                logger.debug(f"Trying signature type {sig_type} ({SignatureTypeDetector.SIGNATURE_TYPES[sig_type]})...")
                
                # Create client with this signature type
                client = ClobClient(
                    host=host,
                    chain_id=chain_id,
                    key=private_key,
                    signature_type=sig_type
                )
                
                # Try to derive API credentials
                api_creds = client.create_or_derive_api_creds()
                
                if api_creds and "apiKey" in api_creds:
                    logger.info(
                        f"✅ Detected signature type: {sig_type} "
                        f"({SignatureTypeDetector.SIGNATURE_TYPES[sig_type]})"
                    )
                    return sig_type, api_creds
                    
            except Exception as e:
                logger.debug(f"Signature type {sig_type} failed: {e}")
                continue
        
        # If all attempts failed
        raise ValueError(
            "Failed to detect signature type. Please check:\n"
            "1. Private key is correct\n"
            "2. Wallet has been used on Polymarket before\n"
            "3. Network connectivity is working"
        )
    
    @staticmethod
    def create_authenticated_client(
        private_key: str,
        host: str = "https://clob.polymarket.com",
        chain_id: int = 137,
        funder: Optional[str] = None
    ) -> Tuple[ClobClient, int, dict]:
        """
        Create a fully authenticated CLOB client with auto-detected signature type.
        
        Args:
            private_key: Wallet private key
            host: CLOB API host
            chain_id: Chain ID
            funder: Funder address (optional, defaults to wallet address)
            
        Returns:
            Tuple of (client, signature_type, api_credentials)
        """
        # Detect signature type and get credentials
        sig_type, api_creds = SignatureTypeDetector.detect(private_key, host, chain_id)
        
        # Derive funder address if not provided
        if funder is None:
            from web3 import Web3
            account = Web3().eth.account.from_key(private_key)
            funder = account.address
        
        # Create authenticated client
        client = ClobClient(
            host=host,
            chain_id=chain_id,
            key=private_key,
            creds=api_creds,
            signature_type=sig_type,
            funder=funder
        )
        
        logger.info(f"✅ Authenticated client created (signature_type={sig_type})")
        
        return client, sig_type, api_creds
