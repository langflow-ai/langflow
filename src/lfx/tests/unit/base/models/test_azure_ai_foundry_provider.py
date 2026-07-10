"""Unit tests for the Azure AI Foundry unified model provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests


def test_azure_ai_foundry_in_provider_registry():
    from lfx.base.models.model_metadata import CONDITIONAL_LIVE_MODEL_PROVIDERS, MODEL_PROVIDER_METADATA

    assert "Azure AI Foundry" in MODEL_PROVIDER_METADATA
    assert "Azure AI Foundry" in CONDITIONAL_LIVE_MODEL_PROVIDERS


def test_azure_ai_foundry_metadata_shape():
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    meta = MODEL_PROVIDER_METADATA["Azure AI Foundry"]
    assert meta["icon"] == "Azure"
    assert meta["mapping"]["model_class"] == "AzureAIOpenAIApiChatModel"
    assert meta["mapping"]["model_param"] == "model"

    var_keys = {v["variable_key"] for v in meta["variables"]}
    assert var_keys == {"AZURE_AI_FOUNDRY_API_KEY", "AZURE_AI_FOUNDRY_ENDPOINT"}

    by_key = {v["variable_key"]: v for v in meta["variables"]}
    assert by_key["AZURE_AI_FOUNDRY_API_KEY"]["required"] is True
    assert by_key["AZURE_AI_FOUNDRY_API_KEY"]["is_secret"] is True
    assert by_key["AZURE_AI_FOUNDRY_API_KEY"]["langchain_param"] == "credential"
    assert by_key["AZURE_AI_FOUNDRY_ENDPOINT"]["required"] is True


def test_azure_ai_foundry_appears_in_get_model_providers():
    from lfx.base.models.unified_models import get_model_providers

    assert "Azure AI Foundry" in get_model_providers()


def test_azure_ai_foundry_param_mapping_resolves_to_foundry_chat_model():
    from lfx.base.models.model_metadata import get_provider_param_mapping

    mapping = get_provider_param_mapping("Azure AI Foundry")
    assert mapping["model_class"] == "AzureAIOpenAIApiChatModel"
    assert mapping["model_param"] == "model"
    assert mapping["api_key_param"] == "credential"  # pragma: allowlist secret


def test_azure_ai_foundry_env_vars_registered_for_auto_import():
    from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

    assert "AZURE_AI_FOUNDRY_API_KEY" in VARIABLES_TO_GET_FROM_ENVIRONMENT
    assert "AZURE_AI_FOUNDRY_ENDPOINT" in VARIABLES_TO_GET_FROM_ENVIRONMENT


def test_azure_ai_foundry_resolves_to_langchain_azure_ai():
    from lfx.utils.flow_requirements import generate_requirements_from_flow

    flow = {
        "data": {
            "nodes": [
                {
                    "data": {
                        "type": "LanguageModel",
                        "node": {
                            "template": {
                                "model": {
                                    "value": [{"provider": "Azure AI Foundry", "name": "gpt-4o"}],
                                },
                                "_type": "Component",
                            },
                            "base_classes": ["LanguageModel"],
                        },
                    },
                }
            ],
            "edges": [],
        }
    }
    result = generate_requirements_from_flow(flow, pin_versions=False)
    assert "langchain-azure-ai" in result


def test_fetch_live_azure_ai_foundry_models_discovers_deployment_ids():
    from lfx.base.models import model_utils

    response = MagicMock()
    response.json.return_value = {
        "data": [
            {"id": "team-production-chat", "created": "123"},
            {"id": "o3-mini", "created": 456},
            {"id": "  "},
        ]
    }
    variables = {
        "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
        "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1/",
    }

    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=lambda _user_id, key: variables[key]),
        patch.object(model_utils.requests, "get", return_value=response) as mock_get,
    ):
        models = model_utils.fetch_live_azure_ai_foundry_models("user-1")

    mock_get.assert_called_once_with(
        "https://example.services.ai.azure.com/openai/v1/models",
        headers={"api-key": "test-key"},
        timeout=model_utils.AZURE_AI_FOUNDRY_FETCH_TIMEOUT,
        allow_redirects=False,
    )
    assert [model["name"] for model in models] == ["o3-mini", "team-production-chat"]
    assert models[0]["reasoning"] is True
    assert models[0]["created"] == 456
    assert models[1]["tool_calling"] is True
    assert models[1]["created"] == 123


def test_fetch_live_azure_ai_foundry_models_requires_endpoint_and_key():
    from lfx.base.models import model_utils

    with (
        patch.object(model_utils, "get_provider_variable_value", return_value=None),
        patch.object(model_utils.requests, "get") as mock_get,
    ):
        assert model_utils.fetch_live_azure_ai_foundry_models("user-1") == []

    mock_get.assert_not_called()


@pytest.mark.parametrize(
    ("payload", "side_effect"),
    [
        ({"data": []}, None),
        ({"data": "not-a-list"}, None),
        (None, ValueError("malformed JSON")),
        (None, OSError("network down")),
    ],
)
def test_fetch_live_azure_ai_foundry_models_safely_falls_back(payload, side_effect):
    from lfx.base.models import model_utils

    response = MagicMock()
    if side_effect is not None:
        if isinstance(side_effect, OSError):
            response.raise_for_status.side_effect = requests.ConnectionError(str(side_effect))
        else:
            response.json.side_effect = side_effect
    else:
        response.json.return_value = payload

    variables = {
        "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
        "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1",
    }
    with (
        patch.object(model_utils, "get_provider_variable_value", side_effect=lambda _user_id, key: variables[key]),
        patch.object(model_utils.requests, "get", return_value=response),
    ):
        assert model_utils.fetch_live_azure_ai_foundry_models("user-1") == []


def test_foundry_empty_live_discovery_keeps_static_catalog():
    from lfx.base.models import model_utils

    seed_models = [{"model_name": "gpt-4o", "metadata": {"default": True}}]
    provider_models = [{"provider": "Azure AI Foundry", "models": seed_models, "num_models": 1}]

    with patch.object(model_utils, "fetch_live_azure_ai_foundry_models", return_value=[]):
        result = model_utils.replace_with_live_models(
            provider_models,
            user_id="user-1",
            enabled_providers={"Azure AI Foundry"},
            model_type="llm",
        )

    assert result[0]["models"] == seed_models


def test_validate_model_provider_key_azure_ai_foundry_success():
    from types import SimpleNamespace

    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}
    fake_chat_models = SimpleNamespace(AzureAIOpenAIApiChatModel=object)
    with (
        patch.dict(
            "sys.modules",
            {
                "langchain_azure_ai": SimpleNamespace(chat_models=fake_chat_models),
                "langchain_azure_ai.chat_models": fake_chat_models,
            },
        ),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch.object(model_utils.requests, "get", return_value=response) as mock_get,
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
                "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1",
            },
        )

    mock_get.assert_called_once_with(
        "https://example.services.ai.azure.com/openai/v1/models",
        headers={"api-key": "test-key"},
        timeout=model_utils.AZURE_AI_FOUNDRY_FETCH_TIMEOUT,
        allow_redirects=False,
    )


@pytest.mark.parametrize("failure", ["connection", "timeout", "http", "malformed"], ids=str)
def test_validate_model_provider_key_azure_ai_foundry_rejects_failed_model_listing(failure):
    from types import SimpleNamespace

    from lfx.base.models import model_utils
    from lfx.base.models.unified_models import validate_model_provider_key

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": []}
    side_effect = None
    if failure == "connection":
        side_effect = requests.ConnectionError("connection refused")
    elif failure == "timeout":
        side_effect = requests.Timeout("request timed out")
    elif failure == "http":
        response.status_code = 503
        response.raise_for_status.side_effect = requests.HTTPError("503 Service Unavailable", response=response)
    else:
        response.json.return_value = {"data": "not-a-list"}

    fake_chat_models = SimpleNamespace(AzureAIOpenAIApiChatModel=object)
    with (
        patch.dict(
            "sys.modules",
            {
                "langchain_azure_ai": SimpleNamespace(chat_models=fake_chat_models),
                "langchain_azure_ai.chat_models": fake_chat_models,
            },
        ),
        patch("lfx.base.models.unified_models.model_catalog.get_unified_models_detailed", return_value=[]),
        patch.object(model_utils.requests, "get", return_value=response, side_effect=side_effect),
        pytest.raises(ValueError, match="Azure AI Foundry"),
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
                "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1",
            },
        )


def _build_azure_ai_foundry_model_selection() -> list[dict]:
    return [
        {
            "name": "gpt-4o",
            "provider": "Azure AI Foundry",
            "metadata": {},
        }
    ]


def test_get_llm_wires_azure_ai_foundry_endpoint_and_credential():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured_kwargs: dict = {}

    class FakeFoundryChatModel:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    with (
        patch.object(
            unified_models_module,
            "get_api_key_for_provider",
            return_value="test-key",
        ),
        patch.object(unified_models_module, "get_model_class", return_value=FakeFoundryChatModel),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1"},
        ),
    ):
        get_llm(_build_azure_ai_foundry_model_selection(), user_id="user-1", stream=False)

    assert captured_kwargs["model"] == "gpt-4o"
    assert captured_kwargs["credential"] == "test-key"
    assert captured_kwargs["endpoint"] == "https://example.services.ai.azure.com/openai/v1"
    assert captured_kwargs["request_timeout"] == 10.0


def test_get_llm_azure_ai_foundry_requires_endpoint():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    class FakeFoundryChatModel:
        def __init__(self, **kwargs):
            pass

    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="test-key"),
        patch.object(unified_models_module, "get_model_class", return_value=FakeFoundryChatModel),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
        patch("lfx.base.models.unified_models.instantiation._env_if_allowed", return_value=None),
        pytest.raises(ValueError, match="Azure AI Foundry endpoint is required"),
    ):
        get_llm(_build_azure_ai_foundry_model_selection(), user_id="user-1", stream=False)


def test_shared_deployment_aliases_resolve_to_openai_for_backwards_compat():
    """Seed Foundry deployment names overlap OpenAI; legacy lookup must prefer OpenAI.

    ``get_provider_for_model_name`` scans the static catalog in list order. Flows
    exported from 1.8.x only stored the model id (e.g. ``gpt-4o``) without a
    provider, so ambiguous aliases must keep resolving to OpenAI.
    """
    from lfx.base.models.unified_models import get_provider_for_model_name

    assert get_provider_for_model_name("gpt-4o") == "OpenAI"
    assert get_provider_for_model_name("Mistral-Large-3") == "Azure AI Foundry"
