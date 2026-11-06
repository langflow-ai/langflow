"""Provider availability for creating or authorizing managed connections."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from lfx.extension.bundle_registry import get_default_registry
from lfx.extension.discovery import discover_all_extensions
from lfx.extension.integration_manifest import resolve_integration_manifest
from lfx.services.integration_policy import integration_policy_key_prefix

if TYPE_CHECKING:
    from lfx.integrations.capabilities import IntegrationCapability
    from lfx.services.integration_policy import IntegrationPolicySnapshot


def _discover_provider_capabilities(providers: frozenset[str]) -> dict[str, tuple[IntegrationCapability, ...]]:
    """Read validated installed or seed catalogs in one scan without importing components.

    Multiple catalogs claiming the same provider are ambiguous, so they cannot
    establish availability until the runtime loader resolves the conflict.
    """
    extensions, _ = discover_all_extensions()
    capabilities = {}
    for provider in providers:
        matches = [
            (extension, reference)
            for extension in extensions
            for reference in extension.manifest.manifest.integrations
            if reference.provider_id == provider
        ]
        if len(matches) != 1:
            continue
        extension, reference = matches[0]
        bundle = next(bundle for bundle in extension.manifest.manifest.bundles if bundle.name == reference.bundle)
        resolved, error = resolve_integration_manifest(extension.extension_root / bundle.path, reference)
        if error is None and resolved is not None:
            capabilities[provider] = resolved.manifest.capabilities
    return capabilities


async def providers_with_usable_actions(
    provider_ids: frozenset[str], policy: IntegrationPolicySnapshot
) -> frozenset[str]:
    """Keep consent available while any known action or trigger is allowed.

    Loaded metadata takes precedence. Before a bundle loads, restricted access
    requires its validated installed or seed catalog to identify allowed actions.
    One worker-thread discovery serves all such providers in this request. No
    metadata or policy decision is cached across requests.
    """
    integrations = get_default_registry().list_integrations()
    available = set()
    undiscovered = set()
    for provider in provider_ids:
        if not policy.allows_provider(provider):
            continue
        capabilities = [
            capability
            for integration in integrations
            if integration.provider_id == provider
            for capability in integration.capability_manifest.capabilities
        ]
        if capabilities:
            if any(policy.allows_capability(capability) for capability in capabilities):
                available.add(provider)
            continue

        prefix = integration_policy_key_prefix(provider)
        if any(key.startswith(prefix) for key in policy.blocked_action_keys):
            undiscovered.add(provider)
        else:
            available.add(provider)

    if undiscovered:
        discovered = await asyncio.to_thread(_discover_provider_capabilities, frozenset(undiscovered))
        available.update(
            provider
            for provider, capabilities in discovered.items()
            if any(policy.allows_capability(capability) for capability in capabilities)
        )
    return frozenset(available)


async def provider_has_usable_action(provider: str, policy: IntegrationPolicySnapshot) -> bool:
    """Apply the request-scoped availability check to one create or consent operation."""
    return provider in await providers_with_usable_actions(frozenset({provider}), policy)
