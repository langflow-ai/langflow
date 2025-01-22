from typing import Optional
import httpx
import asyncio

class APIClient:
    async def make_request(
        self, 
        method: str, 
        url: str, 
        timeout: Optional[float] = 30.0,
        retry_count: int = 3
    ):
        """Make HTTP request with timeout and retry logic"""
        for attempt in range(retry_count):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method,
                        url,
                        timeout=timeout
                    )
                    return response
            except (httpx.TimeoutException, asyncio.TimeoutError):
                if attempt == retry_count - 1:
                    raise
                await asyncio.sleep(1 * (attempt + 1)) 