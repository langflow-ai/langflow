"""MCP resources and long-lived sessions honor current key ceilings."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from langflow.api.v1 import mcp_utils
from langflow.services.auth.context import (
    AuthCredentialContext,
    clear_current_auth_context,
    get_current_auth_context,
    set_current_auth_context,
)
from langflow.services.database.models import Flow, Folder
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.file.model import File
from langflow.services.deps import get_settings_service, session_scope

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture(autouse=True)
def auth_context():
    clear_current_auth_context()
    yield
    clear_current_auth_context()


@pytest.fixture
async def resources(active_user, monkeypatch):
    async with session_scope() as session:
        project = Folder(name="Scoped MCP project", user_id=active_user.id)
        session.add(project)
        await session.flush()
        flows = [
            Flow(name=name, user_id=active_user.id, folder_id=project.id, data={}, mcp_enabled=True)
            for name in ("Allowed", "Denied")
        ]
        files = [
            File(name=name, path=f"{active_user.id}/{name}", size=1, user_id=active_user.id)
            for name in ("a.txt", "b.txt")
        ]
        session.add_all([*flows, *files])
        await session.flush()
        policy = {"restrictions": [{"resource_type": "flow", "actions": ["read"], "resource_ids": [str(flows[0].id)]}]}
        key = ApiKey(api_key="test-credential-value", user_id=active_user.id, permissions=policy)
        session.add(key)
        await session.flush()
        allowed = {f"flow:{flows[0].id}", f"file:{files[0].id}", f"project:{project.id}"}
        context = AuthCredentialContext(
            method="api_key",
            api_key_id=key.id,
            api_key_source="db",  # pragma: allowlist secret
            api_key_restricted=True,
            api_key_permissions=policy,
        )

    async def enforce(*, obj, **_kwargs):
        return obj in allowed

    async def batch(*, requests, **_kwargs):
        return [obj in allowed for obj, _act in requests]

    plugin = SimpleNamespace(supports_api_key_scopes=AsyncMock(return_value=True), enforce=enforce, batch_enforce=batch)
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr("langflow.services.authorization.guards.get_authorization_service", lambda: plugin)
    monkeypatch.setattr("langflow.services.authorization.listing.get_authorization_service", lambda: plugin)
    monkeypatch.setattr("langflow.services.database.models.api_key.crud.get_authorization_service", lambda: plugin)
    storage = SimpleNamespace(
        list_files=AsyncMock(return_value=["flow.txt"]), get_file=AsyncMock(return_value=b"content")
    )
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: storage)
    monkeypatch.setattr(mcp_utils, "json_schema_from_flow", lambda _flow: {"type": "object"})
    token = mcp_utils.current_user_ctx.set(active_user)
    set_current_auth_context(context)
    yield project, flows, files, key, storage, context
    mcp_utils.current_user_ctx.reset(token)


async def test_mcp_lists_filter_flow_and_user_file_resources(resources):
    _project, flows, _files, _key, storage, _context = resources
    listed = await mcp_utils.handle_list_resources()
    assert {resource.name for resource in listed} == {"flow.txt", "a.txt"}
    storage.list_files.assert_awaited_once_with(flow_id=str(flows[0].id))


async def test_mcp_direct_resource_reads_guard_before_storage(resources, active_user):
    _project, flows, files, _key, storage, _context = resources
    for namespace, filename in ((flows[1].id, "flow.txt"), (active_user.id, files[1].name)):
        with pytest.raises(HTTPException) as denied:
            await mcp_utils.handle_read_resource(f"http://localhost/api/v1/files/download/{namespace}/{filename}")
        assert denied.value.status_code == 403
    storage.get_file.assert_not_awaited()


@pytest.mark.parametrize("filename", ["_mcp_servers.json", "_mcp_servers_{owner}.json"])
async def test_mcp_resources_cannot_read_legacy_credential_files(resources, active_user, filename):
    _project, _flows, files, _key, storage, _context = resources
    filename = filename.format(owner=active_user.id)
    async with session_scope() as session:
        row = await session.get(File, files[0].id)
        row.name = filename
        row.path = f"{active_user.id}/{filename}"
        session.add(row)
    with pytest.raises(HTTPException) as denial:
        await mcp_utils.handle_read_resource(f"http://localhost/api/v1/files/download/{active_user.id}/{filename}")
    assert denial.value.status_code == 404
    storage.get_file.assert_not_awaited()


async def test_mcp_tool_metadata_filters_unpermitted_flows(resources, active_user):
    from langflow.api.v1.mcp_projects import _build_project_tools_response

    project, _flows, _files, _key, _storage, _context = resources
    tools, _excluded = await mcp_utils._collect_tools(project.id)
    assert [tool.name for tool in tools] == ["allowed"]
    metadata = await _build_project_tools_response(project.id, active_user, mcp_enabled=True)
    assert [tool.name for tool in metadata.tools] == ["Allowed"]


@pytest.mark.parametrize("project_scoped", [False, True])
async def test_filtered_tool_names_still_resolve_to_the_advertised_flow(
    resources, active_user, monkeypatch, project_scoped
):
    from lfx.base.mcp.util import get_flow_snake_case

    project, flows, _files, _key, _storage, _context = resources
    ordered = sorted(flows, key=lambda flow: flow.id)
    allowed_id = ordered[1].id
    async with session_scope() as session:
        for index, flow in enumerate(flows):
            stored = await session.get(Flow, flow.id)
            stored.name = "Collision" if index == 0 else "COLLISION"
            stored.action_name = "collision"

    async def allow_later(_user, candidates):
        return [flow for flow in candidates if flow.id == allowed_id]

    monkeypatch.setattr(mcp_utils, "filter_mcp_flows", allow_later)
    project_id = project.id if project_scoped else None
    tools, _excluded = await mcp_utils._collect_tools(project_id, mcp_enabled_only=project_scoped)
    assert [tool.name for tool in tools] == ["collision_1"]
    async with session_scope() as session:
        resolved = await get_flow_snake_case(
            tools[0].name,
            active_user.id,
            session,
            project_id=project_id,
            is_action=project_scoped,
            mcp_enabled_only=project_scoped,
        )
    assert resolved.id == allowed_id


@pytest.mark.parametrize("operation", ["resources", "tools", "project", "call_global", "call_project"])
@pytest.mark.usefixtures("resources")
async def test_mcp_metadata_releases_single_connection_before_authorization(
    active_user, monkeypatch, tmp_path, operation
):
    from contextlib import asynccontextmanager

    from langflow.api.v1 import mcp_projects
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'mcp-pool.db'}",
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.2,
    )
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        project = Folder(name="Pool project", user_id=active_user.id)
        session.add(project)
        await session.flush()
        flow = Flow(name="Pool flow", user_id=active_user.id, folder_id=project.id, data={}, mcp_enabled=True)
        session.add(flow)
        session.add(File(user_id=active_user.id, name="pool.txt", path=f"{active_user.id}/pool.txt", size=1))
        await session.commit()

    @asynccontextmanager
    async def local_scope():
        async with AsyncSession(engine, expire_on_commit=True) as session:
            yield session
            await session.commit()

    async def enforce(**_kwargs):
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True

    async def batch(*, requests, **kwargs):
        await enforce(**kwargs)
        return [True] * len(requests)

    async def list_files(**_kwargs):
        await enforce()
        return ["flow.txt"]

    plugin = SimpleNamespace(supports_api_key_scopes=AsyncMock(return_value=True), enforce=enforce, batch_enforce=batch)
    monkeypatch.setattr(mcp_utils, "session_scope", local_scope)
    monkeypatch.setattr(mcp_projects, "session_scope", local_scope)
    monkeypatch.setattr("langflow.services.authorization.guards.get_authorization_service", lambda: plugin)
    monkeypatch.setattr("langflow.services.authorization.listing.get_authorization_service", lambda: plugin)
    monkeypatch.setattr(mcp_utils, "get_storage_service", lambda: SimpleNamespace(list_files=list_files))

    async def run_flow(**_kwargs):
        await enforce()
        return SimpleNamespace(outputs=[])

    run = AsyncMock(side_effect=run_flow)
    monkeypatch.setattr(mcp_utils, "simple_run_flow", run)
    monkeypatch.setattr(mcp_utils.get_mcp_config(), "enable_progress_notifications", False)
    caller_token = mcp_utils.authenticated_caller_ctx.set(active_user.id)
    try:
        if operation == "resources":
            result = await mcp_utils.handle_list_resources()
            assert {item.name for item in result} == {"flow.txt", "pool.txt"}
        elif operation == "tools":
            result, _excluded = await mcp_utils._collect_tools(project.id)
            assert [item.name for item in result] == ["pool_flow"]
        elif operation == "project":
            result = await mcp_projects._build_project_tools_response(project.id, active_user, mcp_enabled=True)
            assert [item.name for item in result.tools] == ["Pool flow"]
        else:
            result = await mcp_utils.handle_call_tool(
                "pool_flow", {}, SimpleNamespace(), project_id=project.id if operation == "call_project" else None
            )
            assert result == []
            run.assert_awaited_once()
    finally:
        mcp_utils.authenticated_caller_ctx.reset(caller_token)
        await engine.dispose()


async def test_mcp_operation_reloads_changed_key_policy(resources, active_user, monkeypatch):
    from langflow.services.database.models.auth import AuthzAuditLog
    from sqlmodel import select

    _project, _flows, _files, key, _storage, original_context = resources
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    mcp_utils.bind_mcp_operation_context(request, active_user, caller_user_id=active_user.id)
    changed = {"restrictions": [{"resource_type": "flow", "actions": ["execute"]}]}
    async with session_scope() as session:
        stored = await session.get(ApiKey, key.id)
        stored.permissions = changed
    callback = AsyncMock(return_value="allowed")
    server = SimpleNamespace(request_context=SimpleNamespace(request=request), request_handlers={"operation": callback})
    mcp_utils.protect_mcp_operation_handlers(server)
    await server.request_handlers["operation"](None)
    assert get_current_auth_context() is not original_context
    assert get_current_auth_context().api_key_permissions == changed
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", True)
    async with session_scope() as session:
        stored = await session.get(ApiKey, key.id)
        stored.is_active = False
    with pytest.raises(HTTPException) as denied:
        await server.request_handlers["operation"](None)
    assert denied.value.status_code == 403
    assert callback.await_count == 1
    async with session_scope() as session:
        events = (
            await session.exec(
                select(AuthzAuditLog).where(AuthzAuditLog.actor_id == key.id, AuthzAuditLog.action == "mcp:request")
            )
        ).all()
    assert len(events) == 1
    assert events[0].user_id == active_user.id
    assert events[0].details["reason"] == "mcp_credential_authorization_invalid"


@pytest.mark.usefixtures("resources")
async def test_mcp_sse_identity_is_bound_to_key_not_just_owner(active_user):
    from langflow.api.v1.mcp import _bind_mcp_transport_user
    from mcp.server.auth.middleware.bearer_auth import authorization_context

    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    _bind_mcp_transport_user(request, active_user)
    initial = authorization_context(request.scope["user"])
    set_current_auth_context(
        AuthCredentialContext(method="api_key", api_key_id=uuid4(), api_key_source="db", api_key_restricted=True)
    )
    _bind_mcp_transport_user(request, active_user)
    assert authorization_context(request.scope["user"]) != initial


async def test_real_sse_post_refuses_another_key_for_the_same_owner(resources, active_user, client, monkeypatch):
    import anyio
    from langflow.api.v1 import mcp
    from mcp.server.auth.middleware.bearer_auth import authorization_context
    from mcp.server.sse import SseServerTransport

    _project, _flows, _files, original_key, _storage, context = resources
    async with session_scope() as session:
        other = ApiKey(
            api_key="different-test-credential",  # pragma: allowlist secret
            user_id=active_user.id,
            permissions=original_key.permissions,
        )
        session.add(other)
    transport = SseServerTransport("/api/v1/mcp/")
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    set_current_auth_context(context)
    mcp._bind_mcp_transport_user(request, active_user)
    session_id = uuid4()
    writer, reader = anyio.create_memory_object_stream(1)
    transport._session_owners[session_id] = authorization_context(request.scope["user"])
    transport._read_stream_writers[session_id] = writer
    monkeypatch.setattr(mcp, "sse", transport)
    client.cookies.clear()
    try:
        refused = await client.post(
            f"api/v1/mcp/?session_id={session_id.hex}",
            headers={"x-api-key": other.api_key},
            json={"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}},
        )
        assert refused.status_code == 404
        assert writer.statistics().current_buffer_used == 0
    finally:
        await writer.aclose()
        await reader.aclose()
