import time
import json
import requests
import random
import traceback
from datetime import datetime
from functools import wraps
from web3 import Web3
from openai import OpenAI
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

# --- ROBUST IMPORT FIX ---
try:
    from py_clob_client.order_builder.constants import BUY
except ImportError:
    BUY = "BUY" # Fallback if library changes

import config
import rust_core

# --- 0. NETWORK RETRY DECORATOR (Exponential Backoff) ---
def network_retry(max_retries=5, base_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    delay = base_delay * (2 ** retries) + random.uniform(0, 1)
                    print(f"[{datetime.now()}] ⚠️ Network Error in {func.__name__}: {e}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
            print(f"[{datetime.now()}] ❌ Failed after {max_retries} retries.")
            return None # Return None on final failure
        return wrapper
    return decorator

# --- 1. SETUP CLIENTS ---
print(f"[{datetime.now()}] ⚙️ Initializing Production Bot...")

client = ClobClient(config.POLYMARKET_CLOB, key=config.PRIVATE_KEY, chain_id=config.CHAIN_ID)
try:
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    print(f"[{datetime.now()}] ✅ API Keys Derived.")
except: pass

web3 = Web3(Web3.HTTPProvider(config.RPC_URL))
account = web3.eth.account.from_key(config.PRIVATE_KEY)

ai_client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=config.NVIDIA_API_KEY)

# --- 2. CORE FUNCTIONS ---

@network_retry()
def get_balances():
    """Checks both Wallet (EOA) and Proxy (Trading) balances."""
    # 1. Check Wallet USDC (EOA)
    usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'
    usdc_ct = web3.eth.contract(address=config.USDC_TOKEN, abi=usdc_abi)
    wallet_bal = usdc_ct.functions.balanceOf(account.address).call() / 10**6

    # 2. Check Trading Allowance/Balance (Proxy)
    # Note: We infer Proxy balance availability by checking what we can trade
    # In 'py-clob-client', create_or_derive_api_creds usually sets up the proxy.
    # We will trust the Wallet Balance for deposits and the User's Portfolio for trading.
    return wallet_bal

@network_retry()
def deposit_funds():
    """Moves funds from Wallet to Polymarket Proxy if needed."""
    wallet_bal = get_balances()
    if wallet_bal > 10.0:
        print(f"[{datetime.now()}] 💰 Wallet has ${wallet_bal}. Depositing to Proxy...")
        try:
            # Approve Exchange
            usdc = web3.eth.contract(address=config.USDC_TOKEN, abi='[{"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"}]')
            approve_tx = usdc.functions.approve(config.CTF_EXCHANGE, int(wallet_bal * 10**6)).build_transaction({
                'from': account.address, 'nonce': web3.eth.get_transaction_count(account.address), 'gasPrice': web3.eth.gas_price
            })
            s_tx = web3.eth.account.sign_transaction(approve_tx, config.PRIVATE_KEY)
            web3.eth.send_raw_transaction(s_tx.raw_transaction)
            time.sleep(5) # Wait for block

            # Deposit (This depends on the specific Proxy implementation, usually handled via UI)
            # For this bot, we assume if you manually deposited, it's fine.
            # AUTOMATED DEPOSIT IS COMPLEX WITHOUT PROXY ADDRESS.
            # We will Log this only.
            print(f"[{datetime.now()}] ✅ Approved. Please Deposit via Polymarket UI if Trading Balance is 0.")
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Deposit Error: {e}")

@network_retry()
def check_safety():
    """NVIDIA AI Guard."""
    try:
        resp = ai_client.chat.completions.create(
            model="stockmark/stockmark-2-100b-instruct",
            messages=[{"role":"user","content":"Is crypto crashing? YES/NO"}],
            max_tokens=5
        )
        return "YES" not in resp.choices[0].message.content.upper()
    except: return True

def merge_positions(condition_id):
    """Merges positions with Gas Estimation."""
    print(f"[{datetime.now()}] 🔄 Attempting Merge...")
    try:
        ctf_abi = '[{"constant":false,"inputs":[{"name":"parentCollectionId","type":"bytes32"},{"name":"conditionId","type":"bytes32"},{"name":"partition","type":"uint256[]"},{"name":"amount","type":"uint256"}],"name":"mergePositions","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"}]'
        contract = web3.eth.contract(address=config.CONDITIONAL_TOKEN, abi=ctf_abi)
        amount = int(config.STAKE_AMOUNT * 10**6)

        # 1. Estimate Gas
        func = contract.functions.mergePositions("0x"+"0"*64, condition_id, [1, 2], amount)
        try:
            gas_est = func.estimate_gas({'from': account.address})
            gas_limit = int(gas_est * 1.2) # Add 20% buffer
        except:
            gas_limit = config.GAS_LIMIT_MERGE

        # 2. Execute
        tx = func.build_transaction({
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address),
            'gasPrice': web3.eth.gas_price,
            'gas': gas_limit
        })
        signed = web3.eth.account.sign_transaction(tx, config.PRIVATE_KEY)
        thash = web3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"[{datetime.now()}] ✅ Merge Sent: {thash.hex()}")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Merge Failed: {e}")
        traceback.print_exc()

# --- 3. MAIN LOOP ---
def main():
    print(f"[{datetime.now()}] 🚀 Bot Started.")
    last_monitor = time.time()
    scanned = 0

    while True:
        # A. Safety
        if not check_safety():
            time.sleep(60); continue

        # B. Scan
        try:
            markets = client.get_markets(next_cursor="")
            m_list = markets.get('data', [])
            scanned += len(m_list)

            for m in m_list:
                if not m['closed'] and "15 minute" in m['question'] and m['active']:
                    found, yes_p, no_p = rust_core.find_arb(json.dumps(m), config.MIN_PROFIT)
                    if found:
                        print(f"[{datetime.now()}] ⚡ ARB: {m['question']} ({yes_p}/{no_p})")
                        # Buy YES
                        client.create_and_post_order(OrderArgs(price=yes_p, size=config.STAKE_AMOUNT, side=BUY, token_id=m['tokens'][0]['token_id'], order_type=OrderType.FOK))
                        # Buy NO
                        client.create_and_post_order(OrderArgs(price=no_p, size=config.STAKE_AMOUNT, side=BUY, token_id=m['tokens'][1]['token_id'], order_type=OrderType.FOK))
                        time.sleep(2)
                        merge_positions(m['condition_id'])
        except Exception:
            time.sleep(1)

        # C. Monitor & Auto-Deposit Check (Every 30s)
        if time.time() - last_monitor > 30:
            bal = get_balances()
            print(f"[{datetime.now()}] 💓 MONITOR: Scanned {scanned} | 💰 Wallet: ${bal:.2f} | ✅ Online")

            # Auto-Deposit Logic: If you have money in wallet, but bot needs it
            if bal > 20.0:
                print(f"[{datetime.now()}] 💡 Tip: You have ${bal} in wallet. Use 'Deposit' on Polymarket to trade with it.")

            scanned, last_monitor = 0, time.time()

        time.sleep(0.1)

if __name__ == "__main__":
    main()
