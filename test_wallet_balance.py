from web3 import Web3
from decimal import Decimal

# Connect to Polygon
w = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64'))

wallet = '0x1A821E4488732156cC9B3580efe3984F9B6C0116'
usdc_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'

# USDC ABI (minimal)
abi = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

# Get USDC balance
contract = w.eth.contract(address=w.to_checksum_address(usdc_address), abi=abi)
balance = contract.functions.balanceOf(w.to_checksum_address(wallet)).call()
decimals = contract.functions.decimals().call()
balance_usdc = Decimal(balance) / Decimal(10**decimals)

print(f"✅ RPC Connected: {w.is_connected()}")
print(f"✅ Chain ID: {w.eth.chain_id}")
print(f"✅ Latest Block: {w.eth.block_number}")
print(f"💰 Wallet: {wallet}")
print(f"💵 USDC Balance: ${balance_usdc}")
