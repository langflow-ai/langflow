"""The LLM Gatekeeper starter answers saved questions without the language model, and sends the rest to it."""

import json
from pathlib import Path

import httpx
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from lfx.graph.graph.base import Graph

STARTER = Path(__file__).resolve().parents[4] / "base/langflow/initial_setup/starter_projects/LLM Gatekeeper.json"
LLM_REPLY = "Here is a migration plan for your billing system."


def _nodes_by_type(data: dict, node_type: str) -> list[dict]:
    return [node for node in data["nodes"] if node["data"].get("type") == node_type]


def _targets(data: dict) -> dict[str, str]:
    """Map each router output to the node it feeds, plus the Chat Output behind the language model."""
    targets = {
        edge["data"]["sourceHandle"]["name"]: edge["target"]
        for edge in data["edges"]
        if edge["data"]["sourceHandle"]["dataType"] == "SmartRouter"
    }
    targets["llm_reply"] = next(edge["target"] for edge in data["edges"] if edge["source"] == targets["default_result"])
    return targets


async def _run(monkeypatch, message: str, decision) -> tuple[Graph, set[str], dict[str, str], list[str]]:
    llm_calls = []

    def post(_url, **_kwargs):
        if isinstance(decision, Exception):
            raise decision
        top = max(decision, key=decision.get)
        answer = {"type": "choice", "choice": top, "confidence": 0.5, "probabilities": decision}
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": {"decision": answer}})

    def get_llm(**_kwargs):
        llm_calls.append(message)
        return FakeListChatModel(responses=[LLM_REPLY])

    monkeypatch.setattr("lfx.base.models.decisions.providers.provider_safe_httpx_post", post)
    monkeypatch.setattr("lfx.base.models.unified_models.get_llm", get_llm)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")  # pragma: allowlist secret
    data = json.loads(STARTER.read_text(encoding="utf-8"))["data"]
    _nodes_by_type(data, "ChatInput")[0]["data"]["node"]["template"]["input_value"]["value"] = message
    graph = Graph.from_payload(data)
    graph.prepare()
    ran = {result.vertex.id async for result in graph.async_start() if hasattr(result, "vertex")}
    return graph, ran, _targets(data), llm_calls


def _text(graph: Graph, vertex_id: str) -> str:
    return graph.get_vertex(vertex_id).built_object["message"].text


def _probabilities(top: str, probability: float) -> dict[str, float]:
    rest = (1 - probability) / 3
    return {f"category_{i}_result": probability if f"category_{i}_result" == top else rest for i in range(1, 5)}


class TestLLMGatekeeperStarter:
    async def test_a_saved_answer_skips_the_language_model(self, monkeypatch):
        graph, ran, targets, llm_calls = await _run(
            monkeypatch, "I forgot my password", _probabilities("category_2_result", 0.94)
        )
        assert targets["category_2_result"] in ran
        assert _text(graph, targets["category_2_result"]).startswith("Use Forgot password?")
        assert not {targets["default_result"], targets["llm_reply"]} & ran
        assert not llm_calls

    async def test_an_uncertain_message_goes_to_the_language_model(self, monkeypatch):
        message = "Can you help me plan a migration from our old billing system?"
        graph, ran, targets, llm_calls = await _run(monkeypatch, message, _probabilities("category_3_result", 0.4))
        assert {targets["default_result"], targets["llm_reply"]} <= ran
        assert not {targets[f"category_{i}_result"] for i in range(1, 5)} & ran
        assert llm_calls == [message]
        assert _text(graph, targets["llm_reply"]) == LLM_REPLY

    async def test_a_decision_outage_still_reaches_the_language_model(self, monkeypatch):
        graph, ran, targets, llm_calls = await _run(
            monkeypatch, "When are you open?", httpx.ReadTimeout("decision provider timed out")
        )
        assert targets["llm_reply"] in ran
        assert llm_calls == ["When are you open?"]
        assert _text(graph, targets["llm_reply"]) == LLM_REPLY

    def test_edge_handles_match_the_fields_they_connect(self):
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

    def test_router_is_a_gatekeeper_in_decision_mode(self):
        data = json.loads(STARTER.read_text(encoding="utf-8"))["data"]
        router = _nodes_by_type(data, "SmartRouter")[0]
        template = router["data"]["node"]["template"]
        assert template["routing_mode"]["value"] == "Decision Model"
        assert template["evaluation_error_action"]["value"] == "Route to Else"
        assert all(row["output_value"].strip() for row in template["routes"]["value"])
        assert Graph.from_payload(data).get_vertex(router["id"]).params["last_route_number"] == 4
