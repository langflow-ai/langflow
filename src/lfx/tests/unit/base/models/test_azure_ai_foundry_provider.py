"""Unit tests for the Azure AI Foundry unified model provider.

Covers provider registry presence, metadata shape, parameter mapping
resolution, env-var registration, requirements generation, credential
validation (success, early-return paths), and LLM instantiation (endpoint
wiring and missing-endpoint error).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_azure_ai_foundry_in_provider_registry():
    """Azure AI Foundry must appear in MODEL_PROVIDER_METADATA after import."""
    from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA

    assert "Azure AI Foundry" in MODEL_PROVIDER_METADATA


def test_azure_ai_foundry_metadata_shape():
    """Metadata must declare Azure icon, AzureAIOpenAIApiChatModel mapping, and both variables."""
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
    """Azure AI Foundry must be returned by get_model_providers()."""
    from lfx.base.models.unified_models import get_model_providers

    assert "Azure AI Foundry" in get_model_providers()


def test_azure_ai_foundry_param_mapping_resolves_to_foundry_chat_model():
    """get_provider_param_mapping must resolve model_class and api_key_param for Foundry."""
    from lfx.base.models.model_metadata import get_provider_param_mapping

    mapping = get_provider_param_mapping("Azure AI Foundry")
    assert mapping["model_class"] == "AzureAIOpenAIApiChatModel"
    assert mapping["model_param"] == "model"
    assert mapping["api_key_param"] == "credential"  # pragma: allowlist secret


def test_azure_ai_foundry_env_vars_registered_for_auto_import():
    """Both Foundry env vars must be in VARIABLES_TO_GET_FROM_ENVIRONMENT."""
    from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

    assert "AZURE_AI_FOUNDRY_API_KEY" in VARIABLES_TO_GET_FROM_ENVIRONMENT
    assert "AZURE_AI_FOUNDRY_ENDPOINT" in VARIABLES_TO_GET_FROM_ENVIRONMENT


def test_azure_ai_foundry_resolves_to_langchain_azure_ai():
    """A flow using Azure AI Foundry must include langchain-azure-ai in requirements."""
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


def test_validate_model_provider_key_azure_ai_foundry_success():
    """validate_model_provider_key must pass api_key as credential and endpoint to the model."""
    from lfx.base.models.unified_models import validate_model_provider_key

    calls = []

    class FakeFoundryChatModel:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def invoke(self, _prompt):
            return "ok"

    fake_chat_models = SimpleNamespace(AzureAIOpenAIApiChatModel=FakeFoundryChatModel)
    with patch.dict(
        "sys.modules",
        {
            "langchain_azure_ai": SimpleNamespace(chat_models=fake_chat_models),
            "langchain_azure_ai.chat_models": fake_chat_models,
        },
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",
                "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1",
            },
            model_name="gpt-4o",
        )

    assert calls[0] == {
        "credential": "test-key",
        "endpoint": "https://example.services.ai.azure.com/openai/v1",
        "model": "gpt-4o",
        "max_tokens": 1,
    }


def test_validate_model_provider_key_azure_ai_foundry_returns_early_without_model():
    """validate_model_provider_key must return without error when no model_name is given."""
    from lfx.base.models.unified_models import validate_model_provider_key

    # Should not raise even though no model is supplied — early return expected.
    validate_model_provider_key(
        "Azure AI Foundry",
        {
            "AZURE_AI_FOUNDRY_API_KEY": "test-key",
            "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1",
        },
        model_name=None,
    )


def test_validate_model_provider_key_azure_ai_foundry_returns_early_without_api_key():
    """validate_model_provider_key must return without error when API key is absent."""
    from lfx.base.models.unified_models import validate_model_provider_key

    validate_model_provider_key(
        "Azure AI Foundry",
        {"AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1"},
        model_name="gpt-4o",
    )


def test_validate_model_provider_key_azure_ai_foundry_returns_early_without_endpoint():
    """validate_model_provider_key must return without error when endpoint is absent."""
    from lfx.base.models.unified_models import validate_model_provider_key

    validate_model_provider_key(
        "Azure AI Foundry",
        {"AZURE_AI_FOUNDRY_API_KEY": "test-key"},
        model_name="gpt-4o",
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
    """get_llm must pass endpoint and credential kwargs for Azure AI Foundry."""
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


def test_get_llm_azure_ai_foundry_requires_endpoint():
    """get_llm must raise ValueError with a clear message when endpoint is not configured."""
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
