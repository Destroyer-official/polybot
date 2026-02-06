#!/usr/bin/env python3
"""
bot_debug.py — debug mode with hardened AI safety check (YES/NO strict)
"""

import os
import time
import json
import logging
import re
import random
from logging.handlers import RotatingFileHandler
from datetime import datetime

from web3 import Web3
from openai import OpenAI

# py-clob imports (may raise if not installed)
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

# Import new production-ready config system
from config.config import load_config
import rust_core

# Load configuration
config = load_config()

# -------------------------
# basic env & flags
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"
AI_CHECK_INTERVAL = int(os.getenv("AI_CHECK_INTERVAL", "30"))
AI_MAX_ATTEMPTS = int(os.getenv("AI_MAX_ATTEMPTS", "2"))
FORCE_ON_AI_FAILURE = os.getenv("FORCE_TRADE_ON_AI_FAILURE", "0") == "1"

LOG_PATH = os.getenv("POLYBOT_LOG", "/home/ubuntu/polybot/logs/polybot.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

# -------------------------
# logging
logger = logging.getLogger("polybot")
logger.setLevel(logging.DEBUG)
fh = RotatingFileHandler(LOG_PATH, maxBytes=10_000_000, backupCount=5)
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(ch)

logger.info("=== Polybot (hardened AI check) starting ===")
logger.info(f"DRY_RUN={DRY_RUN} AI_CHECK_INTERVAL={AI_CHECK_INTERVAL}s AI_MAX_ATTEMPTS={AI_MAX_ATTEMPTS} FORCE_ON_AI_FAILURE={FORCE_ON_AI_FAILURE}")

# -------------------------
# web3 & clients
from web3 import Web3
web3 = Web3(Web3.HTTPProvider(config.polygon_rpc_url))
account = web3.eth.account.from_key(config.private_key)
ADDRESS = account.address

# Clob client (if available)
try:
    # Detect wallet type for proper signature_type
    from src.wallet_type_detector import WalletTypeDetector
    detector = WalletTypeDetector(web3)
    wallet_type, signature_type, funder_address = detector.detect_wallet_type(ADDRESS)
    logger.info(f"Wallet type: {wallet_type}, Signature type: {signature_type}")
    
    client = ClobClient(
        host=config.polymarket_api_url,
        key=config.private_key,
        chain_id=config.chain_id,
        signature_type=signature_type,
        funder=funder_address
    )
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    logger.info("Polymarket CLOB client initialized.")
except Exception:
    logger.exception("Failed to initialize ClobClient; continuing but market scanning will fail.")
    client = None

# AI client
ai_client = None
if config.nvidia_api_key:
    ai_client = OpenAI(
        base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        api_key=config.nvidia_api_key
    )
    logger.info("AI client initialized")
else:
    logger.warning("No NVIDIA API key - AI safety checks disabled")

# BUY constant loader (robust)
try:
    from py_clob_client.order_builder.constants import BUY
    logger.info("BUY loaded from py_clob_client.order_builder.constants.BUY")
except Exception:
    try:
        from py_clob_client.constants import BUY
        logger.info("BUY loaded from py_clob_client.constants.BUY")
    except Exception:
        BUY = "BUY"
        logger.warning("BUY constant fallback -> using string 'BUY'")

# -------------------------
# ABIs
ERC20_ABI = [
    {"constant": True, "inputs":[{"name":"_owner","type":"address"}], "name":"balanceOf", "outputs":[{"name":"balance","type":"uint256"}], "type":"function"},
    {"constant": False, "inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}], "name":"transfer", "outputs":[{"name":"","type":"bool"}], "type":"function"}
]
MERGE_ABI = '[{"constant":false,"inputs":[{"name":"parentCollectionId","type":"bytes32"},{"name":"conditionId","type":"bytes32"},{"name":"partition","type":"uint256[]"},{"name":"amount","type":"uint256"}],"name":"mergePositions","outputs":[],"payable":false,"stateMutability":"nonpayable","type":"function"}]'

# -------------------------
# simple helpers
def get_eth_balance():
    try:
        return web3.eth.get_balance(ADDRESS) / 1e18
    except Exception:
        logger.exception("get_eth_balance failed")
        return 0.0

def get_erc20_balance(token_addr, decimals=6):
    try:
        tk = Web3.to_checksum_address(token_addr)
        c = web3.eth.contract(address=tk, abi=ERC20_ABI)
        raw = c.functions.balanceOf(ADDRESS).call()
        return raw / (10 ** decimals)
    except Exception:
        logger.exception("get_erc20_balance error")
        return 0.0

def get_gas_price():
    try:
        return web3.eth.gas_price
    except Exception:
        logger.exception("get_gas_price error")
        return 0

# -------------------------
# Robust multilingual YES/NO parser
YES_NO_RE = re.compile(
    r"\b(yes|y|no|n|oui|non|si|sí|si|ja|nein|hai|いいえ|はい|iie|nie)\b",
    flags=re.IGNORECASE
)

def parse_yes_no(text):
    if not text:
        return None
    t = text.strip()
    # Direct common single answers
    if t.upper() in ("YES", "Y", "NO", "N"):
        return True if t.upper().startswith("Y") else False
    # Search tokens
    m = YES_NO_RE.search(t)
    if not m:
        return None
    token = m.group(0).lower()
    # group tokens that mean "yes"
    yes_tokens = {"yes","y","oui","si","sí","ja","hai","はい"}
    if token in yes_tokens:
        return True
    no_tokens = {"no","n","non","nein","iie","いいえ","nie"}
    if token in no_tokens:
        return False
    return None

# -------------------------
# Hardened AI safety check
_last_ai_time = 0.0
_cached_ai_result = True

def _ask_ai_once(prompt_messages, params):
    """
    Single low-level call to AI. Returns raw text or raises.
    """
    # Use deterministic params if provided
    completion = ai_client.chat.completions.create(**params, messages=prompt_messages)
    # read response robustly
    raw = ""
    try:
        raw = completion.choices[0].message.content.strip()
    except Exception:
        raw = str(completion).strip()
    return raw

def check_market_safety():
    """
    1) Ask AI (strict YES/NO).
    2) If AI says YES -> True.
    3) If AI says NO or ambiguous:
          - If FORCE_TRADE_ON_AI_FAILURE=1 -> True (override)
          - Else if AI_ALLOW_FALLBACK=1 -> run local_heuristic(); if True -> allow, else -> False
          - Else -> False
    """
    global _last_ai_time, _cached_ai_result

    now = time.time()
    if now - _last_ai_time < AI_CHECK_INTERVAL:
        return _cached_ai_result

    # If no AI client, skip AI check
    if not ai_client:
        logger.debug("No AI client - skipping AI safety check")
        _last_ai_time = time.time()
        _cached_ai_result = True
        return True

    # 1) Run the hardened AI check (reuse existing logic)
    ai_safe = False
    try:
        # use the same strict prompts you already have (attempts, parse_yes_no etc.)
        # Here we call the existing low-level attempt logic (if you implemented earlier)
        # If your file contains _ask_ai_once() and parse_yes_no(), we use them:
        raw = None
        for attempt in range(1, AI_MAX_ATTEMPTS + 1):
            try:
                params = dict(model="stockmark/stockmark-2-100b-instruct",
                              temperature=0.0, top_p=1.0,
                              max_tokens=1 if attempt==1 else 3,
                              stop=["\n"])
                messages = [
                    {"role": "system", "content": "Reply with exactly ONE token: YES or NO. Nothing else."},
                    {"role": "user", "content": "Is the crypto market experiencing a flash crash or extreme volatility right now? Reply ONLY YES or NO."}
                ]
                comp = ai_client.chat.completions.create(**params, messages=messages)
                try:
                    raw = comp.choices[0].message.content.strip()
                except Exception:
                    raw = str(comp).strip()
                logger.debug("AI raw (attempt %d): %s", attempt, raw)
                parsed = parse_yes_no(raw)  # your earlier multilingual parser
                if parsed is True:
                    ai_safe = True
                    break
                if parsed is False:
                    ai_safe = False
                    break
            except Exception:
                logger.exception("AI call error; retrying")
                time.sleep(0.5 + 0.2 * random.random())
    except Exception:
        logger.exception("AI outer failure (treat as not safe)")
        ai_safe = False

    _last_ai_time = time.time()
    _cached_ai_result = ai_safe

    if ai_safe:
        logger.info("AI: SAFE -> trading allowed")
        return True

    # AI returned NO or ambiguous
    logger.warning("AI indicates NOT SAFE. Evaluating fallback heuristic (AI says NO).")

    # Force override environment variable
    if os.getenv("FORCE_TRADE_ON_AI_FAILURE", "0") == "1":
        logger.warning("FORCE_TRADE_ON_AI_FAILURE=1 -> overriding AI and allowing trading (DANGEROUS).")
        _cached_ai_result = True
        return True

    # Allow fallback heuristic? (default enabled)
    if os.getenv("AI_ALLOW_FALLBACK", "1") != "1":
        logger.info("AI fallback disabled (AI_ALLOW_FALLBACK != 1). Treating as NOT SAFE.")
        return False

    # --------------------------
    # Local heuristic: funds/gas/pending checks
    try:
        eth_bal = get_eth_balance()  # returns MATIC/ETH in native token
        usdc_bal = get_erc20_balance(config.usdc_address, 6)
        gas_gwei = (web3.eth.gas_price or 0) / 1e9
        pending_nonce = web3.eth.get_transaction_count(ADDRESS, "pending")
        latest_nonce = web3.eth.get_transaction_count(ADDRESS, "latest")
        pending_txs = max(0, pending_nonce - latest_nonce)

        # thresholds (configurable by env)
        MIN_MATIC_TH = float(os.getenv("MIN_MATIC_THRESHOLD", "0.1"))
        MIN_USDC_TH = float(os.getenv("MIN_USDC_THRESHOLD", str(config.min_balance)))
        GAS_MAX_GWEI = float(os.getenv("GAS_MAX_GWEI", str(config.max_gas_price_gwei)))

        logger.info("Heuristic check: MATIC=%.4f (need>=%.4f) USDC=%.4f (need>=%.4f) gas_gwei=%.2f (max=%.1f) pending_txs=%d",
                    eth_bal, MIN_MATIC_TH, usdc_bal, MIN_USDC_TH, gas_gwei, GAS_MAX_GWEI, pending_txs)

        # Decision logic: require gas + funds + moderate gas price + low pending txs
        if eth_bal >= MIN_MATIC_TH and usdc_bal >= MIN_USDC_TH and gas_gwei <= GAS_MAX_GWEI and pending_txs <= int(os.getenv("MAX_PENDING_TX", "5")):
            logger.warning("Fallback heuristic PASSED -> allowing trading (BUT AI said NO).")
            _cached_ai_result = True
            return True
        else:
            logger.info("Fallback heuristic FAILED -> not safe to trade.")
            return False

    except Exception:
        logger.exception("Fallback heuristic errored -> not safe")
        return False
# -------------------------
# Order helpers (safe)
def safe_post_order(price, size, side, token_id):
    logger.info("Posting order: token=%s price=%s size=%s side=%s DRY_RUN=%s", token_id, price, size, side, DRY_RUN)
    if DRY_RUN:
        return {"ok": True, "simulated": True}
    try:
        oa = OrderArgs(price=price, size=size, side=side, token_id=token_id, order_type=OrderType.FOK)
        res = client.create_and_post_order(oa)
        logger.debug("create_and_post_order response: %s", res)
        return {"ok": True, "res": res}
    except Exception:
        logger.exception("Order post failed")
        return {"ok": False}


def merge_positions(condition_id):
    logger.info("Merging positions for %s", condition_id)
    if DRY_RUN or config.dry_run:
        logger.info("DRY_RUN: skipping merge tx send")
        return True
    try:
        c = web3.eth.contract(address=config.conditional_token_address, abi=MERGE_ABI)
        amount_wei = int(float(config.stake_amount) * (10 ** 6))
        tx = c.functions.mergePositions("0x" + "0" * 64, condition_id, [1, 2], amount_wei).build_transaction({
            "from": ADDRESS,
            "nonce": web3.eth.get_transaction_count(ADDRESS),
            "gasPrice": web3.eth.gas_price
        })
        if "gas" not in tx:
            # optional estimate
            try:
                tx["gas"] = int(web3.eth.estimate_gas(tx) * 1.2)
            except Exception:
                pass
        signed = web3.eth.account.sign_transaction(tx, config.private_key)
        txh = web3.eth.send_raw_transaction(signed.rawTransaction)
        logger.info("Merge tx sent: %s", txh.hex())
        return True
    except Exception:
        logger.exception("merge_positions failed")
        return False

def withdraw_profits():
    logger.info("Checking withdrawable profits (DRY_RUN=%s)", DRY_RUN or config.dry_run)
    try:
        c = web3.eth.contract(address=config.usdc_address, abi=ERC20_ABI)
        raw = c.functions.balanceOf(ADDRESS).call()
        balance = raw / (10 ** 6)
        logger.info("USDC balance: %s", balance)
        if balance > float(config.withdraw_limit):
            amount_to_send = balance - float(config.target_balance)
            # Note: config doesn't have SAFE_WALLET, so we'll skip auto-withdraw
            logger.info("Would withdraw %s USDC (but no SAFE_WALLET configured)", amount_to_send)
            if DRY_RUN or config.dry_run:
                logger.info("DRY_RUN: not sending withdraw tx")
                return False
            # Skip actual withdrawal since we don't have a safe wallet configured
            logger.warning("Auto-withdrawal disabled - no SAFE_WALLET in config")
            return False
        return False
    except Exception:
        logger.exception("withdraw_profits error")
        return False

# -------------------------
# heartbeat
_last_usdc = None

def heartbeat(markets_scanned):
    global _last_usdc
    try:
        eth_bal = get_eth_balance()
        usdc_bal = get_erc20_balance(config.usdc_address, 6)
        gp = get_gas_price() / 1e9 if get_gas_price() else None
        pending_nonce = web3.eth.get_transaction_count(ADDRESS, "pending")
        latest_nonce = web3.eth.get_transaction_count(ADDRESS, "latest")
        pending_txs = pending_nonce - latest_nonce
        deposit = False
        if _last_usdc is None:
            _last_usdc = usdc_bal
        else:
            if usdc_bal > _last_usdc:
                deposit = True
                logger.info("DEPOSIT detected: +%s USDC", usdc_bal - _last_usdc)
            _last_usdc = usdc_bal

        logger.info("HEARTBEAT scanned=%s ETH=%.6f USDC=%.6f GAS(gwei)=%s pendingTxs=%s", markets_scanned, eth_bal, usdc_bal, gp, pending_txs)
        return {"eth": eth_bal, "usdc": usdc_bal, "gas_gwei": gp, "pending": pending_txs, "deposit": deposit}
    except Exception:
        logger.exception("heartbeat error")
        return {}

# -------------------------
# main loop
def main():
    logger.info("Bot started main loop")
    last_withdraw = 0
    last_hb = time.time()
    markets_scanned = 0
    consecutive_errors = 0

    while True:
        try:
            if not check_market_safety():
                logger.warning("AI flagged risk — sleeping 60s")
                time.sleep(60)
                continue

            # scan markets
            if not client:
                logger.error("No CLOB client; sleeping 5s")
                time.sleep(5)
                continue

            markets = client.get_markets(next_cursor="")
            mlist = markets.get("data", [])
            markets_scanned += len(mlist)

            for m in mlist:
                try:
                    if m.get("closed") or not m.get("active"):
                        continue
                    if "15 minute" not in m.get("question", "").lower():
                        continue
                    # rust arb scanner
                    mj = json.dumps(m)
                    found, yes_p, no_p = rust_core.find_arb(mj, float(config.min_profit_threshold))
                    if found:
                        logger.info("ARB found: %s YES=%s NO=%s", m.get("question"), yes_p, no_p)
                        r1 = safe_post_order(yes_p, float(config.stake_amount), BUY, m['tokens'][0]['token_id'])
                        r2 = safe_post_order(no_p, float(config.stake_amount), BUY, m['tokens'][1]['token_id'])
                        if r1.get("ok") and r2.get("ok"):
                            logger.info("Orders posted ok -> merging")
                            merge_positions(m['condition_id'])
                        else:
                            logger.warning("Orders not both ok: r1=%s r2=%s", r1, r2)
                except Exception:
                    logger.exception("market item handling failed; continuing")

            # withdrawal check every 10 minutes
            if time.time() - last_withdraw > 600:
                withdraw_profits()
                last_withdraw = time.time()

            # heartbeat every 30s
            if time.time() - last_hb > 30:
                heartbeat(markets_scanned)
                markets_scanned = 0
                last_hb = time.time()

            consecutive_errors = 0
            time.sleep(0.1)
        except Exception:
            consecutive_errors += 1
            logger.exception("main loop exception")
            if consecutive_errors > 20:
                logger.critical("too many consecutive errors -> aborting")
                return
            time.sleep(min(30, 1.5 ** consecutive_errors))

if __name__ == "__main__":
    main()
