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


def policy_keys_for_capabilities(capability_ids: Iterable[str]) -> tuple[str, ...]:
    """Return the declared policy keys of loaded capability ids, in order.

    The bundle registry is the source of truth for what a capability id means.
    Ids whose manifest is not loaded in this process contribute no keys, so the
    provider ceiling remains the only decision available for them.
    """
    ids = list(capability_ids)
    if not ids:
        return ()
    try:
        from lfx.extension.bundle_registry import get_default_registry

        integrations = get_default_registry().list_integrations()
    except Exception:  # noqa: BLE001
        return ()
    wanted = set(ids)
    keys: list[str] = []
    for integration in integrations:
        for capability in integration.capability_manifest.capabilities:
            if capability.id in wanted:
                keys.extend(capability.policy_keys)
    return tuple(dict.fromkeys(keys))


def integration_policy_identity_for_component_class(class_name: str) -> tuple[str, tuple[str, ...]] | None:
    """Return ``(provider_id, policy_keys)`` for the class a capability names.

    An API-key-mode action component declares no connection-reference input, so
    the bundle registry's ``component_ref`` is the only declaration that ties it
    to a governed action. Returns ``None`` for every component no loaded
    capability points at, which is every non-integration component.
    """
    if not class_name:
        return None
    try:
        from lfx.extension.bundle_registry import get_default_registry

        integrations = get_default_registry().list_integrations()
    except Exception:  # noqa: BLE001
        return None
    provider_id: str | None = None
    keys: list[str] = []
    for integration in integrations:
        for capability in integration.capability_manifest.capabilities:
            if capability.component_ref == class_name:
                provider_id = integration.provider_id
                keys.extend(capability.policy_keys)
    if provider_id is None:
        return None
    return provider_id, tuple(dict.fromkeys(keys))


def resolve_integration_policy_for_current_context(
    *,
    provider_ids: Iterable[str],
    purpose: IntegrationPolicyPurpose,
) -> IntegrationPolicySnapshot:
    """Resolve a snapshot for the principal bound to the current request.

    Synchronous discovery surfaces (template listing, agentic search) have no
    user argument in scope; they run inside a request that already bound the
    policy context, and fall back to an anonymous context when nothing is bound.
    """
    from lfx.services.model_provider_policy.context import current_model_provider_policy_context

    principal = current_model_provider_policy_context()
    return resolve_integration_policy(
        user_id=principal.user_id if principal is not None else None,
        provider_ids=provider_ids,
        purpose=purpose,
        attributes=principal.attributes if principal is not None else None,
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
