"""Exercise Straitly discovery, refresh failures, and chat requests without a live key."""

import importlib
import json
from copy import deepcopy

import httpx
import pytest
from lfx_bundles.straitly.straitly import MODELS_LOAD_FAILED, STRAITLY_API_BASE, StraitlyComponent

API_KEY = "straitly-test-key"  # pragma: allowlist secret


@pytest.fixture
def component() -> StraitlyComponent:
    instance = StraitlyComponent()
    instance.set(api_key=API_KEY, model_name="deepseek/deepseek-v4-1-flash-1017", temperature=0.7, max_tokens=None)
    return instance


@pytest.fixture
def build_config() -> dict:
    return {
        "model_name": {
            "value": "deepseek/deepseek-v4-1-flash-1017",
            "options": ["deepseek/deepseek-v4-1-flash-1017"],
            "tooltips": {"deepseek/deepseek-v4-1-flash-1017": "Existing context"},
        }
    }


def test_lazy_import_exports_component():
    package = importlib.import_module("lfx_bundles.straitly")
    assert package.StraitlyComponent is StraitlyComponent
    assert "StraitlyComponent" in dir(package)
    with pytest.raises(AttributeError, match="has no attribute 'NonExistent'"):
        _ = package.NonExistent


def test_discovery_validates_key_and_filters_text_models(component, monkeypatch):
    seen_urls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        if str(request.url) == f"{STRAITLY_API_BASE}/key":
            return httpx.Response(200, json={"ok": True, "key_id": "test"})
        assert str(request.url) == f"{STRAITLY_API_BASE}/models"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "z-model",
                        "name": "Z Model",
                        "context_length": 128000,
                        "architecture": {"output_modalities": ["text"]},
                    },
                    {
                        "id": "image-only",
                        "name": "Image Only",
                        "architecture": {"output_modalities": ["image"]},
                    },
                    {"id": "a-model"},
                    {"name": "missing-id"},
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.straitly.straitly.httpx.get", client.get)
        assert component.fetch_models() == [
            {"id": "a-model", "name": "a-model", "context": 0},
            {"id": "z-model", "name": "Z Model", "context": 128000},
        ]

    assert seen_urls == [f"{STRAITLY_API_BASE}/key", f"{STRAITLY_API_BASE}/models"]


def test_invalid_key_fails_before_fetching_public_models(component, build_config, monkeypatch):
    seen_urls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(401, json={"error": {"message": "Invalid API key.", "code": 401}})

    original = deepcopy(build_config["model_name"])
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.straitly.straitly.httpx.get", client.get)
        result = component.update_build_config(build_config, "deepseek/deepseek-v4-1-flash-1017", "model_name")

    assert seen_urls == [f"{STRAITLY_API_BASE}/key"]
    for field in ("value", "options", "tooltips"):
        assert result["model_name"][field] == original[field]
    assert MODELS_LOAD_FAILED in result["model_name"]["info"]


def test_missing_key_skips_discovery(component, build_config, monkeypatch):
    def reject_request(*_args, **_kwargs):
        pytest.fail("Discovery must not make a request without credentials")

    component.set(api_key="")
    monkeypatch.setattr("lfx_bundles.straitly.straitly.httpx.get", reject_request)
    original = deepcopy(build_config)
    assert component.fetch_models() == []
    assert component.update_build_config(build_config, "", "model_name") == original


