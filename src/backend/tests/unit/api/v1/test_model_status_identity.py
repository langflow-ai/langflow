from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.v1.models import (
    ModelStatusUpdate,
    _build_model_default_flags,
    _update_model_sets,
    build_model_providers_by_name,
    normalize_model_status_entries,
)
from langflow.api.v1.variable import _cleanup_model_list_variable
from lfx.base.models.model_utils import inject_custom_enabled_models
from lfx.base.models.unified_models.credentials import model_status_contains, model_status_key

pytestmark = pytest.mark.no_blockbuster


CATALOG_WITH_SHARED_ALIAS = [
    {
        "provider": "OpenAI",
        "models": [{"model_name": "gpt-4o-mini", "metadata": {"default": False}}],
    },
    {
        "provider": "Azure AI Foundry",
        "models": [{"model_name": "gpt-4o-mini", "metadata": {"default": True}}],
    },
]


def test_model_defaults_and_updates_are_provider_qualified():
    default_flags = _build_model_default_flags(CATALOG_WITH_SHARED_ALIAS)
    providers_by_name = build_model_providers_by_name(CATALOG_WITH_SHARED_ALIAS)

    assert default_flags == {
        "OpenAI::gpt-4o-mini": False,
        "Azure AI Foundry::gpt-4o-mini": True,
    }

    # A pre-upgrade bare entry applied to both providers. On the next write it
    # is expanded before changing only the provider the user toggled.
    disabled_models = normalize_model_status_entries({"gpt-4o-mini"}, providers_by_name)
    explicitly_enabled_models: set[str] = set()
    _update_model_sets(
        [ModelStatusUpdate(provider="OpenAI", model_id="gpt-4o-mini", enabled=True)],
        disabled_models,
        explicitly_enabled_models,
        default_flags,
    )

    assert disabled_models == {"Azure AI Foundry::gpt-4o-mini"}
    assert explicitly_enabled_models == {"OpenAI::gpt-4o-mini"}


def test_foundry_seed_default_stays_explicitly_enabled():
    disabled_models = {"Azure AI Foundry::gpt-4o-mini"}
    explicitly_enabled_models: set[str] = set()

    _update_model_sets(
        [ModelStatusUpdate(provider="Azure AI Foundry", model_id="gpt-4o-mini", enabled=True)],
        disabled_models,
        explicitly_enabled_models,
        {"Azure AI Foundry::gpt-4o-mini": True},
    )

    assert disabled_models == set()
    assert explicitly_enabled_models == {"Azure AI Foundry::gpt-4o-mini"}


def test_typed_model_statuses_are_independent():
    llm_update = ModelStatusUpdate(
        provider="Azure AI Foundry",
        model_id="portal-deploy",
        enabled=True,
        model_type="llm",
    )
    embedding_update = ModelStatusUpdate(
        provider="Azure AI Foundry",
        model_id="portal-deploy",
        enabled=True,
        model_type="embeddings",
    )
    llm_status = model_status_key("Azure AI Foundry", "portal-deploy", model_type="llm")
    embedding_status = model_status_key("Azure AI Foundry", "portal-deploy", model_type="embeddings")

    assert llm_update.model_type == "llm"
    assert embedding_update.model_type == "embeddings"
    assert llm_status != embedding_status

    llm_enabled: set[str] = set()
    _update_model_sets(
        [llm_update],
        set(),
        llm_enabled,
        {"Azure AI Foundry::portal-deploy": False},
    )
    embedding_enabled: set[str] = set()
    _update_model_sets(
        [embedding_update],
        set(),
        embedding_enabled,
        {"Azure AI Foundry::portal-deploy": False},
    )

    assert llm_enabled == {llm_status}
    assert embedding_enabled == {embedding_status}
    assert model_status_contains(
        {llm_status},
        "Azure AI Foundry",
        "portal-deploy",
        model_type="llm",
    )
    assert not model_status_contains(
        {llm_status},
        "Azure AI Foundry",
        "portal-deploy",
        model_type="embeddings",
    )
    assert model_status_contains(
        {embedding_status},
        "Azure AI Foundry",
        "portal-deploy",
        model_type="embeddings",
    )
    assert not model_status_contains(
        {embedding_status},
        "Azure AI Foundry",
        "portal-deploy",
        model_type="llm",
    )


def test_inject_custom_enabled_models_appends_missing_deployments():
    provider_models = [
        {
            "provider": "Azure AI Foundry",
            "models": [
                {
                    "model_name": "gpt-4o",
                    "metadata": {"default": True, "model_type": "llm"},
                }
            ],
            "num_models": 1,
        }
    ]

    inject_custom_enabled_models(
        provider_models,
        {"Azure AI Foundry::gpt-5-mini", "Azure AI Foundry::gpt-4o", "OpenAI::ignored"},
        model_type="llm",
    )

    names = [model["model_name"] for model in provider_models[0]["models"]]
    assert names == ["gpt-4o", "gpt-5-mini"]
    assert provider_models[0]["num_models"] == 2
    custom = provider_models[0]["models"][1]
    assert custom["metadata"]["model_type"] == "llm"
    assert custom["metadata"]["tool_calling"] is True


