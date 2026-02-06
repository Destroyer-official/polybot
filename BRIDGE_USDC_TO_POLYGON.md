# Bridge USDC from Ethereum to Polygon

## Current Status
- **Your USDC**: $4.63 on Ethereum mainnet
- **Bot needs**: USDC on Polygon network
- **Your wallet**: 0x1A821E4488732156cC9B3580efe3984F9B6C0116

## Option 1: MetaMask Bridge (RECOMMENDED - Easiest)

1. Open MetaMask
2. Click "Bridge" button at the top
3. Select:
   - From: Ethereum
   - To: Polygon
   - Token: USDC
   - Amount: $4.63 (or leave ~$0.50 for gas)
4. Click "Get Quotes"
5. Select best quote (usually takes 5-15 minutes)
6. Confirm transaction
7. Wait for bridge to complete

**Estimated Cost**: ~$2-5 in gas fees on Ethereum
**Time**: 5-15 minutes

## Option 2: Polygon Bridge (Official)

1. Go to: https://wallet.polygon.technology/polygon/bridge
2. Connect your wallet (0x1A821E4488732156cC9B3580efe3984F9B6C0116)
3. Select:
   - From: Ethereum
   - To: Polygon PoS
   - Token: USDC
   - Amount: $4.63
4. Click "Transfer"
5. Confirm in MetaMask
6. Wait for confirmation (5-15 minutes)

**Estimated Cost**: ~$2-5 in gas fees
**Time**: 5-15 minutes

## Option 3: Exchange Withdrawal (CHEAPEST)

If you have a Coinbase/Binance account:

1. Deposit USDC to exchange
2. Withdraw USDC
3. **IMPORTANT**: Select "Polygon" network (NOT Ethereum!)
4. Enter your wallet: 0x1A821E4488732156cC9B3580efe3984F9B6C0116
5. Withdraw

**Estimated Cost**: $0-1 (exchange fees)
**Time**: 10-30 minutes

## After Bridging

Once USDC is on Polygon, run:

```bash
python check_usdc_balance.py
```

You should see:
```
USDC.e (Bridged) - 0x2791...4174
  Balance: $4.63
```

Then start the bot:
```bash
python src/main_orchestrator.py
```

## Need Help?

If you get stuck, the bot can wait. Just bridge the USDC and we'll continue testing!
