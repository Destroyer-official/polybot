import time
import json
import os
import requests
from web3 import Web3
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.constants import BUY
from openai import OpenAI  # For NVIDIA API
import rust_core

load_dotenv()

# --- CONFIGURATION ---
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
SAFE_WALLET = os.getenv("SAFE_WALLET") # Your Cold Wallet
NVIDIA_KEY = os.getenv("NVIDIA_API_KEY")

# Contracts (Polygon)
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E" # Polymarket Exchange
USDC_TOKEN = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"   # USDC.e
CONDITIONAL_TOKEN = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045" # CTF

# Clients
client = ClobClient("https://clob.polymarket.com", key=PRIVATE_KEY, chain_id=137)
web3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
account = web3.eth.account.from_key(PRIVATE_KEY)

# NVIDIA Client
ai_client = OpenAI(
  base_url="https://integrate.api.nvidia.com/v1",
  api_key=NVIDIA_KEY
)

def check_market_vibe():
    """Asks NVIDIA Stockmark: Is the market safe?"""
    try:
        completion = ai_client.chat.completions.create(
            model="stockmark/stockmark-2-100b-instruct",
            messages=[{"role":"user","content":"Is the crypto market currently experiencing a flash crash or extreme volatility? Reply only YES or NO."}],
            temperature=0.1,
            max_tokens=10
        )
        content = completion.choices[0].message.content
        return "YES" in content.upper()
    except Exception as e:
        print(f"⚠️ AI Check Failed: {e}")
        return False # Assume safe if AI fails

def merge_positions(condition_id):
    """
    THE ARB SECRET: Merges YES + NO tokens back into USDC.
    This realizes profit without selling fees.
    """
    print(f"🔄 Merging positions for {condition_id}...")
    try:
        # Load ABI for CTF (Simplified)
        ctf_abi = '[{"constant":false,"inputs":[{"name":"parentCollectionId","type":"bytes32"},{"name":"conditionId","type":"bytes32"},{"name":"partition","type":"uint256[]"},{"name":"amount","type":"uint256"}],"name":"mergePositions","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"}]'
        contract = web3.eth.contract(address=CONDITIONAL_TOKEN, abi=ctf_abi)

        # Merge 1 Share (1000000 units)
        tx = contract.functions.mergePositions(
            "0x" + "0"*64, # Parent Collection (Empty)
            condition_id,
            [1, 2], # Index Set for YES and NO
            1000000 # Amount to merge (Example: 1 USDC)
        ).build_transaction({
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address),
            'gasPrice': web3.eth.gas_price
        })

        signed_tx = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print("✅ Merge Success! Profit Locked.")
    except Exception as e:
        print(f"❌ Merge Failed: {e}")

def withdraw_profits():
    """Checks balance and sends profit to Cold Wallet"""
    try:
        usdc = web3.eth.contract(address=USDC_TOKEN, abi='[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}]')

        balance = usdc.functions.balanceOf(account.address).call() / 10**6
        print(f"💰 Balance: ${balance:.2f}")

        if balance > 500: # If > $500, withdraw excess
            amount = int((balance - 200) * 10**6) # Keep $200
            print(f"💸 Withdrawing ${(amount/10**6):.2f}...")

            tx = usdc.functions.transfer(SAFE_WALLET, amount).build_transaction({
                'from': account.address,
                'nonce': web3.eth.get_transaction_count(account.address),
                'gasPrice': web3.eth.gas_price
            })
            signed_tx = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print("✅ Withdrawal Sent!")
    except Exception as e:
        print(f"⚠️ Withdraw Error: {e}")

def main():
    print("🚀 Destroyer Bot Initialized.")

    # Auth
    try:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
    except: pass

    while True:
        # 1. AI Check (Every 5 mins logic handled by loop count or time check)
        # if check_market_vibe():
        #    print("🛑 Market Volatile. Pausing."); time.sleep(60); continue

        # 2. Scan & Trade
        try:
            markets = client.get_markets(next_cursor="")
            for m in markets.get('data', []):
                if not m['closed'] and "15 minute" in m['question']:
                    market_json = json.dumps(m)
                    found, yes_p, no_p = rust_core.find_arb(market_json, 0.01)

                    if found:
                        print(f"⚡ ARB: YES {yes_p} | NO {no_p}")
                        # Buy YES
                        client.create_and_post_order(OrderArgs(
                            price=yes_p, size=5, side=BUY, token_id=m['tokens'][0]['token_id'], order_type=OrderType.FOK
                        ))
                        # Buy NO
                        client.create_and_post_order(OrderArgs(
                            price=no_p, size=5, side=BUY, token_id=m['tokens'][1]['token_id'], order_type=OrderType.FOK
                        ))
                        # Merge immediately
                        merge_positions(m['condition_id'])
        except Exception as e:
            print(f"Loop Error: {e}")

        # 3. Check Withdrawals
        withdraw_profits()
        time.sleep(0.1)

if __name__ == "__main__":
    main()
