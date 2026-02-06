# 🔑 Complete .env File Setup Guide

**All APIs and Keys You Need for the Polymarket Arbitrage Bot**

---

## 📋 Quick Overview

### Required (Must Have)
1. ✅ **Private Key** - Your Ethereum wallet
2. ✅ **Wallet Address** - Your wallet address
3. ✅ **Polygon RPC URL** - Blockchain connection

### Recommended (Should Have)
4. ⭐ **Backup RPC URLs** - For failover
5. ⭐ **NVIDIA API Key** - For AI safety checks

### Optional (Nice to Have)
6. ⚪ **Kalshi API Key** - For cross-platform arbitrage
7. ⚪ **1inch API Key** - For cross-chain deposits
8. ⚪ **AWS SNS Topic** - For alerts

---

## 🔐 1. PRIVATE KEY (Required)

### What It Is
Your Ethereum wallet's private key - used to sign transactions on Polygon.

### How to Get It

#### Option A: From MetaMask
```
1. Open MetaMask
2. Click the 3 dots menu
3. Select "Account Details"
4. Click "Show Private Key"
5. Enter your password
6. Copy the private key (starts with 0x)
```

#### Option B: From Other Wallets
- **Trust Wallet:** Settings → Wallets → [Your Wallet] → Show Private Key
- **Coinbase Wallet:** Settings → Security → Show Private Key
- **Hardware Wallet:** Export from device (not recommended for bot)

### Format
```bash
PRIVATE_KEY=0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
```

### ⚠️ Security Warning
- **NEVER share your private key**
- **NEVER commit it to git**
- **Use a dedicated wallet for the bot** (not your main wallet)
- **Start with small amounts** ($100-$500)

---

## 📍 2. WALLET ADDRESS (Required)

### What It Is
Your Ethereum wallet address (public address).

### How to Get It

#### From MetaMask
```
1. Open MetaMask
2. Click on your account name at the top
3. Your address is shown (starts with 0x)
4. Click to copy
```

#### From Other Wallets
- Look for "Receive" or "Your Address"
- It's the public address you share to receive funds

### Format
```bash
WALLET_ADDRESS=0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
```

### Verification
The wallet address MUST match the private key. The bot will verify this on startup.

---

## 🌐 3. POLYGON RPC URL (Required)

### What It Is
A connection endpoint to the Polygon blockchain. This is how the bot reads data and sends transactions.

### How to Get It

#### Option A: Alchemy (Recommended - Free)
```
1. Go to https://www.alchemy.com/
2. Sign up for free account
3. Click "Create App"
4. Select:
   - Chain: Polygon
   - Network: Polygon Mainnet
5. Click "View Key"
6. Copy the HTTPS URL
```

**Free Tier:**
- 300M compute units/month
- ~3M requests/month
- More than enough for the bot

**URL Format:**
```bash
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY
```

#### Option B: Infura (Alternative - Free)
```
1. Go to https://infura.io/
2. Sign up for free account
3. Create new project
4. Select Polygon Mainnet
5. Copy the HTTPS endpoint
```

**URL Format:**
```bash
POLYGON_RPC_URL=https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID
```

#### Option C: Public RPC (Free but slower)
```bash
POLYGON_RPC_URL=https://polygon-rpc.com
```

**Note:** Public RPCs are:
- ✅ Free
- ❌ Slower
- ❌ Less reliable
- ❌ Rate limited

**Recommendation:** Use Alchemy or Infura for better performance.

---

## 🔄 4. BACKUP RPC URLS (Recommended)

### What It Is
Backup RPC endpoints for automatic failover if primary fails.

### How to Get It
Use a combination of providers:

```bash
BACKUP_RPC_URLS=https://rpc-mainnet.matic.network,https://polygon-rpc.com,https://polygon-mainnet.infura.io/v3/YOUR_KEY
```

