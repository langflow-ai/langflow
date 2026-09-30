"""Unit tests for the opt-in warm flow-graph registry.

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


async def test_warm_deepcopy_none_when_disabled(monkeypatch):
    """warm_deepcopy is inert when the registry is disabled -> callers rebuild cold."""
    from langflow.api import warm_graph

    monkeypatch.setattr(warm_graph, "is_warm_registry_enabled", lambda _settings: False)
    assert await warm_graph.warm_deepcopy("any-id", expected_version="", user_id="u", session_id=None) is None
