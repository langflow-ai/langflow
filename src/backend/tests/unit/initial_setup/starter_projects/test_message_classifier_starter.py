"""The Message Classifier starter classifies end to end with only the provider HTTP boundary replaced."""

import json
from pathlib import Path

import httpx
from lfx.graph.graph.base import Graph

STARTER = Path(__file__).resolve().parents[4] / "base/langflow/initial_setup/starter_projects/Message Classifier.json"
MESSAGE = "The export button does nothing when I click it."
PROBABILITIES = {"question": 0.06, "bug": 0.88, "feature": 0.04, "billing": 0.02}


def _data() -> dict:
    return json.loads(STARTER.read_text(encoding="utf-8"))["data"]


def _node(data: dict, component_type: str) -> dict:
    return next(node for node in data["nodes"] if node["data"]["type"] == component_type)


async def test_a_message_is_classified_with_a_probability_for_each_category(monkeypatch):
    sent = []

    def post(_url, **kwargs):
        sent.append(kwargs["json"])
        answer = {"type": "choice", "choice": "bug", "probabilities": PROBABILITIES}
        return httpx.Response(200, json={"model": "jev-1.13.0", "answers": {"decision": answer}})

    monkeypatch.setattr("lfx.base.models.decisions.providers.provider_safe_httpx_post", post)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")  # pragma: allowlist secret
    data = _data()
    _node(data, "ChatInput")["data"]["node"]["template"]["input_value"]["value"] = MESSAGE
    graph = Graph.from_payload(data)
    graph.prepare()
    ran = {result.vertex.id async for result in graph.async_start() if hasattr(result, "vertex")}

    chat_output = _node(data, "ChatOutput")["id"]
    assert chat_output in ran
    (request,) = sent
    assert request["state"] == MESSAGE
    assert list(request["questions"]["decision"]["criteria"]) == list(PROBABILITIES)
    fenced = graph.get_vertex(chat_output).built_object["message"].text  # ```json ... ```
    shown = json.loads(fenced.strip().strip("`").removeprefix("json"))
    assert shown["probabilities"] == PROBABILITIES
    assert shown["selected_option"] == "bug"


def test_the_starter_shows_the_components_help():
    """A starter keeps its own copy of the component's help text, which no code-hash check refreshes."""
    from lfx.components.llm_operations.decision_model import DecisionModelComponent

    fresh = DecisionModelComponent().to_frontend_node()["data"]["node"]
    node = _node(_data(), "DecisionModel")["data"]["node"]
    assert node["description"] == fresh["description"]
    for field in ("context", "question_mode", "questions", "timeout"):
        assert node["template"][field]["info"] == fresh["template"][field]["info"], field


def test_the_note_is_translatable():
    note = _node(_data(), "note")["data"]["node"]
    english = json.loads(
        (Path(__file__).resolve().parents[4] / "base/langflow/locales/en.json").read_text(encoding="utf-8")
    )
    assert english[note["i18n_key"]] == note["description"]
