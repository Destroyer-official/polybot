
import asyncio
import aiohttp
import json
import time

async def fetch_debug():
    # Calculate current 15-min interval
    now = int(time.time())
    current_interval = (now // 900) * 900
    
    slug = f"btc-updown-15m-{current_interval}"
    url = f"https://gamma-api.polymarket.com/events/slug/{slug}"
    
    print(f"Fetching: {url}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                print("\n--- RAW DATA DEBUG ---")
                event_markets = data.get("markets", [])
                event_markets = data.get("markets", [])
                if event_markets:
                    m = event_markets[0]
                    print(f"\nMarket 0:")
                    raw_ids = m.get("clobTokenIds")
                    print(f"Type: {type(raw_ids)}")
                    print(f"Value: {repr(raw_ids)}")
                    
                    if isinstance(raw_ids, list) and len(raw_ids) > 0:
                        print(f"Element 0 Type: {type(raw_ids[0])}")
                        print(f"Element 0 Value: {repr(raw_ids[0])}")
                    elif isinstance(raw_ids, str):
                        print(f"IT IS A STRING! Raw repr: {repr(raw_ids)}")
                        print("Trying json.loads...")
                        try:
                            parsed = json.loads(raw_ids)
                            print(f"Parsed Type: {type(parsed)}")
                            print(f"Parsed Value: {parsed}")
                        except Exception as e:
                            print(f"json.loads failed: {e}")
                            import ast
                            print("Trying ast.literal_eval...")
                            try:
                                parsed = ast.literal_eval(raw_ids)
                                print(f"ast.literal_eval success! Type: {type(parsed)}")
                                print(f"Value: {parsed}")
                            except Exception as e2:
                                print(f"ast.literal_eval failed: {e2}")
                else:
                    print("No markets found in this interval.")
            else:
                print(f"Error: {resp.status}")

if __name__ == "__main__":
    asyncio.run(fetch_debug())
