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

Tenant/URL consistency
----------------------
:func:`extract_tenant_from_url` derives the provider tenant identifier from
a URL using per-provider extraction logic.  :func:`validate_tenant_url_consistency`
verifies that a stored ``provider_tenant_id`` matches what the URL implies.
Both are used by the ``DeploymentProviderAccount`` model validator and the
deployment mapper layer.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

if TYPE_CHECKING:
    from collections.abc import Callable

from langflow.services.adapters.deployment.watsonx_orchestrate.local_dev import wxo_local_instance_hostnames
from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey
from langflow.services.database.utils import validate_non_empty_string

_ALLOWED_URL_SCHEMES = frozenset({"https"})
_MAX_URL_LENGTH = 2048
_WXO_LOCAL_DEV_ENV = "LANGFLOW_WXO_LOCAL_DEV"


def _wxo_local_dev_enabled() -> bool:
    return os.getenv(_WXO_LOCAL_DEV_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _http_localhost_allowed(hostname: str) -> bool:
    if not _wxo_local_dev_enabled():
        return False
    return (hostname or "").lower() in wxo_local_instance_hostnames()


def validate_provider_url(v: str, info: object) -> str:
    """Validate and normalize a provider URL.

    Enforces HTTPS-only (except ``http://`` on loopback when
    ``LANGFLOW_WXO_LOCAL_DEV`` is enabled), rejects embedded credentials,
    validates the URL structure, and normalises scheme + host to lowercase.
    """
    stripped = validate_non_empty_string(v, info)
    field = getattr(info, "field_name", "Field")

    if len(stripped) > _MAX_URL_LENGTH:
        msg = f"{field} exceeds maximum length of {_MAX_URL_LENGTH}"
        raise ValueError(msg)

    parsed = urlparse(stripped)
    scheme_l = parsed.scheme.lower()
    hostname = parsed.hostname
    if scheme_l == "http" and _http_localhost_allowed(hostname or ""):
        pass
    elif scheme_l not in _ALLOWED_URL_SCHEMES:
        msg = f"{field} must use the https scheme"
        raise ValueError(msg)

    if parsed.username is not None or parsed.password is not None:
        msg = f"{field} must not contain user credentials"
        raise ValueError(msg)

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
    DeploymentProviderKey.WATSONX_ORCHESTRATE: (".ibm.com",),  # note: on-prem is not supported
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
    if (
        key == DeploymentProviderKey.WATSONX_ORCHESTRATE
        and _wxo_local_dev_enabled()
        and hostname.lower() in wxo_local_instance_hostnames()
    ):
        return
    if any(hostname == s.lstrip(".") or hostname.endswith(s) for s in suffixes):
        return

    msg = f"URL hostname '{hostname}' is not allowed for provider '{key.value}'"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Per-provider tenant extraction from URL
# ---------------------------------------------------------------------------


def _extract_wxo_tenant_from_url(url: str) -> str | None:
    """Extract the tenant/instance id from a WXO URL path.

    WXO URLs embed the tenant in the path as ``/instances/{tenant_id}/...``.
    Returns ``None`` if the path does not contain an ``instances`` segment.
    """
    parsed = urlparse(url)
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    try:
        instances_index = path_segments.index("instances")
    except ValueError:
        return None
    account_index = instances_index + 1
    if account_index >= len(path_segments):
        return None
    return path_segments[account_index].strip() or None


_PROVIDER_TENANT_EXTRACTORS: dict[DeploymentProviderKey, Callable[[str], str | None]] = {
    DeploymentProviderKey.WATSONX_ORCHESTRATE: _extract_wxo_tenant_from_url,
}


def extract_tenant_from_url(provider_url: str, provider_key: str | DeploymentProviderKey) -> str | None:
    """Derive the provider tenant identifier from a URL.

    Uses the per-provider extractor registered in
    ``_PROVIDER_TENANT_EXTRACTORS``.  Returns ``None`` for providers without
    a registered extractor (tenant is not embedded in the URL).
    """
    key = DeploymentProviderKey(provider_key)
    extractor = _PROVIDER_TENANT_EXTRACTORS.get(key)
    if extractor is None:
        return None
    return extractor(provider_url)


def validate_tenant_url_consistency(
    provider_url: str,
    provider_tenant_id: str | None,
    provider_key: str | DeploymentProviderKey,
) -> None:
    """Raise ``ValueError`` if *provider_tenant_id* contradicts the URL.

    If the URL implies a tenant (via the per-provider extractor) and
    *provider_tenant_id* is set to a **different** value, the pair is
    inconsistent and must be rejected.  When either value is ``None``
    the check passes — the mapper is responsible for derivation.
    """
    url_tenant = extract_tenant_from_url(provider_url, provider_key)
    if url_tenant is None or provider_tenant_id is None:
        return
    if url_tenant != provider_tenant_id:
        msg = (
            f"provider_tenant_id '{provider_tenant_id}' does not match "
            f"the tenant '{url_tenant}' embedded in provider_url"
        )
        raise ValueError(msg)
