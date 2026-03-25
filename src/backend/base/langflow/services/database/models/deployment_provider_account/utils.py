"""Validation helpers for deployment provider account fields.

URL validation enforces two things:

1. **Structure** — :func:`validate_provider_url` ensures the URL is well-formed,
   uses HTTPS, contains no embedded credentials, and is normalised.  This runs
   as a Pydantic field validator on every URL, regardless of provider.

2. **Hostname allowlist** — :func:`check_provider_url_allowed` restricts the URL
   hostname to domains known to belong to the given provider (e.g. ``*.ibm.com``
   for WatsonX Orchestrate).  Providers that are not registered in the allowlist
   are rejected (closed-by-default).  The check is called from the API route
   *before* ``verify_credentials`` so that a spoofed endpoint is blocked before
   any credential exchange occurs.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from langflow.services.database.utils import validate_non_empty_string

_ALLOWED_URL_SCHEMES = frozenset({"https"})
_MAX_URL_LENGTH = 2048


def validate_provider_url(v: str, info: object) -> str:
    """Validate and normalize a provider URL.

    Enforces HTTPS-only, rejects embedded credentials, validates the URL
    structure, and normalises scheme + host to lowercase.
    """
    stripped = validate_non_empty_string(v, info)
    field = getattr(info, "field_name", "Field")

    if len(stripped) > _MAX_URL_LENGTH:
        msg = f"{field} exceeds maximum length of {_MAX_URL_LENGTH}"
        raise ValueError(msg)

    parsed = urlparse(stripped)

    if parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        msg = f"{field} must use the https scheme"
        raise ValueError(msg)

    if parsed.username is not None or parsed.password is not None:
        msg = f"{field} must not contain user credentials"
        raise ValueError(msg)

    hostname = parsed.hostname
    if not hostname:
        msg = f"{field} must contain a valid hostname"
        raise ValueError(msg)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, parsed.fragment))


def validate_provider_url_optional(v: str | None, info: object) -> str | None:
    """Like :func:`validate_provider_url` but allows ``None`` (skip)."""
    if v is None:
        return None
    return validate_provider_url(v, info)


# ---------------------------------------------------------------------------
# Per-provider hostname allowlist
# ---------------------------------------------------------------------------
# Each tuple contains hostname suffixes that the provider is known to operate
# under.  A URL whose hostname ends with any listed suffix is accepted; all
# others are rejected.
#
# When onboarding a new provider, add an entry here BEFORE the provider can
# be used — the check is closed-by-default.

_PROVIDER_HOSTNAME_ALLOWLIST: dict[DeploymentProviderKey, tuple[str, ...]] = {
    # https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=api-getting-endpoint
    DeploymentProviderKey.WATSONX_ORCHESTRATE: (".ibm.com",), # note: on-prem is not supported
}


def check_provider_url_allowed(url: str, provider_key: str | DeploymentProviderKey) -> None:
    """Raise ``ValueError`` if *url* hostname is not allowed for *provider_key*.

    Every provider must have an entry in the allowlist.  If a provider key
    is not registered, the URL is rejected (closed-by-default).
    """
    key = DeploymentProviderKey(provider_key)
    suffixes = _PROVIDER_HOSTNAME_ALLOWLIST.get(key)
    if suffixes is None:
        msg = f"No hostname allowlist configured for provider '{key.value}'"
        raise ValueError(msg)

    hostname = urlparse(url).hostname or ""
    if any(hostname == s.lstrip(".") or hostname.endswith(s) for s in suffixes):
        return

    msg = f"URL hostname '{hostname}' is not allowed for provider '{key.value}'"
    raise ValueError(msg)
