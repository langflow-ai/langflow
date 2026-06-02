"""Rate limiting service implementation.

Provides a configured SlowAPI Limiter instance for rate limiting endpoints.
Uses in-memory storage by default, with support for Redis in production.

Environment Variables:
    LANGFLOW_RATE_LIMIT_PER_MINUTE: Number of requests per minute (default: 5)
    LANGFLOW_RATE_LIMIT_STORAGE: Storage URI (default: "memory://")
    LANGFLOW_RATE_LIMIT_HEADERS_ENABLED: Enable rate limit headers (default: "false")
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from slowapi import Limiter
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    from fastapi import Request

# Global limiter instance
_limiter: Limiter | None = None


def get_rate_limit_string() -> str:
    """Get the rate limit string from environment or default.

    Returns:
        str: Rate limit string in format "N/minute"

    Note:
        If LANGFLOW_RATE_LIMIT_PER_MINUTE is not a valid positive integer,
        defaults to 5 requests per minute.
    """
    per_minute_str = os.getenv("LANGFLOW_RATE_LIMIT_PER_MINUTE", "5")
    try:
        per_minute = int(per_minute_str)
        if per_minute <= 0:
            per_minute = 5
    except (ValueError, TypeError):
        per_minute = 5
    return f"{per_minute}/minute"


def get_rate_limiter() -> Limiter:
    """Get or create the global rate limiter instance.

    Returns:
        Limiter: Configured SlowAPI Limiter instance

    Note:
        Uses in-memory storage by default. Set LANGFLOW_RATE_LIMIT_STORAGE environment
        variable to use Redis or other backends in production.

    Example:
            LANGFLOW_RATE_LIMIT_STORAGE=redis://localhost:6379
    """
    global _limiter  # noqa: PLW0603

    if _limiter is None:
        # Use in-memory storage by default (no Redis required)
        # For production with multiple instances, set LANGFLOW_RATE_LIMIT_STORAGE=redis://...
        storage_uri = os.getenv("LANGFLOW_RATE_LIMIT_STORAGE", "memory://")

        # Disable headers in test/dev environments to avoid Redis dependency
        # Enable in production with LANGFLOW_RATE_LIMIT_HEADERS_ENABLED=true
        headers_enabled = os.getenv("LANGFLOW_RATE_LIMIT_HEADERS_ENABLED", "false").lower() == "true"

        # Choose key function based on proxy configuration
        # When behind trusted proxies (load balancer, reverse proxy), use X-Forwarded-For
        # Otherwise use direct connection IP to prevent header spoofing
        trust_proxy = os.getenv("LANGFLOW_RATE_LIMIT_TRUST_PROXY", "false").lower() == "true"
        key_func = get_client_ip if trust_proxy else get_remote_address

        _limiter = Limiter(
            key_func=key_func,
            default_limits=["100/hour"],
            storage_uri=storage_uri,
            # Headers provide client feedback but require working storage backend
            headers_enabled=headers_enabled,
            # Swallow errors to prevent crashes when storage is unavailable
            swallow_errors=True,
        )

    return _limiter


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request.

    Handles X-Forwarded-For header for proxied requests.

    Args:
        request: FastAPI Request object

    Returns:
        str: Client IP address
    """
    # Check X-Forwarded-For header first (for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"
