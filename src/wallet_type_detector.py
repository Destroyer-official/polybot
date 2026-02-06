"""
Wallet Type Detector for Polymarket.

Detects wallet type and determines correct signature_type and funder address.
"""

import logging
from typing import Tuple, Optional
from web3 import Web3
from py_clob_client.client import ClobClient

logger = logging.getLogger(__name__)


class WalletTypeDetector:
    """
    Detects wallet type and configuration for Polymarket trading.
    
    Signature Types:
    - 0: EOA (MetaMask, hardware wallet) - standard Ethereum wallet
    - 1: POLY_PROXY (Magic Link email/Google) - delegated signing
    - 2: GNOSIS_SAFE (multisig) - most common for new users
    """
    
    def __init__(self, web3: Web3, private_key: str):
        """
        Initialize detector.
        
        Args:
            web3: Web3 instance
            private_key: Wallet private key
        """
        self.web3 = web3
        self.private_key = private_key
        self.account = web3.eth.account.from_key(private_key)
    
    def detect_wallet_type(self) -> Tuple[int, str]:
        """
        Detect wallet type and return signature_type and funder address.
        
        Returns:
            Tuple of (signature_type, funder_address)
        """
        address = self.account.address
        
        # Check if address has code (is a contract)
        code = self.web3.eth.get_code(address)
        
        if code == b'' or code == b'0x':
            # No code = EOA (Externally Owned Account)
            logger.info(f"Detected EOA wallet: {address}")
            logger.info("Signature type: 0 (Standard Ethereum wallet)")
            return 0, address
        else:
            # Has code = Smart contract wallet
            logger.info(f"Detected contract wallet: {address}")
            
            # Try to detect if it's a Gnosis Safe
            # Gnosis Safe has specific function signatures
            try:
                # Check for Gnosis Safe signature
                # getOwners() function signature: 0xa0e67e2b
                owners_sig = Web3.keccak(text="getOwners()")[:4].hex()
                
                # Try to call getOwners
                result = self.web3.eth.call({
                    'to': address,
                    'data': owners_sig
                })
                
                if result:
                    logger.info("Detected Gnosis Safe multisig")
                    logger.info("Signature type: 2 (Gnosis Safe)")
                    return 2, address
                    
            except Exception:
                pass
            
            # Check if it's a Polymarket proxy
            # Polymarket proxies are created via Magic Link
            logger.info("Detected Polymarket proxy wallet")
            logger.info("Signature type: 1 (Polymarket Proxy)")
            return 1, address
    
    def get_proxy_address_from_clob(self, clob_host: str = "https://clob.polymarket.com") -> Optional[str]:
        """
        Get proxy address from CLOB API.
        
        For users who logged in via email/Google, their funds are in a proxy wallet.
        This method queries the CLOB API to find the proxy address.
        
        Args:
            clob_host: CLOB API host
            
        Returns:
            Proxy address if found, None otherwise
        """
        try:
            # Create temporary client with L1 auth only
            client = ClobClient(
                host=clob_host,
                key=self.private_key,
                chain_id=137
            )
            
            # Derive API credentials (this also returns proxy info)
            creds = client.create_or_derive_api_creds()
            
            # Try to get user info
            # The CLOB API returns proxy address in user info
            logger.info("Querying CLOB API for proxy address...")
            
            # Set API creds
            client.set_api_creds(creds)
            
            # Get balance (this will show the proxy address)
            try:
                balance_response = client.get_balance_allowance()
                if isinstance(balance_response, dict):
                    proxy = balance_response.get('address')
                    if proxy:
                        logger.info(f"Found proxy address from CLOB: {proxy}")
                        return proxy
            except Exception as e:
                logger.debug(f"Could not get balance from CLOB: {e}")
            
            # If we got here, assume EOA address is the funder
            return self.account.address
            
        except Exception as e:
            logger.error(f"Failed to query CLOB for proxy address: {e}")
            return None
    
    def auto_detect_configuration(self) -> dict:
        """
        Automatically detect complete wallet configuration.
        
        Returns:
            Dict with signature_type, funder_address, and wallet_type
        """
        signature_type, funder = self.detect_wallet_type()
        
        # If it's a proxy wallet, try to get the actual proxy address
        if signature_type == 1:
            proxy_address = self.get_proxy_address_from_clob()
            if proxy_address:
                funder = proxy_address
        
        wallet_types = {
            0: "EOA (MetaMask/Hardware Wallet)",
            1: "Polymarket Proxy (Email/Google)",
            2: "Gnosis Safe (Multisig)"
        }
        
        config = {
            "signature_type": signature_type,
            "funder_address": funder,
            "wallet_type": wallet_types.get(signature_type, "Unknown"),
            "eoa_address": self.account.address
        }
        
        logger.info("=" * 80)
        logger.info("WALLET CONFIGURATION DETECTED")
        logger.info("=" * 80)
        logger.info(f"EOA Address: {config['eoa_address']}")
        logger.info(f"Wallet Type: {config['wallet_type']}")
        logger.info(f"Signature Type: {config['signature_type']}")
        logger.info(f"Funder Address: {config['funder_address']}")
        logger.info("=" * 80)
        
        return config
    
    @staticmethod
    def requires_token_allowances(signature_type: int) -> bool:
        """
        Check if wallet type requires manual token allowances.
        
        Args:
            signature_type: Wallet signature type
            
        Returns:
            True if token allowances need to be set manually
        """
        # Only EOA wallets (type 0) require manual allowances
        # Proxy and Safe wallets have allowances managed automatically
        return signature_type == 0
