import asyncio
from backend.app.services.extractor import extractor

async def test():
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    ]
    for url in urls:
        print(f"\n--- Testing: {url} ---")
        res = await extractor.extract_info(url)
        if res:
            print(f"SUCCESS: {res.title} ({res.platform})")
        else:
            print("FAILED")

if __name__ == "__main__":
    asyncio.run(test())
