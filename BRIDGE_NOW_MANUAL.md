# BRIDGE USDC NOW - Manual Method (Fastest)

## Steps to Bridge via Polymarket:

1. **Go to Polymarket:**
   - Open: https://polymarket.com
   - Click: **Deposit** (top right corner)

2. **Connect Your Wallet:**
   - Click: **Connect Wallet**
   - Select: **MetaMask**
   - Approve connection

3. **Select USDC from Ethereum:**
   - Source: **Ethereum**
   - Token: **USDC**
   - Amount: **$4.63** (or whatever you want)

4. **Confirm Bridge:**
   - Click: **Continue**
   - Polymarket will show you the bridge details
   - **Polymarket pays the gas fees** (you don't need ETH!)
   - Confirm in MetaMask

5. **Wait for Bridge:**
   - Takes 5-15 minutes
   - You'll see "Pending" on Polymarket
   - Check progress: https://polygonscan.com/address/0x1A821E4488732156cC9B3580efe3984F9B6C0116

6. **Run the Bot:**
   ```bash
   python test_autonomous_bot.py
   ```

**This is the EASIEST method - Polymarket handles everything!**
