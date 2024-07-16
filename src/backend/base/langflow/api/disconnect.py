import asyncio
from functools import wraps
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request
from loguru import logger


async def disconnect_poller(request: Request, result: Any):
    """
    Poll for a disconnect.
    If the request disconnects, stop polling and return.
    """
    try:
        while not await request.is_disconnected():
            await asyncio.sleep(0.01)

        logger.debug("Request disconnected")
        return result
    except asyncio.CancelledError:
        logger.debug("Stopping polling loop")


def cancel_on_disconnect(handler: Callable[[Request], Awaitable[Any]]):
    """
    Decorator that will check if the client disconnects,
    and cancel the task if required.
    """

    @wraps(handler)
    async def cancel_on_disconnect_decorator(request: Request, *args, **kwargs):
        sentinel = object()

        # Create two tasks, one to poll the request and check if the
        # client disconnected, and another which is the request handler
        poller_task = asyncio.create_task(disconnect_poller(request, sentinel))
        handler_task = asyncio.create_task(handler(request, *args, **kwargs))

        done, pending = await asyncio.wait([poller_task, handler_task], return_when=asyncio.FIRST_COMPLETED)

        # Cancel any outstanding tasks
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                logger.debug(f"{t} was cancelled")
            except Exception as exc:
                logger.error(f"{t} raised {exc} when being cancelled")

        # Return the result if the handler finished first
        if handler_task in done:
            return await handler_task

        # Otherwise, raise an exception
        logger.error("Raising an HTTP error because I was disconnected!!")
        raise HTTPException(503)

    return cancel_on_disconnect_decorator
