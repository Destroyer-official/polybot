import os
from dotenv import load_dotenv

# Load the secret .env file
load_dotenv()

# --- AUTHENTICATION ---
# The Bot's Wallet (Hot Wallet) - It needs MATIC for gas!
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# The NVIDIA API Key (For Intelligence)
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

# --- WITHDRAWAL SETTINGS ---
# Where to send the profit (Your Hardware Wallet / Binance / Metamask)
SAFE_WALLET = os.getenv("SAFE_WALLET")

# How much money to ALWAYS keep in the bot for trading
KEEP_BALANCE = 200.0

# When to withdraw (e.g., if balance hits $500, withdraw $300)
WITHDRAW_THRESHOLD = 500.0

# --- TRADING SETTINGS ---
# How much to bet per trade (in USDC)
STAKE_AMOUNT = 5.0

# Minimum profit margin to trigger an Arb (0.01 = 1%)
MIN_PROFIT_MARGIN = 0.01

# --- BLOCKCHAIN CONSTANTS (POLYGON) ---
# Polygon RPC URL (Connects bot to blockchain)
RPC_URL = "https://polygon-rpc.com"

# Contract Addresses (Do not change these for Polymarket)
# CTF Exchange (Where we buy/sell)
CTF_EXCHANGE_ADDR = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

# Conditional Token Framework (Where we MERGE tokens for profit)
CONDITIONAL_TOKEN_ADDR = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# USDC.e Token (The money)
USDC_TOKEN_ADDR = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