def test_inject_custom_enabled_models_respects_filters_and_stable_order():
    provider_models = [
        {
            "provider": "Azure AI Foundry",
            "models": [],
            "num_models": 0,
        }
    ]
    enabled = {
        "Azure AI Foundry::zeta-deploy",
        "Azure AI Foundry::alpha-deploy",
        "Azure AI Foundry::beta-deploy",
    }

    inject_custom_enabled_models(
        provider_models,
        enabled,
        model_type="llm",
        metadata_filters={"tool_calling": True},
    )
    names = [model["model_name"] for model in provider_models[0]["models"]]
    assert names == ["alpha-deploy", "beta-deploy", "zeta-deploy"]

    # model_name filter keeps a single match
    provider_models[0]["models"] = []
    inject_custom_enabled_models(
        provider_models,
        enabled,
        model_name="beta-deploy",
        model_type="llm",
    )
    assert [m["model_name"] for m in provider_models[0]["models"]] == ["beta-deploy"]

    # embeddings type + tool_calling=True must not inject (custom embeddings are not tools)
    provider_models[0]["models"] = []
    inject_custom_enabled_models(
        provider_models,
        enabled,
        model_type="embeddings",
        metadata_filters={"tool_calling": True},
    )
    assert provider_models[0]["models"] == []

    provider_models[0]["models"] = []
    inject_custom_enabled_models(
        provider_models,
        {model_status_key("Azure AI Foundry", "text-embed", model_type="embeddings")},
        model_type="embeddings",
    )
    custom = provider_models[0]["models"][0]
    assert custom["model_name"] == "text-embed"
    assert custom["metadata"]["model_type"] == "embeddings"
    assert custom["metadata"]["tool_calling"] is False


def test_inject_custom_enabled_models_creates_provider_stub_for_embeddings():
    """Foundry has no seed embeddings; inject must still create a provider row."""
    provider_models: list[dict] = []
    inject_custom_enabled_models(
        provider_models,
        {model_status_key("Azure AI Foundry", "my-embed-deploy", model_type="embeddings")},
        model_type="embeddings",
    )

    assert len(provider_models) == 1
    assert provider_models[0]["provider"] == "Azure AI Foundry"
    models = provider_models[0]["models"]
    assert len(models) == 1
    assert models[0]["model_name"] == "my-embed-deploy"
    assert models[0]["metadata"]["model_type"] == "embeddings"


def test_inject_custom_enabled_models_uses_persisted_type():
    provider_models = [
        {
            "provider": "Azure AI Foundry",
            "models": [],
            "num_models": 0,
        }
    ]
    inject_custom_enabled_models(
        provider_models,
        {
            model_status_key("Azure AI Foundry", "team-chat", model_type="llm"),
            model_status_key("Azure AI Foundry", "vector-prod", model_type="embeddings"),
        },
    )

    models = provider_models[0]["models"]
    assert {(model["model_name"], model["metadata"]["model_type"]) for model in models} == {
        ("team-chat", "llm"),
        ("vector-prod", "embeddings"),
    }


def test_inject_legacy_custom_enabled_model_defaults_to_llm():
    provider_models = [
        {
            "provider": "Azure AI Foundry",
            "models": [],
            "num_models": 0,
        }
    ]

    inject_custom_enabled_models(
        provider_models,
        {"Azure AI Foundry::legacy-deploy"},
    )

    models = provider_models[0]["models"]
    assert [(model["model_name"], model["metadata"]["model_type"]) for model in models] == [("legacy-deploy", "llm")]


def test_inject_custom_enabled_models_does_not_synthesize_non_custom_provider():
    provider_models = [
        {
            "provider": "OpenAI",
            "models": [],
            "num_models": 0,
        }
    ]

    inject_custom_enabled_models(
        provider_models,
        {"OpenAI::gpt-5-chat-latest"},
        model_type="llm",
        metadata_filters={"tool_calling": True},
    )

    assert provider_models[0]["models"] == []


async def test_provider_cleanup_migrates_legacy_entries_before_removing_target_provider():
    variable_id = uuid4()
    variable_service = SimpleNamespace(
        get_variable_object=AsyncMock(
            return_value=SimpleNamespace(
                id=variable_id,
                value=json.dumps(
                    [
                        "gpt-4o-mini",
                        "OpenAI::custom-deployment",
                        "Azure AI Foundry::gpt-4o-mini",
                        "Anthropic::claude-3-5-sonnet-latest",
                        "unknown-legacy-model",
                    ]
                ),
            )
        ),
        update_variable_fields=AsyncMock(),
        delete_variable=AsyncMock(),
    )
    providers_by_name = build_model_providers_by_name(CATALOG_WITH_SHARED_ALIAS)

    await _cleanup_model_list_variable(
        variable_service,
        uuid4(),
        "__disabled_models__",
        "OpenAI",
        providers_by_name,
        session=SimpleNamespace(),
    )

    variable_service.delete_variable.assert_not_awaited()
    update = variable_service.update_variable_fields.await_args.kwargs["variable"]
    assert set(json.loads(update.value)) == {
        "Azure AI Foundry::gpt-4o-mini",
        "Anthropic::claude-3-5-sonnet-latest",
        "unknown-legacy-model",
    }


async def test_provider_cleanup_ignores_non_string_model_entries():
    variable_id = uuid4()
    variable_service = SimpleNamespace(
        get_variable_object=AsyncMock(
            return_value=SimpleNamespace(
                id=variable_id,
                value=json.dumps(
                    [
                        "OpenAI::custom-deployment",
                        7,
                        "Anthropic::claude-3-5-sonnet-latest",
                    ]
                ),
            )
        ),
        update_variable_fields=AsyncMock(),
        delete_variable=AsyncMock(),
    )

    await _cleanup_model_list_variable(
        variable_service,
        uuid4(),
        "__disabled_models__",
        "OpenAI",
        build_model_providers_by_name(CATALOG_WITH_SHARED_ALIAS),
        session=SimpleNamespace(),
    )

    variable_service.delete_variable.assert_not_awaited()
    update = variable_service.update_variable_fields.await_args.kwargs["variable"]
    assert json.loads(update.value) == ["Anthropic::claude-3-5-sonnet-latest"]
