"""Unit tests for the FlexAI language model component."""

import httpx
import pytest
import respx

pytest.importorskip("lfx_bundles")
pytest.importorskip("langchain_openai")

from langchain_openai import ChatOpenAI
from lfx_bundles.flexai import FlexAIModelComponent
from lfx_bundles.flexai.flexai import FLEXAI_API_BASE, FLEXAI_DEFAULT_MODEL

API_KEY = "test-flexai-key"  # pragma: allowlist secret

MODELS_PAYLOAD = {
    "data": [
        {"id": "chat-b", "name": "Chat B", "context_length": 131072, "supports": ["chat", "tool_use"]},
        {"id": "embed-a", "name": "Embed A", "context_length": 8192, "supports": ["embeddings"]},
        {"id": "chat-a", "name": "Chat A", "context_length": 262144, "supports": ["chat"]},
        {"id": "speech-a", "name": "Speech A", "context_length": None, "supports": ["audio_speech"]},
    ]
}


def _build_config(value: str = FLEXAI_DEFAULT_MODEL) -> dict:
    return {"model_name": {"options": [FLEXAI_DEFAULT_MODEL], "value": value}}


@respx.mock
def test_fetch_models_sends_key_and_keeps_chat_models_only():
    route = respx.get(f"{FLEXAI_API_BASE}/models").mock(return_value=httpx.Response(200, json=MODELS_PAYLOAD))
    component = FlexAIModelComponent(api_key=API_KEY)

    models = component.fetch_models()

    assert route.calls[0].request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert [m["id"] for m in models] == ["chat-a", "chat-b"]
    assert models[0]["context"] == 262144


@respx.mock
def test_fetch_models_without_api_key_makes_no_request():
    route = respx.get(f"{FLEXAI_API_BASE}/models")
    component = FlexAIModelComponent()

    assert component.fetch_models() == []
    assert not route.called


@respx.mock
def test_update_build_config_populates_live_models_and_selects_a_served_one():
    respx.get(f"{FLEXAI_API_BASE}/models").mock(return_value=httpx.Response(200, json=MODELS_PAYLOAD))
    component = FlexAIModelComponent(api_key=API_KEY)

    config = component.update_build_config(_build_config(), API_KEY, "api_key")

    assert config["model_name"]["options"] == ["chat-a", "chat-b"]
    assert config["model_name"]["value"] == "chat-a"
    assert config["model_name"]["tooltips"]["chat-b"] == "Chat B (131,072 tokens)"


@respx.mock
def test_update_build_config_keeps_defaults_when_catalog_unavailable():
    respx.get(f"{FLEXAI_API_BASE}/models").mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
    component = FlexAIModelComponent(api_key=API_KEY)

    config = component.update_build_config(_build_config(), API_KEY, "api_key")

    assert config["model_name"]["options"] == [FLEXAI_DEFAULT_MODEL]
    assert config["model_name"]["value"] == FLEXAI_DEFAULT_MODEL


def test_build_model_targets_flexai_endpoint():
    component = FlexAIModelComponent(api_key=API_KEY, model_name="chat-a", temperature=0.2, max_tokens=64)

    model = component.build_model()

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "chat-a"
    assert model.openai_api_base == FLEXAI_API_BASE
    assert model.openai_api_key.get_secret_value() == API_KEY
    assert model.temperature == 0.2
    assert model.max_tokens == 64


def test_build_model_requires_api_key():
    component = FlexAIModelComponent(model_name="chat-a")

    with pytest.raises(ValueError, match="API key is required"):
        component.build_model()
