"""The Support Ticket Routing starter routes end to end with only the provider HTTP boundary replaced."""

import json
from pathlib import Path

import httpx
import pytest
from lfx.graph.graph.base import Graph

STARTER = (
    Path(__file__).resolve().parents[4] / "base/langflow/initial_setup/starter_projects/Support Ticket Routing.json"
)


def _targets_by_route(data: dict) -> dict[str, str]:
    """Map each router output handle to the node it feeds, plus the review Chat Output behind Else's prompt."""
    targets = {
        edge["data"]["sourceHandle"]["name"]: edge["target"]
        for edge in data["edges"]
        if edge["data"]["sourceHandle"]["dataType"] == "SmartRouter"
    }
    targets["review"] = next(edge["target"] for edge in data["edges"] if edge["source"] == targets["default_result"])
    return targets


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
    losers = {targets["category_2_result"], targets["category_3_result"], targets["default_result"], targets["review"]}
    assert not losers & ran
    criteria = sent[0]["questions"]["decision"]["criteria"]
    assert set(criteria) == {"category_1_result", "category_2_result", "category_3_result"}
    assert criteria["category_1_result"].startswith("Billing: ")
    assert sent[0]["state"] == MESSAGE
    assert _text(graph, targets["category_1_result"]).startswith("Thanks. Our billing team")


async def test_below_threshold_answer_goes_to_review(monkeypatch):
    graph, ran, targets, _ = await _route(
        monkeypatch, {"category_1_result": 0.5, "category_2_result": 0.3, "category_3_result": 0.2}
    )
    assert {targets["default_result"], targets["review"]} <= ran
    assert not {targets["category_1_result"], targets["category_2_result"], targets["category_3_result"]} & ran
    assert _text(graph, targets["review"]) == (
        f"No team was confident enough to take this one, so a person will review it.\n\nYour message: {MESSAGE}"
    )


def test_edge_handles_match_the_fields_they_connect():
    """The editor drops any edge whose handle disagrees with its field, as cleanEdges does on load."""
    data = json.loads(STARTER.read_text(encoding="utf-8"))["data"]
    nodes = {node["id"]: node["data"]["node"] for node in data["nodes"]}
    for edge in data["edges"]:
        source, target = edge["data"]["sourceHandle"], edge["data"]["targetHandle"]
        assert json.loads(edge["sourceHandle"].replace("œ", '"')) == source
        assert json.loads(edge["targetHandle"].replace("œ", '"')) == target
        output = next(output for output in nodes[edge["source"]]["outputs"] if output["name"] == source["name"])
        assert source["output_types"] == output["types"]
        field = nodes[edge["target"]]["template"][target["fieldName"]]
        assert (target["type"], target["inputTypes"]) == (field["type"], field["input_types"])


def test_hidden_route_counter_reaches_the_run():
    """Hidden fields are normally skipped when a flow runs; the route counter must not be."""
    data = json.loads(STARTER.read_text(encoding="utf-8"))["data"]
    router = next(node for node in data["nodes"] if node["data"]["type"] == "SmartRouter")
    graph = Graph.from_payload(data)
    assert graph.get_vertex(router["id"]).params["last_route_number"] == 3


@pytest.mark.parametrize("name", ["Support Ticket Routing", "LLM Gatekeeper"])
def test_the_starter_router_shows_the_components_help(name):
    """A starter keeps its own copy of the router's help text, which no code-hash check refreshes."""
    from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent

    fresh = SmartRouterComponent().to_frontend_node()["data"]["node"]
    data = json.loads(STARTER.with_name(f"{name}.json").read_text(encoding="utf-8"))["data"]
    node = next(n for n in data["nodes"] if n["data"]["type"] == "SmartRouter")["data"]["node"]
    assert node["description"] == fresh["description"]
    for field in ("decision_kind", "routes", "minimum_probability", "enable_else_output", "evaluation_error_action"):
        assert node["template"][field]["info"] == fresh["template"][field]["info"], field
    # Both starters are in Decision Model mode, where a route can set its own threshold.
    columns = {column["name"]: column for column in node["template"]["routes"]["table_schema"]}
    assert columns["minimum_probability"]["hidden"] is False
