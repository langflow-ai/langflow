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


async def test_http_discovery_loads_user_variables_once_and_closes_clients(discovery_db, monkeypatch):
    from aiohttp import web
    from langflow.services.auth.utils import encrypt_api_key
    from langflow.services.database.models.variable.model import Variable
    from lfx.base.mcp import util

    requests = []

    async def respond(request):
        requests.append((request.method, request.headers.get("Authorization")))
        if request.method == "GET":
            return web.Response(status=405)
        if request.method == "DELETE":
            return web.Response(status=200)
        message = await request.json()
        if "id" not in message:
            return web.Response(status=202)
        if message["method"] == "initialize":
            result = {
                "protocolVersion": message["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "discovery-test", "version": "1.0"},
            }
        else:
            result = {"tools": [{"name": "echo", "inputSchema": {"type": "object", "properties": {}}}]}
        return web.json_response(
            {"jsonrpc": "2.0", "id": message["id"], "result": result},
            headers={"Mcp-Session-Id": "discovery-test"},
        )

    app = web.Application()
    app.router.add_route("*", "/mcp", respond)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = runner.addresses[0][1]
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")
        user = SimpleNamespace(id=uuid4(), is_superuser=False)
        other_user_id = uuid4()
        for user_id, token_value in [(user.id, "discovery-test-value"), (other_user_id, "other-user-value")]:
            for name, value, variable_type in [
                ("MCP_ENDPOINT", f"http://127.0.0.1:{port}/mcp", "Generic"),
                ("MCP_TOKEN", token_value, "Credential"),
            ]:
                discovery_db.add(Variable(user_id=user_id, name=name, value=encrypt_api_key(value), type=variable_type))
        for index in range(2):
            discovery_db.add(
                MCPServer(
                    user_id=user.id,
                    name=f"http-{index}",
                    config={"url": "{{MCP_ENDPOINT}}", "headers": {"Authorization": "Bearer {{MCP_TOKEN}}"}},
                    transport="streamable_http",
                )
            )
        await discovery_db.commit()

        variable_loads = 0
        execute = discovery_db.exec

        async def record_exec(statement, *args, **kwargs):
            nonlocal variable_loads
            if Variable.__table__ in statement.get_final_froms():
                variable_loads += 1
            return await execute(statement, *args, **kwargs)

        monkeypatch.setattr(discovery_db, "exec", record_exec)
        clients = []
        create_client = util.create_mcp_http_client_with_ssl_option

        def record_client(*args, **kwargs):
            client = create_client(*args, **kwargs)
            clients.append(client)
            return client

        monkeypatch.setattr(util, "create_mcp_http_client_with_ssl_option", record_client)
        before = _manager_tasks()
        results = await get_servers(user, discovery_db, None, get_settings_service(), action_count=True)

        assert results == [{"name": f"http-{i}", "mode": "streamable_http", "toolsCount": 1} for i in range(2)]
        assert variable_loads == 1
        assert clients
        assert all(client.is_closed for client in clients)
        assert requests
        assert all(value == "Bearer discovery-test-value" for _, value in requests)
        assert sum(method == "DELETE" for method, _ in requests) >= 2
        assert _manager_tasks() <= before
    finally:
        await runner.cleanup()
