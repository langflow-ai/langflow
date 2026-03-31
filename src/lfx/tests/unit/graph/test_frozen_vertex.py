import copy
import json
from pathlib import Path

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
