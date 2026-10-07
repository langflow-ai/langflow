import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from lfx.graph import Graph
from lfx.services.authorization import PUBLIC_ANONYMOUS_ACTOR_ID
from lfx.services.cache.utils import CacheMiss


@pytest.fixture
def simple_chat_flow():
    """Load the simple chat JSON test data."""
    test_data_dir = Path(__file__).parent.parent.parent / "data"
    json_path = test_data_dir / "simple_chat_no_llm.json"
    with json_path.open() as f:
        return json.load(f)


@pytest.fixture
def frozen_chat_flow(simple_chat_flow):
    """Create a flow with a frozen vertex (ChatOutput)."""
    flow = copy.deepcopy(simple_chat_flow)
    for node in flow["data"]["nodes"]:
        if node["data"]["node"].get("display_name") == "Chat Output":
            node["data"]["node"]["frozen"] = True
    return flow


@pytest.mark.asyncio
async def test_frozen_vertex_rebuilds_when_no_cache_service(frozen_chat_flow):
    """A frozen vertex should rebuild gracefully when no cache service is available.

    When running standalone (no server), chat_service is None. The fallback
    get_cache_func should return CacheMiss so frozen vertices fall through
    to the build path instead of crashing with TypeError.

    Reproduces: https://github.com/langflow-ai/langflow/issues/12408
    """
    graph = Graph.from_payload(frozen_chat_flow)

    # Verify the vertex is actually frozen
    frozen_vertices = [v for v in graph.vertices if v.frozen]
    assert len(frozen_vertices) > 0, "Expected at least one frozen vertex"

    # Use arun which goes through process(), the same path as arun_flow_from_json
    results = await graph.arun(inputs=[{"input_value": "hello"}])
    assert len(results) > 0


@pytest.mark.asyncio
async def test_frozen_cached_vertex_reauthorizes_before_cache_lookup(monkeypatch):
    """A policy revocation must stop a frozen vertex before its prior result is reused."""
    graph = Graph()
    vertex = MagicMock()
    vertex.id = "cached-model"
    vertex.display_name = "Cached Model"
    vertex.frozen = True
    vertex.is_loop = False
    vertex.require_model_provider_policy.side_effect = AssertionError("stale synchronous provider check")
    vertex.arequire_model_provider_policy = AsyncMock(side_effect=RuntimeError("provider revoked"))
    monkeypatch.setattr(graph, "get_vertex", lambda _vertex_id: vertex)
    get_cache = AsyncMock(side_effect=AssertionError("cache read before provider reauthorization"))
    event_manager = MagicMock()

    with pytest.raises(RuntimeError, match="provider revoked"):
        await graph.build_vertex(
            vertex.id,
            get_cache=get_cache,
            user_id="user-1",
            event_manager=event_manager,
        )

    vertex.arequire_model_provider_policy.assert_awaited_once_with("user-1", event_manager=event_manager)
    vertex.require_model_provider_policy.assert_not_called()
    get_cache.assert_not_awaited()


def _mock_built_vertex(vertex_id, *, frozen):
    """A mock vertex that can go through Graph.build_vertex's cache write/read paths."""
    vertex = MagicMock()
    vertex.id = vertex_id
    vertex.display_name = "Text Output"
    vertex.frozen = frozen
    vertex.is_loop = False
    vertex.arequire_model_provider_policy = AsyncMock()
    vertex.build = AsyncMock()
    vertex.result = MagicMock()
    vertex.built = True
    vertex.results = {"text": "cached-output"}
    vertex.artifacts = {}
    vertex.built_object = "cached-output"
    vertex.built_result = "cached-output"
    vertex.full_data = {}
    vertex.built_object_repr.return_value = "cached-output"
    return vertex


def _dict_cache(store):
    """get_cache/set_cache pair backed by a shared dict, mimicking the shared cache service."""

    async def get_cache(key):
        return store.get(key, CacheMiss())

    async def set_cache(key, data):
        store[key] = {"result": data}
        return True

    return get_cache, set_cache


