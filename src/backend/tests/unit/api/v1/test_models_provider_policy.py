"""The model-provider policy must hide denied providers across shared OSS APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import status
from lfx.base.models.provider_registry import provider_id_for
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicySnapshot,
)

if TYPE_CHECKING:
    from httpx import AsyncClient


def _openai_only_policy(*, user_id, providers, purpose):
    candidate_ids = frozenset(filter(None, (provider_id_for(provider) for provider in providers)))
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id=user_id),
        purpose=purpose,
        candidate_provider_ids=candidate_ids,
        allowed_provider_ids=frozenset({"openai"}) & candidate_ids,
    )


@pytest.fixture(autouse=True)
def _restrict_to_openai(monkeypatch):
    monkeypatch.setattr("langflow.api.v1.models.resolve_model_provider_policy", _openai_only_policy)


@pytest.mark.usefixtures("active_user")
async def test_provider_reads_hide_denied_providers(client: AsyncClient, logged_in_headers):
    providers_response = await client.get("api/v1/models/providers", headers=logged_in_headers)
    models_response = await client.get("api/v1/models", headers=logged_in_headers)
    mapping_response = await client.get("api/v1/models/provider-variable-mapping", headers=logged_in_headers)

    assert providers_response.status_code == status.HTTP_200_OK
    assert providers_response.json() == ["OpenAI"]

    assert models_response.status_code == status.HTTP_200_OK
    model_groups = models_response.json()
    assert {group["provider"] for group in model_groups} == {"OpenAI"}
    assert {group["provider_id"] for group in model_groups} == {"openai"}

    assert mapping_response.status_code == status.HTTP_200_OK
    assert set(mapping_response.json()) == {"OpenAI"}


@pytest.mark.usefixtures("active_user")
async def test_denied_provider_mutations_return_non_enumerating_not_found(client: AsyncClient, logged_in_headers):
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

    assert validate_response.status_code == status.HTTP_404_NOT_FOUND
    assert default_response.status_code == status.HTTP_404_NOT_FOUND
