from __future__ import annotations

import sys
from unittest.mock import AsyncMock, patch

import pytest


def _shared_alias_catalog() -> list[dict]:
    return [
        {
            "provider": "OpenAI",
            "icon": "OpenAI",
            "models": [{"model_name": "gpt-4o", "metadata": {"default": True}}],
        },
        {
            "provider": "Azure AI Foundry",
            "icon": "Azure",
            "models": [{"model_name": "gpt-4o", "metadata": {"default": True}}],
        },
    ]


def test_status_membership_supports_qualified_and_legacy_entries():
    from lfx.base.models.unified_models.credentials import model_status_contains

    assert model_status_contains({"OpenAI::gpt-4o"}, "OpenAI", "gpt-4o")
    assert not model_status_contains({"OpenAI::gpt-4o"}, "Azure AI Foundry", "gpt-4o")
    assert model_status_contains({"gpt-4o"}, "OpenAI", "gpt-4o")
    assert model_status_contains({"gpt-4o"}, "Azure AI Foundry", "gpt-4o")


def test_language_options_scope_status_to_provider():
    from lfx.base.models.unified_models import model_catalog

    with (
        patch.object(model_catalog, "get_unified_models_detailed", return_value=_shared_alias_catalog()),
        patch.object(
            model_catalog,
            "_get_model_status",
            new=AsyncMock(return_value=({"OpenAI::gpt-4o"}, set())),
        ),
        patch.object(
            model_catalog,
            "_fetch_enabled_providers_for_user",
            new=AsyncMock(return_value={"OpenAI", "Azure AI Foundry"}),
        ),
        patch.object(model_catalog, "replace_with_live_models"),
    ):
        options = model_catalog.get_language_model_options(user_id="00000000-0000-0000-0000-000000000001")

    assert {(option["provider"], option["name"]) for option in options} == {("Azure AI Foundry", "gpt-4o")}


def test_legacy_name_normalization_preserves_first_provider():
    from lfx.base.models.unified_models import model_catalog

    with (
        patch.object(model_catalog, "get_unified_models_detailed", return_value=_shared_alias_catalog()),
        patch.object(model_catalog, "get_provider_param_mapping", return_value={}),
    ):
        normalized = model_catalog.normalize_model_names_to_dicts("gpt-4o")

    assert normalized[0]["provider"] == "OpenAI"


def test_reasoning_model_instantiation_omits_temperature_and_preserves_max_tokens():
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured: dict = {}

    class FakeFoundryChatModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    selection = [
        {
            "name": "o3-mini",
            "provider": "Azure AI Foundry",
            "metadata": {"reasoning": True},
        }
    ]
    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="test-key"),
        patch.object(unified_models_module, "get_model_class", return_value=FakeFoundryChatModel),
        patch.object(
            unified_models_module,
            "get_all_variables_for_provider",
            return_value={"AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1"},
        ),
    ):
        get_llm(selection, user_id="user-1", temperature=0.7, max_tokens=25)

    assert "temperature" not in captured
    assert captured["max_tokens"] == 25
    assert captured["request_timeout"] == 10.0


def test_openai_reasoning_instantiation_omits_temperature_and_preserves_max_tokens():
    """OpenAI reasoning models keep the caller's explicit output limit.

    ChatOpenAI normalizes ``max_tokens`` to ``max_completion_tokens`` for
    reasoning models, so Langflow must forward the configured cap instead of
    silently discarding it.
    """
    from lfx.base.models import unified_models as unified_models_module
    from lfx.base.models.unified_models.instantiation import get_llm

    captured: dict = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    selection = [
        {
            "name": "o1",
            "provider": "OpenAI",
            "metadata": {"reasoning": True, "max_tokens_field_name": "max_tokens"},
        }
    ]
    with (
        patch.object(unified_models_module, "get_api_key_for_provider", return_value="test-key"),
        patch.object(unified_models_module, "get_model_class", return_value=FakeChatOpenAI),
        patch.object(unified_models_module, "get_all_variables_for_provider", return_value={}),
    ):
        get_llm(selection, user_id="user-1", temperature=0.7, max_tokens=25)

    assert "temperature" not in captured
    assert captured["max_tokens"] == 25
    assert "max_completion_tokens" not in captured


def test_foundry_validation_fails_when_sdk_is_missing():
    from lfx.base.models.unified_models.credentials import validate_model_provider_key

    with (
        patch.dict(
            sys.modules,
            {"langchain_azure_ai": None, "langchain_azure_ai.chat_models": None},
        ),
        pytest.raises(ValueError, match="langchain-azure-ai"),
    ):
        validate_model_provider_key(
            "Azure AI Foundry",
            {
                "AZURE_AI_FOUNDRY_API_KEY": "test-key",  # pragma: allowlist secret
                "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1",
            },
            model_name="gpt-4o",
        )