class TestVertexResultCacheKey:
    def test_scoped_to_authenticated_user(self):
        graph = Graph(user_id="user-a", flow_id="flow-1")
        assert graph._vertex_result_cache_key("vertex-1") == "user:user-a:vertex-1"

    def test_distinct_users_get_distinct_keys(self):
        victim = Graph(user_id="victim-id", flow_id="flow-1")
        attacker = Graph(user_id="attacker-id", flow_id="flow-2")
        assert victim._vertex_result_cache_key("shared-vertex") != attacker._vertex_result_cache_key("shared-vertex")

    def test_end_user_identity_included_for_serving_plane(self):
        graph = Graph(user_id="service-account", flow_id="flow-1")
        graph.end_user_id = "end-user-1"
        assert graph._vertex_result_cache_key("vertex-1") == "user:service-account:end-user:end-user-1:vertex-1"

    def test_anonymous_public_actor_scoped_to_flow(self):
        graph = Graph(user_id=str(PUBLIC_ANONYMOUS_ACTOR_ID), flow_id="public-flow")
        assert graph._vertex_result_cache_key("vertex-1") == "flow:public-flow:vertex-1"

    def test_flow_scope_when_no_user(self):
        graph = Graph(flow_id="flow-1")
        assert graph._vertex_result_cache_key("vertex-1") == "flow:flow-1:vertex-1"

    def test_bare_key_without_principal_context(self):
        graph = Graph()
        assert graph._vertex_result_cache_key("vertex-1") == "vertex-1"


@pytest.mark.asyncio
async def test_vertex_cache_write_is_scoped_to_authenticated_user(monkeypatch):
    """The cache write after a real build must not land under the bare vertex id (H1-3985565)."""
    store = {}
    get_cache, set_cache = _dict_cache(store)
    graph = Graph(user_id="victim-id", flow_id="victim-flow")
    vertex = _mock_built_vertex("shared-vertex-id", frozen=False)
    monkeypatch.setattr(graph, "get_vertex", lambda _vertex_id: vertex)

    await graph.build_vertex(vertex.id, get_cache=get_cache, set_cache=set_cache, user_id="victim-id")

    assert list(store) == ["user:victim-id:shared-vertex-id"]


@pytest.mark.asyncio
async def test_frozen_vertex_cannot_read_another_users_cached_result(monkeypatch):
    """A frozen vertex reusing another tenant's vertex id must miss the cache and rebuild."""
    store = {}
    get_cache, set_cache = _dict_cache(store)

    victim_graph = Graph(user_id="victim-id", flow_id="victim-flow")
    victim_vertex = _mock_built_vertex("shared-vertex-id", frozen=False)
    monkeypatch.setattr(victim_graph, "get_vertex", lambda _vertex_id: victim_vertex)
    await victim_graph.build_vertex(victim_vertex.id, get_cache=get_cache, set_cache=set_cache, user_id="victim-id")

    attacker_graph = Graph(user_id="attacker-id", flow_id="attacker-flow")
    attacker_vertex = _mock_built_vertex("shared-vertex-id", frozen=True)
    monkeypatch.setattr(attacker_graph, "get_vertex", lambda _vertex_id: attacker_vertex)
    await attacker_graph.build_vertex(
        attacker_vertex.id, get_cache=get_cache, set_cache=set_cache, user_id="attacker-id"
    )

    # The frozen vertex missed the victim's entry and rebuilt instead of restoring it.
    attacker_vertex.build.assert_awaited_once()
    assert attacker_vertex.result.used_frozen_result is not True
    assert set(store) == {"user:victim-id:shared-vertex-id", "user:attacker-id:shared-vertex-id"}


@pytest.mark.asyncio
async def test_frozen_vertex_restores_own_users_cached_result(monkeypatch):
    """The frozen cache-hit path keeps working within the same principal scope."""
    store = {}
    get_cache, set_cache = _dict_cache(store)
    graph = Graph(user_id="user-1", flow_id="flow-1")

    first_vertex = _mock_built_vertex("vertex-1", frozen=False)
    monkeypatch.setattr(graph, "get_vertex", lambda _vertex_id: first_vertex)
    await graph.build_vertex(first_vertex.id, get_cache=get_cache, set_cache=set_cache, user_id="user-1")

    frozen_vertex = _mock_built_vertex("vertex-1", frozen=True)
    frozen_vertex.built_object = "uncached-output"
    monkeypatch.setattr(graph, "get_vertex", lambda _vertex_id: frozen_vertex)
    await graph.build_vertex(frozen_vertex.id, get_cache=get_cache, set_cache=set_cache, user_id="user-1")

    frozen_vertex.build.assert_not_awaited()
    assert frozen_vertex.result.used_frozen_result is True
    assert frozen_vertex.built_object == "cached-output"
