#!/usr/bin/env python3
"""Check for 15-minute crypto markets."""

import requests
import json

url = "https://gamma-api.polymarket.com/markets"
params = {'closed': 'false', 'limit': 100}

response = requests.get(url, params=params, timeout=10)
markets = response.json()

if not isinstance(markets, list):
    markets = markets.get('data', [])

# Find 15-minute crypto markets
crypto_15min = []
for m in markets:
    question = m.get('question', '').lower()
    if '15' in question and ('btc' in question or 'eth' in question or 'bitcoin' in question or 'ethereum' in question):
        crypto_15min.append(m)

print(f"\n✅ Found {len(crypto_15min)} 15-minute crypto markets\n")

if crypto_15min:
    print("Active 15-minute markets:")
    for m in crypto_15min[:10]:
        question = m.get('question', '')
        print(f"  • {question[:80]}")
else:
    print("❌ No 15-minute crypto markets active right now")
    print("\nThis is normal - these markets:")
    print("  • Open and close every 15 minutes")
    print("  • Are only active during high trading hours")
    print("  • May not be available 24/7")
    print("\nThe bot will automatically detect when they appear!")
