"""Exercise tool-count discovery with the real DB, MCP handshake, and child processes."""

import asyncio
import sys
from types import SimpleNamespace
from uuid import uuid4

import mcp.client.stdio
import pytest
from fastapi import HTTPException
from langflow.api.utils.mcp.discovery import MAX_CONCURRENT_CHECKS
from langflow.api.v2.mcp import get_servers
from langflow.services.database.models import MCPServer
from langflow.services.deps import get_settings_service
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

SERVER = """
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    if request["method"] == "initialize":
        result = {
            "protocolVersion": request["params"]["protocolVersion"],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "discovery-test", "version": "1.0"},
        }
    else:
        result = {"tools": [{"name": "echo", "inputSchema": {"type": "object", "properties": {}}}]}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
"""


@pytest.fixture
async def discovery_db():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.fixture
def server_scripts(tmp_path):
    healthy = tmp_path / "healthy.py"
    healthy.write_text(SERVER)
    hanging = tmp_path / "hanging.py"
    # Never initialize MCP, but exit when the SDK closes stdin during cleanup.
    hanging.write_text("import sys\nsys.stdin.read()\n")
    return healthy, hanging


@pytest.fixture
async def processes(monkeypatch):
    children = []
    started = asyncio.Queue()
    create_process = mcp.client.stdio._create_platform_compatible_process

    async def record_process(*args, **kwargs):
        process = await create_process(*args, **kwargs)
        children.append(process)
        await started.put(process)
        return process

    # Observe the real SDK process boundary; creation, protocol, and reaping stay real.
    monkeypatch.setattr(mcp.client.stdio, "_create_platform_compatible_process", record_process)
    yield children, started
    for process in children:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def _register(session, script, count):
    user = SimpleNamespace(id=uuid4(), is_superuser=False)
    for index in range(count):
        session.add(
            MCPServer(
                user_id=user.id,
                name=f"server-{index}",
                config={"command": sys.executable, "args": [str(script)]},
                transport="stdio",
            )
        )
    await session.commit()
    return user


def _manager_tasks():
    return {task for task in asyncio.all_tasks() if "MCPSessionManager" in task.get_coro().__qualname__}


async def test_plain_listing_does_not_start_processes(discovery_db, server_scripts, processes):
    user = await _register(discovery_db, server_scripts[1], 12)
    results = await get_servers(user, discovery_db, None, get_settings_service(), action_count=False)

    assert len(results) == 12
    assert all(result["toolsCount"] is None for result in results)
    assert processes[0] == []


async def test_successful_counts_reap_processes_and_manager_tasks(discovery_db, server_scripts, processes):
    user = await _register(discovery_db, server_scripts[0], 6)
    before = _manager_tasks()
    results = await get_servers(user, discovery_db, None, get_settings_service(), action_count=True)

    assert results == [{"name": f"server-{i}", "mode": "stdio", "toolsCount": 1} for i in range(6)]
    assert len(processes[0]) == 6
    assert all(process.returncode is not None for process in processes[0])
    assert _manager_tasks() <= before


async def test_timeout_limits_real_processes_and_reaps_uninitialized_sessions(
    discovery_db, server_scripts, processes, monkeypatch
):
    user = await _register(discovery_db, server_scripts[1], 12)
    settings = get_settings_service()
    monkeypatch.setattr(settings.settings, "mcp_server_timeout", 2)
    before = _manager_tasks()

    results = await get_servers(user, discovery_db, None, settings, action_count=True)

    assert len(results) == 12
    assert all(result["toolsCount"] is None and "error" in result for result in results)
    assert len(processes[0]) == MAX_CONCURRENT_CHECKS
    assert all(process.returncode is not None for process in processes[0])
    assert _manager_tasks() <= before


async def test_cancellation_reaps_real_processes_before_readmitting_requests(discovery_db, server_scripts, processes):
    user = await _register(discovery_db, server_scripts[1], 12)
    before = _manager_tasks()
    settings = get_settings_service()
    request = asyncio.create_task(get_servers(user, discovery_db, None, settings, action_count=True))
    try:
        for _ in range(MAX_CONCURRENT_CHECKS):
            await asyncio.wait_for(processes[1].get(), timeout=10)
        with pytest.raises(HTTPException) as exc:
            await get_servers(user, discovery_db, None, settings, action_count=True)
        assert exc.value.status_code == 429
    finally:
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request

    assert len(processes[0]) == MAX_CONCURRENT_CHECKS
    assert all(process.returncode is not None for process in processes[0])
    assert _manager_tasks() <= before

    healthy_user = await _register(discovery_db, server_scripts[0], 1)
    [result] = await get_servers(healthy_user, discovery_db, None, settings, action_count=True)
    assert result["toolsCount"] == 1


async def test_code_execution_restriction_precedes_discovery(discovery_db, server_scripts, processes, monkeypatch):
    user = await _register(discovery_db, server_scripts[0], 1)
    settings = get_settings_service()
    monkeypatch.setattr(settings.settings, "custom_component_admin_only", True)
    with pytest.raises(HTTPException) as exc:
        await get_servers(user, discovery_db, None, settings, action_count=True)
    assert exc.value.status_code == 403
    assert processes[0] == []