### Recommended Setup
```bash
# Primary: Alchemy (fast, reliable)
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY

# Backups: Mix of providers
BACKUP_RPC_URLS=https://polygon-mainnet.infura.io/v3/YOUR_KEY,https://rpc-mainnet.matic.network,https://polygon-rpc.com
```

---

## 🤖 5. NVIDIA API KEY (Recommended)

### What It Is
API key for NVIDIA's AI service - used for AI safety checks on markets.

### How to Get It

```
1. Go to https://build.nvidia.com/
2. Sign up for NVIDIA account
3. Navigate to API section
4. Generate API key
5. Copy the key
```

**Free Tier:**
- Limited requests per month
- Sufficient for bot usage

### Format
```bash
NVIDIA_API_KEY=nvapi-1234567890abcdef1234567890abcdef
```

### What It Does
- Validates market questions for clarity
- Detects ambiguous or risky markets
- Provides multilingual safety checks
- Falls back to heuristics if unavailable

### If You Don't Have It
The bot will use fallback heuristics:
- Balance > $10
- Gas < 800 gwei
- Pending TX < 5
- Keyword filtering for ambiguous markets

---

## 📊 6. KALSHI API KEY (Optional)

### What It Is
API key for Kalshi prediction market - enables cross-platform arbitrage.

### How to Get It

```
1. Go to https://kalshi.com/
2. Sign up for account
3. Complete KYC verification
4. Go to API settings
5. Generate API key
6. Copy key and secret
```

### Format
```bash
KALSHI_API_KEY=your_kalshi_api_key_here
KALSHI_API_SECRET=your_kalshi_api_secret_here
```

### What It Enables
- Cross-platform arbitrage between Polymarket and Kalshi
- Additional profit opportunities
- Diversified trading strategies

### If You Don't Have It
The bot will only use internal arbitrage (still profitable!).

---

## 🔗 7. 1INCH API KEY (Optional)

### What It Is
API key for 1inch DEX aggregator - enables cross-chain deposits.

### How to Get It

```
1. Go to https://portal.1inch.dev/
2. Sign up for account
3. Create new API key
4. Copy the key
```

**Free Tier:**
- 1 request per second
- Sufficient for occasional deposits

### Format
```bash
ONEINCH_API_KEY=your_1inch_api_key_here
```

### What It Enables
- Deposit from Ethereum, Arbitrum, Optimism
- Automatic token swaps to USDC
- Cross-chain bridging to Polygon

### If You Don't Have It
You'll need to manually deposit USDC to Polygon.

---

## 📧 8. AWS SNS TOPIC (Optional)

### What It Is
AWS Simple Notification Service topic ARN - for email/SMS alerts.

### How to Get It

```
1. Log into AWS Console
2. Go to SNS (Simple Notification Service)
3. Create new topic
4. Create subscription (email or SMS)
5. Confirm subscription
6. Copy topic ARN
```

### Format
```bash
SNS_ALERT_TOPIC=arn:aws:sns:us-east-1:123456789012:polymarket-bot-alerts
```

### What It Enables
- Email alerts for critical issues
- SMS notifications (optional)
- Balance warnings
- Error notifications

### If You Don't Have It
Alerts will only be logged (no email/SMS).

---

## 📝 COMPLETE .env FILE TEMPLATE

### Minimal Configuration (Required Only)

```bash
# ============================================================================
# REQUIRED - Bot will not start without these
# ============================================================================

# Your Ethereum wallet private key
PRIVATE_KEY=0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef

# Your wallet address (must match private key)
WALLET_ADDRESS=0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb

# Polygon RPC URL (get from Alchemy or Infura)
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# CRITICAL: Start in DRY_RUN mode for testing!
DRY_RUN=true
```

### Recommended Configuration

