from __future__ import annotations

import json

import anthropic
import httpx
import pytest
from langchain_openai import ChatOpenAI
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
    assert all("tool_calling" not in model for model in models)
    assert "headers" not in calls[0][1]
    provider.load_catalog()
    assert len(calls) == 1
    monkeypatch.setitem(provider._catalog_state, "expires", 0)
    monkeypatch.setattr(
        provider.httpx, "get", lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.ConnectError("unavailable"))
    )
    assert provider.load_catalog() == models
