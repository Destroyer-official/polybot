#!/usr/bin/env python3
"""
Pre-flight check before running the bot.
Verifies all requirements are met for successful trading.
"""

import asyncio
import sys
from decimal import Decimal
from config.config import load_config
from web3 import Web3
from py_clob_client.client import ClobClient

def print_header(text):
    print("\n" + "=" * 80)
    print(text.center(80))
    print("=" * 80 + "\n")

def print_check(passed, message):
    symbol = "✓" if passed else "✗"
    status = "PASS" if passed else "FAIL"
    print(f"[{symbol}] {message}: {status}")
    return passed

async def main():
    print_header("POLYMARKET BOT PRE-FLIGHT CHECK")
    
    all_checks_passed = True
    
    # 1. Load configuration
    print("1. Loading configuration...")
    try:
        config = load_config()
        print_check(True, "Configuration loaded")
    except Exception as e:
        print_check(False, f"Configuration load failed: {e}")
        return 1
    
    # 2. Check wallet configuration
    print("\n2. Checking wallet configuration...")
    try:
        web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
        account = web3.eth.account.from_key(config.private_key)
        
        wallet_match = account.address.lower() == config.wallet_address.lower()
        all_checks_passed &= print_check(wallet_match, f"Wallet address matches private key")
        
        if not wallet_match:
            print(f"   Expected: {config.wallet_address}")
            print(f"   Got: {account.address}")
            return 1
            
        print(f"   Wallet: {account.address}")
    except Exception as e:
        all_checks_passed &= print_check(False, f"Wallet check failed: {e}")
        return 1
    
    # 3. Check RPC connection
    print("\n3. Checking RPC connection...")
    try:
        connected = web3.is_connected()
        all_checks_passed &= print_check(connected, "RPC connection")
        
        if connected:
            block = web3.eth.block_number
            print(f"   Latest block: {block}")
            chain_id = web3.eth.chain_id
            print(f"   Chain ID: {chain_id}")
            
            chain_match = chain_id == config.chain_id
            all_checks_passed &= print_check(chain_match, f"Chain ID matches (expected {config.chain_id})")
    except Exception as e:
        all_checks_passed &= print_check(False, f"RPC check failed: {e}")
        return 1
    
    # 4. Check USDC balance on Polygon
    print("\n4. Checking USDC balance on Polygon...")
    try:
        usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
        usdc_contract = web3.eth.contract(address=config.usdc_address, abi=usdc_abi)
        balance_wei = usdc_contract.functions.balanceOf(account.address).call()
        balance = Decimal(balance_wei) / Decimal(10**6)
        
        print(f"   Balance: ${balance:.2f} USDC")
        
        has_balance = balance >= Decimal("1.0")
        all_checks_passed &= print_check(has_balance, "Sufficient USDC balance (min $1.00)")
        
        if not has_balance:
            print("\n   ⚠️  INSUFFICIENT FUNDS")
            print(f"   Your balance: ${balance:.2f}")
            print(f"   Minimum needed: $1.00")
            print(f"\n   TO ADD FUNDS:")
            print(f"   1. Send USDC to: {account.address}")
            print(f"   2. Network: Polygon (Chain ID: 137)")
            print(f"   3. Token: USDC (0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174)")
            print(f"\n   OPTIONS:")
            print(f"   - Bridge from Ethereum: https://wallet.polygon.technology/")
            print(f"   - Withdraw from exchange (select Polygon network)")
            print(f"   - Use MetaMask Bridge feature")
            return 1
    except Exception as e:
        all_checks_passed &= print_check(False, f"Balance check failed: {e}")
        return 1
    
    # 5. Check gas balance (MATIC)
    print("\n5. Checking gas balance (MATIC)...")
    try:
        matic_balance_wei = web3.eth.get_balance(account.address)
        matic_balance = web3.from_wei(matic_balance_wei, 'ether')
        
        print(f"   Balance: {matic_balance:.4f} MATIC")
        
        has_gas = matic_balance >= Decimal("0.01")
        all_checks_passed &= print_check(has_gas, "Sufficient MATIC for gas (min 0.01)")
        
        if not has_gas:
            print("\n   ⚠️  INSUFFICIENT GAS")
            print(f"   Your balance: {matic_balance:.4f} MATIC")
            print(f"   Minimum needed: 0.01 MATIC (~$0.01)")
            print(f"\n   TO ADD MATIC:")
            print(f"   1. Send MATIC to: {account.address}")
            print(f"   2. Network: Polygon")
            print(f"   3. Get free MATIC: https://faucet.polygon.technology/")
            return 1
    except Exception as e:
        all_checks_passed &= print_check(False, f"Gas check failed: {e}")
        return 1
    
    # 6. Check Polymarket API connection
    print("\n6. Checking Polymarket API connection...")
    try:
        clob_client = ClobClient(
            host=config.polymarket_api_url,
            key=config.private_key,
            chain_id=config.chain_id
        )
        
        # Try to derive API credentials
        try:
            creds = clob_client.create_or_derive_api_creds()
            clob_client.set_api_creds(creds)
            print_check(True, "API credentials derived")
        except Exception as e:
            print_check(False, f"API credentials failed: {e}")
            all_checks_passed = False
        
        # Try to fetch markets
        try:
            markets = clob_client.get_markets()
            market_count = len(markets.get('data', []) if isinstance(markets, dict) else markets)
            print_check(True, f"API connection ({market_count} markets available)")
        except Exception as e:
            print_check(False, f"Market fetch failed: {e}")
            all_checks_passed = False
    except Exception as e:
        all_checks_passed &= print_check(False, f"Polymarket API check failed: {e}")
        return 1
    
    # 7. Check NVIDIA AI API (optional)
    print("\n7. Checking NVIDIA AI API (optional)...")
    if config.nvidia_api_key and config.nvidia_api_key != "your_nvidia_api_key_here":
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=config.nvidia_api_key
            )
            
            # Quick test
            response = client.chat.completions.create(
                model="deepseek-ai/deepseek-v3.2",
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=5
            )
            
            print_check(True, "NVIDIA AI API connected")
        except Exception as e:
            print_check(False, f"NVIDIA AI API failed: {e}")
            print("   Note: AI safety guard will be disabled")
    else:
        print("   [⚠] NVIDIA API key not configured (optional)")
        print("   Note: AI safety guard will be disabled")
    
    # 8. Check DRY_RUN mode
    print("\n8. Checking trading mode...")
    if config.dry_run:
        print("   [⚠] DRY_RUN MODE ENABLED")
        print("   No real trades will be executed")
        print("   This is SAFE for testing")
        print("\n   To enable real trading:")
        print("   1. Edit .env file")
        print("   2. Change DRY_RUN=true to DRY_RUN=false")
        print("   3. Run this check again")
    else:
        print("   [🚀] LIVE TRADING MODE ENABLED")
        print("   ⚠️  REAL MONEY WILL BE USED")
        print("   ⚠️  REAL TRADES WILL BE EXECUTED")
        print(f"   Starting balance: ${balance:.2f} USDC")
    
    # Final summary
    print_header("PRE-FLIGHT CHECK SUMMARY")
    
    if all_checks_passed and balance >= Decimal("1.0"):
        print("✅ ALL CHECKS PASSED")
        print("\n🚀 READY TO START TRADING!")
        print("\nTo start the bot, run:")
        print("   python src/main_orchestrator.py")
        print("\nOr use the Windows batch file:")
        print("   START_BOT.bat")
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        print("\n⚠️  Please fix the issues above before starting the bot")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
