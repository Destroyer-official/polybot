import os
import time
import logging
import requests
import json
from decimal import Decimal
from datetime import datetime
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.constants import POLYGON

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ManualTradeTest")

load_dotenv()

def main():
    logger.info("🚀 Starting Manual Live Trade Test (Gamma API Method)...")
    
    # 1. Config & Auth
    host = "https://clob.polymarket.com"
    key = os.getenv("PRIVATE_KEY")
    chain_id = 137
    
    if not key:
        logger.error("❌ No PRIVATE_KEY found in env!")
        return

    try:
        # FORCE EOA (0)
        client = ClobClient(
            host,
            key=key,
            chain_id=chain_id,
            signature_type=0, 
        )
        # Derive creds
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        logger.info("✅ API Credentials set.")
        
    except Exception as e:
        logger.error(f"❌ Auth Failed: {e}")
        return

    # 2. Find Active Market using Gamma API (Same as Strategy)
    logger.info("🔍 Fetching current BTC 15m market via Gamma API...")
    
    target_token_id = None
    market_slug = None
    
    try:
        # Calculate current 15-min interval
        now = int(time.time())
        current_interval = (now // 900) * 900
        
        # Try current interval
        slug = f"btc-updown-15m-{current_interval}"
        url = f"https://gamma-api.polymarket.com/events/slug/{slug}"
        
        logger.info(f"   Checking slug: {slug}")
        
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            markets = data.get("markets", [])
            if markets:
                m = markets[0] # Usually only one market per event?
                # Extract token IDs
                token_ids = m.get("clobTokenIds", [])
                if isinstance(token_ids, str):
                    token_ids = json.loads(token_ids)
                
                if len(token_ids) >= 2:
                    # Buy NO (Index 1) for safety/test
                    target_token_id = token_ids[1]
                    market_slug = slug
                    logger.info(f"   ✅ Found Market! Token ID: {target_token_id}")
                else:
                    logger.warning(f"   ⚠️ Market found but invalid token_ids: {token_ids}")
            else:
                logger.warning("   ⚠️ Event found but no markets linked.")
        else:
            logger.warning(f"   ⚠️ API 404/Error for {slug}: {resp.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Market Fetch Error: {e}")
        return

    if not target_token_id:
        logger.error("❌ Could not find a suitable market to trade.")
        return

    # 3. Check Balance & Allowance
    logger.info("💰 Checking Balances & Allowances...")
    try:
        from web3 import Web3
        try:
            from web3.middleware import geth_poa_middleware
        except ImportError:
            # Try v7+ style or just skip if not available (might fail on Tx)
            try:
                from web3.middleware import ExtraDataToPOAMiddleware as geth_poa_middleware
            except ImportError:
                geth_poa_middleware = None
                logger.warning("⚠️ Could not import geth_poa_middleware")

        # Setup Web3
        rpc_url = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        if geth_poa_middleware:
             w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        account = w3.eth.account.from_key(key)
        my_address = account.address
        logger.info(f"   Wallet: {my_address}")
        
        # Check MATIC
        matic_bal = w3.eth.get_balance(my_address)
        matic_eth = w3.from_wei(matic_bal, 'ether')
        logger.info(f"   MATIC: {matic_eth:.4f}")
        
        if matic_eth < 0.01:
            logger.error("❌ Insufficient MATIC for gas!")
            return

        # Check USDC (Polygon)
        usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174" # USDC.e
        # Or standard USDC? Polymarket uses USDC.e on Polygon POS usually.
        # Check config:
        # POLYGON_USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        
        usdc_abi = [
            {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},
            {"constant":True,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"remaining","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"},
            {"constant":False,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"payable":false,"stateMutability":"nonpayable","type":"function"}
        ]
        
        usdc_contract = w3.eth.contract(address=usdc_address, abi=usdc_abi)
        usdc_bal_wei = usdc_contract.functions.balanceOf(my_address).call()
        usdc_bal = usdc_bal_wei / 10**6
        logger.info(f"   USDC: {usdc_bal:.2f}")
        
        if usdc_bal < 2.0:
            logger.error("❌ Insufficient USDC! Need at least $2.00.")
            return

        # Check Allowance checking (Spender: Exchange Proxy)
        # Exchange Proxy address: 0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E (Mainnet)
        # Verify address?
        # Usually client.get_collateral_address? No.
        # Hardcoded:
        exchange_proxy = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
        
        allowance = usdc_contract.functions.allowance(my_address, exchange_proxy).call()
        logger.info(f"   Allowance: {allowance}")
        
        if allowance < 2000000: # 2 USDC
            logger.warning("⚠️ Low Allowance! Approving...")
            # Approve Max
            max_uint = 2**256 - 1
            txn = usdc_contract.functions.approve(exchange_proxy, max_uint).build_transaction({
                'from': my_address,
                'nonce': w3.eth.get_transaction_count(my_address),
                'gas': 100000,
                'gasPrice': w3.eth.gas_price
            })
            signed_txn = w3.eth.account.sign_transaction(txn, key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            logger.info(f"   Approve Tx Sent: {tx_hash.hex()}")
            logger.info("   Waiting for confirmation...")
            w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info("✅ Approved!")
            time.sleep(2)
        else:
            logger.info("✅ Allowance OK.")

    except Exception as e:
        logger.error(f"❌ Balance Check Error: {e}")
        # Continue? Maybe risky.
        pass

    # 4. BUY (Aggressive Limit / Market)
    logger.info("💸 Placing BUY Order (Size: $2)...")
    
    try:
        # Buy 2 shares at $0.99 (Limit that fills as Market) -> Total ~$1.98
        buy_price = 0.99
        buy_size = 2.0 
        
        order_args = OrderArgs(
            price=buy_price,
            size=buy_size,
            side="BUY",
            token_id=target_token_id
        )
        
        # Signed order
        resp = client.create_and_post_order(order_args)
        logger.info(f"📝 Buy Order Response: {resp}")
        
        if not resp or not resp.get('success'):
            logger.error(f"❌ Buy Order Failed! Resp: {resp}")
            return
            
        order_id = resp.get('orderID')
        logger.info(f"✅ Buy Order Placed! ID: {order_id}")
        
    except Exception as e:
        logger.error(f"❌ Buy Exception: {e}")
        return
        
    # 5. Wait
    logger.info("⏳ Waiting 5 seconds...")
    time.sleep(5)
    
    # 6. SELL
    logger.info("📉 Placing SELL Order (Closing Position)...")
    
    try:
        # Sell 1 share at $0.01 (Limit that fills as Market)
        sell_order_args = OrderArgs(
            price=0.01, 
            size=buy_size,
            side="SELL",
            token_id=target_token_id
        )
        
        resp_sell = client.create_and_post_order(sell_order_args)
        logger.info(f"📝 Sell Order Response: {resp_sell}")
        
        if resp_sell and resp_sell.get('success'):
             logger.info("✅ Sell Order Placed (Position Closed).")
        else:
             logger.error(f"❌ Sell Order Failed! Resp: {resp_sell}")
             
    except Exception as e:
        logger.error(f"❌ Sell Exception: {e}")

    logger.info("🏁 Test Complete.")

if __name__ == "__main__":
    main()
