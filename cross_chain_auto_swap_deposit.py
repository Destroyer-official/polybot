# cross_chain_auto_swap_deposit.py
"""
Auto-swap any supported token -> chain-native USDC and deposit to Polymarket deposit address.

Controls:
 - DRY_RUN=1 avoids broadcasting txs (good for testing)
 - Use paid RPC endpoints to avoid rate limits
 - Configure USDC addresses and Polymarket deposit addresses per chain in the mappings below
"""

import os
import time
import json
import math
import requests
from decimal import Decimal

from web3 import Web3
from web3.exceptions import TransactionNotFound
from eth_account import Account

# ---------- CONFIG - EDIT THESE ----------
# Chains you want to support (keys used in RPC_URL_... env)
SUPPORTED_CHAINS = ["ethereum", "polygon", "arbitrum", "optimism"]

# Chain IDs for 1inch API (v5)
CHAIN_IDS = {
    "ethereum": 1,
    "polygon": 137,
    "arbitrum": 42161,
    "optimism": 10,
}

# RPC env var names like RPC_URL_ETHEREUM, RPC_URL_POLYGON, ...
RPC_ENV_BY_CHAIN = {
    "ethereum": "RPC_URL_ETHEREUM",
    "polygon": "RPC_URL_POLYGON",
    "arbitrum": "RPC_URL_ARBITRUM",
    "optimism": "RPC_URL_OPTIMISM",
}

# USDC token addresses (verify before use)
USDC_ADDRESS_BY_CHAIN = {
    "ethereum": Web3.to_checksum_address("0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"),
    "polygon": Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"),
    "arbitrum": Web3.to_checksum_address("0xFF970A61A04b1cA14834A43f5DE4533eBDDB5CC8"),
    "optimism": Web3.to_checksum_address("0x7F5c764cBc14f9669B88837ca1490cCa17c31607"),
}

# Common token addresses to check (curated to avoid scanning entire tokenlist)
# Verify/extend for your chains. Provide checksum addresses.
COMMON_TOKENS = {
    "ethereum": {
        # USDT, WETH, DAI
        "USDT": Web3.to_checksum_address("0xdAC17F958D2ee523a2206206994597C13D831ec7"),
        "WETH": Web3.to_checksum_address("0xC02aaA39b223FE8D0a0e5C4F27eAD9083C756Cc2"),
        "DAI": Web3.to_checksum_address("0x6B175474E89094C44Da98b954EedeAC495271d0F"),
    },
    "polygon": {
        "USDT": Web3.to_checksum_address("0x3813e82e6f7098b9583FC0F33a962D02018B6803"),  # (Note: verify on polygon)
        "WETH": Web3.to_checksum_address("0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"),
        "DAI": Web3.to_checksum_address("0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063"),
    },
    "arbitrum": {
        "USDT": Web3.to_checksum_address("0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9"),
        "WETH": Web3.to_checksum_address("0x82af49447d8a07e3bd95bd0d56f35241523fbab1"),
        "DAI": Web3.to_checksum_address("0xda10009cbd5d07dd0cecc66161fc93d7c9000da1"),
    },
    "optimism": {
        "USDT": Web3.to_checksum_address("0x94b008aA00579c1307B0EF2c499aD98a8ce58e58"),
        "WETH": Web3.to_checksum_address("0x4200000000000000000000000000000000000006"),
        "DAI": Web3.to_checksum_address("0xDA10009cbd5D07dd0CeCc66161FC93D7c9000da1"),
    },
}

# Polymarket deposit addresses per chain (YOU MUST FILL these from your account UI)
POLY_DEPOSIT_ADDRESSES = {
    # "ethereum": "0xYourPolymarketDepositAddressOnEth",
    # "polygon": "0xYourPolymarketDepositAddressOnPolygon",
    # "arbitrum": "...",
    # "optimism": "...",
}
# ---------- END CONFIG ----------


# ENV & GLOBALS
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
if not PRIVATE_KEY:
    raise RuntimeError("Set PRIVATE_KEY environment variable before running (test only in DRY_RUN).")

DRY_RUN = os.environ.get("DRY_RUN", "1") == "1"
MIN_USDC_USD = float(os.environ.get("MIN_USDC_USD", "3.0"))   # minimum deposit
SWAP_SLIPPAGE_PCT = float(os.environ.get("SWAP_SLIPPAGE_PCT", "0.01"))  # 1% default
RETRY_BASE_DELAY = float(os.environ.get("RETRY_BASE_DELAY", "0.5"))
RETRY_MAX = int(os.environ.get("RETRY_MAX", "5"))
ALLOW_AUTO_SWAP = os.environ.get("ALLOW_AUTO_SWAP", "1") == "1"

