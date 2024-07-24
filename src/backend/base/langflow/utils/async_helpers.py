import asyncio


def run_until_complete(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("The event loop is closed.")
    except RuntimeError:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)
