import json

import httpx
import pytest
from langchain_core.messages import AIMessageChunk
from lfx_bundles.fortytwo.chat import ChatFortytwo
from lfx_bundles.fortytwo.fortytwo import BASE_URL, HEADERS, FortytwoComponent


@pytest.fixture
def component():
    component = FortytwoComponent()
    component.set(api_key="test-key", model_name="test-model")
    return component


def test_discovery_authenticates_and_normalises(component, monkeypatch):
    def get(url, **kwargs):
        assert url == f"{BASE_URL}/models"
        assert kwargs["headers"] == {**HEADERS, "Authorization": "Bearer test-key"}
        assert kwargs["follow_redirects"] is False
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={
                "data": [{"id": "z"}, {"id": "a"}, {"id": "a"}, {"id": None}, "invalid"],
            },
        )

    monkeypatch.setattr("lfx_bundles.fortytwo.fortytwo.httpx.get", get)
    assert component.fetch_models() == ["a", "z"]


@pytest.mark.parametrize("status", [301, 401, 429, 500])
def test_discovery_failure_clears_stale_selection(component, monkeypatch, status):
    def get(url, **_kwargs):
        return httpx.Response(status, request=httpx.Request("GET", url), text="secret-response-body")

    monkeypatch.setattr("lfx_bundles.fortytwo.fortytwo.httpx.get", get)
    config = {"model_name": {"value": "stale-model", "options": ["stale-model"]}}
    with pytest.raises(ValueError, match=f"HTTP {status}") as error:
        component.update_build_config(config, "test-model", "model_name")
    assert "secret-response-body" not in str(error.value)
    assert config["model_name"] == {"value": "", "options": []}


@pytest.mark.parametrize("payload", [None, [], {"data": {}}, {"data": None}])
def test_malformed_catalogue(component, monkeypatch, payload):
    monkeypatch.setattr(
        "lfx_bundles.fortytwo.fortytwo.httpx.get",
        lambda url, **_kwargs: httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json=payload,
        ),
    )
    with pytest.raises(ValueError, match="invalid model catalogue"):
        component.fetch_models()


def test_missing_key_does_not_request(component, monkeypatch):
    component.set(api_key="")
    monkeypatch.setattr(
        "lfx_bundles.fortytwo.fortytwo.httpx.get", lambda *_args, **_kwargs: pytest.fail("request without key")
    )
    assert component.fetch_models() == []
    with pytest.raises(ValueError, match="API key"):
        component.build_model()


def test_refresh_retains_valid_selection_and_selects_new_model(component, monkeypatch):
    monkeypatch.setattr(component, "fetch_models", lambda: ["a", "z"])
    config = {"model_name": {"value": "z"}}
    assert component.update_build_config(config, "z", "model_name")["model_name"]["value"] == "z"
    config["model_name"]["value"] = "retired"
    assert component.update_build_config(config, "retired", "model_name")["model_name"]["value"] == "a"


def test_build_model_preserves_parameters(component):
    component.set(max_tokens=1234, reasoning_effort="none", temperature=0.2)
    model = component.build_model()
    assert isinstance(model, ChatFortytwo)
    assert model.openai_api_base == BASE_URL
    assert model.default_headers == HEADERS
    assert model.max_tokens == 1234
    assert model.reasoning_effort == "none"
    assert model.temperature == 0.2
    assert model.use_responses_api is False


def test_reasoning_and_tool_chunks_survive():
    model = ChatFortytwo(api_key="test-key", model="test-model")
    chunks = [
        {"reasoning": "First "},
        {"reasoning": "think."},
        {
            "tool_calls": [
                {"index": 0, "id": "call-1", "type": "function", "function": {"name": "add", "arguments": '{"a":1}'}}
            ]
        },
    ]
    messages = [
        model._convert_chunk_to_generation_chunk({"choices": [{"delta": delta}]}, AIMessageChunk, None).message
        for delta in chunks
    ]
    combined = messages[0] + messages[1] + messages[2]
    assert combined.additional_kwargs["reasoning_content"] == "First think."
    assert combined.tool_calls[0]["args"] == {"a": 1}


@pytest.mark.asyncio
async def test_real_client_stream_sync_and_async():
    events = [
        {"choices": [{"index": 0, "delta": {"role": "assistant", "reasoning": "Think."}}]},
        {"choices": [{"index": 0, "delta": {"content": "Hello"}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]

    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert json.loads(request.content)["reasoning_effort"] == "medium"
        data = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, text=data)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as sync_client:
        async with httpx.AsyncClient(transport=transport) as async_client:
            model = ChatFortytwo(
                api_key="test-key",
                model="test-model",
                reasoning_effort="medium",
                base_url=BASE_URL,
                http_client=sync_client,
                http_async_client=async_client,
            )
            for chunks in [list(model.stream("hello")), [chunk async for chunk in model.astream("hello")]]:
                assert "".join(chunk.content for chunk in chunks) == "Hello"
                assert "".join(chunk.additional_kwargs.get("reasoning_content", "") for chunk in chunks) == "Think."


def test_non_streamed_reasoning():
    model = ChatFortytwo(api_key="test-key", model="test-model")
    result = model._create_chat_result(
        {
            "choices": [
                {"message": {"role": "assistant", "content": "Answer", "reasoning": "Think"}, "finish_reason": "stop"}
            ]
        }
    )
    assert result.generations[0].message.additional_kwargs["reasoning_content"] == "Think"
    assert result.generations[0].message.content == "Answer"