# Minimal ERC20 ABI pieces we use
ERC20_ABI = json.loads("""[
  {"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
  {"constant":false,"inputs":[{"name":"_spender","type":"address"},{"name":"_value","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},
  {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
  {"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"},
  {"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}
]""")


# ---------- helpers ----------
def retry_rpc(fn):
    def wrapper(*args, **kwargs):
        last_exc = None
        for attempt in range(RETRY_MAX):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_exc = e
                sleep = RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(sleep)
        raise last_exc
    return wrapper


def build_web3_for_chain(chain):
    env = RPC_ENV_BY_CHAIN.get(chain)
    if not env:
        raise KeyError(f"No RPC env configured for chain {chain}")
    url = os.environ.get(env)
    if not url:
        raise RuntimeError(f"Set env {env} to a valid RPC URL for chain {chain}")
    w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 20}))
    if not w3.is_connected():
        raise RuntimeError(f"Web3 provider for {chain} not connected at {url}")
    return w3


@retry_rpc
def get_native_balance(w3, address):
    return w3.eth.get_balance(address)


@retry_rpc
def get_erc20_balance(w3, token_addr, address):
    token = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    return token.functions.balanceOf(address).call()


@retry_rpc
def get_token_decimals(w3, token_addr):
    token = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    try:
        return token.functions.decimals().call()
    except Exception:
        # some tokens may not implement decimals; assume 18
        return 18


@retry_rpc
def get_allowance(w3, token_addr, owner, spender):
    token = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    return token.functions.allowance(owner, spender).call()


@retry_rpc
def send_raw_transaction(w3, signed_raw_tx):
    return w3.eth.send_raw_transaction(signed_raw_tx)


def build_transfer_tx(w3, token_addr, from_addr, to_addr, amount_wei, gas=None, gas_price=None):
    token = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    tx = token.functions.transfer(Web3.to_checksum_address(to_addr), int(amount_wei)).buildTransaction({
        "from": Web3.to_checksum_address(from_addr),
        "nonce": w3.eth.get_transaction_count(Web3.to_checksum_address(from_addr)),
        "gas": gas or 120000,
        "gasPrice": gas_price or w3.eth.gas_price,
    })
    return tx


def build_approve_tx(w3, token_addr, owner, spender, amount_wei, gas=None, gas_price=None):
    token = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    tx = token.functions.approve(spender, int(amount_wei)).buildTransaction({
        "from": Web3.to_checksum_address(owner),
        "nonce": w3.eth.get_transaction_count(Web3.to_checksum_address(owner)),
        "gas": gas or 100000,
        "gasPrice": gas_price or w3.eth.gas_price,
    })
    return tx


# ---------- 1inch helpers ----------
def oneinch_api_base(chain):
    chain_id = CHAIN_IDS.get(chain)
    if not chain_id:
        raise KeyError(f"Chain id not known for {chain}")
    return f"https://api.1inch.io/v5.0/{chain_id}"


def get_1inch_quote(chain, src_token, dst_token, amount_wei):
    api = oneinch_api_base(chain)
    url = api + "/quote"
    params = {"fromTokenAddress": src_token, "toTokenAddress": dst_token, "amount": str(int(amount_wei))}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def build_1inch_swap(chain, account, src_token, dst_token, amount_wei, slippage_pct, dest_receiver=None):
    api = oneinch_api_base(chain)
    url = api + "/swap"
    body = {
        "fromTokenAddress": src_token,
        "toTokenAddress": dst_token,
        "amount": str(int(amount_wei)),
        "fromAddress": account,
        "slippage": int(slippage_pct * 100),  # 1inch expects integer percent
    }
    if dest_receiver:
        body["destReceiver"] = dest_receiver
    r = requests.get(url, params=body, timeout=20)
    r.raise_for_status()
    return r.json()


# ---------- main flow ----------
def amount_to_decimal(amount_wei, decimals):
    return Decimal(amount_wei) / (Decimal(10) ** decimals)


def decimal_to_wei(amount_dec, decimals):
    return int((Decimal(amount_dec) * (Decimal(10) ** decimals)).to_integral_value())


