#!/usr/bin/env python3
"""
Check USDC balance across multiple networks.
This will help identify where your $4.63 USDC is located.
"""

from web3 import Web3
from decimal import Decimal

# Your wallet address
WALLET = "0x1A821E4488732156cC9B3580efe3984F9B6C0116"

# USDC addresses on different networks
NETWORKS = {
    "Ethereum": {
        "rpc": "https://eth.llamarpc.com",
        "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "decimals": 6
    },
    "Polygon": {
        "rpc": "https://polygon-rpc.com",
        "usdc": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "decimals": 6
    },
    "Arbitrum": {
        "rpc": "https://arb1.arbitrum.io/rpc",
        "usdc": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
        "decimals": 6
    },
    "Optimism": {
        "rpc": "https://mainnet.optimism.io",
        "usdc": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
        "decimals": 6
    },
    "Base": {
        "rpc": "https://mainnet.base.org",
        "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "decimals": 6
    }
}

# ERC20 ABI for balanceOf
ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]

print("=" * 80)
print("CHECKING USDC BALANCE ACROSS ALL NETWORKS")
print("=" * 80)
print(f"Wallet: {WALLET}")
print()

total_usdc = Decimal('0')

for network_name, config in NETWORKS.items():
    try:
        # Connect to network
        web3 = Web3(Web3.HTTPProvider(config["rpc"]))
        
        if not web3.is_connected():
            print(f"❌ {network_name}: Connection failed")
            continue
        
        # Get USDC contract
        usdc_contract = web3.eth.contract(
            address=Web3.to_checksum_address(config["usdc"]),
            abi=ABI
        )
        
        # Get balance
        balance_raw = usdc_contract.functions.balanceOf(
            Web3.to_checksum_address(WALLET)
        ).call()
        
        balance = Decimal(balance_raw) / Decimal(10 ** config["decimals"])
        total_usdc += balance
        
        if balance > 0:
            print(f"✅ {network_name}: ${balance:.2f} USDC")
        else:
            print(f"⚪ {network_name}: $0.00 USDC")
            
    except Exception as e:
        print(f"❌ {network_name}: Error - {e}")

print()
print("=" * 80)
print(f"TOTAL USDC ACROSS ALL NETWORKS: ${total_usdc:.2f}")
print("=" * 80)
print()

if total_usdc > 0:
    print("✅ USDC found!")
    print()
    print("Next steps:")
    print("1. If USDC is on Polygon: You're ready to trade!")
    print("2. If USDC is on another network: Bridge to Polygon")
    print()
    print("To bridge:")
    print("- Use MetaMask 'Bridge' button")
    print("- Or use Polygon Bridge: https://wallet.polygon.technology/")
    print("- Or withdraw from exchange to Polygon network")
else:
    print("❌ No USDC found on any network")
    print()
    print("Your MetaMask shows $4.63 USDC, but it might be:")
    print("1. On a different wallet address")
    print("2. On a network not checked here")
    print("3. A display issue in MetaMask")
    print()
    print("Please check:")
    print("- Which network is selected in MetaMask?")
    print("- Is the wallet address correct?")
