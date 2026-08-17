"""MCP failures must reach the client instead of being swallowed.

Two paths hid failures. ``handle_call_tool`` appended the error string as ordinary
tool content and returned normally, so an agent consumed the error as an answer.
``handle_list_tools`` dropped any flow whose schema could not be derived and logged a
warning, so a version-skewed deploy answered with an empty tool list and no error.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.v1 import mcp_utils
from lfx.utils.flow_validation import CustomComponentValidationError


def _build_fake_server() -> SimpleNamespace:
    return SimpleNamespace(
        request_context=SimpleNamespace(
            meta=SimpleNamespace(progressToken=None),
            session=SimpleNamespace(send_progress_notification=AsyncMock()),
        )
    )


async def _call_tool_with_failure(monkeypatch, exc: Exception):
    flow = SimpleNamespace(
        id="flow-id-1",
        name="my_flow",
        folder_id=None,
        user_id="user-1",
        workspace_id=None,
        data={"nodes": [], "edges": []},
    )

    async def fake_get_flow_snake_case(*_args, **_kwargs):
        return flow

    async def failing_run(*_args, **_kwargs):
        raise exc

    monkeypatch.setattr(mcp_utils, "get_flow_snake_case", fake_get_flow_snake_case)
    monkeypatch.setattr(mcp_utils, "simple_run_flow", failing_run)
    monkeypatch.setattr(mcp_utils, "with_db_session", lambda operation: operation(SimpleNamespace()))
    mcp_utils.get_mcp_config().enable_progress_notifications = False

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id="user-1"))
    try:
        return await mcp_utils.handle_call_tool(name="my_flow", arguments={}, server=_build_fake_server())
    finally:
        mcp_utils.current_user_ctx.reset(token)


@pytest.mark.asyncio
async def test_should_raise_when_flow_execution_fails(monkeypatch):
    """A runtime failure must surface as an error, not as successful tool content."""
    with pytest.raises(RuntimeError, match="my_flow"):
        await _call_tool_with_failure(monkeypatch, ValueError("boom"))


@pytest.mark.asyncio
async def test_should_raise_when_flow_build_is_blocked(monkeypatch):
    """A blocked build must surface as an error rather than a text answer."""
    with pytest.raises(RuntimeError, match="blocked"):
        await _call_tool_with_failure(monkeypatch, CustomComponentValidationError("component hash mismatch"))


@pytest.mark.asyncio
async def test_should_preserve_original_message_when_execution_fails(monkeypatch):
    """The client still needs the underlying cause, not just a generic failure."""
    with pytest.raises(RuntimeError, match="boom"):
        await _call_tool_with_failure(monkeypatch, ValueError("boom"))


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, flows):
        self._flows = flows

    async def exec(self, _stmt):
        return _FakeResult(self._flows)


class _FakeSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _patch_list_tools(monkeypatch, flows, *, schema_error: Exception | None = None):
    monkeypatch.setattr(mcp_utils, "session_scope", lambda: _FakeSessionContext(_FakeSession(flows)))
    if schema_error is not None:

        def failing_schema(_flow):
            raise schema_error

        monkeypatch.setattr(mcp_utils, "json_schema_from_flow", failing_schema)


def _fake_flow(name: str, project_id):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        user_id=uuid4(),
        folder_id=project_id,
        action_name=name,
        action_description=None,
        description=None,
        mcp_enabled=True,
    )


@pytest.mark.asyncio
async def test_should_raise_when_every_flow_in_project_fails_validation(monkeypatch):
    """An all-invalid project must not answer with a silent empty tool list."""
    project_id = uuid4()
    flows = [_fake_flow("broken_one", project_id)]
    _patch_list_tools(monkeypatch, flows, schema_error=CustomComponentValidationError("hash mismatch"))

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=flows[0].user_id))
    try:
        with pytest.raises(RuntimeError, match="broken_one"):
            await mcp_utils.handle_list_tools(project_id=project_id, mcp_enabled_only=True)
    finally:
        mcp_utils.current_user_ctx.reset(token)


@pytest.mark.asyncio
async def test_should_return_valid_tools_when_only_some_flows_fail(monkeypatch):
    """One broken flow must not take down a project that still has working tools."""
    project_id = uuid4()
    user_id = uuid4()
    good = _fake_flow("good_tool", project_id)
    bad = _fake_flow("bad_tool", project_id)
    good.user_id = bad.user_id = user_id

    def selective_schema(flow):
        if flow.name == "bad_tool":
            msg = "hash mismatch"
            raise CustomComponentValidationError(msg)
        return {"type": "object", "properties": {}}

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: _FakeSessionContext(_FakeSession([good, bad])))
    monkeypatch.setattr(mcp_utils, "json_schema_from_flow", selective_schema)

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=user_id))
    try:
        tools = await mcp_utils.handle_list_tools(project_id=project_id, mcp_enabled_only=True)
    finally:
        mcp_utils.current_user_ctx.reset(token)

    assert [tool.name for tool in tools] == ["good_tool"]


def _partial_failure_flows(monkeypatch):
    """Project with one buildable flow and one that fails schema generation."""
    project_id = uuid4()
    user_id = uuid4()
    good = _fake_flow("good_tool", project_id)
    bad = _fake_flow("bad_tool", project_id)
    good.user_id = bad.user_id = user_id

    def selective_schema(flow):
        if flow.name == "bad_tool":
            msg = "hash mismatch"
            raise CustomComponentValidationError(msg)
        return {"type": "object", "properties": {}}

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: _FakeSessionContext(_FakeSession([good, bad])))
    monkeypatch.setattr(mcp_utils, "json_schema_from_flow", selective_schema)
    return project_id, user_id, bad


@pytest.mark.asyncio
async def test_should_report_excluded_flow_in_meta_when_only_some_flows_fail(monkeypatch):
    """A partially broken project must name what it dropped instead of hiding it.

    Returning only the surviving tools reads as a complete list: the operator has no
    way to tell a tool went missing, and the sole trace is a log line on the server.
    """
    project_id, user_id, bad = _partial_failure_flows(monkeypatch)

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=user_id))
    try:
        result = await mcp_utils.handle_list_tools_result(project_id=project_id, mcp_enabled_only=True)
    finally:
        mcp_utils.current_user_ctx.reset(token)

    assert [tool.name for tool in result.tools] == ["good_tool"]

    excluded = (result.meta or {}).get(mcp_utils.EXCLUDED_FLOWS_META_KEY)
    assert excluded is not None, "a dropped flow must be reported to the client"
    assert len(excluded) == 1
    assert excluded[0]["tool_name"] == "bad_tool"
    assert excluded[0]["flow_id"] == str(bad.id)
    # The exception type, not its message: the project endpoint answers end users on the
    # serving plane, and the raw text carries paths, SQL and component internals.
    assert excluded[0]["reason"] == "CustomComponentValidationError"
    assert "hash mismatch" not in str(excluded[0])


@pytest.mark.asyncio
async def test_should_not_attach_meta_when_every_flow_builds(monkeypatch):
    """A healthy project must keep a clean response — no diagnostic noise."""
    project_id = uuid4()
    user_id = uuid4()
    flow = _fake_flow("good_tool", project_id)
    flow.user_id = user_id
    monkeypatch.setattr(mcp_utils, "session_scope", lambda: _FakeSessionContext(_FakeSession([flow])))
    monkeypatch.setattr(mcp_utils, "json_schema_from_flow", lambda _flow: {"type": "object", "properties": {}})

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=user_id))
    try:
        result = await mcp_utils.handle_list_tools_result(project_id=project_id, mcp_enabled_only=True)
    finally:
        mcp_utils.current_user_ctx.reset(token)

    assert [tool.name for tool in result.tools] == ["good_tool"]
    assert (result.meta or {}).get(mcp_utils.EXCLUDED_FLOWS_META_KEY) is None


@pytest.mark.asyncio
async def test_should_still_raise_from_result_handler_when_every_flow_fails(monkeypatch):
    """The all-invalid project keeps raising: an empty list must never look healthy."""
    project_id = uuid4()
    flows = [_fake_flow("broken_one", project_id)]
    _patch_list_tools(monkeypatch, flows, schema_error=CustomComponentValidationError("hash mismatch"))

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=flows[0].user_id))
    try:
        with pytest.raises(RuntimeError, match="broken_one"):
            await mcp_utils.handle_list_tools_result(project_id=project_id, mcp_enabled_only=True)
    finally:
        mcp_utils.current_user_ctx.reset(token)


@pytest.mark.asyncio
async def test_should_keep_global_server_free_of_exclusion_meta(monkeypatch):
    """The global server is the editor plane — its contract must not change."""
    user_id = uuid4()
    good = _fake_flow("good_tool", None)
    bad = _fake_flow("bad_tool", None)
    good.user_id = bad.user_id = user_id

    def selective_schema(flow):
        if flow.name == "bad_tool":
            msg = "hash mismatch"
            raise CustomComponentValidationError(msg)
        return {"type": "object", "properties": {}}

    monkeypatch.setattr(mcp_utils, "session_scope", lambda: _FakeSessionContext(_FakeSession([good, bad])))
    monkeypatch.setattr(mcp_utils, "json_schema_from_flow", selective_schema)

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=user_id))
    try:
        tools = await mcp_utils.handle_list_tools()
    finally:
        mcp_utils.current_user_ctx.reset(token)

    assert [tool.name for tool in tools] == ["good_tool"]


@pytest.mark.asyncio
async def test_should_not_raise_when_project_legitimately_has_no_flows(monkeypatch):
    """An empty project is not a failure and must keep returning an empty list."""
    project_id = uuid4()
    user_id = uuid4()
    _patch_list_tools(monkeypatch, [])

    token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=user_id))
    try:
        tools = await mcp_utils.handle_list_tools(project_id=project_id, mcp_enabled_only=True)
    finally:
        mcp_utils.current_user_ctx.reset(token)

    assert tools == []
