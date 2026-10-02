"""Enforce a single owner for integration identities in a registry snapshot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.extension.errors import ExtensionError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from lfx.extension.loader import LoadedIntegration


class IntegrationConflictError(ValueError):
    """A proposed registry snapshot contains ambiguous integration metadata."""

    def __init__(self, errors: list[ExtensionError]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(error.message for error in errors))


def validate_integration_ownership(integrations: Iterable[LoadedIntegration]) -> None:
    """Reject shared provider identities, action ids, or cross-provider policy keys.

    One provider may intentionally group several actions under a policy key.
    Another provider or bundle cannot claim that key. Callers validate the
    proposed snapshot before publishing it, excluding the record being reloaded.
    """
    owners: dict[tuple[str, str], LoadedIntegration] = {}
    errors: list[ExtensionError] = []
    for integration in integrations:
        claims = {("provider_id", integration.provider_id)}
        for capability in integration.capability_manifest.capabilities:
            claims.add(("capability id", capability.id))
            claims.update(("policy key", key) for key in capability.policy_keys)
        for kind, key in sorted(claims):
            previous = owners.get((kind, key))
            if previous is None:
                owners[kind, key] = integration
                continue
            errors.append(
                ExtensionError(
                    code="integration-identity-conflict",
                    message=(
                        f"Integration {kind} {key!r} is claimed by both "
                        f"{previous.extension_id!r}/{previous.bundle!r} ({previous.provider_id}) and "
                        f"{integration.extension_id!r}/{integration.bundle!r} ({integration.provider_id})."
                    ),
                    location=f"{previous.manifest_path} -> {integration.manifest_path}",
                    content=key,
                    hint="Remove the conflicting bundle or assign distinct provider, capability, and policy keys.",
                )
            )
    if errors:
        raise IntegrationConflictError(errors)
