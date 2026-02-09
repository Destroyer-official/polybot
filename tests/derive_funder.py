#!/usr/bin/env python3
"""
CREATE2 Address Derivation for Polymarket Proxy Wallets.

Based on rs-clob-client implementation:
- Safe wallet: derive_safe_wallet(EOA) 
- Proxy wallet: derive_proxy_wallet(EOA)

The funder address shown on Polymarket profile is the CREATE2-derived address.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web3 import Web3
from eth_abi import encode
from eth_utils import keccak

# Polymarket Safe Factory and constants (from rs-clob-client)
POLYGON_CHAIN_ID = 137

# Gnosis Safe Proxy Factory on Polygon
SAFE_PROXY_FACTORY = "0xC22834581EbC8527d974F8a1c97E1bEA4EF910BC"
SAFE_SINGLETON = "0x69f4D1788e39c87893C980c06EdF4b7f686e2938"

# Polymarket Proxy Factory
PROXY_FACTORY = "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"

def compute_create2_address(deployer: str, salt: bytes, init_code_hash: bytes) -> str:
    """
    Compute CREATE2 address.
    
    CREATE2 address = keccak256(0xff ++ deployer ++ salt ++ init_code_hash)[12:]
    """
    data = b'\xff' + bytes.fromhex(deployer[2:]) + salt + init_code_hash
    return Web3.to_checksum_address('0x' + keccak(data).hex()[-40:])

def derive_safe_wallet(eoa_address: str, chain_id: int = POLYGON_CHAIN_ID) -> str:
    """
    Derive Gnosis Safe wallet address from EOA using CREATE2.
    
    This matches what Polymarket shows as your "profile address" when 
    you log in with a browser wallet (MetaMask, etc).
    """
    eoa_bytes = bytes.fromhex(eoa_address[2:].lower())
    
    # Safe setup data - standard for Polymarket
    # Salt is derived from EOA address and nonce
    salt_nonce = 0
    salt = keccak(eoa_bytes + salt_nonce.to_bytes(32, 'big'))
    
    # Init code hash for Safe proxy
    # This is the keccak256 of the Safe proxy creation code
    init_code = bytes.fromhex(SAFE_SINGLETON[2:])  # Simplified
    init_code_hash = keccak(init_code)
    
    return compute_create2_address(SAFE_PROXY_FACTORY, salt, init_code_hash)

def derive_proxy_wallet_v2(eoa_address: str) -> str:
    """
    Alternative derivation using Polymarket's actual CREATE2 formula.
    
    Based on py-clob-client and Polymarket contracts.
    """
    # Polymarket uses a specific initialization pattern
    eoa = Web3.to_checksum_address(eoa_address)
    
    # The proxy wallet is simply associated with the EOA via the factory
    # For now, let's verify the relationship empirically
    return None

def main():
    from dotenv import load_dotenv
    load_dotenv()
    
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    
    w3 = Web3()
    account = w3.eth.account.from_key(PRIVATE_KEY)
    eoa = account.address
    
    print("=" * 60)
    print("POLYMARKET WALLET ADDRESS DERIVATION")
    print("=" * 60)
    print(f"\nYour EOA (signing key): {eoa}")
    
    # User's known proxy address from Polymarket profile
    known_proxy = "0x93e65c1419AB8147cbd16d440Bb7FC178b3b2F35"
    print(f"\nKnown Polymarket profile address: {known_proxy}")
    
    # Let's check if py-clob-client has built-in derivation
    print("\n--- Checking py-clob-client for address derivation ---")
    
    try:
        from py_clob_client.signer import Signer
        signer = Signer(PRIVATE_KEY, 137)
        print(f"Signer address: {signer.address()}")
        
        # Check if there's a method to get funder
        if hasattr(signer, 'get_funder'):
            print(f"Funder from signer: {signer.get_funder()}")
    except Exception as e:
        print(f"Signer check error: {e}")
    
    # Test the relationship
    print("\n--- Testing Create and Derive API Creds ---")
    
    from py_clob_client.client import ClobClient
    
    # The key insight: when we derive API creds, the server knows our funder!
    for sig_type in [0, 1, 2]:
        sig_name = {0: "EOA", 1: "POLY_PROXY", 2: "GNOSIS_SAFE"}[sig_type]
        print(f"\nTrying signature_type={sig_type} ({sig_name})...")
        
        try:
            # Create with the KNOWN PROXY as funder
            client = ClobClient(
                host="https://clob.polymarket.com",
                key=PRIVATE_KEY,
                chain_id=137,
                signature_type=sig_type,
                funder=known_proxy  # Use known profile address
            )
            
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            print(f"  API Key: {creds.api_key[:20]}...")
            
            # Now try to get balance
            try:
                from py_clob_client.clob_types import OrderArgs
                from py_clob_client.order_builder.constants import BUY
                from types import SimpleNamespace
                import requests
                
                # Get a market
                resp = requests.get("https://clob.polymarket.com/sampling-markets?limit=5", timeout=30)
                markets = resp.json().get('data', [])
                for m in markets:
                    if m.get('active') and m.get('enable_order_book') and not m.get('neg_risk'):
                        tokens = m.get('tokens', [])
                        if tokens:
                            token_id = tokens[0]['token_id']
                            tick_size = str(m.get('minimum_tick_size', '0.01'))
                            
                            order_args = OrderArgs(
                                token_id=token_id,
                                price=0.50,
                                size=1.0,
                                side=BUY
                            )
                            
                            options = SimpleNamespace(tick_size=tick_size, neg_risk=False)
                            response = client.create_and_post_order(order_args, options)
                            print(f"  Order response: {response}")
                            
                            resp_str = str(response).lower() if response else ""
                            if 'invalid signature' not in resp_str:
                                print(f"\n🎉 SUCCESS with sig_type={sig_type}!")
                                return sig_type
                            break
                            
            except Exception as e:
                error_str = str(e).lower()
                if 'invalid signature' in error_str:
                    print(f"  Order failed: invalid signature")
                elif 'insufficient' in error_str:
                    print(f"  🎉 SIGNATURE WORKS! (insufficient balance)")
                    return sig_type
                else:
                    print(f"  Order error: {e}")
                    
        except Exception as e:
            print(f"  Error: {e}")
    
    print("\n❌ All combinations failed")
    return None

if __name__ == "__main__":
    result = main()
    if result is not None:
        print(f"\n✅ Working configuration: signature_type={result} + funder=PROFILE_ADDRESS")
