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


def test_status_membership_scopes_typed_entries_and_preserves_separator_names():
    from lfx.base.models.unified_models.credentials import model_status_contains, model_status_key

    provider = "Azure AI Foundry"
    model_name = "shared::deployment"
    typed_entry = "Azure AI Foundry::llm::shared::deployment"

    assert model_status_key(provider, model_name, model_type="llm") == typed_entry
    assert model_status_contains({typed_entry}, provider, model_name, model_type="llm")
    assert not model_status_contains({typed_entry}, provider, model_name, model_type="embeddings")

    # Provider-qualified and bare pre-type entries remain readable, including
    # deployment names that contain the status separator themselves.
    legacy_entry = "Azure AI Foundry::shared::deployment"
    assert model_status_contains({legacy_entry}, provider, model_name, model_type="llm")
    assert model_status_contains({legacy_entry}, provider, model_name, model_type="embeddings")
    assert model_status_contains({model_name}, provider, model_name, model_type="embeddings")


def test_custom_injection_uses_persisted_type_and_defaults_legacy_to_llm():
    from lfx.base.models.model_utils import inject_custom_enabled_models

    typed_models: list[dict] = []
    inject_custom_enabled_models(
        typed_models,
        {
            "Azure AI Foundry::llm::chat::deployment",
            "Azure AI Foundry::embeddings::embed::deployment",
        },
    )

    typed_pairs = {
        (model["model_name"], model["metadata"]["model_type"])
        for provider in typed_models
        for model in provider["models"]
    }
    assert typed_pairs == {
        ("chat::deployment", "llm"),
        ("embed::deployment", "embeddings"),
    }

    legacy_models: list[dict] = []
    inject_custom_enabled_models(
        legacy_models,
        {"Azure AI Foundry::legacy::deployment"},
    )
    legacy_pairs = [
        (model["model_name"], model["metadata"]["model_type"])
        for provider in legacy_models
        for model in provider["models"]
    ]
    assert legacy_pairs == [("legacy::deployment", "llm")]


def test_custom_injection_skips_mismatched_typed_entry_without_provider_stub():
    from lfx.base.models.model_utils import inject_custom_enabled_models

    provider_models: list[dict] = []
    inject_custom_enabled_models(
        provider_models,
        {"Azure AI Foundry::llm::chat-deployment"},
        model_type="embeddings",
    )

    assert provider_models == []


def test_custom_injection_does_not_fabricate_capabilities_for_non_custom_provider():
    from lfx.base.models.model_utils import inject_custom_enabled_models

    provider_models = [{"provider": "OpenAI", "models": [], "num_models": 0}]
    inject_custom_enabled_models(
        provider_models,
        {"OpenAI::llm::gpt-5-chat-latest"},
        model_type="llm",
        metadata_filters={"tool_calling": True},
    )

    assert provider_models[0]["models"] == []


def test_language_options_scope_status_to_provider():
    from lfx.base.models.unified_models import model_catalog

    with (
        patch.object(model_catalog, "get_unified_models_detailed", return_value=_shared_alias_catalog()),
        patch.object(
            model_catalog,
            "_get_model_status",
            # OpenAI gpt-4o disabled; Foundry gpt-4o must be explicitly enabled
            # (Foundry ignores seed defaults so deployment names never auto-select).
            new=AsyncMock(return_value=({"OpenAI::gpt-4o"}, {"Azure AI Foundry::gpt-4o"})),
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


def test_language_options_include_custom_foundry_deployment():
    """Free-text Foundry deployments must appear in the Agent/Language Model picker."""
    from lfx.base.models.unified_models import model_catalog

    with (
        patch.object(model_catalog, "get_unified_models_detailed", return_value=_shared_alias_catalog()),
        patch.object(
            model_catalog,
            "_get_model_status",
            new=AsyncMock(return_value=(set(), {"Azure AI Foundry::gpt-5-mini"})),
        ),
        patch.object(
            model_catalog,
            "_fetch_enabled_providers_for_user",
            new=AsyncMock(return_value={"Azure AI Foundry"}),
        ),
        patch.object(model_catalog, "replace_with_live_models"),
    ):
        options = model_catalog.get_language_model_options(user_id="00000000-0000-0000-0000-000000000001")

    assert {(option["provider"], option["name"]) for option in options} == {
        ("Azure AI Foundry", "gpt-5-mini"),
    }


def test_typed_custom_deployment_only_appears_in_matching_picker():
    from lfx.base.models.unified_models import model_catalog

    provider = "Azure AI Foundry"
    deployment_name = "shared::deployment"

    def catalog_for_requested_type(*_args, **kwargs):
        model_type = kwargs.get("model_type")
        return [
            {
                "provider": provider,
                "icon": "Azure",
                "models": [
                    {
                        "model_name": deployment_name,
                        "metadata": {"default": False, "model_type": model_type},
                    }
                ],
            }
        ]

    with (
        patch.object(model_catalog, "get_unified_models_detailed", side_effect=catalog_for_requested_type),
        patch.object(
            model_catalog,
            "_get_model_status",
            new=AsyncMock(return_value=(set(), {f"{provider}::embeddings::{deployment_name}"})),
        ),
        patch.object(
            model_catalog,
            "_fetch_enabled_providers_for_user",
            new=AsyncMock(return_value={provider}),
        ),
        patch.object(model_catalog, "replace_with_live_models"),
    ):
        language_options = model_catalog.get_language_model_options(user_id="00000000-0000-0000-0000-000000000001")
        embedding_options = model_catalog.get_embedding_model_options(user_id="00000000-0000-0000-0000-000000000001")

    assert language_options == []
    assert {(option["provider"], option["name"]) for option in embedding_options} == {(provider, deployment_name)}


def test_embedding_lookup_preserves_type_for_same_name_catalog_rows():
    from lfx.base.models.unified_models import instantiation

    provider = "Azure AI Foundry"
    deployment_name = "shared::deployment"
    catalog_rows = [
        {
            "model_name": deployment_name,
            "metadata": {"default": False, "model_type": "embeddings"},
        },
        {
            "model_name": deployment_name,
            "metadata": {"default": False, "model_type": "llm"},
        },
    ]

    with (
        patch.object(instantiation, "_get_provider_catalog_models", return_value=catalog_rows),
        patch.object(
            instantiation,
            "_get_model_status",
            new=AsyncMock(return_value=(set(), {f"{provider}::embeddings::{deployment_name}"})),
        ),
        patch.object(
            instantiation,
            "_fetch_enabled_providers_for_user",
            new=AsyncMock(return_value={provider}),
        ),
    ):
        names = instantiation._get_provider_embedding_model_names(
            provider,
            "00000000-0000-0000-0000-000000000001",
        )

    assert names == [deployment_name]


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
