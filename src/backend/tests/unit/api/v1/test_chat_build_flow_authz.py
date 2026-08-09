"""Route-level tests for the share-aware load + deny->404 path in ``build_flow``.

The handler was historically owner-OR-public scoped, which silently blocked
shared-flow execution by non-owners even when the registered authorization
plugin would have allowed it. These tests pin the new behavior:

* Non-owner request loaded via the share-aware helper (plugin decides)
* Plugin deny translated to 404 so callers can't enumerate UUIDs via 403 vs 404
* PUBLIC fallback still works when the share-aware load returns None
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException


class _FakeSession:
    """Minimal async session that returns canned exec results."""

    def __init__(self, exec_results: list[Any] | None = None) -> None:
        self._exec_results = exec_results or []

    async def exec(self, _stmt):
        rows = self._exec_results.pop(0) if self._exec_results else []
        return _ExecResult(rows)


class _ExecResult:
    def __init__(self, rows: list[Any]):
        self._rows = list(rows)

    def first(self):
        return self._rows[0] if self._rows else None


def _make_user(*, is_superuser: bool = False) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), is_superuser=is_superuser, username="u")


def _make_flow(*, owner_id: UUID, public: bool = False):
    """Build a flow stub with the attributes build_flow reads."""
    from langflow.services.database.models.flow.model import AccessTypeEnum

    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        workspace_id=None,
        folder_id=None,
        data=None,
        access_type=AccessTypeEnum.PUBLIC if public else AccessTypeEnum.PRIVATE,
    )


@pytest.fixture
def patch_build_flow(monkeypatch):
    """Install fakes for session_scope, _read_flow, ensure_flow_permission, start_flow_build."""
    from langflow.api.v1 import chat as chat_module

    state: dict[str, Any] = {
        "session_exec": [],
        "read_flow": None,
        "ensure_raises": None,
        "start_kwargs": None,
    }

    @asynccontextmanager
    async def fake_session_scope():
        yield _FakeSession(state["session_exec"])

    async def fake_read_flow(_session, _flow_id, _user_id):
        return state["read_flow"]

    async def fake_ensure(*_args, **_kwargs):
        if state["ensure_raises"] is not None:
            raise state["ensure_raises"]

    async def fake_start_build(**kwargs):
        state["start_kwargs"] = kwargs
        return "fake-job-id"

    monkeypatch.setattr(chat_module, "session_scope", fake_session_scope)

    # _read_flow is imported lazily inside build_flow; patch the helper module.
    from langflow.api.v1 import flows_helpers

    monkeypatch.setattr(flows_helpers, "_read_flow", fake_read_flow)
    monkeypatch.setattr(chat_module, "ensure_flow_permission", fake_ensure)
    monkeypatch.setattr(chat_module, "start_flow_build", fake_start_build)

    # validate_flow_for_current_settings is called when flow.data exists; we
    # leave flow.data=None so it's not invoked. queue_service.register_job_owner
    # is awaited at the end — provide a stub queue service in the call.

    return state


def _make_queue_service():
    """Stub the queue service object passed via Depends in the real route."""

    async def register(_job_id, _user_id):
        return None

    return SimpleNamespace(register_job_owner=register)


# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_build_flow_owner_succeeds(patch_build_flow):
    """Owner can build their own private flow — the historical happy path."""
    from langflow.api.v1 import chat as chat_module

    owner = _make_user()
    flow = _make_flow(owner_id=owner.id, public=False)
    patch_build_flow["read_flow"] = flow

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=owner,
        queue_service=_make_queue_service(),
    )
    assert result == {"job_id": "fake-job-id"}


@pytest.mark.asyncio
async def test_build_flow_shared_private_non_owner_succeeds(patch_build_flow):
    """Non-owner can build a private shared flow when the plugin allows execute."""
    from langflow.api.v1 import chat as chat_module

    user = _make_user()
    flow = _make_flow(owner_id=uuid4(), public=False)
    patch_build_flow["read_flow"] = flow

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=user,
        queue_service=_make_queue_service(),
    )
    assert result == {"job_id": "fake-job-id"}


@pytest.mark.asyncio
async def test_build_flow_non_owner_cannot_override_flow_data(patch_build_flow):
    """Non-owner with execute access cannot supply alternate graph data in the body."""
    from langflow.api.v1 import chat as chat_module
    from langflow.api.v1.schemas import FlowDataRequest

    user = _make_user()
    flow = _make_flow(owner_id=uuid4(), public=False)
    patch_build_flow["read_flow"] = flow
    override = FlowDataRequest(nodes=[{"id": "n1"}], edges=[])

    with pytest.raises(HTTPException) as excinfo:
        await chat_module.build_flow(
            flow_id=flow.id,
            background_tasks=None,
            current_user=user,
            queue_service=_make_queue_service(),
            data=override,
        )
    assert excinfo.value.status_code == 404
    assert f"Flow with id {flow.id} not found" in excinfo.value.detail


@pytest.mark.asyncio
async def test_build_flow_owner_can_override_flow_data(patch_build_flow, monkeypatch):
    """Owner may still pass flow data overrides in the build request."""
    from langflow.api.v1 import chat as chat_module
    from langflow.api.v1.schemas import FlowDataRequest

    async def allow_inline(_data, *, is_superuser):
        assert is_superuser is False

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", allow_inline)

    owner = _make_user()
    flow = _make_flow(owner_id=owner.id, public=False)
    patch_build_flow["read_flow"] = flow
    override = FlowDataRequest(nodes=[{"id": "n1"}], edges=[])

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=owner,
        queue_service=_make_queue_service(),
        data=override,
    )
    assert result == {"job_id": "fake-job-id"}


@pytest.mark.asyncio
async def test_build_flow_admin_only_blocks_non_superuser_inline_custom_code(patch_build_flow, monkeypatch):
    """Admin-only policy is applied before owner-supplied inline graph data reaches the build worker."""
    from langflow.api.v1 import chat as chat_module
    from langflow.api.v1.schemas import FlowDataRequest
    from lfx.utils.flow_validation import CustomComponentValidationError

    owner = _make_user()
    flow = _make_flow(owner_id=owner.id, public=False)
    patch_build_flow["read_flow"] = flow
    override = FlowDataRequest(nodes=[{"id": "custom"}], edges=[])

    async def reject_custom_code(_data, *, is_superuser):
        assert is_superuser is False
        message = "custom components are restricted to administrators"
        raise CustomComponentValidationError(message)

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", reject_custom_code)

    with pytest.raises(HTTPException) as excinfo:
        await chat_module.build_flow(
            flow_id=flow.id,
            background_tasks=None,
            current_user=owner,
            queue_service=_make_queue_service(),
            data=override,
        )

    assert excinfo.value.status_code == 400
    assert "restricted to administrators" in excinfo.value.detail
    assert patch_build_flow["start_kwargs"] is None


@pytest.mark.asyncio
async def test_build_flow_admin_only_passes_sanitized_template_to_worker(patch_build_flow, monkeypatch):
    """A known template remains usable, but the worker receives the server-trusted payload."""
    from langflow.api.v1 import chat as chat_module
    from langflow.api.v1.schemas import FlowDataRequest

    owner = _make_user()
    flow = _make_flow(owner_id=owner.id, public=False)
    patch_build_flow["read_flow"] = flow
    override = FlowDataRequest(nodes=[{"id": "known", "data": {"source": "request"}}], edges=[])
    sanitized = {"nodes": [{"id": "known", "data": {"source": "server"}}], "edges": [], "viewport": None}

    async def sanitize(_data, *, is_superuser):
        assert is_superuser is False
        return sanitized

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", sanitize)

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=owner,
        queue_service=_make_queue_service(),
        data=override,
    )

    assert result == {"job_id": "fake-job-id"}
    assert patch_build_flow["start_kwargs"]["data"].model_dump() == sanitized
    assert override.nodes[0]["data"]["source"] == "request"


@pytest.mark.asyncio
async def test_build_flow_admin_only_keeps_superuser_inline_custom_code(patch_build_flow, monkeypatch):
    """The operator's admin-only setting preserves the documented superuser exception."""
    from langflow.api.v1 import chat as chat_module
    from langflow.api.v1.schemas import FlowDataRequest

    owner = _make_user(is_superuser=True)
    flow = _make_flow(owner_id=owner.id, public=False)
    patch_build_flow["read_flow"] = flow
    override = FlowDataRequest(nodes=[{"id": "custom"}], edges=[])
    seen: dict[str, Any] = {}

    async def preserve_superuser_data(data, *, is_superuser):
        assert is_superuser is True
        seen["validated"] = data

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", preserve_superuser_data)

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=owner,
        queue_service=_make_queue_service(),
        data=override,
    )

    assert result == {"job_id": "fake-job-id"}
    assert seen["validated"] == override.model_dump()
    assert patch_build_flow["start_kwargs"]["data"] is override


