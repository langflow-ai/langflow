"""Request-local authentication credential context.

Authentication resolves every credential to a Langflow user, but authorization
plugins sometimes need to know how that user authenticated. Keep that metadata
request-local so API-key caveats can be enforced without changing route
signatures or teaching OSS how to interpret policy.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Protocol
    from uuid import UUID

    class ApiKeyAuthResult(Protocol):
        user: Any
        api_key_source: str
        api_key_id: UUID | None


AUTH_METHOD_API_KEY = "api_key"  # pragma: allowlist secret
AUTH_METHOD_AUTO_LOGIN = "auto_login"
AUTH_METHOD_EXTERNAL = "external"
AUTH_METHOD_JWT = "jwt"


@dataclass(frozen=True)
class AuthCredentialContext:
    """Metadata about the credential that authenticated the current request."""

    method: str
    api_key_id: UUID | None = None
    api_key_source: str | None = None
    external_provider: str | None = None

    @classmethod
    def from_api_key_result(cls, result: ApiKeyAuthResult) -> AuthCredentialContext:
        """Build API-key credential context from an authenticated API-key result.

        Centralizes the API-key projection so every call site stays in sync if the
        set of API-key caveat fields ever changes.
        """
        return cls(
            method=AUTH_METHOD_API_KEY,
            api_key_id=result.api_key_id,
            api_key_source=result.api_key_source,
        )

    def to_authz_context(self) -> dict[str, Any]:
        """Return values safe to pass into authorization plugin context."""
        context: dict[str, Any] = {"auth_method": self.method}
        if self.api_key_id is not None:
            context["api_key_id"] = self.api_key_id
        if self.api_key_source is not None:
            context["api_key_source"] = self.api_key_source
        if self.external_provider is not None:
            context["external_provider"] = self.external_provider
        return context

    def to_audit_details(self) -> dict[str, str]:
        """Return JSON-friendly values safe for authz audit details."""
        details = {"auth_method": self.method}
        if self.api_key_id is not None:
            details["api_key_id"] = str(self.api_key_id)
        if self.api_key_source is not None:
            details["api_key_source"] = self.api_key_source
        if self.external_provider is not None:
            details["external_provider"] = self.external_provider
        return details


_current_auth_context = ContextVar["AuthCredentialContext | None"](
    "langflow_auth_credential_context",
    default=None,
)


def set_current_auth_context(context: AuthCredentialContext | None) -> None:
    """Store credential metadata for the current request/task."""
    _current_auth_context.set(context)


def clear_current_auth_context() -> None:
    """Clear credential metadata for the current request/task."""
    _current_auth_context.set(None)


def get_current_auth_context() -> AuthCredentialContext | None:
    """Return credential metadata for the current request/task, if any."""
    return _current_auth_context.get()


def current_auth_context_for_authz() -> dict[str, Any]:
    """Return current credential metadata as an authz context fragment."""
    context = get_current_auth_context()
    return context.to_authz_context() if context is not None else {}


def current_auth_context_for_audit() -> dict[str, str]:
    """Return current credential metadata as an audit details fragment."""
    context = get_current_auth_context()
    return context.to_audit_details() if context is not None else {}


def current_auth_is_api_key() -> bool:
    """Return True when the active request authenticated with a Langflow API key."""
    context = get_current_auth_context()
    return context is not None and context.method == AUTH_METHOD_API_KEY
