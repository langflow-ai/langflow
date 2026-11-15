"""Exercise TrustedRouter discovery, refresh failures, and chat requests without a live key."""

import importlib
import json
from copy import deepcopy

import httpx
import pytest
from lfx_bundles.trustedrouter.trustedrouter import (
    DEFAULT_MODEL,
    MODELS_LOAD_FAILED,
    TRUSTEDROUTER_API_BASE,
    TrustedRouterComponent,
)

API_KEY = "trustedrouter-test-key"  # pragma: allowlist secret
TEXT_MODEL = {"modality": "text->text"}


@pytest.fixture
def component() -> TrustedRouterComponent:
    instance = TrustedRouterComponent()
    instance.set(api_key=API_KEY, model_name="vendor/chat-model", temperature=0.7, max_tokens=None)
    return instance


@pytest.fixture
def build_config() -> dict:
    return {
        "model_name": {
            "value": "vendor/chat-model",
            "options": ["vendor/chat-model"],
            "tooltips": {"vendor/chat-model": "Existing context"},
        }
    }


def test_default_model_is_auto():
    assert TrustedRouterComponent().model_name == DEFAULT_MODEL


def test_discovery_is_public_and_filters_text_models(component, monkeypatch):
    def respond(request):
        assert request.url == f"{TRUSTEDROUTER_API_BASE}/models"
        assert "Authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "z/chat", "context_length": 128000, "architecture": TEXT_MODEL},
                    {"id": "a/vision", "architecture": {"modality": "text+image->text"}},
                    {"id": "e/embed", "architecture": {"modality": "text->embedding"}},
                    {"id": "i/image", "architecture": {"modality": "text->image"}},
                    {"architecture": TEXT_MODEL},
                    {"id": "unspecified"},
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.trustedrouter.trustedrouter.httpx.get", client.get)
        assert component.fetch_models() == [{"id": "a/vision", "context": 0}, {"id": "z/chat", "context": 128000}]


def test_discovery_does_not_need_key(component, monkeypatch):
    component.set(api_key="")
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"data": [{"id": "x/y", "architecture": TEXT_MODEL}]})
        )
    ) as client:
        monkeypatch.setattr("lfx_bundles.trustedrouter.trustedrouter.httpx.get", client.get)
        assert component.fetch_models() == [{"id": "x/y", "context": 0}]


@pytest.mark.parametrize("failure", [429, 500, "timeout", "empty"])
def test_failed_refresh_preserves_selection(component, build_config, monkeypatch, failure):
    def respond(request):
        if failure == "timeout":
            message = "Timed out"
            raise httpx.ReadTimeout(message, request=request)
        return httpx.Response(200 if failure == "empty" else failure, json={"data": []})

    original = deepcopy(build_config["model_name"])
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.trustedrouter.trustedrouter.httpx.get", client.get)
        result = component.update_build_config(build_config, "vendor/chat-model", "model_name")

    for field in ("value", "options", "tooltips"):
        assert result["model_name"][field] == original[field]
    assert MODELS_LOAD_FAILED in result["model_name"]["info"]
    assert component.build_model().model_name == "vendor/chat-model"


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"null",
        b"[]",
        b'{"data": null}',
        b'{"data": [null]}',
        b'{"data": [{"id": "x/y", "context_length": "unknown", "architecture": {"modality": "text->text"}}]}',
    ],
)
def test_malformed_refresh_preserves_selection(component, build_config, monkeypatch, body):
    original = deepcopy(build_config["model_name"])
    with httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=body))) as client:
        monkeypatch.setattr("lfx_bundles.trustedrouter.trustedrouter.httpx.get", client.get)
        result = component.update_build_config(build_config, "vendor/chat-model", "model_name")

    for field in ("value", "options", "tooltips"):
        assert result["model_name"][field] == original[field]
    assert MODELS_LOAD_FAILED in result["model_name"]["info"]


def test_numeric_string_context_is_formatted(component, build_config, monkeypatch):
    body = {"data": [{"id": "x/y", "context_length": "128000", "architecture": TEXT_MODEL}]}
    with httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=body))) as client:
        monkeypatch.setattr("lfx_bundles.trustedrouter.trustedrouter.httpx.get", client.get)
        result = component.update_build_config(build_config, "x/y", "model_name")

    assert result["model_name"]["tooltips"] == {"x/y": "128,000 tokens"}
    assert result["model_name"]["info"] == ""


def test_refresh_recovers_and_clears_error(component, build_config, monkeypatch):
    build_config["model_name"]["info"] = MODELS_LOAD_FAILED
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"data": [{"id": "vendor/chat-model", "context_length": 128000, "architecture": TEXT_MODEL}]},
            )
        )
    ) as client:
        monkeypatch.setattr("lfx_bundles.trustedrouter.trustedrouter.httpx.get", client.get)
        result = component.update_build_config(build_config, "vendor/chat-model", "model_name")

    assert result["model_name"] == {
        "value": "vendor/chat-model",
        "options": ["vendor/chat-model"],
        "tooltips": {"vendor/chat-model": "128,000 tokens"},
        "info": "",
    }


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
    assert model.model_name == "vendor/chat-model"
    assert model.openai_api_base == TRUSTEDROUTER_API_BASE
    assert model.openai_api_key.get_secret_value() == API_KEY
    assert model.temperature == temperature
    assert model.max_tokens == 42


def test_model_sends_chat_request(component, monkeypatch):
    model = component.build_model()

    def send(_client, request, **_kwargs):
        assert str(request.url) == f"{TRUSTEDROUTER_API_BASE}/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        payload = json.loads(request.content)
        assert payload["model"] == "vendor/chat-model"
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]
        # Answer with the Response type of whichever httpx distribution the OpenAI SDK uses.
        http = importlib.import_module(type(request).__module__.split(".")[0])
        return http.Response(
            200,
            request=request,
            json={
                "id": "test-completion",
                "object": "chat.completion",
                "created": 0,
                "model": "vendor/chat-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
            },
        )

    # Patch the SDK's own HTTP client class so the request never leaves the process.
    monkeypatch.setattr(type(model.root_client._client), "send", send)
    assert model.invoke("Hello").content == "Hi"
