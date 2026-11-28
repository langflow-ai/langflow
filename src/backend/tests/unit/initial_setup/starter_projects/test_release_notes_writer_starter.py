"""Exercise the Release Notes Writer starter with a local chat model double."""

import json
from pathlib import Path

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from lfx.graph.graph.base import Graph

STARTER = Path(__file__).resolve().parents[4] / "base/langflow/initial_setup/starter_projects/Release Notes Writer.json"
GMI_MODEL = {"name": "Qwen/Qwen3.8-Flash", "provider": "OpenAI Compatible"}
CHANGELOG = "Added CSV export to Reports. Fixed duplicate invoice rows."
RELEASE_NOTES = "## Highlights\n- Export Reports as CSV.\n\n## Fixes\n- Removed duplicate invoice rows."


@pytest.fixture
def starter_data() -> dict:
    return json.loads(STARTER.read_text(encoding="utf-8"))["data"]


def _node(data: dict, node_type: str) -> dict:
    return next(node for node in data["nodes"] if node["data"].get("type") == node_type)


def _template(data: dict, node_type: str) -> dict:
    return _node(data, node_type)["data"]["node"]["template"]


def test_starter_wires_the_changelog_and_system_prompt_to_the_model(starter_data):
    node_types = {node["id"]: node["data"].get("type") for node in starter_data["nodes"]}
    edges = {
        (
            node_types[edge["source"]],
            edge["data"]["sourceHandle"]["name"],
            node_types[edge["target"]],
            edge["data"]["targetHandle"]["fieldName"],
        )
        for edge in starter_data["edges"]
    }
    assert edges == {
        ("ChatInput", "message", "LanguageModelComponent", "input_value"),
        ("Prompt", "prompt", "LanguageModelComponent", "system_message"),
        ("LanguageModelComponent", "text_output", "ChatOutput", "input_value"),
    }


def test_starter_documents_gmi_setup_and_release_notes_rules(starter_data):
    note = next(node["data"]["node"]["description"] for node in starter_data["nodes"] if node["type"] == "noteNode")
    assert "https://api.gmi-serving.com/v1" in note
    assert GMI_MODEL["provider"] in note
    assert GMI_MODEL["name"] in note
    assert "GMI Cloud API key" in note
    model = _template(starter_data, "LanguageModelComponent")
    assert not model["api_key"]["value"]
    assert not model["model"]["value"]

    prompt = _template(starter_data, "Prompt")["template"]["value"]
    assert "Highlights for new capabilities" in prompt
    assert "Fixes for resolved problems" in prompt
    assert "Action required only when the input explicitly describes an action customers must take" in prompt
    assert "Omit empty sections" in prompt
    assert "ask the user for changelog entries" in prompt


async def test_starter_sends_the_prompt_and_changelog_and_returns_markdown(starter_data, monkeypatch):
    received = []

    class RecordMessages(BaseCallbackHandler):
        def on_chat_model_start(self, _serialized, messages, **_kwargs):
            received.extend(messages)

    def get_llm(*, model, **_kwargs):
        assert model == [GMI_MODEL]
        return FakeListChatModel(responses=[RELEASE_NOTES], callbacks=[RecordMessages()])

    monkeypatch.setattr("lfx.base.models.unified_models.get_llm", get_llm)
    _template(starter_data, "ChatInput")["input_value"]["value"] = CHANGELOG
    for node_type in ("ChatInput", "ChatOutput"):
        _template(starter_data, node_type)["should_store_message"]["value"] = False
    _template(starter_data, "LanguageModelComponent")["model"]["value"] = [GMI_MODEL.copy()]

    graph = Graph.from_payload(starter_data)
    graph.prepare()
    ran = {result.vertex.id async for result in graph.async_start() if hasattr(result, "vertex")}

    (messages,) = received
    prompt = _template(starter_data, "Prompt")["template"]["value"]
    assert [(message.type, message.content) for message in messages] == [("system", prompt), ("human", CHANGELOG)]
    output_id = _node(starter_data, "ChatOutput")["id"]
    assert output_id in ran
    assert graph.get_vertex(output_id).built_object["message"].text == RELEASE_NOTES
