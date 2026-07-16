from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from lfx.base.models.unified_models import get_llm
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicyError,
    ModelProviderPolicyPurpose,
    ModelProviderPolicyService,
    ModelProviderPolicySnapshot,
)


def _restricted_snapshot(*allowed: str) -> ModelProviderPolicySnapshot:
    return ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id="user-1"),
        purpose=ModelProviderPolicyPurpose.USE,
        candidate_provider_ids=frozenset({"openai", "anthropic"}),
        allowed_provider_ids=frozenset(allowed),
    )


def test_default_service_allows_every_candidate():
    service = ModelProviderPolicyService()

    snapshot = service.resolve(
        context=ModelProviderPolicyContext(user_id="user-1"),
        candidate_provider_ids=frozenset({"openai", "anthropic"}),
        purpose=ModelProviderPolicyPurpose.USE,
    )

    assert snapshot.allowed_provider_ids == frozenset({"openai", "anthropic"})
    assert snapshot.allows("OpenAI")
    assert snapshot.allows("Anthropic")


def test_snapshot_is_immutable_and_cannot_allow_non_candidates():
    snapshot = _restricted_snapshot("openai")

    with pytest.raises(FrozenInstanceError):
        snapshot.purpose = ModelProviderPolicyPurpose.CONFIGURE  # type: ignore[misc]

    with pytest.raises(ValueError, match="subset"):
        ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(),
            purpose=ModelProviderPolicyPurpose.DISCOVER,
            candidate_provider_ids=frozenset({"openai"}),
            allowed_provider_ids=frozenset({"openai", "anthropic"}),
        )


def test_runtime_denies_provider_before_credential_resolution(monkeypatch):
    credential_lookup_called = False

    def _credential_lookup(*_args, **_kwargs):
        nonlocal credential_lookup_called
        credential_lookup_called = True
        return "secret"

    monkeypatch.setattr("lfx.base.models.unified_models.get_api_key_for_provider", _credential_lookup)

    with pytest.raises(ModelProviderPolicyError) as exc_info:
        get_llm(
            [{"name": "claude-test", "provider": "Anthropic", "metadata": {}}],
            user_id="user-1",
            provider_policy=_restricted_snapshot("openai"),
        )

    assert exc_info.value.code == "policy_blocked"
    assert credential_lookup_called is False
