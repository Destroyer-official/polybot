from web3 import Web3

# Polygon RPC
w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))
addr = '0x1A821E4488732156cC9B3580efe3984F9B6C0116'

# USDC on Polygon
usdc_polygon = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'

# USDC ABI
usdc_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'

# Check USDC balance
usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(usdc_polygon), abi=usdc_abi)
usdc_balance = usdc_contract.functions.balanceOf(addr).call()
usdc_balance_decimal = usdc_balance / 10**6  # USDC has 6 decimals

print("=" * 80)
print("POLYGON USDC BALANCE CHECK")
print("=" * 80)
print(f"Wallet: {addr}")
print(f"Network: Polygon")
print(f"USDC Balance: ${usdc_balance_decimal:.2f}")
print()
if usdc_balance_decimal > 0:
    print("✓ YOU HAVE USDC ON POLYGON!")
    print("✓ BOT CAN START TRADING NOW!")
else:
    print("✗ NO USDC ON POLYGON")
    print("✗ Need to bridge from Ethereum")
print("=" * 80)