def swap_token_to_usdc_and_deposit(chain, account_address, token_addr, token_amount_wei):
    """
    1) Query 1inch quote for token -> USDC
    2) Approve 1inch router if needed
    3) Execute swap
    4) Transfer USDC to Polymarket deposit address (configured)
    """
    if chain not in POLY_DEPOSIT_ADDRESSES:
        raise RuntimeError(f"Missing Polymarket deposit address for chain {chain} in POLY_DEPOSIT_ADDRESSES")

    w3 = build_web3_for_chain(chain)
    usdc_addr = USDC_ADDRESS_BY_CHAIN[chain]
    deposit_addr = Web3.to_checksum_address(POLY_DEPOSIT_ADDRESSES[chain])
    account = Web3.to_checksum_address(account_address)

    # 1) quote
    quote = get_1inch_quote(chain, token_addr, usdc_addr, token_amount_wei)
    estimated_to_amount = int(quote["toTokenAmount"])
    # simple slippage check: 1inch quote may be OK; trusting it because swap will include slippage param.

    # 2) build swap
    swap_resp = build_1inch_swap(chain, account, token_addr, usdc_addr, token_amount_wei, SWAP_SLIPPAGE_PCT)
    tx_obj = swap_resp.get("tx")
    if not tx_obj:
        raise RuntimeError("1inch swap response missing tx object")

    # If approvalData present -> need to approve
    approval_spender = tx_obj.get("to")  # 1inch router address
    # check allowance:
    allowance = get_allowance(w3, token_addr, account, approval_spender) if token_addr.lower() != "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" else 2**256-1
    if allowance < token_amount_wei:
        print(f"Approving {token_addr} to spender {approval_spender} for amount {token_amount_wei}")
        if DRY_RUN:
            print("DRY_RUN mode: skipping approve tx")
        else:
            approve_tx = build_approve_tx(w3, token_addr, account, approval_spender, token_amount_wei)
            signed = Account.sign_transaction(approve_tx, PRIVATE_KEY)
            txh = send_raw_transaction(w3, signed.rawTransaction)
            receipt = w3.eth.wait_for_transaction_receipt(txh, timeout=600)
            if receipt.status != 1:
                raise RuntimeError("Approve transaction failed")

    # 3) send swap tx (tx_obj contains to, data, value, gas, gasPrice maybe)
    tx_for_sign = {
        "to": Web3.to_checksum_address(tx_obj["to"]),
        "data": tx_obj["data"],
        "value": int(tx_obj.get("value", 0)),
        "chainId": w3.eth.chain_id,
        "nonce": w3.eth.get_transaction_count(account),
        # gas / gasPrice: prefer the tx_obj values if present
        "gas": int(tx_obj.get("gas", 800000)),
        "gasPrice": int(tx_obj.get("gasPrice", w3.eth.gas_price)),
    }
    print("Sending swap tx:", {k: v for k, v in tx_for_sign.items() if k != "data"})
    if DRY_RUN:
        print("DRY_RUN - not broadcasting swap tx. Estimated USDC:", estimated_to_amount)
    else:
        signed_swap = Account.sign_transaction(tx_for_sign, PRIVATE_KEY)
        txh = send_raw_transaction(w3, signed_swap.rawTransaction)
        print("swap tx sent", txh.hex())
        receipt = w3.eth.wait_for_transaction_receipt(txh, timeout=900)
        if receipt.status != 1:
            raise RuntimeError("Swap transaction failed")
        print("swap success", receipt.transactionHash.hex())

    # 4) after swap, compute USDC balance and transfer to Polymarket deposit address
    usdc_balance = get_erc20_balance(w3, usdc_addr, account)
    decimals = get_token_decimals(w3, usdc_addr)
    usdc_dec = amount_to_decimal(usdc_balance, decimals)
    print(f"Post-swap USDC balance: {usdc_dec} (decimals={decimals})")
    if usdc_balance == 0:
        raise RuntimeError("Swap produced 0 USDC - aborting")

    # Respect Polymarket min (we check USD amount only)
    if float(usdc_dec) < MIN_USDC_USD:
        raise RuntimeError(f"Post-swap USDC {usdc_dec} is below MIN_USDC_USD {MIN_USDC_USD}")

    # Transfer USDC to deposit address
    transfer_tx = build_transfer_tx(w3, usdc_addr, account, deposit_addr, usdc_balance)
    print("Transferring USDC to Polymarket deposit address:", deposit_addr)
    if DRY_RUN:
        print("DRY_RUN - skip transfer")
    else:
        signed_t = Account.sign_transaction(transfer_tx, PRIVATE_KEY)
        txh = send_raw_transaction(w3, signed_t.rawTransaction)
        print("deposit tx sent", txh.hex())
        receipt = w3.eth.wait_for_transaction_receipt(txh, timeout=600)
        if receipt.status != 1:
            raise RuntimeError("Deposit transfer failed")
        print("deposit success", receipt.transactionHash.hex())

    return True


