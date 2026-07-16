"""Rate limiting service implementation.

Provides a configured SlowAPI Limiter instance for rate limiting endpoints.
Uses in-memory storage by default, with support for Redis in production.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from limits import parse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.wrappers import Limit

from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from fastapi import Request

# Global limiter instance
_limiter: Limiter | None = None


def get_rate_limit_string() -> str:
    """Get the rate limit string from settings.

    Returns:
        str: Rate limit string in format "N/minute", or a very high limit if disabled
    """
    settings = get_settings_service().settings
    if not settings.rate_limit_enabled:
        # Return a very high limit to effectively disable rate limiting
        return "10000/minute"
    return f"{settings.rate_limit_per_minute}/minute"


def get_rate_limiter() -> Limiter:
    """Get or create the global rate limiter instance.

    Returns:
        Limiter: Configured SlowAPI Limiter instance
    """
    global _limiter  # noqa: PLW0603

    if _limiter is None:
        settings = get_settings_service().settings

        # Choose key function based on proxy configuration
        # When behind trusted proxies (load balancer, reverse proxy), use X-Forwarded-For
        # Otherwise use direct connection IP to prevent header spoofing
        key_func = get_client_ip if settings.rate_limit_trust_proxy else get_remote_address

        _limiter = Limiter(
            key_func=key_func,
            storage_uri=settings.rate_limit_storage_uri,
            # Don't swallow errors - we want rate limit violations to raise exceptions
            swallow_errors=False,
        )

    return _limiter


def check_rate_limit(
    request: Request,
    *,
    scope: str | None = None,
    limit_per_minute: int | None = None,
) -> None:
    """Enforce the configured rate limit for a request.

    A scope creates a distinct counter namespace while retaining the configured
    client-IP key. This lets public flows have independent build counters without
    consuming the login-attempt counter for the same client.

    Args:
        request: FastAPI request whose app owns the configured limiter.
        scope: Optional counter namespace, such as a public flow identifier.
        limit_per_minute: Optional endpoint-specific limit. When omitted, the
            configured login limit is used.

    Raises:
        RateLimitExceeded: If the configured limit has been exceeded.
    """
    limiter = request.app.state.limiter
    limit_string = f"{limit_per_minute}/minute" if limit_per_minute is not None else get_rate_limit_string()
    limit_item = parse(limit_string)
    client_key = limiter._key_func(request)  # noqa: SLF001
    identifiers = (scope, client_key) if scope is not None else (client_key,)

    if not limiter._limiter.hit(limit_item, *identifiers):  # noqa: SLF001
        limit_wrapper = Limit(
            limit=limit_item,
            key_func=limiter._key_func,  # noqa: SLF001
            scope=scope,
            per_method=False,
            methods=None,
            error_message=None,
            exempt_when=None,
            cost=1,
            override_defaults=False,
        )
        raise RateLimitExceeded(limit_wrapper)


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request, using rightmost X-Forwarded-For entry.

    When behind a trusted proxy, the rightmost IP in X-Forwarded-For is the last hop
    before our server (the trusted proxy itself). The leftmost IP is client-supplied
    and can be spoofed.

    Args:
        request: FastAPI Request object

    Returns:
        str: Client IP address
    """
    # Check X-Forwarded-For header first (for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For format: "client, proxy1, proxy2"
        # Take the rightmost IP (last proxy before us)
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        return ips[-1]

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


def get_limiter_key(request: Request) -> str:
    """Get the key that the limiter will actually use for this request.

    This matches the limiter's key_func to ensure logging uses the same IP.

    Args:
        request: FastAPI Request object

    Returns:
        str: The IP address or key used for rate limiting
    """
    settings = get_settings_service().settings
    if settings.rate_limit_trust_proxy:
        return get_client_ip(request)
    return get_remote_address(request)