@pytest.mark.asyncio
async def test_legacy_vertices_route_passes_only_sanitized_inline_data(monkeypatch):
    """The still-routed legacy graph cache cannot bypass the inline-data policy."""
    from langflow.api.v1 import chat as chat_module
    from langflow.api.v1.schemas import FlowDataRequest

    owner = _make_user()
    flow = _make_flow(owner_id=owner.id)
    original = FlowDataRequest(nodes=[{"id": "known", "data": {"source": "request"}}], edges=[])
    sanitized = {"nodes": [{"id": "known", "data": {"source": "server"}}], "edges": [], "viewport": None}
    seen: dict[str, Any] = {}

    async def ensure_allowed(*_args, **_kwargs):
        return None

    async def sanitize(_data, *, is_superuser):
        assert is_superuser is False
        return sanitized

    graph = MagicMock()
    graph.prepare.return_value = graph
    graph.vertices = []
    graph.vertices_to_run = set()
    graph.first_layer = []
    graph.run_id = None
    graph.set_run_id.side_effect = lambda value: setattr(graph, "run_id", value)

    async def build_from_data(*, graph_data, **_kwargs):
        seen["graph_data"] = graph_data
        return graph

    chat_service = SimpleNamespace(set_cache=AsyncMock())
    monkeypatch.setattr(chat_module, "ensure_flow_permission", ensure_allowed)
    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", sanitize)
    monkeypatch.setattr(chat_module, "build_and_cache_graph_from_data", build_from_data)
    monkeypatch.setattr(chat_module, "get_chat_service", lambda: chat_service)
    monkeypatch.setattr(chat_module, "get_telemetry_service", MagicMock)
    monkeypatch.setattr(chat_module, "get_top_level_vertices", lambda *_args: [])

    await chat_module.retrieve_vertices_order(
        flow_id=flow.id,
        background_tasks=SimpleNamespace(add_task=lambda *_args, **_kwargs: None),
        data=original,
        session=_FakeSession([[flow]]),
        current_user=owner,
    )

    assert seen["graph_data"] == sanitized
    assert original.nodes[0]["data"]["source"] == "request"


