# POLYMARKET SETUP - CORRECT METHOD

Based on official Polymarket documentation: https://docs.polymarket.com/quickstart/first-order

## Understanding Polymarket Trading Types:

### Type 1: EOA Wallet (What You're Using)
- **Signature Type**: `EOA` (0)
- **Funder Address**: Your wallet address
- **How it works**: 
  - Your wallet holds USDC and position tokens
  - You pay your own gas fees
  - Direct trading from your wallet

### Type 2: Polymarket.com Account (Magic Link/Google)
- **Signature Type**: `POLY_PROXY` (1)
- **Funder Address**: Your proxy wallet address
- **How it works**:
  - Polymarket creates a proxy wallet for you
  - You trade through Polymarket's interface
  - Polymarket manages gas

### Type 3: Polymarket.com Account (Browser Wallet)
- **Signature Type**: `GNOSIS_SAFE` (2)
- **Funder Address**: Your proxy wallet address
- **How it works**:
  - Uses Gnosis Safe multisig
  - More secure but more complex
  - Polymarket manages the safe

## Your Current Setup:

**Wallet Address:** `0x1A821E4488732156cC9B3580efe3984F9B6C0116`

**Trading Type:** EOA (Type 0)

**What This Means:**
- You trade directly from your wallet
- USDC must be in your wallet on Polygon
- You pay gas fees for each trade
- No proxy wallet needed

## How to Fund Your Bot:

### Option 1: Direct USDC Transfer (SIMPLEST)

**Send USDC to your wallet on Polygon:**
```
Address: 0x1A821E4488732156cC9B3580efe3984F9B6C0116
Network: Polygon
Token: USDC
Amount: $3.59 or more
```

**Steps:**
1. Open MetaMask
2. Switch to Polygon network
3. Click "Send"
4. Paste your address: `0x1A821E4488732156cC9B3580efe3984F9B6C0116`
5. Select USDC token
6. Enter amount: $3.59
7. Confirm

**Bot will detect balance immediately and start trading!**

---

### Option 2: Polymarket Website Deposit

**If you want to use Polymarket's interface:**

1. Go to: https://polymarket.com
2. Connect wallet: `0x1A821E4488732156cC9B3580efe3984F9B6C0116`
3. Click profile → "Deposit"
4. Enter $3.59
5. Select "Wallet" as source
6. Confirm

**This creates a proxy wallet and deposits there.**

**Note:** If you use this method, you'll need to update the bot to use POLY_PROXY signature type.

---

## Current Bot Configuration:

The bot is configured for **EOA trading** (Type 0):
- Signature Type: EOA
- Funder: Your wallet address
- USDC Location: Your wallet on Polygon

**This is the SIMPLEST setup!**

---

## Recommended: Use EOA Trading

**Why:**
- ✅ Simplest setup
- ✅ No proxy wallet needed
- ✅ Direct control of funds
- ✅ Bot already configured for this

**How:**
1. Send $3+ USDC to your wallet on Polygon
2. Bot detects balance automatically
3. Bot starts trading immediately

**Your Wallet:** `0x1A821E4488732156cC9B3580efe3984F9B6C0116`

---

## Summary:

**For EOA Trading (Current Setup):**
- Send USDC directly to: `0x1A821E4488732156cC9B3580efe3984F9B6C0116`
- Network: Polygon
- Amount: $3+ USDC
- Bot will trade automatically

**For Proxy Trading (Polymarket Website):**
- Deposit via Polymarket.com
- Creates proxy wallet
- Need to update bot configuration

**Recommendation:** Use EOA trading (send USDC directly to your wallet) - it's simpler and the bot is already configured for it!

---

## Where to Get USDC on Polygon:

### If You Have USDC on Ethereum:
- Bridge via: https://wallet.polygon.technology/
- Or use Polymarket deposit (bridges automatically)

### If You Have Other Tokens:
- Swap on Uniswap: https://app.uniswap.org/
- Or QuickSwap: https://quickswap.exchange/

### If You Need to Buy:
- Buy on exchange (Coinbase, Binance)
- Withdraw to Polygon network
- Send to your wallet

---

## After Funding:

**Bot will automatically:**
1. Detect USDC balance in your wallet
2. Start scanning 77 markets
3. Execute trades when profitable (5%+ profit)
4. Run 24/7 autonomously

**No configuration changes needed!**

Just send $3+ USDC to your wallet and the bot starts trading! 🚀