@pytest.mark.parametrize("failure", [401, 500, "timeout", "empty", "invalid_json"])
def test_failed_refresh_preserves_selection(component, build_config, monkeypatch, failure):
    def respond(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            message = "Timed out"
            raise httpx.ReadTimeout(message, request=request)
        if str(request.url) == f"{STRAITLY_API_BASE}/key":
            if failure in {401, 500}:
                return httpx.Response(failure, json={"error": {"message": "error"}})
            return httpx.Response(200, json={"ok": True})
        if failure == "invalid_json":
            return httpx.Response(200, text="<html>bad gateway</html>")
        return httpx.Response(200, json={"data": []})

    original = deepcopy(build_config["model_name"])
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.straitly.straitly.httpx.get", client.get)
        result = component.update_build_config(build_config, "deepseek/deepseek-v4-1-flash-1017", "model_name")

    for field in ("value", "options", "tooltips"):
        assert result["model_name"][field] == original[field]
    assert MODELS_LOAD_FAILED in result["model_name"]["info"]
    assert component.build_model().model_name == "deepseek/deepseek-v4-1-flash-1017"


@pytest.mark.parametrize(
    "bad_model",
    [
        {"id": "m", "context_length": "128000"},
        {"id": "m", "context_length": True},
        {"id": "m", "context_length": False},
        {"id": "m", "context_length": -1},
        {"id": "m", "context_length": {"tokens": 128000}},
        {"id": "m", "name": 123},
        {"id": 123, "name": "Numeric Id"},
        {"id": False, "name": "Bool Id"},
        "not-a-dict",
    ],
)
def test_malformed_model_metadata_preserves_selection(component, build_config, monkeypatch, bad_model):
    def respond(request: httpx.Request) -> httpx.Response:
        if str(request.url) == f"{STRAITLY_API_BASE}/key":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "valid-model", "name": "Valid Model", "context_length": 64000},
                    bad_model,
                ]
            },
        )

    original = deepcopy(build_config["model_name"])
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.straitly.straitly.httpx.get", client.get)
        result = component.update_build_config(build_config, "deepseek/deepseek-v4-1-flash-1017", "model_name")

    for field in ("value", "options", "tooltips"):
        assert result["model_name"][field] == original[field]
    assert MODELS_LOAD_FAILED in result["model_name"]["info"]


def test_build_model_raises_helpful_import_error_when_langchain_openai_missing(component, monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "langchain_openai":
            msg = "No module named 'langchain_openai'"
            raise ModuleNotFoundError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    with pytest.raises(ImportError, match="lfx-bundles\\[straitly\\]"):
        component.build_model()


def test_update_build_config_supports_numeric_float_context_length(component, build_config, monkeypatch):
    def respond(request: httpx.Request) -> httpx.Response:
        if str(request.url) == f"{STRAITLY_API_BASE}/key":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(
            200,
            json={"data": [{"id": "float-ctx", "name": "Float Context", "context_length": 128000.0}]},
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.straitly.straitly.httpx.get", client.get)
        result = component.update_build_config(build_config, "float-ctx", "model_name")

    assert result["model_name"] == {
        "value": "deepseek/deepseek-v4-1-flash-1017",
        "options": ["float-ctx"],
        "tooltips": {"float-ctx": "Float Context (128,000.0 tokens)"},
        "info": "",
    }


def test_refresh_recovers_and_clears_error(component, build_config, monkeypatch):
    build_config["model_name"]["info"] = MODELS_LOAD_FAILED

    def respond(request: httpx.Request) -> httpx.Response:
        if str(request.url) == f"{STRAITLY_API_BASE}/key":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "claude-sonnet-5-5",
                        "name": "Claude Sonnet 5.5",
                        "context_length": 200000,
                        "architecture": {"output_modalities": ["text"]},
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr("lfx_bundles.straitly.straitly.httpx.get", client.get)
        result = component.update_build_config(build_config, "claude-sonnet-5-5", "model_name")

    assert result["model_name"] == {
        "value": "deepseek/deepseek-v4-1-flash-1017",
        "options": ["claude-sonnet-5-5"],
        "tooltips": {"claude-sonnet-5-5": "Claude Sonnet 5.5 (200,000 tokens)"},
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
    assert model.model_name == "deepseek/deepseek-v4-1-flash-1017"
    assert model.openai_api_base == STRAITLY_API_BASE
    assert model.openai_api_key.get_secret_value() == API_KEY
    assert model.temperature == temperature
    assert model.max_tokens == 42


def test_model_sends_chat_request(component, monkeypatch):
    def _make_response(response_cls, request):
        assert str(request.url) == f"{STRAITLY_API_BASE}/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek/deepseek-v4-1-flash-1017"
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]
        return response_cls(
            200,
            request=request,
            json={
                "id": "test-completion",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek/deepseek-v4-1-flash-1017",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
            },
        )

    monkeypatch.setattr(
        httpx.Client, "send", lambda _client, request, **_kwargs: _make_response(httpx.Response, request)
    )
    try:
        httpx2 = importlib.import_module("httpx2")
    except ImportError:
        httpx2 = None
    if httpx2 is not None:
        monkeypatch.setattr(
            httpx2.Client, "send", lambda _client, request, **_kwargs: _make_response(httpx2.Response, request)
        )

    assert component.build_model().invoke("Hello").content == "Hi"
