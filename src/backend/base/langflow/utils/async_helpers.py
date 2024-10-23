import asyncio
import threading


def run_until_complete(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Run the coroutine in a separate event loop in a new thread
            return run_in_thread(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        # If there's no event loop, create a new one and run the coroutine
        return asyncio.run(coro)


def run_in_thread(coro):
    result = None
    exception = None

    def target() -> None:
        nonlocal result, exception
        try:
            result = asyncio.run(coro)
        except Exception as e:  # noqa: BLE001
            exception = e

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()

    if exception:
        raise exception
    return result
