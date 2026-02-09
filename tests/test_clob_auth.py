import os
import asyncio
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

# Load env
load_dotenv()

async def main():
    print("Testing CLOB Authentication...")
    
    private_key = os.getenv("PRIVATE_KEY")
    host = "https://clob.polymarket.com"
    chain_id = 137 # Polygon
    
    # Check variable names from .env.example if needed
    # It seems we rely on PRIVATE_KEY to derive creds
    print(f"Private Key present: {bool(private_key)}")
    
    try:
        # Match main_orchestrator.py logic
        client = ClobClient(
            host,
            key=private_key,
            chain_id=chain_id,
            signature_type=0, # Try EOA (0) first, as 1 causes issues if not Gnosis 
            # Wait, main_orchestrator detects it. Let's try to detect or just use EOA (0) first?
            # If the user is using EOA, signature_type is 0?
            # Let's try explicit 0 for EOA first (no proxy)
            # signature_type=0
        )
        
        # Or better yet, just copy the logic effectively
        # But we need signature_type.
        # Let's try to derive creds
        print("Client initialized. Attempting to create/derive API creds...")
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print("Success! Keys derived and set.")
        print(creds)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
