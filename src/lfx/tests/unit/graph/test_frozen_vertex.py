import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from lfx.graph import Graph


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
