from __future__ import annotations

import json

import anthropic
import httpx
import pytest
from langchain_openai import ChatOpenAI
from lfx.base.models.model_metadata import matches_model_metadata
from lfx_acedatacloud import provider


def row(name: str, protocol: str = "chat_completions") -> dict:
    return {
        "id": name,
        "type": "chat",
        "endpoints": [
            {
                "protocol": protocol,
                "base_url": "https://api.acedata.cloud" if protocol == "messages" else provider.API_BASE,
                "path": {
                    "messages": "/v1/messages",
                    "responses": "/v1/responses",
                    "chat_completions": "/v1/chat/completions",
                }[protocol],
                "auth": "bearer",
            }
        ],
    }


@pytest.fixture(autouse=True)
def catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [row("chat-model"), row("messages-model", "messages"), row("responses-model", "responses")]
    monkeypatch.setitem(provider._catalog_state, "rows", {item["id"]: item for item in rows})
    monkeypatch.setitem(provider._catalog_state, "expires", float("inf"))


def test_factory_uses_each_published_protocol_and_preserves_settings() -> None:
    chat = provider.ChatAceDataCloud(model="chat-model", api_key="test-only", max_tokens=41)
    assert isinstance(chat, ChatOpenAI)
    assert chat.max_tokens == 41
    assert chat.profile == {}
    responses = provider.ChatAceDataCloud(model="responses-model", api_key="test-only")
    assert isinstance(responses, ChatOpenAI)
    assert responses.use_responses_api is True
    messages = provider.ChatAceDataCloud(model="messages-model", api_key="test-only", max_completion_tokens=42)
    assert isinstance(messages, provider._AceMessages)
    assert messages.max_tokens == 42
    assert messages.profile == {}
    with pytest.raises(ValueError, match="does not publish a Responses"):
        provider.ChatAceDataCloud(model="messages-model", api_key="test-only", use_responses_api=True)


def test_custom_endpoint_does_not_inherit_ace_metadata() -> None:
    model = provider.ChatAceDataCloud(
        model="messages-model",
        api_key="custom-only",
        base_url="https://custom.example/v1",
        profile={"max_input_tokens": 55},
    )
    assert isinstance(model, ChatOpenAI)
    assert model.profile == {"max_input_tokens": 55}
    assert str(model.openai_api_base).rstrip("/") == "https://custom.example/v1"


def test_native_messages_uses_bearer_and_existing_tool_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-must-not-be-sent")
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "messages-model",
                "content": [{"type": "tool_use", "id": "call_test", "name": "lookup", "input": {"q": "hello"}}],
                "stop_reason": "tool_use",
                "stop_sequence": None,
                "usage": {"input_tokens": 8, "output_tokens": 4},
            },
        )

    model = provider.ChatAceDataCloud(model="messages-model", api_key="ace-test-key", max_tokens=32)
    model.__dict__["_client"] = anthropic.Anthropic(
        **model._client_params, http_client=httpx.Client(transport=httpx.MockTransport(handle))
    )
    result = model.bind_tools(
        [
            {
                "name": "lookup",
                "description": "Look up a value",
                "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
            }
        ]
    ).invoke("hello")
    assert result.tool_calls[0]["name"] == "lookup"
    assert result.usage_metadata["input_tokens"] == 8
    request = seen[0]
    assert str(request.url) == "https://api.acedata.cloud/v1/messages"
    assert request.headers["Authorization"] == "Bearer ace-test-key"
    assert "x-api-key" not in request.headers
    body = json.loads(request.content)
    assert body["model"] == "messages-model"
    assert body["max_tokens"] == 32
    assert body["tools"][0]["name"] == "lookup"


