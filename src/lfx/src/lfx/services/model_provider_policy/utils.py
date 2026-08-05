"""Provider-name normalization and policy-service resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.base.models.provider_registry import resolve_provider_id
from lfx.services.model_provider_policy.base import ModelProviderPolicyContext, ModelProviderPolicyPurpose

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from lfx.services.model_provider_policy.base import ModelProviderPolicySnapshot


def _policy_call_arguments(
    *,
    user_id,
    providers: Iterable[str],
    purpose: ModelProviderPolicyPurpose,
    attributes: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Prepare the canonical candidates and effective request context."""
    from lfx.services.model_provider_policy.context import current_model_provider_policy_context

    effective_attributes = attributes
    if effective_attributes is None:
        principal = current_model_provider_policy_context()
        if principal is not None and str(principal.user_id) == str(user_id):
            effective_attributes = principal.attributes

    # Preserve the OSS runtime's historical behavior for legacy or malformed
    # saved selections: registered names resolve to stable IDs, while unknown
    # names remain candidates that the allow-all default can pass through to
    # the existing validation path. Restrictive policies can still omit them.
    return {
        "context": ModelProviderPolicyContext(user_id=user_id, attributes=effective_attributes or {}),
        "candidate_provider_ids": frozenset(resolve_provider_id(provider) for provider in providers),
        "purpose": purpose,
    }


def resolve_model_provider_policy(
    *,
    user_id,
    providers: Iterable[str],
    purpose: ModelProviderPolicyPurpose,
    attributes: Mapping[str, Any] | None = None,
) -> ModelProviderPolicySnapshot:
    """Resolve a policy snapshot for provider names from any catalog surface."""
    from lfx.services.deps import get_model_provider_policy_service

    service = get_model_provider_policy_service()
    return service.resolve(
        **_policy_call_arguments(
            user_id=user_id,
            providers=providers,
            purpose=purpose,
            attributes=attributes,
        )
    )


async def aresolve_model_provider_policy(
    *,
    user_id,
    providers: Iterable[str],
    purpose: ModelProviderPolicyPurpose,
    attributes: Mapping[str, Any] | None = None,
) -> ModelProviderPolicySnapshot:
    """Resolve an immutable snapshot through an async-capable policy source."""
    from lfx.services.deps import get_model_provider_policy_service

    service = get_model_provider_policy_service()
    return await service.aresolve(
        **_policy_call_arguments(
            user_id=user_id,
            providers=providers,
            purpose=purpose,
            attributes=attributes,
        )
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
