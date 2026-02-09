import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load env
load_dotenv()

async def main():
    print("Testing NVIDIA LLM Connectivity...")
    
    api_key = os.getenv("NVIDIA_API_KEY")
    base_url = "https://integrate.api.nvidia.com/v1"
    
    print(f"API Key present: {bool(api_key)}")
    print(f"Base URL: {base_url}")
    
    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        print("Client initialized. Sending test request...")
        
        response = await client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct", # Try a standard new model
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            temperature=0.1,
            max_tokens=50
        )
        
        print("Success! Response received:")
        print(response.choices[0].message.content)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
