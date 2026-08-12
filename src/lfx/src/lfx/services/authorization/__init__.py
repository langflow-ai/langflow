"""LFX authorization service package (abstract base + default no-op allow-all implementation)."""

from lfx.services.authorization.base import (
    PUBLIC_ANONYMOUS_ACTOR_ID,
    AuthorizationAuditEvent,
    AuthorizationMutation,
    AuthorizationMutationKind,
    AuthorizationMutationRejected,
    AuthorizationPrincipal,
    BaseAuthorizationService,
    DirectoryMembershipClaimState,
    DirectoryMembershipIngestResult,
    DirectoryMembershipSnapshot,
    PublicAuthorizationRequest,
    PublicResourceAction,
    ResourceVisibilityScope,
    ShareRuleSnapshot,
    UserAuthorizationSnapshot,
)
from lfx.services.authorization.service import AuthorizationService

__all__ = [
    "PUBLIC_ANONYMOUS_ACTOR_ID",
    "AuthorizationAuditEvent",
    "AuthorizationMutation",
    "AuthorizationMutationKind",
    "AuthorizationMutationRejected",
    "AuthorizationPrincipal",
    "AuthorizationService",
    "BaseAuthorizationService",
    "DirectoryMembershipClaimState",
    "DirectoryMembershipIngestResult",
    "DirectoryMembershipSnapshot",
    "PublicAuthorizationRequest",
    "PublicResourceAction",
    "ResourceVisibilityScope",
    "ShareRuleSnapshot",
    "UserAuthorizationSnapshot",
]