def process_chain(chain, account_address):
    print("Processing chain:", chain)
    w3 = build_web3_for_chain(chain)
    account = Web3.to_checksum_address(account_address)

    # Quick checks
    native_bal = get_native_balance(w3, account)
    native_eth_dec = w3.from_wei(native_bal, "ether")
    print(f"Native balance on {chain}: {native_eth_dec}")

    usdc_addr = USDC_ADDRESS_BY_CHAIN.get(chain)
    if not usdc_addr:
        print(f"No USDC address configured for {chain} - skipping")
        return False

    usdc_balance = get_erc20_balance(w3, usdc_addr, account)
    usdc_dec = amount_to_decimal(usdc_balance, get_token_decimals(w3, usdc_addr))
    print(f"USDC balance: {usdc_dec}")

    if float(usdc_dec) >= MIN_USDC_USD:
        print("Enough USDC to deposit. Preparing transfer to Polymarket deposit address.")
        if chain not in POLY_DEPOSIT_ADDRESSES:
            print("Polymarket deposit address not configured for this chain. Please add to POLY_DEPOSIT_ADDRESSES.")
            return False
        # Transfer USDC to deposit
        deposit_addr = Web3.to_checksum_address(POLY_DEPOSIT_ADDRESSES[chain])
        tx = build_transfer_tx(w3, usdc_addr, account, deposit_addr, usdc_balance)
        if DRY_RUN:
            print("DRY_RUN mode - would transfer:", tx)
            return True
        signed = Account.sign_transaction(tx, PRIVATE_KEY)
        txh = send_raw_transaction(w3, signed.rawTransaction)
        print("Sent USDC transfer tx:", txh.hex())
        receipt = w3.eth.wait_for_transaction_receipt(txh, timeout=600)
        print("Transfer receipt status:", receipt.status)
        return receipt.status == 1

    # Not enough USDC; if auto swap allowed, try other tokens
    if not ALLOW_AUTO_SWAP:
        print("Auto-swap disabled. Skipping.")
        return False

    # Look for configured common tokens with balance > 0
    token_map = COMMON_TOKENS.get(chain, {})
    found = []
    for name, addr in token_map.items():
        try:
            bal = get_erc20_balance(w3, addr, account)
            if bal > 0:
                dec = get_token_decimals(w3, addr)
                print(f"Found token {name} balance {amount_to_decimal(bal, dec)}")
                found.append((name, addr, bal))
        except Exception as e:
            print("Error reading token", name, e)

    if not found:
        print("No candidate tokens with balance found in curated list. Enable FULL_SCAN or extend COMMON_TOKENS.")
        return False

    # Choose largest by USD estimate: we use 1inch quote to USDC as proxy
    best = None
    best_usdc_out = 0
    for (name, addr, bal) in found:
        try:
            quote = get_1inch_quote(chain, addr, usdc_addr, bal)
            usdc_out = int(quote["toTokenAmount"])
            usdc_dec_out = amount_to_decimal(usdc_out, get_token_decimals(w3, usdc_addr))
            print(f"Quote {name} -> USDC: {usdc_dec_out}")
            if usdc_out > best_usdc_out:
                best_usdc_out = usdc_out
                best = (name, addr, bal, usdc_out)
        except Exception as e:
            print("Quote error for", name, e)

    if not best:
        print("No viable swap quote found")
        return False

    name, addr, bal, usdc_out = best
    print(f"Best swap candidate: {name}, amount {amount_to_decimal(bal, get_token_decimals(w3, addr))}")

    try:
        swap_result = swap_token_to_usdc_and_deposit(chain, account, addr, bal)
        return swap_result
    except Exception as e:
        print("Swap+deposit failed:", e)
        return False


if __name__ == "__main__":
    # Provide the account address (derived from private key)
    acct = Account.from_key(PRIVATE_KEY)
    account_address = acct.address
    print("Running auto-swap deposit. Account:", account_address, "DRY_RUN=", DRY_RUN)

    # Optionally override supported chains with env var
    env_chains = os.environ.get("ALLOWED_CHAINS")
    if env_chains:
        chains = [c.strip() for c in env_chains.split(",") if c.strip()]
    else:
        chains = SUPPORTED_CHAINS

    for ch in chains:
        try:
            success = process_chain(ch, account_address)
            print(f"Chain {ch} processed: success={success}")
        except Exception as e:
            print(f"Error processing {ch}: {e}")
