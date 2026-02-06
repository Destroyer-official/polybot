#!/usr/bin/env python3
"""
Swap MATIC to USDC on Polygon using QuickSwap
This allows you to start trading immediately without bridging from Ethereum
"""

import sys
from decimal import Decimal
from web3 import Web3
from config.config import Config

# QuickSwap Router V2 on Polygon
QUICKSWAP_ROUTER = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"

# QuickSwap Router ABI (minimal)
ROUTER_ABI = '''[
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]'''

# WMATIC address on Polygon
WMATIC = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"

def main():
    print("=" * 80)
    print("SWAP MATIC TO USDC ON POLYGON")
    print("=" * 80)
    
    # Load config
    config = Config.from_env()
    
    # Setup Web3
    web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
    account = web3.eth.account.from_key(config.private_key)
    
    print(f"\nWallet: {account.address}")
    
    # Check MATIC balance
    matic_balance_wei = web3.eth.get_balance(account.address)
    matic_balance = Decimal(matic_balance_wei) / Decimal(10**18)
    
    print(f"MATIC Balance: {matic_balance:.6f} MATIC")
    
    if matic_balance < Decimal("0.5"):
        print("\n[ERROR] Insufficient MATIC balance")
        print("You need at least 0.5 MATIC to swap (0.4 for swap + 0.1 for gas)")
        return
    
    # Amount to swap (leave 0.5 MATIC for gas)
    swap_amount_matic = min(Decimal("1.0"), matic_balance - Decimal("0.5"))
    swap_amount_wei = int(swap_amount_matic * Decimal(10**18))
    
    print(f"\nSwapping: {swap_amount_matic:.6f} MATIC")
    print(f"Keeping: {matic_balance - swap_amount_matic:.6f} MATIC for gas")
    
    # Setup router contract
    router = web3.eth.contract(
        address=Web3.to_checksum_address(QUICKSWAP_ROUTER),
        abi=ROUTER_ABI
    )
    
    # Get expected USDC output
    path = [
        Web3.to_checksum_address(WMATIC),
        Web3.to_checksum_address(config.usdc_address)
    ]
    
    try:
        amounts_out = router.functions.getAmountsOut(swap_amount_wei, path).call()
        usdc_out = Decimal(amounts_out[1]) / Decimal(10**6)
        
        print(f"Expected USDC: ${usdc_out:.6f}")
        
        # Apply 1% slippage
        min_usdc_out = int(amounts_out[1] * 0.99)
        
        print(f"Minimum USDC (1% slippage): ${Decimal(min_usdc_out) / Decimal(10**6):.6f}")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to get quote: {e}")
        return
    
    # Confirm with user
    print("\n" + "=" * 80)
    print("CONFIRM SWAP")
    print("=" * 80)
    print(f"Swap {swap_amount_matic:.6f} MATIC → ${usdc_out:.6f} USDC")
    print(f"Gas cost: ~0.01 MATIC (~$0.01)")
    print("\nThis will execute a REAL transaction on Polygon mainnet")
    
    response = input("\nProceed with swap? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("Swap cancelled")
        return
    
    # Execute swap
    print("\nExecuting swap...")
    
    try:
        # Get current gas price
        gas_price = web3.eth.gas_price
        
        # Build transaction
        deadline = web3.eth.get_block('latest')['timestamp'] + 300  # 5 minutes
        
        tx = router.functions.swapExactETHForTokens(
            min_usdc_out,
            path,
            account.address,
            deadline
        ).build_transaction({
            'from': account.address,
            'value': swap_amount_wei,
            'gas': 250000,
            'gasPrice': gas_price,
            'nonce': web3.eth.get_transaction_count(account.address)
        })
        
        # Sign and send
        signed_tx = web3.eth.account.sign_transaction(tx, config.private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"\nTransaction sent: {tx_hash.hex()}")
        print("Waiting for confirmation...")
        
        # Wait for receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt['status'] == 1:
            print("\n✓ Swap successful!")
            print(f"Transaction: https://polygonscan.com/tx/{tx_hash.hex()}")
            
            # Check new USDC balance
            usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
            usdc_contract = web3.eth.contract(address=config.usdc_address, abi=usdc_abi)
            
            new_usdc_balance_raw = usdc_contract.functions.balanceOf(account.address).call()
            new_usdc_balance = Decimal(new_usdc_balance_raw) / Decimal(10**6)
            
            print(f"\nNew USDC Balance: ${new_usdc_balance:.6f}")
            
            if new_usdc_balance >= Decimal("0.50"):
                print("\n✓ You can now start trading!")
                print("\nRun: python test_real_trading.py")
            else:
                print("\n[WARNING] USDC balance still low")
                print("Consider swapping more MATIC or bridging from Ethereum")
        else:
            print("\n✗ Swap failed!")
            print(f"Transaction: https://polygonscan.com/tx/{tx_hash.hex()}")
            
    except Exception as e:
        print(f"\n[ERROR] Swap failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
