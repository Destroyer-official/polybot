#!/usr/bin/env python3
"""
Emergency Position Closer

This script forcefully closes ALL open positions on Polymarket.
Use this when the bot fails to close positions automatically.

Usage:
    python emergency_close_positions.py

Requirements:
    - .env file with PRIVATE_KEY and WALLET_ADDRESS
    - Active internet connection
    - USDC balance for gas (if needed)
"""

import asyncio
import logging
import os
import json
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, BalanceAllowanceParams, AssetType
from py_clob_client.order_builder.constants import SELL

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_all_positions(clob_client: ClobClient) -> list:
    """Get all open positions from Polymarket."""
    try:
        # Get balance/allowance which includes positions
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        balance_info = clob_client.get_balance_allowance(params)
        
        logger.info(f"Balance info: {balance_info}")
        
        # Try to get positions from Data API
        # Note: This requires the wallet address
        wallet_address = os.getenv("WALLET_ADDRESS")
        if not wallet_address:
            logger.error("WALLET_ADDRESS not found in environment")
            return []
        
        # Use CLOB API to get open orders (positions)
        try:
            orders = clob_client.get_orders()
            logger.info(f"Found {len(orders) if orders else 0} open orders")
            return orders if orders else []
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []


async def close_position_by_token(clob_client: ClobClient, token_id: str, size: float, current_price: float = None):
    """Close a position by selling all shares."""
    try:
        logger.info(f"Closing position for token {token_id[:16]}...")
        logger.info(f"  Size: {size:.2f} shares")
        
        # If no price provided, get from orderbook
        if current_price is None:
            try:
                orderbook = clob_client.get_order_book(token_id)
                if orderbook and hasattr(orderbook, 'bids') and orderbook.bids:
                    # Get best bid
                    best_bid = orderbook.bids[0]
                    current_price = float(getattr(best_bid, 'price', 0.5))
                    logger.info(f"  Best bid price: ${current_price:.4f}")
                else:
                    current_price = 0.5  # Default mid price
                    logger.warning(f"  No orderbook data, using default price: ${current_price:.4f}")
            except Exception as e:
                logger.error(f"  Failed to get orderbook: {e}")
                current_price = 0.5
        
        # Round size to 2 decimals
        size = round(size, 2)
        
        # Create sell order
        order_args = OrderArgs(
            token_id=token_id,
            price=current_price,
            size=size,
            side=SELL
        )
        
        logger.info(f"  Creating SELL order: {size:.2f} shares @ ${current_price:.4f}")
        
        # Sign and post order
        signed_order = clob_client.create_order(order_args)
        response = clob_client.post_order(signed_order)
        
        if response:
            order_id = response.get("orderID") or response.get("order_id") or "unknown"
            logger.info(f"  ✅ Position closed successfully! Order ID: {order_id}")
            return True
        else:
            logger.error(f"  ❌ Failed to close position - empty response")
            return False
    
    except Exception as e:
        logger.error(f"  ❌ Failed to close position: {e}")
        return False


async def close_all_positions_from_file():
    """Close all positions from active_positions.json file."""
    load_dotenv()
    
    # Check for required env vars
    private_key = os.getenv("PRIVATE_KEY")
    wallet_address = os.getenv("WALLET_ADDRESS")
    
    if not private_key or not wallet_address:
        logger.error("Missing PRIVATE_KEY or WALLET_ADDRESS in .env file")
        return
    
    # Initialize CLOB client
    logger.info("Initializing Polymarket CLOB client...")
    clob_client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137,
        signature_type=2,  # Gnosis Safe
        funder="0x93e65c1419AB8147cbd16d440Bb7FC178b3b2F35"
    )
    
    # Derive API credentials
    logger.info("Deriving API credentials...")
    creds = clob_client.create_or_derive_api_creds()
    clob_client.set_api_creds(creds)
    logger.info(f"✅ CLOB client initialized")
    
    # Check for active_positions.json
    positions_file = Path("data/active_positions.json")
    
    if positions_file.exists():
        logger.info(f"Found positions file: {positions_file}")
        
        with open(positions_file, 'r') as f:
            positions_data = json.load(f)
        
        if not positions_data:
            logger.info("No positions in file")
            return
        
        logger.info(f"Found {len(positions_data)} positions to close")
        
        for token_id, pos_data in positions_data.items():
            logger.info("=" * 80)
            logger.info(f"Position: {pos_data.get('asset')} {pos_data.get('side')}")
            logger.info(f"  Token ID: {token_id[:16]}...")
            logger.info(f"  Entry Price: ${pos_data.get('entry_price')}")
            logger.info(f"  Size: {pos_data.get('size')} shares")
            logger.info(f"  Entry Time: {pos_data.get('entry_time')}")
            
            # Calculate age
            entry_time = datetime.fromisoformat(pos_data.get('entry_time'))
            age_min = (datetime.now(timezone.utc) - entry_time).total_seconds() / 60
            logger.info(f"  Age: {age_min:.1f} minutes")
            
            # Close position
            size = float(pos_data.get('size', 0))
            if size > 0:
                success = await close_position_by_token(clob_client, token_id, size)
                if success:
                    logger.info(f"  ✅ Successfully closed position")
                else:
                    logger.error(f"  ❌ Failed to close position")
            else:
                logger.warning(f"  ⚠️ Invalid size: {size}")
            
            # Wait between orders
            await asyncio.sleep(2)
        
        logger.info("=" * 80)
        logger.info("All positions processed")
        
        # Backup and clear the file
        backup_file = positions_file.with_suffix('.json.backup')
        positions_file.rename(backup_file)
        logger.info(f"Backed up positions to: {backup_file}")
    
    else:
        logger.info("No active_positions.json file found")
        logger.info("Checking for open orders via API...")
        
        # Try to get positions from API
        positions = await get_all_positions(clob_client)
        
        if positions:
            logger.info(f"Found {len(positions)} open orders")
            for order in positions:
                logger.info(f"Order: {order}")
        else:
            logger.info("No open orders found")


async def main():
    """Main entry point."""
    logger.info("=" * 80)
    logger.info("EMERGENCY POSITION CLOSER")
    logger.info("=" * 80)
    logger.info("This script will close ALL open positions on Polymarket")
    logger.info("=" * 80)
    
    # Confirm with user
    response = input("\nAre you sure you want to close all positions? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Aborted by user")
        return
    
    await close_all_positions_from_file()
    
    logger.info("=" * 80)
    logger.info("DONE")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
