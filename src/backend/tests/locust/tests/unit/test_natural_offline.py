"""Fast offline contracts for Natural fixtures.

Whole-graph execution belongs to the integration layer: importing these large
starter graphs starts shared runtime executors, and Python 3.14's
``asyncio.run`` shutdown can wait indefinitely for their executor lifecycle.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import HumanMessage

from tests.locust.langflow_runtime.components.perf_echo_agent import _PerfEchoChatModel
from tests.locust.langflow_runtime.components.perf_mock_llm import PERF_MOCK_LLM_MARKER
from tests.locust.langflow_runtime.flows.defaults import FLOWS_DIR

STUBBED_OFFLINE_SHAPES = (
    "natural_basic_prompting__external_stubbed",
    "natural_simple_agent__external_stubbed",
    "natural_memory_chatbot__external_stubbed",
    "natural_vector_store_rag__external_stubbed",
    "natural_file_parser_agent__external_stubbed",
)

EMBEDDING_SHAPES = (
    "natural_memory_chatbot__external_stubbed",
    "natural_memory_chatbot__external_live",
    "natural_vector_store_rag__external_stubbed",
    "natural_vector_store_rag__external_live",
)


def test_echo_agent_model_echoes_latest_user_input() -> None:
    result = _PerfEchoChatModel().invoke([HumanMessage(content="earlier"), HumanMessage(content="perf-chat-turn-7")])

    assert result.content == "perf-chat-turn-7"


def _flow_entry(flow_id: str) -> dict[str, Any]:
    manifest = json.loads((FLOWS_DIR / "fixture_index.json").read_text(encoding="utf-8"))
    for entry in manifest["flows"]:
        if entry["id"] == flow_id:
            return entry
    msg = f"missing fixture_index entry {flow_id}"
    raise AssertionError(msg)


def _fixture(flow_id: str) -> dict[str, Any]:
    entry = _flow_entry(flow_id)
    return json.loads((FLOWS_DIR / entry["fixture_path"]).read_text(encoding="utf-8"))


@pytest.mark.parametrize("flow_id", STUBBED_OFFLINE_SHAPES)
def test_natural_stubbed_component_sources_compile(flow_id: str) -> None:
    """Catch malformed source injection without booting a Langflow runtime."""
    payload = _fixture(flow_id)
    compiled = 0
    for node in payload.get("data", {}).get("nodes", []):
        data = node.get("data") or {}
        code = (((data.get("node") or {}).get("template") or {}).get("code") or {}).get("value")
        if not code:
            continue
        compile(str(code), f"{flow_id}:{data.get('type', 'unknown')}", "exec")
        compiled += 1
    assert compiled > 0


@pytest.mark.parametrize(
    "flow_id",
    [flow_id for flow_id in STUBBED_OFFLINE_SHAPES if "basic_prompting" not in flow_id],
)
def test_stubbed_agent_keeps_real_agent_and_replaces_only_model_edge(flow_id: str) -> None:
    payload = _fixture(flow_id)
    agent = next(node for node in payload["data"]["nodes"] if node.get("data", {}).get("type") == "Agent")
    source = agent["data"]["node"]["template"]["code"]["value"]
    assert "create_agent(" in source
    assert "class AgentComponent" in source
    assert "def _resolve_selected_model(self):\n        return _perf_model()" in source
    assert "def _get_llm(self):\n        return _perf_model()" in source
    assert PERF_MOCK_LLM_MARKER in source


@pytest.mark.parametrize(
    "flow_id",
    EMBEDDING_SHAPES,
)
def test_natural_embeddings_are_local_stable_and_non_global(flow_id: str) -> None:
    payload = _fixture(flow_id)
    node_type = "MemoryBase" if "memory_chatbot" in flow_id else "Knowledge"
    node = next(node for node in payload["data"]["nodes"] if node.get("data", {}).get("type") == node_type)
    source = node["data"]["node"]["template"]["code"]["value"]
    assert "_perf_hashlib.sha256" in source
    assert "_PerfDeterministicEmbeddings" in source
    assert "_perf_um.get_embeddings" not in source
