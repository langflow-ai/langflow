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


def _make_flow(*, owner_id: UUID, public: bool = False, data: dict[str, Any] | None = None):
    """Build a flow stub with the attributes build_flow reads."""
    from langflow.services.database.models.flow.model import AccessTypeEnum

    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        workspace_id=None,
        folder_id=None,
        data=data,
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
async def test_build_flow_non_owner_cannot_override_flow_data(patch_build_flow, monkeypatch):
    """Non-owner with execute access cannot supply alternate graph data in the body.

    This asserted a 404 until LE-1905. Denying the override broke the
    Playground, which posts the canvas data on every run: a non-owner with
    execute permission was told the flow did not exist. The override is now
    gated on ``flow:write``; an execute-only caller has it dropped and runs
    the stored graph. The security property is unchanged and still asserted
    here: the caller-supplied graph never runs.
    """
    from langflow.api.v1 import chat as chat_module
    from langflow.api.v1.schemas import FlowDataRequest
    from langflow.services.authorization import flow_data_override

    async def _deny_write(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="forbidden")

    # Execute-only caller: the flow:write gate denies the override.
    monkeypatch.setattr(flow_data_override, "ensure_flow_permission", _deny_write)

    user = _make_user()
    flow = _make_flow(owner_id=uuid4(), public=False)
    patch_build_flow["read_flow"] = flow
    override = FlowDataRequest(nodes=[{"id": "n1"}], edges=[])

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=user,
        queue_service=_make_queue_service(),
        data=override,
    )
    # The run proceeds with the stored graph; the override is dropped.
    assert result == {"job_id": "fake-job-id"}
    assert patch_build_flow["start_kwargs"]["data"] is None


@pytest.mark.asyncio
async def test_build_flow_write_holder_may_override_someone_elses_flow(patch_build_flow, monkeypatch):
    """A caller holding ``flow:write`` may run an unsaved graph they cannot save.

    Overriding the stored graph is an edit expressed at run time, so it is
    gated on ``flow:write`` rather than ownership (LE-1905): a caller who can
    persist the graph can already PATCH it and run it, so honoring the unsaved
    copy grants nothing new.
    """
    from langflow.api.v1 import chat as chat_module
    from langflow.api.v1.schemas import FlowDataRequest
    from langflow.services.authorization import flow_data_override

    async def _allow_write(*_args, **_kwargs):
        return None

    # Non-owner, but the flow:write gate allows the override.
    monkeypatch.setattr(flow_data_override, "ensure_flow_permission", _allow_write)

    async def allow_inline(_data, *, is_superuser):
        assert is_superuser is False

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", allow_inline)

    user = _make_user()
    flow = _make_flow(owner_id=uuid4(), public=False)
    patch_build_flow["read_flow"] = flow
    override = FlowDataRequest(nodes=[{"id": "n1"}], edges=[])

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=user,
        queue_service=_make_queue_service(),
        data=override,
    )
    assert result == {"job_id": "fake-job-id"}
    # The caller's graph is honored, not the stored one.
    assert patch_build_flow["start_kwargs"]["data"] is override


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


def _stored_graph(source: str) -> dict[str, Any]:
    """A stored graph whose single node carries component source in the usual place."""
    return {
        "nodes": [
            {
                "id": "ChatInput-1",
                "data": {
                    "id": "ChatInput-1",
                    "type": "ChatInput",
                    "node": {"template": {"code": {"value": source}}},
                },
            }
        ],
        "edges": [],
        "viewport": None,
    }


@pytest.mark.asyncio
async def test_build_flow_admin_only_blocks_non_superuser_stored_custom_code(patch_build_flow, monkeypatch):
    """Stored graph data must face the same caller-aware policy as inline request data.

    A regular user could otherwise persist modified component source through the
    ordinary flow-write API and then execute it by building with an empty body,
    because the stored branch only ran the caller-agnostic global validator.
    """
    from langflow.api.v1 import chat as chat_module
    from lfx.utils.flow_validation import CustomComponentValidationError

    owner = _make_user()
    flow = _make_flow(owner_id=owner.id, public=False, data=_stored_graph("# attacker source"))
    patch_build_flow["read_flow"] = flow
    seen: dict[str, Any] = {}

    async def reject_custom_code(data, *, is_superuser):
        seen["validated"] = data
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
        )

    assert excinfo.value.status_code == 400
    assert "restricted to administrators" in excinfo.value.detail
    assert seen["validated"] == flow.data
    assert patch_build_flow["start_kwargs"] is None


@pytest.mark.asyncio
async def test_build_flow_admin_only_passes_sanitized_stored_data_to_worker(patch_build_flow, monkeypatch):
    """The worker must receive the server-trusted copy, not the stored bytes."""
    from langflow.api.v1 import chat as chat_module

    owner = _make_user()
    stored = _stored_graph("# stored source")
    flow = _make_flow(owner_id=owner.id, public=False, data=stored)
    patch_build_flow["read_flow"] = flow
    sanitized = _stored_graph("# trusted server source")

    async def sanitize(_data, *, is_superuser):
        assert is_superuser is False
        return sanitized

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", sanitize)

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=owner,
        queue_service=_make_queue_service(),
    )

    assert result == {"job_id": "fake-job-id"}
    forwarded = patch_build_flow["start_kwargs"]["data"]
    assert forwarded is not None
    assert forwarded.model_dump()["nodes"] == sanitized["nodes"]
    # The stored row is never mutated by the sanitizer.
    assert flow.data["nodes"][0]["data"]["node"]["template"]["code"]["value"] == "# stored source"


@pytest.mark.asyncio
async def test_build_flow_stored_data_permissive_policy_still_builds_from_db(patch_build_flow, monkeypatch):
    """When no caller-aware restriction applies the build keeps loading from the DB."""
    from langflow.api.v1 import chat as chat_module

    owner = _make_user()
    flow = _make_flow(owner_id=owner.id, public=False, data=_stored_graph("# stored source"))
    patch_build_flow["read_flow"] = flow
    seen: dict[str, Any] = {}

    async def permissive(data, *, is_superuser):
        seen["validated"] = data
        assert is_superuser is False

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", permissive)

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=owner,
        queue_service=_make_queue_service(),
    )

    assert result == {"job_id": "fake-job-id"}
    assert seen["validated"] == flow.data
    assert patch_build_flow["start_kwargs"]["data"] is None


@pytest.mark.asyncio
async def test_build_flow_admin_only_keeps_superuser_stored_custom_code(patch_build_flow, monkeypatch):
    """Superusers keep the documented exception on the stored path too."""
    from langflow.api.v1 import chat as chat_module

    owner = _make_user(is_superuser=True)
    flow = _make_flow(owner_id=owner.id, public=False, data=_stored_graph("# admin source"))
    patch_build_flow["read_flow"] = flow
    seen: dict[str, Any] = {}

    async def preserve_superuser_data(data, *, is_superuser):
        seen["validated"] = data
        assert is_superuser is True

    monkeypatch.setattr(chat_module, "prepare_flow_build_for_user", preserve_superuser_data)

    result = await chat_module.build_flow(
        flow_id=flow.id,
        background_tasks=None,
        current_user=owner,
        queue_service=_make_queue_service(),
    )

    assert result == {"job_id": "fake-job-id"}
    assert seen["validated"] == flow.data
    assert patch_build_flow["start_kwargs"]["data"] is None


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
