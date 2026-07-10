from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.v1.models import (
    ModelStatusUpdate,
    _build_model_default_flags,
    _build_model_providers_by_name,
    _normalize_model_status_entries,
    _update_model_sets,
)
from langflow.api.v1.variable import _cleanup_model_list_variable

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
    providers_by_name = _build_model_providers_by_name(CATALOG_WITH_SHARED_ALIAS)

    assert default_flags == {
        "OpenAI::gpt-4o-mini": False,
        "Azure AI Foundry::gpt-4o-mini": True,
    }

    # A pre-upgrade bare entry applied to both providers. On the next write it
    # is expanded before changing only the provider the user toggled.
    disabled_models = _normalize_model_status_entries({"gpt-4o-mini"}, providers_by_name)
    explicitly_enabled_models: set[str] = set()
    _update_model_sets(
        [ModelStatusUpdate(provider="OpenAI", model_id="gpt-4o-mini", enabled=True)],
        disabled_models,
        explicitly_enabled_models,
        default_flags,
    )

    assert disabled_models == {"Azure AI Foundry::gpt-4o-mini"}
    assert explicitly_enabled_models == {"OpenAI::gpt-4o-mini"}


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
    providers_by_name = _build_model_providers_by_name(CATALOG_WITH_SHARED_ALIAS)

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
