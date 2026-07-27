"""Unit tests for the warm flow-graph registry and PROD workflow host.

These cover the registry bookkeeping (add / get / version / evict / active_ids)
and the host's not-found guard without building a real ``Graph`` or touching the
DB — ``WarmGraphRegistry._build`` is patched to a sentinel so the tests stay fast
and hermetic. Reconcile-against-DB is covered by integration tests.
"""

from __future__ import annotations

import pytest
from langflow.services.warm_registry.service import WarmGraphRegistry


class _FakeGraph:
    """Stand-in for a built ``Graph`` template."""

    def __init__(self, flow_id: str, name: str | None) -> None:
        self.flow_id = flow_id
        self.name = name


@pytest.fixture
def registry(monkeypatch):
    """A registry whose ``_build`` returns a cheap sentinel instead of a real Graph."""
    monkeypatch.setattr(
        WarmGraphRegistry,
        "_build",
        staticmethod(lambda flow_id, name, data: _FakeGraph(flow_id, name)),  # noqa: ARG005
    )
    return WarmGraphRegistry()


async def test_add_and_get(registry):
    await registry.add("flow-1", "First", {"nodes": []}, "v1")
    hit = registry.get("flow-1")
    assert hit is not None
    template, version = hit
    assert isinstance(template, _FakeGraph)
    assert template.flow_id == "flow-1"
    assert version == "v1"


async def test_get_missing_returns_none(registry):
    assert registry.get("nope") is None
    assert registry.version_of("nope") is None


async def test_add_overwrites_version(registry):
    await registry.add("flow-1", "First", {}, "v1")
    first_template = registry.get("flow-1")[0]
    await registry.add("flow-1", "First", {}, "v2")
    assert registry.version_of("flow-1") == "v2"
    # A rebuild produces a fresh template object.
    assert registry.get("flow-1")[0] is not first_template


async def test_evict(registry):
    await registry.add("flow-1", "First", {}, "v1")
    assert len(registry) == 1
    await registry.evict("flow-1")
    assert registry.get("flow-1") is None
    assert len(registry) == 0


async def test_evict_missing_is_noop(registry):
    await registry.evict("ghost")  # must not raise
    assert len(registry) == 0


async def test_active_ids(registry):
    await registry.add("a", None, {}, "v1")
    await registry.add("b", None, {}, "v1")
    assert registry.active_ids() == {"a", "b"}


async def test_get_does_not_copy_template(registry):
    """``get`` returns the shared template; the host owns the deepcopy."""
    await registry.add("flow-1", "First", {}, "v1")
    assert registry.get("flow-1")[0] is registry.get("flow-1")[0]


async def test_host_get_flow_404_when_absent(monkeypatch):
    """A flow neither cached nor warmable -> 404 FLOW_NOT_FOUND (the pulled-flow guard)."""
    from fastapi import HTTPException
    from langflow.api.v2 import warm_workflow_host as mod

    empty = WarmGraphRegistry()
    monkeypatch.setattr(mod, "get_warm_registry", lambda: empty, raising=False)

    async def _no_warm(_flow_id):
        return None

    # ``warm_one`` and ``get_warm_registry`` are imported inside get_flow; patch the source modules.
    import langflow.services.warm_registry.reconcile as reconcile_mod
    import langflow.services.warm_registry.service as service_mod

    monkeypatch.setattr(service_mod, "get_warm_registry", lambda: empty)
    monkeypatch.setattr(reconcile_mod, "warm_one", _no_warm)

    host = mod.WarmWorkflowHost()
    with pytest.raises(HTTPException) as exc:
        await host.get_flow("missing-id", caller=None)
    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "FLOW_NOT_FOUND"


def test_run_user_id_from_caller():
    from types import SimpleNamespace

    from langflow.api.v2.warm_workflow_host import WarmWorkflowHost

    host = WarmWorkflowHost()
    assert host._run_user_id(SimpleNamespace(id="user-42")) == "user-42"
    assert host._run_user_id(SimpleNamespace(id=None)) is None
    assert host._run_user_id(object()) is None
