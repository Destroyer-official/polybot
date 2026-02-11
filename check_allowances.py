#!/usr/bin/env python3
"""Check token allowances"""
import os
from py_clob_client.client import ClobClient
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER_ADDRESS = "0x93e65c1419AB8147cbd16d440Bb7FC178b3b2F35"

print("Checking allowances...")
client = ClobClient(
    "https://clob.polymarket.com",
    key=PRIVATE_KEY,
    chain_id=137,
    signature_type=2,
    funder=FUNDER_ADDRESS
)

creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)

try:
    allowances = client.get_allowances()
    print(f"✅ Allowances: {allowances}")
except Exception as e:
    print(f"❌ Error: {e}")