@pytest.mark.asyncio
async def test_build_flow_plugin_deny_returns_404_not_403(patch_build_flow):
    """ensure_flow_permission raising 403 must surface as 404 (UUID privacy)."""
    from langflow.api.v1 import chat as chat_module

    user = _make_user()
    # _read_flow finds the flow (cross-user-fetch enabled in plugin would do this)
    flow = _make_flow(owner_id=uuid4(), public=False)  # owned by someone else
    patch_build_flow["read_flow"] = flow
    patch_build_flow["ensure_raises"] = HTTPException(status_code=403, detail="forbidden")

    with pytest.raises(HTTPException) as excinfo:
        await chat_module.build_flow(
            flow_id=flow.id,
            background_tasks=None,
            current_user=user,
            queue_service=_make_queue_service(),
        )
    # Must be 404 — not 403 — so callers can't probe for resource existence.
    assert excinfo.value.status_code == 404
    assert f"Flow with id {flow.id} not found" in excinfo.value.detail


@pytest.mark.asyncio
async def test_build_flow_unknown_flow_returns_404(patch_build_flow):
    """Both share-aware and PUBLIC fallback miss → 404 before plugin is consulted."""
    from langflow.api.v1 import chat as chat_module

    user = _make_user()
    flow_id = uuid4()
    patch_build_flow["read_flow"] = None
    patch_build_flow["session_exec"] = [[]]  # PUBLIC fallback also empty

    with pytest.raises(HTTPException) as excinfo:
        await chat_module.build_flow(
            flow_id=flow_id,
            background_tasks=None,
            current_user=user,
            queue_service=_make_queue_service(),
        )
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_build_flow_public_fallback_when_share_aware_misses(patch_build_flow):
    """Plugin can't see the flow (returns None), but PUBLIC fallback finds it."""
    from langflow.api.v1 import chat as chat_module

    user = _make_user()
    owner_id = uuid4()
    public_flow = _make_flow(owner_id=owner_id, public=True)
    patch_build_flow["read_flow"] = None  # share-aware load misses
    patch_build_flow["session_exec"] = [[public_flow]]  # PUBLIC query hits

    result = await chat_module.build_flow(
        flow_id=public_flow.id,
        background_tasks=None,
        current_user=user,
        queue_service=_make_queue_service(),
    )
    assert result == {"job_id": "fake-job-id"}


@pytest.mark.asyncio
async def test_build_flow_non_403_exception_not_converted(patch_build_flow):
    """A non-403 exception from ensure_flow_permission (e.g. 500) must pass through."""
    from langflow.api.v1 import chat as chat_module

    user = _make_user()
    flow = _make_flow(owner_id=user.id, public=False)
    patch_build_flow["read_flow"] = flow
    # 500 from upstream — deny_to_404 only rewrites 403.
    patch_build_flow["ensure_raises"] = HTTPException(status_code=500, detail="upstream")

    with pytest.raises(HTTPException) as excinfo:
        await chat_module.build_flow(
            flow_id=flow.id,
            background_tasks=None,
            current_user=user,
            queue_service=_make_queue_service(),
        )
    # deny_to_404 only converts 403; other status codes preserved (though detail
    # is sanitized to the supplied default).
    assert excinfo.value.status_code == 500
