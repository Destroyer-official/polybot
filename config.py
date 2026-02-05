import os
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# -------------------------
# REQUIRED SECRETS
# -------------------------

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
SAFE_WALLET = os.getenv("SAFE_WALLET")

if not PRIVATE_KEY:
    raise ValueError("❌ PRIVATE_KEY missing from .env")

if not SAFE_WALLET:
    raise ValueError("❌ SAFE_WALLET missing from .env")

# -------------------------
# SETTINGS
# -------------------------

STAKE_AMOUNT = float(os.getenv("STAKE_AMOUNT", 10.0))
MIN_PROFIT = float(os.getenv("MIN_PROFIT", 0.01))

WITHDRAW_LIMIT = float(os.getenv("WITHDRAW_LIMIT", 500.0))
KEEP_AMOUNT = float(os.getenv("KEEP_AMOUNT", 200.0))

USDC_DECIMALS = 6
MIN_MATIC = 0.1

# -------------------------
# BLOCKCHAIN
# -------------------------

RPC_URL = os.getenv("RPC_URL", "https://polygon-rpc.com")
CHAIN_ID = int(os.getenv("CHAIN_ID", 137))

web3 = Web3(Web3.HTTPProvider(RPC_URL))

# -------------------------
# CONTRACTS
# -------------------------

USDC_TOKEN = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKEN = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

POLYMARKET_CLOB = "https://clob.polymarket.com"

# -------------------------
# CHECKSUM ENFORCEMENT
# -------------------------

def ck(addr):
    try:
        return Web3.to_checksum_address(addr)
    except Exception:
        raise ValueError(f"Invalid address format: {addr}")

SAFE_WALLET = ck(SAFE_WALLET)
USDC_TOKEN = ck(USDC_TOKEN)
CONDITIONAL_TOKEN = ck(CONDITIONAL_TOKEN)
CTF_EXCHANGE = ck(CTF_EXCHANGE)

# -------------------------
# DERIVED BOT ADDRESS
# -------------------------

ACCOUNT = web3.eth.account.from_key(PRIVATE_KEY)
BOT_ADDRESS = Web3.to_checksum_address(ACCOUNT.address)
