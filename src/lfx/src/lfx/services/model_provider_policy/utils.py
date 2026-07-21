"""Provider-name normalization and policy-service resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.base.models.provider_registry import provider_id_for
from lfx.services.model_provider_policy.base import ModelProviderPolicyContext, ModelProviderPolicyPurpose

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from lfx.services.model_provider_policy.base import ModelProviderPolicySnapshot


def resolve_model_provider_policy(
    *,
    user_id,
    providers: Iterable[str],
    purpose: ModelProviderPolicyPurpose,
    attributes: Mapping[str, Any] | None = None,
) -> ModelProviderPolicySnapshot:
    """Resolve a policy snapshot for provider names from any catalog surface."""
    from lfx.services.deps import get_model_provider_policy_service

    # Preserve the OSS runtime's historical behavior for legacy or malformed
    # saved selections: registered names resolve to stable IDs, while unknown
    # names remain candidates that the allow-all default can pass through to
    # the existing validation path. Restrictive policies can still omit them.
    candidate_ids = frozenset(provider_id_for(provider) or provider for provider in providers)
    service = get_model_provider_policy_service()
    return service.resolve(
        context=ModelProviderPolicyContext(user_id=user_id, attributes=attributes or {}),
        candidate_provider_ids=candidate_ids,
        purpose=purpose,
    )


def require_model_provider(
    *,
    user_id,
    provider: str,
    purpose: ModelProviderPolicyPurpose = ModelProviderPolicyPurpose.USE,
    attributes: Mapping[str, Any] | None = None,
) -> ModelProviderPolicySnapshot:
    """Require one provider before any secret lookup or network-capable import."""
    snapshot = resolve_model_provider_policy(
        user_id=user_id,
        providers=[provider],
        purpose=purpose,
        attributes=attributes,
    )
    snapshot.require(provider)
    return snapshot
