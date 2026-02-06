#!/usr/bin/env python3
"""Find which network your USDC is on."""

from web3 import Web3
from decimal import Decimal

wallet = '0x1A821E4488732156cC9B3580efe3984F9B6C0116'

# USDC contracts on different networks
networks = {
    'Ethereum': {
        'rpc': 'https://eth.llamarpc.com',
        'usdc': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'decimals': 6
    },
    'Polygon': {
        'rpc': 'https://polygon-rpc.com',
        'usdc': '0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359',
        'decimals': 6
    },
    'Arbitrum': {
        'rpc': 'https://arb1.arbitrum.io/rpc',
        'usdc': '0xaf88d065e77c8cC2239327C5EDb3A432268e5831',
        'decimals': 6
    },
    'Optimism': {
        'rpc': 'https://mainnet.optimism.io',
        'usdc': '0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85',
        'decimals': 6
    },
    'Base': {
        'rpc': 'https://mainnet.base.org',
        'usdc': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
        'decimals': 6
    }
}

usdc_abi = '''[{
    "constant": true,
    "inputs": [{"name": "_owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "type": "function"
}]'''

print("=" * 80)
print("SEARCHING FOR YOUR USDC ACROSS NETWORKS...")
print("=" * 80)
print()

total_found = Decimal('0')
found_on = []

for network_name, config in networks.items():
    try:
        print(f"Checking {network_name}...", end=' ')
        
        web3 = Web3(Web3.HTTPProvider(config['rpc']))
        if not web3.is_connected():
            print("[SKIP] Connection failed")
            continue
        
        usdc_contract = web3.eth.contract(
            address=Web3.to_checksum_address(config['usdc']),
            abi=usdc_abi
        )
        
        balance_raw = usdc_contract.functions.balanceOf(wallet).call()
        balance = Decimal(balance_raw) / Decimal(10 ** config['decimals'])
        
        if balance > 0:
            print(f"[FOUND] ${balance:.2f} USDC")
            total_found += balance
            found_on.append((network_name, balance))
        else:
            print("[EMPTY] $0.00")
            
    except Exception as e:
        print(f"[ERROR] {str(e)[:50]}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

if total_found > 0:
    print(f"Total USDC found: ${total_found:.2f}")
    print()
    print("Found on:")
    for network, amount in found_on:
        print(f"  - {network}: ${amount:.2f}")
    print()
    
    if 'Polygon' not in [n for n, _ in found_on]:
        print("[ACTION NEEDED] Your USDC is NOT on Polygon!")
        print()
        print("To use the bot, you need to bridge USDC to Polygon:")
        print()
        for network, amount in found_on:
            print(f"Bridge from {network} to Polygon:")
            print(f"  1. Go to https://jumper.exchange/")
            print(f"  2. From: {network} → To: Polygon")
            print(f"  3. Amount: ${amount:.2f} USDC")
            print(f"  4. Confirm transaction")
            print()
    else:
        print("[OK] USDC is on Polygon - bot is ready!")
else:
    print("No USDC found on any network!")
    print()
    print("Your MetaMask shows $4.63 USDC, but it's not visible on-chain.")
    print()
    print("POSSIBLE REASONS:")
    print("1. USDC is on a network not checked (BSC, Avalanche, etc.)")
    print("2. MetaMask is showing a different wallet")
    print("3. The balance is pending/unconfirmed")
    print()
    print("SOLUTION:")
    print("1. In MetaMask, click on USDC token")
    print("2. Check which network you're on (top of screen)")
    print("3. Copy the contract address")
    print("4. Let me know which network it is")