```bash
# ============================================================================
# REQUIRED
# ============================================================================

PRIVATE_KEY=0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
WALLET_ADDRESS=0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# ============================================================================
# RECOMMENDED
# ============================================================================

# Backup RPC URLs (comma-separated, for failover)
BACKUP_RPC_URLS=https://polygon-mainnet.infura.io/v3/YOUR_KEY,https://rpc-mainnet.matic.network,https://polygon-rpc.com

# NVIDIA AI API (for safety checks)
NVIDIA_API_KEY=nvapi-1234567890abcdef1234567890abcdef

# ============================================================================
# OPERATIONAL SETTINGS
# ============================================================================

# DRY_RUN mode (MUST be true for first 24 hours!)
DRY_RUN=true

# Trading parameters
STAKE_AMOUNT=1.0
MIN_PROFIT_THRESHOLD=0.005
MAX_POSITION_SIZE=5.0
MIN_POSITION_SIZE=0.1

# Fund management
MIN_BALANCE=50.0
TARGET_BALANCE=100.0
WITHDRAW_LIMIT=500.0

# Risk management
MAX_PENDING_TX=5
MAX_GAS_PRICE_GWEI=800
CIRCUIT_BREAKER_THRESHOLD=10

# Monitoring
PROMETHEUS_PORT=9090
CLOUDWATCH_LOG_GROUP=/polymarket-arbitrage-bot

# Operational
SCAN_INTERVAL_SECONDS=2
HEARTBEAT_INTERVAL_SECONDS=60
```

### Full Configuration (All Options)

```bash
# ============================================================================
# REQUIRED CONFIGURATION
# ============================================================================

# Wallet Configuration
PRIVATE_KEY=0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
WALLET_ADDRESS=0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb

# RPC Configuration
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY
BACKUP_RPC_URLS=https://polygon-mainnet.infura.io/v3/YOUR_KEY,https://rpc-mainnet.matic.network

# ============================================================================
# API KEYS (Optional but Recommended)
# ============================================================================

# NVIDIA AI API (for AI safety checks)
NVIDIA_API_KEY=nvapi-1234567890abcdef1234567890abcdef

# Kalshi API (for cross-platform arbitrage)
KALSHI_API_KEY=your_kalshi_api_key_here
KALSHI_API_SECRET=your_kalshi_api_secret_here

# 1inch API (for cross-chain deposits)
ONEINCH_API_KEY=your_1inch_api_key_here

# ============================================================================
# CONTRACT ADDRESSES (Defaults are correct for Polygon mainnet)
# ============================================================================

USDC_ADDRESS=0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
CTF_EXCHANGE_ADDRESS=0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E
CONDITIONAL_TOKEN_ADDRESS=0x4D97DCd97eC945f40cF65F87097ACe5EA0476045

# ============================================================================
# TRADING PARAMETERS
# ============================================================================

# Position sizing
STAKE_AMOUNT=1.0
MIN_PROFIT_THRESHOLD=0.005
MAX_POSITION_SIZE=5.0
MIN_POSITION_SIZE=0.1

# Fund management
MIN_BALANCE=50.0
TARGET_BALANCE=100.0
WITHDRAW_LIMIT=500.0

# Risk management
MAX_PENDING_TX=5
MAX_GAS_PRICE_GWEI=800
CIRCUIT_BREAKER_THRESHOLD=10

# ============================================================================
# AWS CONFIGURATION (Optional)
# ============================================================================

# AWS Region
AWS_REGION=us-east-1

# Use AWS Secrets Manager (instead of .env)
USE_AWS_SECRETS=false
SECRET_NAME=polymarket-bot-credentials

# CloudWatch Logging
CLOUDWATCH_LOG_GROUP=/polymarket-arbitrage-bot

# SNS Alerts
SNS_ALERT_TOPIC=arn:aws:sns:us-east-1:123456789012:polymarket-bot-alerts

# ============================================================================
# MONITORING
# ============================================================================

PROMETHEUS_PORT=9090

# ============================================================================
# OPERATIONAL SETTINGS
# ============================================================================

# DRY_RUN mode (CRITICAL: Start with true!)
DRY_RUN=true

# Scanning
SCAN_INTERVAL_SECONDS=2
HEARTBEAT_INTERVAL_SECONDS=60

# Chain
CHAIN_ID=137
```

