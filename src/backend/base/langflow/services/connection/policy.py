"""Provider availability for creating or authorizing managed connections."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.extension.bundle_registry import get_default_registry
from lfx.services.integration_policy import integration_policy_key_prefix

if TYPE_CHECKING:
    from lfx.services.integration_policy import IntegrationPolicySnapshot


def provider_has_usable_action(provider: str, policy: IntegrationPolicySnapshot) -> bool:
    """Keep consent available while any loaded action or trigger is allowed."""
    if not policy.allows_provider(provider):
        return False
    capabilities = [
        capability
        for integration in get_default_registry().list_integrations()
        if integration.provider_id == provider
        for capability in integration.capability_manifest.capabilities
    ]
    if capabilities:
        return any(policy.allows_capability(capability) for capability in capabilities)

    # Configured registrations can precede loading the provider bundle. Preserve
    # that path unless action restrictions require a manifest to prove access.
    prefix = integration_policy_key_prefix(provider)
    return not any(key.startswith(prefix) for key in policy.blocked_action_keys)
