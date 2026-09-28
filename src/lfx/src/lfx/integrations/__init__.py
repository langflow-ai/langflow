"""Public provider-neutral contracts for dedicated integrations."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.integrations.capabilities import (
        ConditionalScopeRequirement,
        IntegrationCapability,
        IntegrationCapabilityManifest,
        IntegrationProvider,
        McpToolPin,
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
        IncompatibleToolError,
        IntegrationError,
        IntegrationPolicyBlockedError,
        InvalidRequestError,
        ProviderUnavailableError,
        RateLimitedError,
        ResourceNotFoundError,
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
    "IncompatibleToolError",
    "IntegrationCapability",
    "IntegrationCapabilityManifest",
    "IntegrationError",
    "IntegrationPolicyBlockedError",
    "IntegrationProvider",
    "InvalidRequestError",
    "McpToolPin",
    "OAuthProfile",
    "ProviderUnavailableError",
    "RateLimitedError",
    "ResolvedCredential",
    "ResourceNotFoundError",
    "ScopeCondition",
    "ScopeMissingError",
    "ScopeSet",
    "integration_action",
    "normalize_integration_error",
    "register_error_normalizer",
]

_MODULES = {
    **dict.fromkeys(
        (
            "ConditionalScopeRequirement",
            "IntegrationCapability",
            "IntegrationCapabilityManifest",
            "IntegrationProvider",
            "McpToolPin",
            "OAuthProfile",
            "ScopeCondition",
            "ScopeSet",
        ),
        "capabilities",
    ),
    **dict.fromkeys(
        (
            "ConnectionAccount",
            "ConnectionRef",
            "ConnectionResolutionRequest",
            "ConnectionStatus",
            "CredentialLease",
            "ResolvedCredential",
        ),
        "models",
    ),
    **dict.fromkeys(
        (
            "INTEGRATION_ERROR_CODES",
            "ActionUnsupportedError",
            "AuthExpiredError",
            "ConnectionNotAuthorizedError",
            "ConnectionUnresolvedError",
            "IncompatibleToolError",
            "IntegrationError",
            "IntegrationPolicyBlockedError",
            "InvalidRequestError",
            "ProviderUnavailableError",
            "RateLimitedError",
            "ResourceNotFoundError",
            "ScopeMissingError",
            "normalize_integration_error",
            "register_error_normalizer",
        ),
        "errors",
    ),
    "integration_action": "telemetry",
}


def __getattr__(name: str) -> Any:
    """Load runtime contracts only when requested, keeping schema imports light."""
    module = _MODULES.get(name)
    if module is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value
