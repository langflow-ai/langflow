"""Unit tests for the APIMart unified model provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests


def test_apimart_metadata_and_catalog_registration():
    from lfx.base.models.apimart_constants import APIMART_TEXT_MODEL_NAMES
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA
    from lfx.base.models.unified_models import get_model_providers, get_unified_models_detailed

    metadata = MODEL_PROVIDER_METADATA["APIMart"]
    assert metadata["base_url"] == "https://api.apimart.ai/v1"
    assert metadata["mapping"] == {"model_class": "ChatOpenAI", "model_param": "model"}
    assert metadata["variables"][0]["variable_key"] == "APIMART_API_KEY"
    assert metadata["variables"][0]["is_secret"] is True
    assert "APIMart" in get_model_providers()

    catalog = get_unified_models_detailed(providers=["APIMart"])
    model_names = [model["model_name"] for model in catalog[0]["models"]]

    assert len(APIMART_TEXT_MODEL_NAMES) == 151
    assert len(APIMART_TEXT_MODEL_NAMES) == len(set(APIMART_TEXT_MODEL_NAMES))
    assert len(model_names) == 151
    assert catalog[0]["models"][0]["model_name"] == "gpt-5.5"
    assert catalog[0]["models"][0]["metadata"]["reasoning"] is True
    assert catalog[0]["models"][0]["metadata"]["tool_calling"] is True
    assert {
        "claude-opus-4-6",
        "deepseek-v3.2",
        "gemini-3.1-pro-preview",
        "glm-5",
        "grok-4.5",
        "kimi-k2.5",
        "minimax-m2.5",
        "qwen3.6-plus",
        "step-3.7-flash",
    }.issubset(model_names)
    assert {
        "deepseek-ocr",
        "gpt-4o-transcribe",
        "gpt-4o-realtime-preview",
        "omni-moderation-latest",
        "text-embedding-3-large",
    }.isdisjoint(model_names)


def test_apimart_param_mapping_resolves_to_chatopenai():
    from lfx.base.models.model_metadata import get_provider_param_mapping

    mapping = get_provider_param_mapping("APIMart")
    assert mapping["model_class"] == "ChatOpenAI"
    assert mapping["model_param"] == "model"
    assert mapping["api_key_param"] == "api_key"  # pragma: allowlist secret


def test_apimart_env_var_registered_for_auto_import():
    from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

    assert "APIMART_API_KEY" in VARIABLES_TO_GET_FROM_ENVIRONMENT


def test_get_llm_for_apimart_sets_base_url_and_omits_temperature():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    selection = [
        {
            "name": "gpt-5.5",
            "provider": "APIMart",
            "metadata": {
                "model_class": "ChatOpenAI",
                "model_name_param": "model",
                "api_key_param": "api_key",  # pragma: allowlist secret
                "reasoning": True,
            },
        }
    ]

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="dummy-apimart-key",  # pragma: allowlist secret
        ),
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
    ):
        get_llm(selection, user_id=None, temperature=0.7)

    assert captured_kwargs["model"] == "gpt-5.5"
    assert captured_kwargs["api_key"] == "dummy-apimart-key"  # pragma: allowlist secret
    assert captured_kwargs["base_url"] == "https://api.apimart.ai/v1"
    assert captured_kwargs["stream_usage"] is True
    assert "temperature" not in captured_kwargs


def test_validate_apimart_key_uses_authenticated_models_endpoint():
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock(status_code=200)
    response.raise_for_status.return_value = None

    with patch.object(requests, "get", return_value=response) as mock_get:
        validate_model_provider_key(
            "APIMart",
            {"APIMART_API_KEY": "dummy-apimart-key"},  # pragma: allowlist secret
        )

    call = mock_get.call_args
    assert call.args[0] == "https://api.apimart.ai/v1/models"
    assert call.kwargs["headers"]["Authorization"].startswith("Bearer ")


def test_validate_apimart_key_rejects_unauthorized():
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock(status_code=401)

    with (
        patch.object(requests, "get", return_value=response),
        pytest.raises(ValueError, match="Invalid APIMart API key"),
    ):
        validate_model_provider_key(
            "APIMart",
            {"APIMART_API_KEY": "dummy-apimart-key"},  # pragma: allowlist secret
        )


def test_validate_apimart_network_error_raises_value_error():
    from lfx.base.models.unified_models import validate_model_provider_key

    with (
        patch.object(requests, "get", side_effect=requests.ConnectionError("network down")),
        pytest.raises(ValueError, match="Could not reach APIMart"),
    ):
        validate_model_provider_key(
            "APIMart",
            {"APIMART_API_KEY": "dummy-apimart-key"},  # pragma: allowlist secret
        )
