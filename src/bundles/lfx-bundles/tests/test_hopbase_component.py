"""Exercise HopBase discovery, refresh failures, and chat requests without a live key."""

import json
from copy import deepcopy

import httpx
import pytest
from lfx_bundles.hopbase.hopbase import HOPBASE_API_BASE, MODELS_LOAD_FAILED, HopBaseComponent

API_KEY = "hopbase-test-key"  # pragma: allowlist secret


@pytest.fixture
def component() -> HopBaseComponent:
    instance = HopBaseComponent()
    instance.set(api_key=API_KEY, model_name="chat-model", temperature=0.7, max_tokens=None)
    return instance


@pytest.fixture
def build_config() -> dict:
    return {"model_name": {"value": "chat-model", "options": ["chat-model"]}}


def test_discovery_authenticates_and_sorts_models(component, monkeypatch):
    def respond(request):
        assert request.url == f"{HOPBASE_API_BASE}/models"
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        return httpx.Response(
            200,
            json={"data": [{"id": "z-model"}, {"id": "a-model"}, {"object": "model"}, {"id": "a-model"}]},
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.hopbase.hopbase.httpx.get", client.get)
        assert component.fetch_models() == ["a-model", "z-model"]


def test_missing_key_skips_discovery(component, build_config, monkeypatch):
    def reject_request(*_args, **_kwargs):
        pytest.fail("Discovery must not make a request without credentials")

    component.set(api_key="")
    monkeypatch.setattr("lfx_bundles.hopbase.hopbase.httpx.get", reject_request)
    original = deepcopy(build_config)
    assert component.fetch_models() == []
    assert component.update_build_config(build_config, "", "model_name") == original


@pytest.mark.parametrize("failure", [401, 500, "timeout", "empty", "invalid-json"])
def test_failed_refresh_preserves_selection(component, build_config, monkeypatch, failure):
    def respond(request):
        if failure == "timeout":
            message = "Timed out"
            raise httpx.ReadTimeout(message, request=request)
        if failure == "invalid-json":
            return httpx.Response(200, content=b"not json")
        return httpx.Response(200 if failure == "empty" else failure, json={"data": []})

    original = deepcopy(build_config["model_name"])
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.hopbase.hopbase.httpx.get", client.get)
        result = component.update_build_config(build_config, "chat-model", "model_name")

    for field in ("value", "options"):
        assert result["model_name"][field] == original[field]
    assert MODELS_LOAD_FAILED in result["model_name"]["info"]
    assert component.build_model().model_name == "chat-model"


def test_refresh_recovers_and_clears_error(component, build_config, monkeypatch):
    build_config["model_name"]["info"] = MODELS_LOAD_FAILED
    with httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"data": [{"id": "chat-model"}]}))
    ) as client:
        monkeypatch.setattr("lfx_bundles.hopbase.hopbase.httpx.get", client.get)
        result = component.update_build_config(build_config, "chat-model", "model_name")

    assert result["model_name"] == {"value": "chat-model", "options": ["chat-model"], "info": ""}


def test_build_requires_key(component):
    component.set(api_key="")
    with pytest.raises(ValueError, match="API key is required"):
        component.build_model()


@pytest.mark.parametrize("model_name", ["", "Loading...", MODELS_LOAD_FAILED])
def test_build_requires_valid_selection(component, model_name):
    component.set(model_name=model_name)
    with pytest.raises(ValueError, match="Please select a model"):
        component.build_model()


@pytest.mark.parametrize("temperature", [0, 0.7, 2])
def test_build_preserves_generation_settings(component, temperature):
    component.set(temperature=temperature, max_tokens=42)
    model = component.build_model()
    assert model.model_name == "chat-model"
    assert model.openai_api_base == HOPBASE_API_BASE
    assert model.openai_api_key.get_secret_value() == API_KEY
    assert model.temperature == temperature
    assert model.max_tokens == 42


def test_model_sends_chat_request(component, monkeypatch):
    def send(_client, request, **_kwargs):
        assert request.url == f"{HOPBASE_API_BASE}/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        payload = json.loads(request.content)
        assert payload["model"] == "chat-model"
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]
        return httpx.Response(
            200,
            request=request,
            json={
                "id": "test-completion",
                "object": "chat.completion",
                "created": 0,
                "model": "chat-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
            },
        )

    monkeypatch.setattr(httpx.Client, "send", send)
    assert component.build_model().invoke("Hello").content == "Hi"
