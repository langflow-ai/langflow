"""Validate the exported Nebius example without starting an HTTP server."""

import json
from pathlib import Path

from lfx.graph import Graph

_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "nebius-serverless-chat.json"


def test_example_contains_no_credentials_and_preserves_connections():
    """Preserve browser edges, blank secrets and Playground message storage."""
    payload = json.loads(_EXAMPLE.read_text())
    edges = payload["data"]["edges"]
    assert len({edge["id"] for edge in edges}) == len(edges)
    for edge in edges:
        for handle in ("sourceHandle", "targetHandle"):
            assert json.loads(edge[handle].replace("œ", '"')) == edge["data"][handle]
    graph = Graph.from_payload(payload)
    assert len(graph.vertices) == 3
    assert {(edge.source_id, edge.target_id) for edge in graph.edges} == {
        ("ChatInput-nebius", "LanguageModelComponent-nebius"),
        ("LanguageModelComponent-nebius", "ChatOutput-nebius"),
    }
    for node in payload["data"]["nodes"]:
        if node["type"] == "noteNode":
            continue
        template = node["data"]["node"]["template"]
        for field in template.values():
            if isinstance(field, dict) and field.get("password"):
                assert not field.get("value")
        if "should_store_message" in template:
            assert template["should_store_message"]["value"] is True
