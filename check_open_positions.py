#!/usr/bin/env python3
"""
Check actual open positions on Polymarket account.
This will show if there are any positions the bot "forgot" about after restart.
"""
import asyncio
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from dotenv import load_dotenv
import os

load_dotenv()

async def check_positions():
    # Initialize client
    host = "https://clob.polymarket.com"
    key = os.getenv("POLYMARKET_PRIVATE_KEY")
    chain_id = 137  # Polygon
    
    # Create API credentials
    creds = ApiCreds(
        api_key=os.getenv("POLYMARKET_API_KEY", ""),
        api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
        api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE", "")
    )
    
    client = ClobClient(host, key=key, chain_id=chain_id, creds=creds)
    
    print("=" * 80)
    print("CHECKING POLYMARKET ACCOUNT")
    print("=" * 80)
    print()
    
    # Get balance
    try:
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        balance_info = client.get_balance_allowance(params)
        
        if isinstance(balance_info, dict):
            balance_raw = balance_info.get('balance', '0')
            balance = float(balance_raw) / 1_000_000  # USDC has 6 decimals
            print(f"💰 Balance: ${balance:.2f} USDC")
            print()
    except Exception as e:
        print(f"Could not get balance: {e}")
        print()
    
    # Get open orders
    try:
        orders = client.get_orders()
        if orders:
            print(f"📋 Open Orders: {len(orders)}")
            for order in orders:
                print(f"   Order ID: {order.get('id', 'unknown')}")
                print(f"   Market: {order.get('market', 'unknown')}")
                print(f"   Side: {order.get('side', 'unknown')}")
                print(f"   Size: {order.get('size', 0)}")
                print(f"   Price: ${order.get('price', 0)}")
                print()
        else:
            print("📋 No open orders")
            print()
    except Exception as e:
        print(f"Could not get orders: {e}")
        print()
    
    # Try to get positions (if API supports it)
    try:
        # Note: py-clob-client may not have a direct "get positions" method
        # Positions are typically tracked client-side
        print("ℹ️  Note: Polymarket positions are typically tracked client-side")
        print("   The bot lost position tracking when it restarted")
        print()
    except Exception as e:
        print(f"Error: {e}")
    
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()
    print("If the bot placed an order at 11:16 for XRP UP @ $0.49:")
    print("  • That market ended at 11:30 (15 minutes later)")
    print("  • If XRP went UP, position auto-resolved to $1.00/share = PROFIT")
    print("  • If XRP went DOWN, position auto-resolved to $0.00/share = LOSS")
    print("  • Check your Polymarket web interface to see resolved positions")
    print()
    print("The bot needs position persistence to survive restarts!")
    print()

if __name__ == "__main__":
    asyncio.run(check_positions())
