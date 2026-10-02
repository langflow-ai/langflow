"""Bound the work and transport lifetime of MCP tool-count discovery."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager, suppress

from fastapi import HTTPException
from lfx.base.mcp.util import MCPSessionManager, MCPStdioClient, MCPStreamableHttpClient
from lfx.services.cache.service import ThreadingInMemoryCache

# Shared by all discovery requests in a worker, including requests from different users.
# Store the gate on the loop so app restarts/tests cannot reuse a gate from a closed loop.
MAX_CONCURRENT_CHECKS = 4
_LIMITER_ATTRIBUTE = "_langflow_mcp_discovery_limiter"

ServerInfo = dict[str, str | int | None]


async def _finish_cleanup(future: asyncio.Future) -> bool:
    """Drain owned work even under repeated cancellation; report deferred cancellation."""
    cancelled = False
    while not future.done():
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError:
            cancelled = True
    future.result()
    return cancelled


@asynccontextmanager
async def discovery_clients() -> AsyncIterator[tuple[MCPStdioClient, MCPStreamableHttpClient]]:
    """Own every session and background task created by a single discovery check."""
    manager = MCPSessionManager()
    stdio_client: MCPStdioClient | None = None
    http_client: MCPStreamableHttpClient | None = None

    async def close_clients() -> None:
        try:
            try:
                if stdio_client is not None:
                    await stdio_client.disconnect()
            finally:
                if http_client is not None:
                    await http_client.disconnect()
        finally:
            await manager.cleanup_all()

    try:
        cache: ThreadingInMemoryCache = ThreadingInMemoryCache()
        cache.set("mcp_session_manager", manager)
        stdio_client = MCPStdioClient(component_cache=cache)
        http_client = MCPStreamableHttpClient(component_cache=cache)
        yield stdio_client, http_client
    finally:
        # disconnect() only releases established contexts. An interrupted handshake
        # also owns transport/reaper tasks and the manager's periodic cleanup task.
        cleanup = asyncio.create_task(close_clients())
        if await _finish_cleanup(cleanup):
            raise asyncio.CancelledError


async def run_server_checks(
    server_names: Sequence[str],
    check_server: Callable[[str], Awaitable[ServerInfo]],
    *,
    timeout: float,
) -> list[ServerInfo]:
    """Run a fixed worker pool within one deadline, retaining completed results.

    Reserve available slots without queuing requests: a request arriving at capacity
    receives 429. Each slot stays reserved until transport cleanup finishes, including
    when the caller times out or is cancelled. Limits are per application worker;
    multiple processes each have their own event loop and budget.
    """
    if not server_names:
        return []

    loop = asyncio.get_running_loop()
    limiter = getattr(loop, _LIMITER_ATTRIBUTE, None)
    if limiter is None:
        limiter = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
        setattr(loop, _LIMITER_ATTRIBUTE, limiter)

    slots = 0
    while slots < min(len(server_names), MAX_CONCURRENT_CHECKS) and not limiter.locked():
        # acquire() does not suspend when a slot is available, so checking and
        # reserving it cannot race another request on this loop.
        await limiter.acquire()
        slots += 1
    if not slots:
        raise HTTPException(
            status_code=429,
            detail="MCP server discovery is busy. Please retry shortly.",
            headers={"Retry-After": "1"},
        )

    results: list[ServerInfo] = [
        {"name": name, "mode": None, "toolsCount": None, "error": "Timeout when checking server tools"}
        for name in server_names
    ]
    pending = iter(enumerate(server_names))

    async def worker() -> None:
        for index, name in pending:
            results[index] = await check_server(name)

    tasks = [asyncio.create_task(worker()) for _ in range(slots)]
    workers = asyncio.gather(*tasks, return_exceptions=True)
    cancelled = False
    try:
        with suppress(asyncio.TimeoutError):
            # Shield so timeout/caller cancellation cannot interrupt cleanup twice.
            await asyncio.wait_for(asyncio.shield(workers), timeout=timeout)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        try:
            cancelled = await _finish_cleanup(workers)
        finally:
            for _ in range(slots):
                limiter.release()

    if cancelled:
        raise asyncio.CancelledError
    for outcome in workers.result():
        if isinstance(outcome, Exception):
            raise outcome
    return results
