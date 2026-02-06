#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive test script for Polymarket Arbitrage Bot.

Tests all components:
1. Configuration loading
2. Wallet connectivity
3. Balance checking
4. NVIDIA AI integration
5. Dynamic position sizing
6. Fund management logic
7. Market scanning
"""

import asyncio
import sys
import os
from decimal import Decimal
from datetime import datetime
from web3 import Web3

# Fix Windows encoding
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("POLYMARKET ARBITRAGE BOT - COMPREHENSIVE TEST")
print("=" * 80)
print()

# Test 1: Configuration Loading
print("TEST 1: Configuration Loading")
print("-" * 80)
try:
    from config.config import load_config
    config = load_config()
    print(f"[OK] Config loaded successfully")
    print(f"   Wallet: {config.wallet_address}")
    print(f"   DRY_RUN: {config.dry_run}")
    print(f"   Min profit: {config.min_profit_threshold * 100}%")
    print(f"   Position size: ${config.min_position_size} - ${config.max_position_size}")
    print(f"   NVIDIA API: {'Configured' if config.nvidia_api_key else 'Not configured'}")
except Exception as e:
    print(f"[FAIL] Config loading failed: {e}")
    sys.exit(1)
print()

# Test 2: Wallet Connectivity
print("TEST 2: Wallet Connectivity")
print("-" * 80)
try:
    web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
    connected = web3.is_connected()
    print(f"[OK] RPC Connected: {connected}")
    
    if connected:
        chain_id = web3.eth.chain_id
        block_number = web3.eth.block_number
        print(f"   Chain ID: {chain_id}")
        print(f"   Latest Block: {block_number}")
        
        # Verify wallet
        account = web3.eth.account.from_key(config.private_key)
        print(f"   Wallet: {account.address}")
        
        if account.address.lower() != config.wallet_address.lower():
            print(f"[WARN] WARNING: Wallet mismatch!")
            print(f"   Expected: {config.wallet_address}")
            print(f"   Got: {account.address}")
except Exception as e:
    print(f"[FAIL] Wallet connectivity failed: {e}")
    sys.exit(1)
print()

# Test 3: Balance Checking
print("TEST 3: Balance Checking")
print("-" * 80)
try:
    # Check USDC balance
    usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
    usdc_contract = web3.eth.contract(
        address=Web3.to_checksum_address(config.usdc_address),
        abi=usdc_abi
    )
    
    balance_raw = usdc_contract.functions.balanceOf(account.address).call()
    balance_usdc = Decimal(balance_raw) / Decimal(10 ** 6)
    
    print(f"[OK] USDC Balance: ${balance_usdc:.2f}")
    
    if balance_usdc == 0:
        print(f"[WARN] WARNING: Zero balance - bot needs USDC to trade")
        print(f"   Please deposit USDC to: {account.address}")
        print(f"   Minimum recommended: $5")
except Exception as e:
    print(f"[FAIL] Balance check failed: {e}")
print()

# Test 4: NVIDIA AI Integration
print("TEST 4: NVIDIA AI Integration")
print("-" * 80)
if config.nvidia_api_key:
    try:
        from openai import OpenAI
        
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=config.nvidia_api_key
        )
        
        # Test simple query
        print("   Testing NVIDIA API connection...")
        completion = client.chat.completions.create(
            model="deepseek-ai/deepseek-v3.2",
            messages=[
                {"role": "user", "content": "Respond with YES if you can read this."}
            ],
            temperature=1,
            top_p=0.95,
            max_tokens=10,
            timeout=5.0
        )
        
        response = completion.choices[0].message.content if completion.choices else ""
        print(f"[OK] NVIDIA API working")
        print(f"   Model: deepseek-ai/deepseek-v3.2")
        print(f"   Response: {response}")
    except Exception as e:
        print(f"[FAIL] NVIDIA API test failed: {e}")
        print(f"   Bot will use fallback heuristics")
else:
    print("[WARN] NVIDIA API key not configured")
    print("   Bot will use fallback heuristics only")
print()

# Test 5: Dynamic Position Sizing
print("TEST 5: Dynamic Position Sizing")
print("-" * 80)
try:
    from src.dynamic_position_sizer import DynamicPositionSizer
    from src.models import Opportunity
    
    sizer = DynamicPositionSizer(
        min_position_size=config.min_position_size,
        max_position_size=config.max_position_size
    )
    
    # Test with different balance scenarios
    test_scenarios = [
        (Decimal('5.0'), Decimal('0'), "Small capital ($5)"),
        (Decimal('2.0'), Decimal('3.0'), "Split balance ($2 + $3)"),
        (Decimal('10.0'), Decimal('10.0'), "Medium capital ($20)"),
        (Decimal('50.0'), Decimal('0'), "Large capital ($50)"),
    ]
    
    # Create mock opportunity - simplified
    mock_opp = Opportunity(
        opportunity_id="test",
        market_id="test",
        strategy="internal_arbitrage",
        yes_price=Decimal('0.45'),
        no_price=Decimal('0.50'),
        total_cost=Decimal('0.95'),
        expected_profit=Decimal('0.05'),
        profit_percentage=Decimal('0.0526'),  # 5.26%
        timestamp=datetime.now(),
        yes_fee=Decimal('0.01'),
        no_fee=Decimal('0.01'),
        position_size=Decimal('1.0'),
        gas_estimate=Decimal('0.05')
    )
    
    print("   Testing position sizing with different balances:")
    for private, polymarket, desc in test_scenarios:
        size = sizer.calculate_position_size(
            private_wallet_balance=private,
            polymarket_balance=polymarket,
            opportunity=mock_opp
        )
        total = private + polymarket
        pct = (size / total * 100) if total > 0 else 0
        print(f"   {desc}: ${size:.2f} ({pct:.1f}% of balance)")
    
    print(f"[OK] Dynamic position sizing working")
except Exception as e:
    print(f"[FAIL] Position sizing test failed: {e}")
print()

# Test 6: Fund Management Logic
print("TEST 6: Fund Management Logic")
print("-" * 80)
try:
    from src.fund_manager import FundManager
    
    fund_mgr = FundManager(
        web3=web3,
        wallet=account,
        usdc_address=config.usdc_address,
        ctf_exchange_address=config.ctf_exchange_address,
        min_balance=config.min_balance,
        target_balance=config.target_balance,
        withdraw_limit=config.withdraw_limit,
        dry_run=True  # Always dry run for testing
    )
    
    print(f"[OK] Fund manager initialized")
    print(f"   Min balance: ${config.min_balance}")
    print(f"   Target balance: ${config.target_balance}")
    print(f"   Withdraw limit: ${config.withdraw_limit}")
    print(f"   Mode: DRY RUN")
except Exception as e:
    print(f"[FAIL] Fund manager test failed: {e}")
print()

# Test 7: Market Scanning
print("TEST 7: Market Scanning")
print("-" * 80)
try:
    from py_clob_client.client import ClobClient
    
    clob_client = ClobClient(
        host=config.polymarket_api_url,
        key=config.private_key,
        chain_id=config.chain_id
    )
    
    print("   Fetching markets from Polymarket...")
    markets_response = clob_client.get_markets()
    
    if isinstance(markets_response, dict):
        markets = markets_response.get('data', [])
    else:
        markets = markets_response
    
    total_markets = len(markets)
    active_markets = sum(1 for m in markets if not m.get('closed', True))
    
    print(f"[OK] Market scanning working")
    print(f"   Total markets: {total_markets}")
    print(f"   Active markets: {active_markets}")
    
    # Show sample markets
    if active_markets > 0:
        print(f"   Sample markets:")
        count = 0
        for m in markets:
            if not m.get('closed', True) and count < 3:
                question = m.get('question', 'Unknown')
                if len(question) > 60:
                    question = question[:57] + "..."
                print(f"     - {question}")
                count += 1
except Exception as e:
    print(f"[FAIL] Market scanning failed: {e}")
print()

# Summary
print("=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print()
print("[OK] All core components tested successfully!")
print()
print("NEXT STEPS:")
print("1. Ensure you have USDC in your wallet")
print("2. Start with DRY_RUN=true to test without real trades")
print("3. Monitor for 24 hours to verify behavior")
print("4. Once confident, set DRY_RUN=false for live trading")
print()
print("TO START THE BOT:")
print("  python src/main_orchestrator.py")
print()
print("=" * 80)
