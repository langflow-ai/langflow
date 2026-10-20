"""The Support Ticket Routing starter routes end to end with only the provider HTTP boundary replaced."""

import json
from pathlib import Path

import httpx
from lfx.graph.graph.base import Graph

STARTER = (
    Path(__file__).resolve().parents[3] / "base/langflow/initial_setup/starter_projects/Support Ticket Routing.json"
)


def _targets_by_route(data: dict) -> dict[str, str]:
    """Map each router output handle to the Chat Output it feeds."""
    return {
        edge["data"]["sourceHandle"]["name"]: edge["target"]
        for edge in data["edges"]
        if edge["data"]["sourceHandle"]["dataType"] == "SmartRouter"
    }


MESSAGE = "I was charged twice for my October invoice."


def _text(graph: Graph, vertex_id: str) -> str:
    return graph.get_vertex(vertex_id).built_object["message"].text


async def _route(monkeypatch, probabilities: dict[str, float]) -> tuple[Graph, set[str], dict[str, str], list[dict]]:
    sent = []

    def post(_url, **kwargs):
        sent.append(kwargs["json"])
        top = max(probabilities, key=probabilities.get)
        answer = {"type": "choice", "choice": top, "confidence": 0.5, "probabilities": probabilities}
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": {"decision": answer}})

    monkeypatch.setattr("lfx.base.models.decisions.providers.provider_safe_httpx_post", post)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")  # pragma: allowlist secret
    data = json.loads(STARTER.read_text(encoding="utf-8"))["data"]
    chat_input = next(node for node in data["nodes"] if node["data"]["type"] == "ChatInput")
    chat_input["data"]["node"]["template"]["input_value"]["value"] = MESSAGE
    graph = Graph.from_payload(data)
    graph.prepare()
    ran = {result.vertex.id async for result in graph.async_start() if hasattr(result, "vertex")}
    return graph, ran, _targets_by_route(data), sent


async def test_confident_answer_reaches_only_its_route(monkeypatch):
    graph, ran, targets, sent = await _route(
        monkeypatch, {"category_1_result": 0.92, "category_2_result": 0.05, "category_3_result": 0.03}
    )
    assert targets["category_1_result"] in ran
    assert not {targets["category_2_result"], targets["category_3_result"], targets["default_result"]} & ran
    criteria = sent[0]["questions"]["decision"]["criteria"]
    assert set(criteria) == {"category_1_result", "category_2_result", "category_3_result"}
    assert criteria["category_1_result"].startswith("Billing: ")
    assert sent[0]["state"] == MESSAGE
    assert _text(graph, targets["category_1_result"]).startswith("Thanks. Our billing team")


async def test_below_threshold_answer_goes_to_review(monkeypatch):
    graph, ran, targets, _ = await _route(
        monkeypatch, {"category_1_result": 0.5, "category_2_result": 0.3, "category_3_result": 0.2}
    )
    assert targets["default_result"] in ran
    assert not {targets["category_1_result"], targets["category_2_result"], targets["category_3_result"]} & ran
    assert _text(graph, targets["default_result"]) == MESSAGE
