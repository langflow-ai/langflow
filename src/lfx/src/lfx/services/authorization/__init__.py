"""LFX authorization service package (abstract base + default no-op allow-all implementation)."""

from lfx.services.authorization.base import BaseAuthorizationService, ResourceVisibilityScope, ShareRuleSnapshot
from lfx.services.authorization.service import AuthorizationService

__all__ = ["AuthorizationService", "BaseAuthorizationService", "ResourceVisibilityScope", "ShareRuleSnapshot"]
