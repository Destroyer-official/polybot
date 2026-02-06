from web3 import Web3
import time

# Use your Alchemy RPC
w3 = Web3(Web3.HTTPProvider('https://polygon-mainnet.g.alchemy.com/v2/Htq4bYCsLyC0tngoi7z64'))

# Transaction hash from the bot
tx_hash = '0x7303abe6e4f94f16907c8e3564b20a10f2252fee5fbd06ecb59d7634efd0ebf7'

print("=" * 80)
print("CHECKING TRANSACTION STATUS")
print("=" * 80)
print(f"Transaction: {tx_hash}")
print()

try:
    # Try to get transaction receipt
    receipt = w3.eth.get_transaction_receipt(tx_hash)
    
    if receipt:
        print("✓ TRANSACTION CONFIRMED!")
        print(f"Block: {receipt['blockNumber']}")
        print(f"Gas Used: {receipt['gasUsed']}")
        print(f"Status: {'SUCCESS' if receipt['status'] == 1 else 'FAILED'}")
    else:
        print("⏳ Transaction pending...")
        
except Exception as e:
    print(f"⏳ Transaction still pending or not found")
    print(f"This is normal - transactions take 10-30 seconds")
    
print("=" * 80)
