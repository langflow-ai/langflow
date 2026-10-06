"""Tests for the Opper language model component."""

import httpx
import pytest
import respx

pytest.importorskip("lfx_bundles")
pytest.importorskip("langchain_openai")

from langchain_openai import ChatOpenAI
from lfx_bundles.opper import OpperComponent
from lfx_bundles.opper.opper import OPPER_DEFAULT_MODELS

API_KEY = "test-opper-key"  # pragma: allowlist secret
MODELS_URL = "https://api.opper.ai/v3/compat/models"


def _build_config() -> dict:
    return {"model_name": {"options": [], "value": ""}}


def test_build_model_targets_the_opper_compat_endpoint() -> None:
    component = OpperComponent(api_key=API_KEY, model_name="claude-sonnet-4-6", temperature=0.2, max_tokens=256)

    model = component.build_model()

    assert isinstance(model, ChatOpenAI)
    assert model.openai_api_base == "https://api.opper.ai/v3/compat"
    assert model.model_name == "claude-sonnet-4-6"
    assert model.openai_api_key.get_secret_value() == API_KEY
    assert model.temperature == 0.2
    assert model.max_tokens == 256


def test_build_model_requires_an_api_key() -> None:
    component = OpperComponent(model_name="claude-sonnet-4-6")

    with pytest.raises(ValueError, match="API key is required"):
        component.build_model()


def test_model_dropdown_defaults_to_pool_names() -> None:
    model_input = next(field for field in OpperComponent.inputs if field.name == "model_name")

    assert model_input.options == OPPER_DEFAULT_MODELS
    assert model_input.value == "claude-sonnet-4-6"


@respx.mock
def test_update_build_config_lists_chat_models_for_the_entered_key() -> None:
    route = respx.get(MODELS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "claude-sonnet-4-6", "context_length": 200000, "opper": {"kind": "pool", "type": "llm"}},
                    {"id": "openai/gpt-5.4-mini", "context_length": 400000, "opper": {"kind": "model", "type": "llm"}},
                    {"id": "text-embedding-3-small", "opper": {"kind": "pool", "type": "embedding"}},
                ],
            },
        )
    )
    component = OpperComponent()

    build_config = component.update_build_config(_build_config(), API_KEY, "api_key")

    assert route.calls[0].request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert build_config["model_name"]["options"] == ["claude-sonnet-4-6", "openai/gpt-5.4-mini"]
    assert build_config["model_name"]["tooltips"]["claude-sonnet-4-6"] == "claude-sonnet-4-6 (200,000 tokens)"


@respx.mock
def test_update_build_config_falls_back_to_pool_names_on_error() -> None:
    respx.get(MODELS_URL).mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
    component = OpperComponent()

    build_config = component.update_build_config(_build_config(), "invalid-key", "api_key")

    assert build_config["model_name"]["options"] == OPPER_DEFAULT_MODELS
    assert "Error fetching models" in component.status


@respx.mock
def test_update_build_config_falls_back_to_pool_names_on_a_malformed_payload() -> None:
    respx.get(MODELS_URL).mock(return_value=httpx.Response(200, json=["not", "an", "object"]))
    component = OpperComponent()

    build_config = component.update_build_config(_build_config(), "test-key", "api_key")

    assert build_config["model_name"]["options"] == OPPER_DEFAULT_MODELS
    assert "Error fetching models" in component.status


@respx.mock
def test_update_build_config_without_a_key_skips_the_request() -> None:
    component = OpperComponent()

    build_config = component.update_build_config(_build_config(), "", "model_name")

    assert not respx.calls
    assert build_config["model_name"]["options"] == OPPER_DEFAULT_MODELS
