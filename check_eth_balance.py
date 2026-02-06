from web3 import Web3

w3 = Web3(Web3.HTTPProvider('https://eth.llamarpc.com'))
addr = '0x1A821E4488732156cC9B3580efe3984F9B6C0116'
bal = w3.eth.get_balance(addr)
eth_balance = bal / 10**18

print("=" * 80)
print("ETH BALANCE CHECK")
print("=" * 80)
print(f"Wallet: {addr}")
print(f"ETH Balance: {eth_balance:.6f} ETH")
print(f"USD Value: ${eth_balance * 2500:.2f}")
print()
print("GAS REQUIREMENTS:")
print(f"  Approval transaction: ~0.001 ETH (~$2.50)")
print(f"  Bridge transaction: ~0.001 ETH (~$2.50)")
print(f"  Total needed: 0.002 ETH (~$5.00)")
print()
print(f"YOU HAVE: {eth_balance:.6f} ETH (${eth_balance * 2500:.2f})")
print(f"YOU NEED: 0.002000 ETH ($5.00)")
print()
if eth_balance >= 0.002:
    print("✓ ENOUGH ETH - Bot can bridge automatically!")
else:
    missing = 0.002 - eth_balance
    print(f"✗ NOT ENOUGH ETH - Missing {missing:.6f} ETH (${missing * 2500:.2f})")
print("=" * 80)