def test_catalog_is_dynamic_typed_public_and_retains_last_good(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(provider._catalog_state, "expires", 0)
    monkeypatch.setitem(provider._catalog_state, "rows", {})
    calls = []

    def get(url: str, **kwargs) -> httpx.Response:
        calls.append((url, kwargs))
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={
                "data": [
                    row("future-model"),
                    {**row("gpt-4o-image"), "capabilities": ["image_generation"]},
                    {**row("image-only"), "type": "image"},
                    {"id": "untyped", "type": "chat"},
                ]
            },
        )

    monkeypatch.setattr(provider.httpx, "get", get)
    models = provider.load_catalog()
    assert [model["name"] for model in models] == ["future-model", "gpt-4o-image"]
    assert all(model["tool_calling"] is None for model in models)
    assert "headers" not in calls[0][1]
    provider.load_catalog()
    assert len(calls) == 1
    monkeypatch.setitem(provider._catalog_state, "expires", 0)
    monkeypatch.setattr(
        provider.httpx, "get", lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.ConnectError("unavailable"))
    )
    assert provider.load_catalog() == models


@pytest.mark.parametrize(
    ("metadata", "filters", "expected"),
    [
        ({"tool_calling": None}, {"tool_calling": True}, False),
        ({"tool_calling": False}, {"tool_calling": True}, False),
        ({"tool_calling": True}, {"tool_calling": True}, True),
        ({}, {"tool_calling": True}, False),
        ({"tool_calling": None}, {"tool_calling": False}, False),
        ({"tool_calling": False}, {"tool_calling": False}, True),
        ({"tool_calling": True}, {"tool_calling": False}, False),
        ({}, {"tool_calling": False}, False),
        ({"tool_calling": None}, {}, True),
        ({"tool_calling": False}, {}, True),
        ({"tool_calling": True}, {}, True),
        ({}, {}, True),
        ({"tool_calling": None, "reasoning": None}, {"reasoning": True}, False),
        ({"tool_calling": None, "reasoning": False}, {"tool_calling": True, "reasoning": True}, False),
    ],
)
def test_tool_filters_match_declared_values_without_rewriting_capabilities(metadata, filters, expected) -> None:
    original = dict(metadata)
    assert matches_model_metadata(metadata, filters) is expected
    assert metadata == original


@pytest.mark.parametrize(
    ("filters", "expected_names"),
    [
        ({}, ["unknown", "supported", "unsupported", "missing"]),
        ({"tool_calling": True}, ["supported"]),
        ({"tool_calling": False}, ["unsupported"]),
    ],
)
def test_static_and_live_catalogs_only_filter_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    filters: dict,
    expected_names: list[str],
) -> None:
    from lfx.base.models.model_utils import apply_metadata_filters, inject_custom_enabled_models
    from lfx.base.models.unified_models import model_catalog

    models = [
        {"provider": "Ace Data Cloud", "name": name, "model_type": "llm", "tool_calling": value}
        for name, value in [("unknown", None), ("supported", True), ("unsupported", False)]
    ]
    models.append({"provider": "Ace Data Cloud", "name": "missing", "model_type": "llm"})
    monkeypatch.setattr(model_catalog, "get_models_detailed", lambda: [models])
    static = model_catalog.get_unified_models_detailed(**filters)
    assert [model["model_name"] for model in static[0]["models"]] == expected_names
    live = [
        {
            "provider": "Ace Data Cloud",
            "models": [{"model_name": model["name"], "metadata": dict(model)} for model in models],
        }
    ]
    suppressed = apply_metadata_filters(live, filters)
    assert [model["model_name"] for model in live[0]["models"]] == expected_names
    removed = {(model["name"], "llm") for model in models if model["name"] not in expected_names}
    assert suppressed == ({"Ace Data Cloud": removed} if removed else {})
    inject_custom_enabled_models(
        live,
        {f"Ace Data Cloud::llm::{model['name']}" for model in models},
        metadata_filters=filters,
        suppressed=suppressed,
    )
    assert [model["model_name"] for model in live[0]["models"]] == expected_names
    assert models[0]["tool_calling"] is None
    assert "tool_calling" not in models[-1]
    if not filters:
        assert static[0]["models"][0]["metadata"]["tool_calling"] is None
        assert live[0]["models"][0]["metadata"]["tool_calling"] is None
        assert "tool_calling" not in static[0]["models"][-1]["metadata"]
        assert "tool_calling" not in live[0]["models"][-1]["metadata"]
