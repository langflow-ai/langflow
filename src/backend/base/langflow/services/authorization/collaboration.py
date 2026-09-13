"""Fail-closed capability discovery for the registered collaboration service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from langflow.services.deps import get_authorization_service

if TYPE_CHECKING:
    from lfx.services.authorization.base import BaseAuthorizationService


@dataclass(frozen=True, slots=True)
class CollaborationCapabilities:
    """Verified capabilities advertised by the currently registered service."""

    enforcement_active: bool
    service_ready: bool
    team_roles_supported: bool
    user_team_sharing_supported: bool
    conditional_writes_supported: bool

    @property
    def collaboration_ready(self) -> bool:
        return (
            self.enforcement_active
            and self.service_ready
            and self.team_roles_supported
            and self.user_team_sharing_supported
        )

    @property
    def conditional_writes_required(self) -> bool:
        return self.enforcement_active and self.conditional_writes_supported


class CollaborationCapabilityError(RuntimeError):
    """The registered service could not safely report its capabilities."""


async def discover_collaboration_capabilities(
    service: BaseAuthorizationService | None = None,
) -> CollaborationCapabilities:
    """Probe the actual service without treating lookup failures as disabled mode.

    A caller deciding whether a security precondition is mandatory must never
    catch an initialization/settings error and silently select a weaker path.
    This helper therefore raises one sanitized domain error on any failed probe.
    """
    try:
        resolved = service or get_authorization_service()
        enforcement_active = bool(await resolved.is_enabled())
        team_roles_supported = bool(await resolved.supports_team_roles())
        user_team_sharing_supported = bool(await resolved.supports_user_team_sharing())
        conditional_writes_supported = bool(await resolved.supports_conditional_writes())
        readiness_probe = getattr(resolved, "collaboration_ready", None)
        schema_ready = bool(await readiness_probe()) if readiness_probe is not None else bool(resolved.ready)
        service_ready = bool(resolved.ready) and schema_ready
    except Exception as exc:
        message = "Authorization capability discovery failed"
        raise CollaborationCapabilityError(message) from exc

    if enforcement_active and not service_ready:
        message = "Authorization service is not ready"
        raise CollaborationCapabilityError(message)

    return CollaborationCapabilities(
        enforcement_active=enforcement_active,
        service_ready=service_ready,
        team_roles_supported=team_roles_supported,
        user_team_sharing_supported=user_team_sharing_supported,
        conditional_writes_supported=conditional_writes_supported,
    )


__all__ = [
    "CollaborationCapabilities",
    "CollaborationCapabilityError",
    "discover_collaboration_capabilities",
]
