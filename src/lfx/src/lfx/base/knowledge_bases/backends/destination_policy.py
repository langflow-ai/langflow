"""Operator-controlled destination policy for the network Knowledge Base backends.

Why this exists on top of ``validate_connector_url_for_ssrf``
-------------------------------------------------------------

The connector SSRF guard is *validate-then-connect*: it resolves the hostname,
checks the answers against the blocklist, and then hands the original URL to a
third-party SDK that resolves DNS again at connect time. For the SDKs the API
Request component uses we close that window by pinning the validated IPs
(``lfx.utils.ssrf_transport.SSRFProtectedTransport``), but neither KB network SDK
offers a seam for it:

* ``chromadb.CloudClient`` builds its own ``httpx.Client`` inside
  ``chromadb.api.fastapi.FastAPI.__init__`` with no transport parameter, and
  ``Client.__init__`` makes an identity request *during construction*, so there is
  no moment between "client exists" and "first request" in which to install one.
* ``langchain_community``'s ``OpenSearchVectorSearch`` forwards one ``**kwargs``
  dict to both ``OpenSearch`` (urllib3) and ``AsyncOpenSearch`` (aiohttp), so a
  single ``connection_class`` cannot pin both transports.

So for these two backends a tenant-chosen *hostname* whose DNS answer flips
between validation and the SDK's own resolution can still land on an internal
address. Literal IP targets — cloud metadata at ``169.254.169.254``, RFC1918
literals — have no DNS to rebind and are blocked by the SSRF guard either way;
this module closes the hostname case instead, by requiring the destination to be
one the *operator* chose rather than one the tenant supplied.

The policy
----------

A KB network destination is permitted only when it is operator-controlled:

* its value came from a process environment variable (only whoever runs the
  server can set one), or
* its host is named in ``LANGFLOW_KB_ALLOWED_HOSTS``.

Anything else — a URL written into a Langflow variable through the UI/API, a
``cloud_host`` posted in a request body — is refused whether or not the host
looks public. That exclusivity is the point: ``LANGFLOW_SSRF_ALLOWED_HOSTS`` is an
*exception* list that widens the blocklist and still admits every unlisted public
host, which is exactly what a rebinding record presents itself as.

This gate runs *in addition to* ``validate_connector_url_for_ssrf``, never instead
of it: an operator-provenance URL still may not name a blocked IP, so an env var
pointing at cloud metadata stays refused. Operators with a genuinely internal
cluster keep using ``LANGFLOW_SSRF_ALLOWED_HOSTS`` for the IP policy, as before.

Both gates share one kill switch: ``LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED=false``
turns connector destination policy off wholesale for single-tenant deployments.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from lfx.services.deps import get_settings_service
from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_connector_ssrf_validation_enabled,
    is_host_allowed,
)

__all__ = [
    "enforce_kb_destination",
    "get_kb_allowed_hosts",
    "is_kb_destination_host_allowed",
]


def get_kb_allowed_hosts() -> list[str]:
    """Operator-approved destination hosts for the network KB backends.

    Read from the environment first so tests (and ``patch.dict``) can override it
    without fighting the settings-service cache, mirroring
    :func:`lfx.utils.ssrf_protection.get_allowed_hosts`.

    Returns:
        Stripped host / CIDR patterns, or an empty list when unset. Empty means
        *nothing* tenant-supplied is approved — this is an exclusive list, so an
        empty one denies rather than allows.
    """
    env_value = os.getenv("LANGFLOW_KB_ALLOWED_HOSTS", "")
    if env_value:
        return [host.strip() for host in env_value.split(",") if host.strip()]

    try:
        settings_service = get_settings_service()
    except Exception:  # noqa: BLE001 — settings service is optional in lfx-only contexts
        return []
    if settings_service is None:
        return []
    configured = getattr(settings_service.settings, "kb_allowed_hosts", None)
    if configured:
        return [host.strip() for host in configured if host and host.strip()]
    return []


def is_kb_destination_host_allowed(hostname: str) -> bool:
    """Whether ``hostname`` is named in the operator's KB destination allow-list."""
    allowed = get_kb_allowed_hosts()
    if not allowed:
        return False
    # Reuse the SSRF matcher so exact hosts, wildcard domains (*.corp.example),
    # literal IPs and CIDR blocks behave identically in both lists.
    ip = hostname if _is_ip_literal(hostname) else None
    return is_host_allowed(hostname, ip=ip, allowed_hosts=allowed)


def _is_ip_literal(hostname: str) -> bool:
    import ipaddress

    try:
        ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        return False
    return True


def enforce_kb_destination(url: str, *, source: str, description: str) -> None:
    """Refuse a KB network destination the operator did not choose.

    Args:
        url: The destination about to be dialed, as an http(s) URL.
        source: Provenance of the value — ``"environment"`` for a process env var
            (operator-controlled), anything else for tenant-supplied input.
        description: Where the value came from, for the error message
            (e.g. ``"Langflow variable 'OPENSEARCH_URL'"``).

    Raises:
        SSRFProtectionError: If the destination is tenant-supplied and its host is
            not named in ``LANGFLOW_KB_ALLOWED_HOSTS``.
    """
    if not is_connector_ssrf_validation_enabled():
        return
    if source == "environment":
        # Only whoever runs the server can set a process env var, so the value is
        # operator-controlled. The IP/DNS policy in validate_connector_url_for_ssrf
        # still applies on top — this gate decides *who chose the host*, not
        # whether that host is a safe address.
        return

    hostname = urlparse(url).hostname
    if not hostname:
        # Malformed or scheme-less: let validate_connector_url_for_ssrf own the
        # canonical shape error rather than inventing a second wording for it.
        return
    if is_kb_destination_host_allowed(hostname):
        return

    msg = (
        f"Knowledge base destination {hostname!r} (from {description}) is not an approved "
        "destination. The OpenSearch and Chroma Cloud SDKs re-resolve DNS when they connect, so "
        "a tenant-supplied hostname cannot be pinned to the address it validated as. Set the "
        "destination in a server environment variable, or add the host to "
        "LANGFLOW_KB_ALLOWED_HOSTS. Note this is an exclusive allow-list: unlike "
        "LANGFLOW_SSRF_ALLOWED_HOSTS, a host that is merely public is not approved by default."
    )
    raise SSRFProtectionError(msg)
