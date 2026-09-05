"""Resolution helpers for integration provider and action policy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.services.integration_policy.base import (
    IntegrationPolicyContext,
    IntegrationPolicyPurpose,
    integration_policy_key_provider,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from lfx.services.integration_policy.base import IntegrationPolicySnapshot


def _policy_call_arguments(
    *,
    user_id,
    provider_ids: Iterable[str],
    purpose: IntegrationPolicyPurpose,
    attributes: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Prepare the candidate set and the effective request context.

    The integration context is the model-provider context, so an execution
    scope already bound by ``scoped_model_provider_policy_for_flow`` applies
    here without a second binding seam.
    """
    from lfx.services.model_provider_policy.context import current_model_provider_policy_context

    effective_attributes = attributes
    if effective_attributes is None:
        principal = current_model_provider_policy_context()
        if principal is not None and str(principal.user_id) == str(user_id):
            effective_attributes = principal.attributes
    return {
        "context": IntegrationPolicyContext(user_id=user_id, attributes=effective_attributes or {}),
        "candidate_provider_ids": frozenset(provider_ids),
        "purpose": purpose,
    }


def resolve_integration_policy(
    *,
    user_id,
    provider_ids: Iterable[str],
    purpose: IntegrationPolicyPurpose,
    attributes: Mapping[str, Any] | None = None,
) -> IntegrationPolicySnapshot:
    """Resolve one integration policy snapshot for a set of providers."""
    from lfx.services.deps import get_integration_policy_service

    service = get_integration_policy_service()
    return service.resolve(
        **_policy_call_arguments(
            user_id=user_id,
            provider_ids=provider_ids,
            purpose=purpose,
            attributes=attributes,
        )
    )


async def aresolve_integration_policy(
    *,
    user_id,
    provider_ids: Iterable[str],
    purpose: IntegrationPolicyPurpose,
    attributes: Mapping[str, Any] | None = None,
) -> IntegrationPolicySnapshot:
    """Resolve one snapshot through the async-capable policy source."""
    from lfx.services.deps import get_integration_policy_service

    service = get_integration_policy_service()
    return await service.aresolve(
        **_policy_call_arguments(
            user_id=user_id,
            provider_ids=provider_ids,
            purpose=purpose,
            attributes=attributes,
        )
    )


def require_integration_provider(
    *,
    user_id,
    provider_id: str,
    purpose: IntegrationPolicyPurpose = IntegrationPolicyPurpose.USE,
    attributes: Mapping[str, Any] | None = None,
) -> IntegrationPolicySnapshot:
    """Require one provider before any credential lookup or adapter call."""
    snapshot = resolve_integration_policy(
        user_id=user_id,
        provider_ids=[provider_id],
        purpose=purpose,
        attributes=attributes,
    )
    snapshot.require_provider(provider_id)
    return snapshot


def require_integration_actions(
    *,
    user_id,
    provider_id: str,
    policy_keys: Iterable[str],
    purpose: IntegrationPolicyPurpose = IntegrationPolicyPurpose.USE,
    attributes: Mapping[str, Any] | None = None,
) -> IntegrationPolicySnapshot:
    """Require one provider and every action key it is being used for."""
    keys = list(policy_keys)
    candidates = {provider_id}
    for key in keys:
        try:
            candidates.add(integration_policy_key_provider(key))
        except ValueError:
            # Malformed keys stay in the request so ``require_action`` denies
            # them explicitly instead of being silently dropped here.
            continue
    snapshot = resolve_integration_policy(
        user_id=user_id,
        provider_ids=candidates,
        purpose=purpose,
        attributes=attributes,
    )
    snapshot.require_provider(provider_id)
    snapshot.require_actions(keys)
    return snapshot


async def arequire_integration_actions(
    *,
    user_id,
    provider_id: str,
    policy_keys: Iterable[str],
    purpose: IntegrationPolicyPurpose = IntegrationPolicyPurpose.USE,
    attributes: Mapping[str, Any] | None = None,
) -> IntegrationPolicySnapshot:
    """Async twin of :func:`require_integration_actions`."""
    keys = list(policy_keys)
    candidates = {provider_id}
    for key in keys:
        try:
            candidates.add(integration_policy_key_provider(key))
        except ValueError:
            continue
    snapshot = await aresolve_integration_policy(
        user_id=user_id,
        provider_ids=candidates,
        purpose=purpose,
        attributes=attributes,
    )
    snapshot.require_provider(provider_id)
    snapshot.require_actions(keys)
    return snapshot
