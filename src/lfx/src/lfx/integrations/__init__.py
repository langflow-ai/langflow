"""Public provider-neutral contracts for dedicated integrations."""

from lfx.integrations.capabilities import (
    ConditionalScopeRequirement,
    IntegrationCapability,
    IntegrationCapabilityManifest,
    IntegrationProvider,
    OAuthProfile,
    ScopeCondition,
    ScopeSet,
)
from lfx.integrations.errors import (
    INTEGRATION_ERROR_CODES,
    ActionUnsupportedError,
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ConnectionUnresolvedError,
    IntegrationError,
    ProviderUnavailableError,
    RateLimitedError,
    ScopeMissingError,
    normalize_integration_error,
    register_error_normalizer,
)
from lfx.integrations.models import (
    ConnectionAccount,
    ConnectionRef,
    ConnectionResolutionRequest,
    ConnectionStatus,
    CredentialLease,
    ResolvedCredential,
)
from lfx.integrations.telemetry import integration_action

__all__ = [
    "INTEGRATION_ERROR_CODES",
    "ActionUnsupportedError",
    "AuthExpiredError",
    "ConditionalScopeRequirement",
    "ConnectionAccount",
    "ConnectionNotAuthorizedError",
    "ConnectionRef",
    "ConnectionResolutionRequest",
    "ConnectionStatus",
    "ConnectionUnresolvedError",
    "CredentialLease",
    "IntegrationCapability",
    "IntegrationCapabilityManifest",
    "IntegrationError",
    "IntegrationProvider",
    "OAuthProfile",
    "ProviderUnavailableError",
    "RateLimitedError",
    "ResolvedCredential",
    "ScopeCondition",
    "ScopeMissingError",
    "ScopeSet",
    "integration_action",
    "normalize_integration_error",
    "register_error_normalizer",
]
