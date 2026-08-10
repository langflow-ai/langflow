"""LFX authorization service package (abstract base + default no-op allow-all implementation)."""

from lfx.services.authorization.base import (
    AuthorizationMutation,
    AuthorizationMutationKind,
    AuthorizationMutationRejected,
    BaseAuthorizationService,
    DirectoryMembershipClaimState,
    DirectoryMembershipIngestResult,
    DirectoryMembershipSnapshot,
    ResourceVisibilityScope,
    ShareRuleSnapshot,
    UserAuthorizationSnapshot,
)
from lfx.services.authorization.service import AuthorizationService

__all__ = [
    "AuthorizationMutation",
    "AuthorizationMutationKind",
    "AuthorizationMutationRejected",
    "AuthorizationService",
    "BaseAuthorizationService",
    "DirectoryMembershipClaimState",
    "DirectoryMembershipIngestResult",
    "DirectoryMembershipSnapshot",
    "ResourceVisibilityScope",
    "ShareRuleSnapshot",
    "UserAuthorizationSnapshot",
]
