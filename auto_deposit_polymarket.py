#!/usr/bin/env python3
"""
Automatic deposit to Polymarket using Bridge API.
Based on: https://docs.polymarket.com/api-reference/bridge/create-deposit-addresses
"""

import asyncio
import requests
import json
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv
import os
import time

load_dotenv()

class PolymarketAutoDeposit:
    """Automatic deposit to Polymarket using their Bridge API."""
    
    def __init__(self):
        self.polygon_rpc = os.getenv('POLYGON_RPC_URL')
        self.private_key = os.getenv('PRIVATE_KEY')
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        self.usdc_address = os.getenv('USDC_ADDRESS')
        
        self.web3 = Web3(Web3.HTTPProvider(self.polygon_rpc))
        self.account = self.web3.eth.account.from_key(self.private_key)
        
        # Polymarket Bridge API
        self.bridge_api = "https://bridge.polymarket.com"
        
    def get_polygon_balance(self):
        """Get USDC balance on Polygon."""
        usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
        usdc_contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(self.usdc_address),
            abi=usdc_abi
        )
        
        balance_raw = usdc_contract.functions.balanceOf(
            Web3.to_checksum_address(self.wallet_address)
        ).call()
        
        return Decimal(balance_raw) / Decimal(10**6)
    
    def create_deposit_address(self):
        """
        Create a deposit address using Polymarket Bridge API.
        
        API Endpoint: POST https://bridge.polymarket.com/deposit
        
        Returns:
            dict: Deposit address information
        """
        print("\n[1] Creating Polymarket deposit address...")
        print("-" * 80)
        
        try:
            # Request deposit address
            url = f"{self.bridge_api}/deposit"
            headers = {
                'Content-Type': 'application/json'
            }
            
            # The API might need the wallet address
            payload = {
                'address': self.wallet_address
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            # Accept both 200 and 201 (Created) status codes
            if response.status_code in [200, 201]:
                data = response.json()
                print(f"✓ Deposit address created successfully")
                print(f"Response: {json.dumps(data, indent=2)}")
                return data
            else:
                print(f"✗ Failed to create deposit address: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"✗ Error creating deposit address: {e}")
            return None
    
    def transfer_to_polymarket(self, amount: Decimal, deposit_address: str):
        """
        Transfer USDC from Polygon wallet to Polymarket deposit address.
        
        Args:
            amount: Amount of USDC to transfer
            deposit_address: Polymarket deposit address
        """
        print(f"\n[2] Transferring ${amount:.2f} USDC to Polymarket...")
        print("-" * 80)
        
        try:
            # USDC contract
            usdc_abi = [
                {"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}
            ]
            
            usdc_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.usdc_address),
                abi=usdc_abi
            )
            
            # Convert amount to raw units (6 decimals for USDC)
            amount_raw = int(amount * Decimal(10**6))
            
            # Build transaction
            tx = usdc_contract.functions.transfer(
                Web3.to_checksum_address(deposit_address),
                amount_raw
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.web3.eth.get_transaction_count(self.account.address),
                'gas': 100000,
                'gasPrice': self.web3.eth.gas_price
            })
            
            # Sign and send
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)  # Use raw_transaction (lowercase with underscore)
            
            print(f"✓ Transaction sent: {tx_hash.hex()}")
            print(f"Waiting for confirmation...")
            
            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                print(f"✓ Transfer confirmed!")
                print(f"Gas used: {receipt['gasUsed']}")
                return True
            else:
                print(f"✗ Transfer failed!")
                return False
                
        except Exception as e:
            print(f"✗ Error transferring: {e}")
            return False
    
    async def auto_deposit(self):
        """Automatically deposit all Polygon USDC to Polymarket."""
        
        print("=" * 80)
        print("POLYMARKET AUTO-DEPOSIT")
        print("=" * 80)
        
        # Check balance
        balance = self.get_polygon_balance()
        print(f"\n💰 Polygon USDC Balance: ${balance:.2f}")
        
        if balance < Decimal("0.50"):
            print(f"\n❌ Insufficient balance for deposit (minimum: $0.50)")
            return False
        
        # Create deposit address
        deposit_info = self.create_deposit_address()
        
        if not deposit_info:
            print("\n❌ Failed to create deposit address")
            print("\nFALLBACK: Use Polymarket website to deposit:")
            print("1. Go to: https://polymarket.com")
            print("2. Connect wallet")
            print("3. Click profile → Deposit")
            print(f"4. Deposit ${balance:.2f} USDC from Polygon")
            return False
        
        # Extract deposit address
        # The API returns addresses for different chains
        # We need the EVM (Polygon) address
        addresses = deposit_info.get('address', {})
        deposit_address = addresses.get('evm')  # EVM address for Polygon
        
        if not deposit_address:
            print(f"\n❌ Could not find EVM deposit address in response")
            print(f"Available addresses: {addresses}")
            print("\nFALLBACK: Use Polymarket website to deposit")
            return False
        
        # Transfer to Polymarket
        success = self.transfer_to_polymarket(balance, deposit_address)
        
        if success:
            print("\n" + "=" * 80)
            print("✅ DEPOSIT SUCCESSFUL!")
            print("=" * 80)
            print(f"Deposited: ${balance:.2f} USDC")
            print(f"To: {deposit_address}")
            print("\nStarting bot in 5 seconds...")
            await asyncio.sleep(5)
            return True
        else:
            print("\n❌ Deposit failed")
            return False

async def main():
    """Main entry point."""
    
    depositor = PolymarketAutoDeposit()
    success = await depositor.auto_deposit()
    
    if success:
        # Start the trading bot
        print("\n🤖 STARTING AUTO-TRADING BOT...")
        print("=" * 80)
        
        from config.config import Config
        from src.main_orchestrator import MainOrchestrator
        
        config = Config.from_env()
        orchestrator = MainOrchestrator(config)
        await orchestrator.run()
    else:
        print("\n" + "=" * 80)
        print("MANUAL DEPOSIT REQUIRED")
        print("=" * 80)
        print("\nThe automatic deposit failed. Please deposit manually:")
        print("1. Go to: https://polymarket.com")
        print("2. Connect wallet")
        print("3. Click profile → Deposit")
        print("4. Deposit from Polygon (instant & free)")
        print("\nThen run: python START_REAL_TRADING.py")

if __name__ == "__main__":
    asyncio.run(main())
