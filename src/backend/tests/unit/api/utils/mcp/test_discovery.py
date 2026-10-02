"""Discovery work must stay bounded across servers, users, and cancellation."""

import asyncio

import pytest
from fastapi import HTTPException
from langflow.api.utils.mcp.discovery import MAX_CONCURRENT_CHECKS, run_server_checks


async def test_bounds_large_lists_and_rejects_overlapping_requests():
    started = asyncio.Queue()
    release = asyncio.Event()
    active = peak = 0

    async def check(name):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await started.put(name)
        try:
            await release.wait()
            return {"name": name, "mode": "stdio", "toolsCount": 1}
        finally:
            active -= 1

    names = [f"server-{i}" for i in range(200)]
    request = asyncio.create_task(run_server_checks(names, check, timeout=10))
    try:
        for _ in range(MAX_CONCURRENT_CHECKS):
            await asyncio.wait_for(started.get(), timeout=5)
        with pytest.raises(HTTPException) as exc:
            await run_server_checks(["other-user-server"], check, timeout=10)
        assert exc.value.status_code == 429
        assert exc.value.headers == {"Retry-After": "1"}
        assert await run_server_checks([], check, timeout=10) == []
    finally:
        release.set()
        results = await request

    assert peak == MAX_CONCURRENT_CHECKS
    assert [result["name"] for result in results] == names
    assert all(result["toolsCount"] == 1 for result in results)
    assert active == 0


async def test_uses_only_capacity_remaining_from_another_request():
    started = asyncio.Queue()
    release = asyncio.Event()

    async def check(name):
        await started.put(name)
        await release.wait()
        return {"name": name, "toolsCount": 1}

    first = asyncio.create_task(run_server_checks(["first"], check, timeout=10))
    await asyncio.wait_for(started.get(), timeout=5)
    second = asyncio.create_task(run_server_checks([f"second-{i}" for i in range(8)], check, timeout=10))
    try:
        for _ in range(MAX_CONCURRENT_CHECKS - 1):
            await asyncio.wait_for(started.get(), timeout=5)
        with pytest.raises(HTTPException) as exc:
            await run_server_checks(["third"], check, timeout=10)
        assert exc.value.status_code == 429
    finally:
        release.set()
        await asyncio.gather(first, second)


async def test_one_deadline_preserves_completed_results_and_cancels_active_checks():
    started = []
    finished = []

    async def check(name):
        started.append(name)
        if name == "fast":
            return {"name": name, "mode": "stdio", "toolsCount": 2}
        try:
            await asyncio.Event().wait()
        finally:
            finished.append(name)

    names = ["fast", *[f"slow-{i}" for i in range(100)]]
    results = await run_server_checks(names, check, timeout=0.1)

    assert results[0] == {"name": "fast", "mode": "stdio", "toolsCount": 2}
    assert all(result["error"] == "Timeout when checking server tools" for result in results[1:])
    assert len(started) == 1 + MAX_CONCURRENT_CHECKS
    assert sorted(finished) == sorted(started[1:])


async def test_repeated_cancellation_keeps_capacity_reserved_until_cleanup_finishes():
    started = asyncio.Queue()
    cleaning = asyncio.Queue()
    release_cleanup = asyncio.Event()

    async def check(name):
        await started.put(name)
        try:
            await asyncio.Event().wait()
        finally:
            await cleaning.put(name)
            await release_cleanup.wait()

    request = asyncio.create_task(run_server_checks([str(i) for i in range(20)], check, timeout=10))
    try:
        for _ in range(MAX_CONCURRENT_CHECKS):
            await asyncio.wait_for(started.get(), timeout=5)
        request.cancel()
        for _ in range(MAX_CONCURRENT_CHECKS):
            await asyncio.wait_for(cleaning.get(), timeout=5)
        request.cancel()
        with pytest.raises(HTTPException) as exc:
            await run_server_checks(["new"], check, timeout=10)
        assert exc.value.status_code == 429
    finally:
        release_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await request

    async def healthy(name):
        return {"name": name, "toolsCount": 1}

    assert await run_server_checks(["after-cleanup"], healthy, timeout=1) == [
        {"name": "after-cleanup", "toolsCount": 1}
    ]


async def test_unexpected_check_failure_is_propagated_and_releases_capacity():
    async def broken(name):
        raise RuntimeError(name)

    for _ in range(2):
        with pytest.raises(RuntimeError, match="broken"):
            await run_server_checks(["broken"] * MAX_CONCURRENT_CHECKS, broken, timeout=1)


@pytest.mark.parametrize("stage", ["cache_creation", "cache_registration", "stdio_client", "http_client"])
async def test_initialization_failure_cleans_owned_manager_and_constructed_clients(monkeypatch, stage):
    from langflow.api.utils.mcp import discovery

    before = asyncio.all_tasks()
    disconnected = []
    original_disconnect = discovery.MCPStdioClient.disconnect

    async def record_disconnect(client):
        disconnected.append(client)
        await original_disconnect(client)

    def fail(*_args, **_kwargs):
        message = "discovery setup failed"
        raise RuntimeError(message)

    monkeypatch.setattr(discovery.MCPStdioClient, "disconnect", record_disconnect)
    if stage == "cache_creation":
        monkeypatch.setattr(discovery, "ThreadingInMemoryCache", fail)
    elif stage == "cache_registration":
        monkeypatch.setattr(discovery.ThreadingInMemoryCache, "set", fail)
    elif stage == "stdio_client":
        monkeypatch.setattr(discovery, "MCPStdioClient", fail)
    else:
        monkeypatch.setattr(discovery, "MCPStreamableHttpClient", fail)

    try:
        with pytest.raises(RuntimeError, match="discovery setup failed"):
            async with discovery.discovery_clients():
                pytest.fail("Failed discovery initialization must not yield clients")
        assert not asyncio.all_tasks() - before
        assert len(disconnected) == (1 if stage == "http_client" else 0)
    finally:
        # Keep an unfixed implementation from leaking tasks into subsequent cases.
        leaked = asyncio.all_tasks() - before
        for task in leaked:
            task.cancel()
        await asyncio.gather(*leaked, return_exceptions=True)
