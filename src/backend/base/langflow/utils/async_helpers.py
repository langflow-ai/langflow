import asyncio


def run_until_complete(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # If there's no event loop, create a new one and run the coroutine
        return asyncio.run(coro)
    return loop.run_until_complete(coro)
