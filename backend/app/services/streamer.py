import httpx
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

class StreamProxy:
    async def proxy_stream(self, url: str, range_header: str = None, filename: str = None) -> StreamingResponse:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        if range_header: headers['Range'] = range_header
        
        client = httpx.AsyncClient(follow_redirects=True)
        
        async def stream_generator() -> AsyncGenerator[bytes, None]:
            try:
                async with client.stream("GET", url, headers=headers, timeout=30) as response:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 128):
                        yield chunk
            except Exception as e:
                print(f"Streaming error: {e}")
            finally:
                await client.aclose()

        async with client.stream("GET", url, headers=headers) as initial_res:
            res_headers = {
                "Content-Type": initial_res.headers.get("Content-Type", "video/mp4"),
                "Accept-Ranges": "bytes",
                "Content-Length": initial_res.headers.get("Content-Length", ""),
                "Content-Range": initial_res.headers.get("Content-Range", ""),
                "Access-Control-Allow-Origin": "*",
            }
            
            if filename:
                res_headers["Content-Disposition"] = f'attachment; filename="{filename}"'

            # Remove empty values
            res_headers = {k: v for k, v in res_headers.items() if v}

            return StreamingResponse(
                stream_generator(),
                status_code=initial_res.status_code,
                headers=res_headers
            )

stream_proxy = StreamProxy()
