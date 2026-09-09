"""Sanitized, machine-readable failures for provider integrations."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from typing import Any, Literal

_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_TOO_MANY_REQUESTS = 429
HTTP_NOT_IMPLEMENTED = 501

INTEGRATION_ERROR_CODES = frozenset(
    {
        "connection-unresolved",
        "connection-not-authorized",
        "auth-expired",
        "scope-missing",
        "rate-limited",
        "provider-unavailable",
        "action-unsupported",
    }
)


def _sanitize(text: str) -> str:
    from lfx.utils.url_redaction import redact_urls_in_text

    return _EMAIL_RE.sub("[redacted-email]", redact_urls_in_text(text))


def _sanitize_details(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize(value)
    if isinstance(value, dict):
        return {_sanitize(str(key)): _sanitize_details(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_sanitize_details(item) for item in value]
    return value


class IntegrationError(Exception):
    """Base error whose string form is always safe for clients and telemetry."""

    code = "provider-unavailable"

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        provider: str | None = None,
        retryable: bool = False,
        http_status: int | None = None,
        safe_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = _sanitize(message)
        self.safe_message = _sanitize(safe_message or message)
        self.hint = _sanitize(hint) if hint else None
        self.provider = provider
        self.retryable = retryable
        self.http_status = http_status
        self.details = _sanitize_details(details or {})
        super().__init__(self.safe_message)


class ConnectionUnresolvedError(IntegrationError):
    code = "connection-unresolved"

    def __init__(self, handle: str, *, env_key: str | None = None, provider: str | None = None) -> None:
        location = f" Set {env_key} to a token or credential JSON object." if env_key else ""
        super().__init__(
            f"Connection {handle!r} could not be resolved.{location}",
            hint="Configure the connection for this execution environment.",
            provider=provider,
        )
        self.handle = handle
        self.env_key = env_key


class ConnectionNotAuthorizedError(IntegrationError):
    code = "connection-not-authorized"

    def __init__(self, *, provider: str | None = None, reason: Literal["principal", "provider"] = "principal") -> None:
        super().__init__(
            "The provider denied this action."
            if reason == "provider"
            else "This execution principal is not authorized to use the requested connection.",
            hint="Check the provider's access and administrator policy."
            if reason == "provider"
            else "Use an owned or explicitly shared connection.",
            provider=provider,
            http_status=403,
        )


class AuthExpiredError(IntegrationError):
    code = "auth-expired"

    def __init__(self, *, provider: str | None = None, http_status: int | None = 401) -> None:
        super().__init__(
            "The provider credential is expired or was rejected.",
            hint="Reconnect the integration and try again.",
            provider=provider,
            http_status=http_status,
        )


class ScopeMissingError(IntegrationError):
    code = "scope-missing"

    def __init__(self, missing: frozenset[str] = frozenset(), *, provider: str | None = None) -> None:
        super().__init__(
            "The connection does not grant every scope required by this action.",
            hint="Grant the missing scopes and reconnect.",
            provider=provider,
            http_status=403,
            details={"missing": sorted(missing)},
        )
        self.missing = missing


class RateLimitedError(IntegrationError):
    code = "rate-limited"

    def __init__(
        self,
        *,
        provider: str | None = None,
        retry_after: float | None = None,
        http_status: int | None = 429,
    ) -> None:
        super().__init__(
            "The provider rate limit was reached.",
            hint="Retry after the provider's backoff interval.",
            provider=provider,
            retryable=True,
            http_status=http_status,
            details={"retry_after": retry_after} if retry_after is not None else None,
        )
        self.retry_after = retry_after


class ProviderUnavailableError(IntegrationError):
    code = "provider-unavailable"

    def __init__(self, *, provider: str | None = None, http_status: int | None = None) -> None:
        super().__init__(
            "The provider is temporarily unavailable.",
            hint="Retry the action later.",
            provider=provider,
            retryable=True,
            http_status=http_status,
        )


class ActionUnsupportedError(IntegrationError):
    code = "action-unsupported"

    def __init__(self, *, provider: str | None = None, http_status: int | None = None) -> None:
        super().__init__(
            "The provider does not support this action.",
            provider=provider,
            http_status=http_status,
        )


ErrorNormalizer = Callable[[BaseException], IntegrationError | None]
_NORMALIZERS: dict[str, ErrorNormalizer] = {}


def register_error_normalizer(provider: str, normalizer: ErrorNormalizer) -> None:
    """Register a bundle-owned SDK error normalizer without importing its SDK in lfx."""
    if not provider or not callable(normalizer):
        msg = "provider must be non-empty and normalizer must be callable"
        raise ValueError(msg)
    _NORMALIZERS[provider] = normalizer


def _retry_after(exc: BaseException) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _iter_errors(error: BaseException) -> Iterator[BaseException]:
    """Visit wrappers, group members, causes and contexts once, including cycles."""
    pending = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        if current.__context__ is not None:
            pending.append(current.__context__)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        # Supports both built-in ExceptionGroup and its Python 3.10 backport.
        pending.extend(reversed(getattr(current, "exceptions", ())))


def normalize_integration_error(exc: BaseException, *, provider: str) -> IntegrationError:
    """Map provider/transport failures into the stable sanitized error vocabulary."""
    from lfx.base.mcp.util import extract_http_status

    normalizer = _NORMALIZERS.get(provider)
    for error in _iter_errors(exc):
        if isinstance(error, IntegrationError):
            return error
        if normalizer is not None:
            normalized = normalizer(error)
            if normalized is not None:
                return normalized
        if getattr(error, "exceptions", None):
            continue  # Inspect each leaf so status and Retry-After come from the same response.
        status = extract_http_status(error)
        if status == HTTP_UNAUTHORIZED:
            return AuthExpiredError(provider=provider, http_status=status)
        if status == HTTP_FORBIDDEN:
            headers = getattr(getattr(error, "response", None), "headers", {})
            challenge = headers.get("www-authenticate", "")
            if re.search(r'\berror\s*=\s*"?insufficient_scope\b', challenge, re.IGNORECASE):
                return ScopeMissingError(provider=provider)
            return ConnectionNotAuthorizedError(provider=provider, reason="provider")
        if status == HTTP_TOO_MANY_REQUESTS:
            return RateLimitedError(provider=provider, retry_after=_retry_after(error), http_status=status)
        if status in {HTTP_NOT_FOUND, HTTP_METHOD_NOT_ALLOWED, HTTP_NOT_IMPLEMENTED}:
            return ActionUnsupportedError(provider=provider, http_status=status)
        if status is not None:
            return ProviderUnavailableError(provider=provider, http_status=status)
    return ProviderUnavailableError(provider=provider)
