"""Provider-owned OAuth differences behind the shared connection broker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langflow.services.connection.oauth.config import OAuthRegistration


@dataclass(frozen=True)
class OAuthAdapter:
    """Trusted endpoints and response parsing supplied by an installed provider."""

    endpoints: Callable[[OAuthRegistration], tuple[str, str]]
    allowed_origins: tuple[str, ...]
    validate_registration: Callable[[OAuthRegistration], None]
    parse_token: Callable[..., Awaitable[tuple[dict, dict | None]]]
    authorization_params: Callable[[OAuthRegistration], dict[str, str]] | None = None
    scope_separator: str = " "
    token_encoding: Literal["form", "json"] = "form"  # noqa: S105 - serialization format
    supports_pkce: bool = True
    required_scopes: tuple[str, ...] = ()
    # Error codes this provider uses, besides the shared ones, to reject a stored refresh token.
    refresh_rejection_errors: frozenset[str] = frozenset()

    def checked_endpoints(self, registration: OAuthRegistration) -> tuple[str, str]:
        """Reject a provider endpoint outside its declared credential hosts."""
        from langflow.services.connection.oauth.config import OAuthError

        endpoints = self.endpoints(registration)
        for endpoint in endpoints:
            parts = urlsplit(endpoint)
            origin = f"{parts.scheme}://{parts.netloc}"
            if (
                parts.scheme != "https"
                or not parts.hostname
                or parts.username
                or parts.password
                or parts.query
                or parts.fragment
                or origin not in self.allowed_origins
            ):
                msg = "The OAuth endpoint is outside the provider's configured HTTPS origins."
                raise OAuthError(msg, reason="registration-unavailable")
        return endpoints


def provider_adapter(provider_id: str) -> OAuthAdapter | None:
    from langflow.services.triggers.providers.registry import get_provider

    provider = get_provider(provider_id)
    return provider.oauth if provider is not None else None
