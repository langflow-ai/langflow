"""Validation helpers for deployment provider account fields.

URL validation uses a **blocklist** approach: private/reserved IP ranges and
unsafe hostnames are rejected, but any public HTTPS URL is accepted regardless
of provider.  Per-provider **allowlisting** (restricting URLs to known provider
domains such as ``*.cloud.ibm.com`` for WatsonX Orchestrate) is not enforced
here.  Instead, provider-specific URL legitimacy is verified *implicitly* by
the ``verify_credentials`` step during account creation — if the URL doesn't
belong to the expected provider, the credential exchange will fail.

A future enhancement may introduce an explicit per-provider allowlist.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse, urlunparse

from langflow.services.database.utils import validate_non_empty_string

_ALLOWED_URL_SCHEMES = frozenset({"https"})
_MAX_URL_LENGTH = 2048

_PRIVATE_NETWORKS = (
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("224.0.0.0/4"),  # multicast
    ipaddress.ip_network("240.0.0.0/4"),  # reserved for future use
    # IPv6
    ipaddress.ip_network("::/128"),  # unspecified
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),  # multicast
)

_UNSAFE_HOSTNAMES = frozenset({"localhost", "localhost.localdomain"})


def _is_literal_private_ip(hostname: str) -> bool:
    """Return True if *hostname* is a literal private/reserved IP address.

    Handles IPv6-mapped IPv4 addresses (e.g. ``::ffff:127.0.0.1``) by
    extracting the mapped IPv4 address and checking it separately.

    Only checks syntactic IP literals (e.g. ``127.0.0.1``, ``::1``).
    Hostnames that require DNS resolution are *not* checked here — full
    SSRF protection against DNS rebinding must be enforced at the HTTP
    client layer where the outbound connection is made.
    """
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    if any(addr in net for net in _PRIVATE_NETWORKS):
        return True
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return any(addr.ipv4_mapped in net for net in _PRIVATE_NETWORKS)
    return False


def validate_provider_url(v: str, info: object) -> str:
    """Validate and normalize a provider URL.

    Enforces HTTPS-only, rejects private/reserved IP addresses, validates
    the URL structure, and normalises scheme + host to lowercase.
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

    if hostname in _UNSAFE_HOSTNAMES or hostname.endswith(".localhost"):
        msg = f"{field} must not point to a local-only hostname"
        raise ValueError(msg)

    if _is_literal_private_ip(hostname):
        msg = f"{field} must not point to a private or reserved IP address"
        raise ValueError(msg)

    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=parsed.path.rstrip("/") or "/",
    )
    return urlunparse(normalized)


def validate_provider_url_optional(v: str | None, info: object) -> str | None:
    """Like :func:`validate_provider_url` but allows ``None`` (skip)."""
    if v is None:
        return None
    return validate_provider_url(v, info)