---

## 🚀 Quick Start Checklist

### Step 1: Get Required Keys
- [ ] Create/export wallet private key
- [ ] Copy wallet address
- [ ] Sign up for Alchemy and get RPC URL

### Step 2: Get Recommended Keys
- [ ] Sign up for NVIDIA AI and get API key
- [ ] Get backup RPC URLs from Infura

### Step 3: Create .env File
- [ ] Copy template above
- [ ] Fill in your keys
- [ ] Set DRY_RUN=true
- [ ] Save as `.env` in project root

### Step 4: Verify
- [ ] Check private key starts with 0x
- [ ] Check wallet address starts with 0x
- [ ] Test RPC URL with curl
- [ ] Ensure DRY_RUN=true

---

## 🧪 Testing Your Configuration

### Test RPC Connection
```bash
curl -X POST https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

**Expected Response:**
```json
{"jsonrpc":"2.0","id":1,"result":"0x31f5e0a"}
```

### Test Wallet Balance
```bash
# Check your wallet on Polygonscan
https://polygonscan.com/address/YOUR_WALLET_ADDRESS
```

### Verify .env File
```bash
# On Linux/Mac
cat .env | grep -v "^#" | grep -v "^$"

# On Windows
type .env | findstr /V "^#"
```

---

## ⚠️ Security Best Practices

### DO:
- ✅ Use a dedicated wallet for the bot
- ✅ Start with small amounts ($100-$500)
- ✅ Keep private key in .env file only
- ✅ Add .env to .gitignore
- ✅ Use AWS Secrets Manager in production
- ✅ Rotate keys periodically
- ✅ Monitor wallet activity

### DON'T:
- ❌ Commit .env to git
- ❌ Share private key with anyone
- ❌ Use your main wallet
- ❌ Store keys in code
- ❌ Use same key across multiple bots
- ❌ Disable DRY_RUN without testing

---

## 📊 Cost Breakdown

### Free Tier Limits

| Service | Free Tier | Cost After |
|---------|-----------|------------|
| Alchemy RPC | 300M compute units/month | $49/month for more |
| Infura RPC | 100k requests/day | $50/month for more |
| NVIDIA AI | Limited requests | Pay per request |
| Kalshi API | Free | Trading fees apply |
| 1inch API | 1 req/sec | $49/month for more |
| AWS SNS | 1,000 emails/month | $0.50 per 1,000 after |

**Total Monthly Cost (Free Tier):** $0

**Estimated Monthly Cost (Paid):** $50-$100 if you exceed free tiers

---

## 🎯 Summary

### Minimum to Start (Free)
```
1. Private Key (from your wallet)
2. Wallet Address (from your wallet)
3. Alchemy RPC URL (free tier)
4. DRY_RUN=true
```

### Recommended Setup (Free)
```
+ Backup RPC URLs (free)
+ NVIDIA API Key (free tier)
```

### Full Setup (Some Paid)
```
+ Kalshi API (optional)
+ 1inch API (optional)
+ AWS SNS (optional)
```

---

## 📞 Need Help?

### Getting Keys
- **Alchemy:** https://docs.alchemy.com/docs/alchemy-quickstart-guide
- **Infura:** https://docs.infura.io/getting-started
- **NVIDIA:** https://build.nvidia.com/docs
- **Kalshi:** https://trading-api.readme.io/reference/getting-started
- **1inch:** https://portal.1inch.dev/documentation

### Wallet Setup
- **MetaMask:** https://metamask.io/
- **Trust Wallet:** https://trustwallet.com/
- **Coinbase Wallet:** https://www.coinbase.com/wallet

---

**Ready to deploy?** Once you have your .env file configured, follow DEPLOYMENT_READY.md!
