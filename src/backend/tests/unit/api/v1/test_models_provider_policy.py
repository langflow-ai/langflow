"""The model-provider policy must hide denied providers across shared OSS APIs."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from lfx.base.models.provider_registry import provider_id_for
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicySnapshot,
)

if TYPE_CHECKING:
    from httpx import AsyncClient


def _openai_only_policy(*, user_id, providers, purpose, attributes=None):
    _ = attributes
    candidate_ids = frozenset(filter(None, (provider_id_for(provider) for provider in providers)))
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id=user_id),
        purpose=purpose,
        candidate_provider_ids=candidate_ids,
        allowed_provider_ids=frozenset({"openai"}) & candidate_ids,
    )


def _allow_all_policy(*, user_id, providers, purpose, attributes=None):
    _ = attributes
    candidate_ids = frozenset(provider_id_for(provider) or provider for provider in providers)
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id=user_id),
        purpose=purpose,
        candidate_provider_ids=candidate_ids,
        allowed_provider_ids=candidate_ids,
    )


@pytest.fixture(autouse=True)
def _restrict_to_openai(monkeypatch):
    monkeypatch.setattr("langflow.api.v1.models.resolve_model_provider_policy", _openai_only_policy)


@pytest.mark.usefixtures("active_user")
async def test_provider_reads_hide_denied_providers(client: AsyncClient, logged_in_headers):
    providers_response = await client.get("api/v1/models/providers", headers=logged_in_headers)
    descriptors_response = await client.get("api/v1/models/provider-descriptors", headers=logged_in_headers)
    models_response = await client.get("api/v1/models", headers=logged_in_headers)
    mapping_response = await client.get("api/v1/models/provider-variable-mapping", headers=logged_in_headers)
    denied_query_response = await client.get(
        "api/v1/models",
        headers=logged_in_headers,
        params={"provider": "Anthropic"},
    )

    assert providers_response.status_code == status.HTTP_200_OK
    assert providers_response.json() == ["OpenAI"]
    assert descriptors_response.status_code == status.HTTP_200_OK
    assert descriptors_response.json() == [{"provider_id": "openai", "display_name": "OpenAI", "provider": "OpenAI"}]

    assert models_response.status_code == status.HTTP_200_OK
    model_groups = models_response.json()
    assert {group["provider"] for group in model_groups} == {"OpenAI"}
    assert {group["provider_id"] for group in model_groups} == {"openai"}

    assert mapping_response.status_code == status.HTTP_200_OK
    assert set(mapping_response.json()) == {"OpenAI"}
    assert denied_query_response.status_code == status.HTTP_200_OK
    assert denied_query_response.json() == []


async def test_provider_descriptors_union_stamped_palette_ids_without_duplicates(monkeypatch):
    from langflow.api.v1 import models as models_module

    captured_candidates = set()

    def _allow_openai_and_mistral(*, user_id, providers, purpose, attributes=None):
        nonlocal captured_candidates
        _ = attributes
        captured_candidates = set(providers)
        candidate_ids = frozenset(provider_id_for(provider) or provider for provider in providers)
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id),
            purpose=purpose,
            candidate_provider_ids=candidate_ids,
            allowed_provider_ids=frozenset({"openai", "mistral"}) & candidate_ids,
        )

    palette = {
        "mixed": {
            "OpenAIModel": {"metadata": {"model_provider_id": "openai", "model_provider_display_name": "OpenAI"}},
            "MistralChat": {"metadata": {"model_provider_id": "mistral", "model_provider_display_name": "Mistral"}},
            "MistralEmbedding": {
                "metadata": {"model_provider_id": "mistral", "model_provider_display_name": "Mistral"}
            },
            "HiddenModel": {
                "metadata": {"model_provider_id": "hidden-provider", "model_provider_display_name": "Hidden"}
            },
            "Utility": {"metadata": {}},
        }
    }
    monkeypatch.setattr(models_module, "resolve_model_provider_policy", _allow_openai_and_mistral)
    monkeypatch.setattr(models_module, "get_model_providers", lambda: ["OpenAI"])
    monkeypatch.setattr(models_module, "get_and_cache_all_types_dict", AsyncMock(return_value=palette))

    descriptors = await models_module.list_model_provider_descriptors(SimpleNamespace(id="user-1"))

    assert [descriptor.model_dump() for descriptor in descriptors] == [
        {"provider_id": "mistral", "display_name": "Mistral", "provider": "mistral"},
        {"provider_id": "openai", "display_name": "OpenAI", "provider": "OpenAI"},
    ]
    assert captured_candidates == {"openai", "mistral", "hidden-provider"}


@pytest.mark.usefixtures("active_user")
async def test_denied_provider_mutations_return_non_enumerating_not_found(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    provider_validation_called = False

    def _provider_validation(*_args, **_kwargs):
        nonlocal provider_validation_called
        provider_validation_called = True

    monkeypatch.setattr("langflow.api.v1.variable.validate_model_provider_key", _provider_validation)
    validate_response = await client.post(
        "api/v1/models/validate-provider",
        headers=logged_in_headers,
        json={
            "provider": "Anthropic",
            "variables": {"ANTHROPIC_API_KEY": "test"},  # pragma: allowlist secret
        },
    )
    default_response = await client.post(
        "api/v1/models/default_model",
        headers=logged_in_headers,
        json={"provider": "Anthropic", "model_name": "claude-test", "model_type": "language"},
    )
    variable_response = await client.post(
        "api/v1/variables/",
        headers=logged_in_headers,
        json={
            "name": "ANTHROPIC_API_KEY",
            "value": "test",  # pragma: allowlist secret
            "type": "Credential",
            "default_fields": [],
        },
    )
    enabled_response = await client.post(
        "api/v1/models/enabled_models",
        headers=logged_in_headers,
        json=[{"provider": "Anthropic", "model_id": "claude-test", "enabled": True}],
    )

    assert validate_response.status_code == status.HTTP_404_NOT_FOUND
    assert default_response.status_code == status.HTTP_404_NOT_FOUND
    assert variable_response.status_code == status.HTTP_404_NOT_FOUND
    assert enabled_response.status_code == status.HTTP_404_NOT_FOUND
    assert provider_validation_called is False


@pytest.mark.usefixtures("active_user")
async def test_dynamic_model_sources_cannot_reintroduce_denied_provider(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    from langflow.api.v1 import models as models_module

    monkeypatch.setattr(
        models_module,
        "get_enabled_providers",
        AsyncMock(
            return_value={
                "enabled_providers": ["OpenAI", "Anthropic"],
                "provider_status": {"OpenAI": True, "Anthropic": True},
            }
        ),
    )
    monkeypatch.setattr(
        models_module,
        "get_enabled_models",
        AsyncMock(return_value={"enabled_models": {}, "enabled_models_by_type": {}}),
    )
    live_provider_sets = []

    def _replace_with_live(groups, _user_id, configured_providers, *_args, **_kwargs):
        live_provider_sets.append(set(configured_providers))
        groups.append({"provider": "Anthropic", "models": [], "num_models": 0})

    def _inject_custom(groups, *_args, **_kwargs):
        groups.append(
            {
                "provider": "Anthropic",
                "models": [{"model_name": "blocked-custom", "metadata": {"model_type": "llm"}}],
                "num_models": 1,
            }
        )

    monkeypatch.setattr(models_module, "replace_with_live_models", _replace_with_live)
    monkeypatch.setattr(models_module, "inject_custom_enabled_models", _inject_custom)

    response = await client.get("api/v1/models", headers=logged_in_headers)

    assert response.status_code == status.HTTP_200_OK
    assert {group["provider"] for group in response.json()} == {"OpenAI"}
    assert live_provider_sets == [{"OpenAI"}]


@pytest.mark.usefixtures("active_user")
async def test_hidden_provider_variables_are_omitted_but_can_be_deleted(
    client: AsyncClient, logged_in_headers, monkeypatch
):
    monkeypatch.setattr("langflow.api.v1.models.resolve_model_provider_policy", _allow_all_policy)
    existing_response = await client.get("api/v1/variables/", headers=logged_in_headers)
    for variable in existing_response.json():
        if variable["name"] == "ANTHROPIC_API_KEY":
            await client.delete(f"api/v1/variables/{variable['id']}", headers=logged_in_headers)

    monkeypatch.setattr("langflow.api.v1.variable.validate_model_provider_key", lambda *_args, **_kwargs: None)
    create_response = await client.post(
        "api/v1/variables/",
        headers=logged_in_headers,
        json={
            "name": "ANTHROPIC_API_KEY",
            "value": "test",  # pragma: allowlist secret
            "type": "Credential",
            "default_fields": [],
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    variable_id = create_response.json()["id"]

    monkeypatch.setattr("langflow.api.v1.models.resolve_model_provider_policy", _openai_only_policy)
    hidden_response = await client.get("api/v1/variables/", headers=logged_in_headers)
    delete_response = await client.delete(f"api/v1/variables/{variable_id}", headers=logged_in_headers)

    assert "ANTHROPIC_API_KEY" not in {variable["name"] for variable in hidden_response.json()}
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
