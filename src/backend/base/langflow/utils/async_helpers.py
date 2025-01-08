import asyncio
from contextlib import asynccontextmanager

if hasattr(asyncio, "timeout"):
    timeout_context = asyncio.timeout  # type: ignore[misc]
else:
    @asynccontextmanager
    async def timeout_context(timeout_seconds):  # type: ignore[misc]
        try:
            yield await asyncio.wait_for(asyncio.Future(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            msg = f"Operation timed out after {timeout_seconds} seconds"
            raise TimeoutError(msg) from e


def run_until_complete(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # If there's no event loop, create a new one and run the coroutine
        return asyncio.run(coro)
    return loop.run_until_complete(coro)
