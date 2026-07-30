"""SSRF (Server-Side Request Forgery) protection utilities.

This module provides validation to prevent SSRF attacks by blocking requests to:
- Private IP ranges (RFC 1918)
- Loopback addresses
- Cloud metadata endpoints (169.254.169.254)
- Other internal/special-use addresses

IMPORTANT: HTTP Redirects
    According to OWASP SSRF Prevention Cheat Sheet, HTTP redirects should be DISABLED
    to prevent bypass attacks where a public URL redirects to internal resources.
    The API Request component has (as of v1.7.0) follow_redirects=False by default.
    See: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html

Configuration:
    LANGFLOW_SSRF_PROTECTION_ENABLED: Enable/disable SSRF protection (default: true)
    LANGFLOW_SSRF_ALLOWED_HOSTS: Comma-separated list of allowed hosts/CIDR ranges
        Examples: "192.168.1.0/24,internal-api.company.local,10.0.0.5"
"""

import functools
import ipaddress
import re
import socket
from urllib.parse import urlparse

from lfx.logging import logger
from lfx.services.deps import get_settings_service
from lfx.utils.file_path_security import is_local_file_access_restricted


class SSRFProtectionError(ValueError):
    """Raised when a URL is blocked due to SSRF protection."""


@functools.cache
def get_blocked_ip_ranges() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Get the list of blocked IP ranges, initializing lazily on first access.

    This lazy loading avoids the startup cost of creating all ip_network objects
    at module import time.

    Returns:
        list: List of blocked IPv4 and IPv6 network ranges.
    """
    return [
        # IPv4 ranges
        ipaddress.ip_network("0.0.0.0/8"),  # Current network (only valid as source)
        ipaddress.ip_network("10.0.0.0/8"),  # Private network (RFC 1918)
        ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT (RFC 6598)
        ipaddress.ip_network("127.0.0.0/8"),  # Loopback
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local / AWS metadata
        ipaddress.ip_network("172.16.0.0/12"),  # Private network (RFC 1918)
        ipaddress.ip_network("192.0.0.0/24"),  # IETF Protocol Assignments
        ipaddress.ip_network("192.0.2.0/24"),  # Documentation (TEST-NET-1)
        ipaddress.ip_network("192.168.0.0/16"),  # Private network (RFC 1918)
        ipaddress.ip_network("198.18.0.0/15"),  # Benchmarking
        ipaddress.ip_network("198.51.100.0/24"),  # Documentation (TEST-NET-2)
        ipaddress.ip_network("203.0.113.0/24"),  # Documentation (TEST-NET-3)
        ipaddress.ip_network("224.0.0.0/4"),  # Multicast
        ipaddress.ip_network("240.0.0.0/4"),  # Reserved
        ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
        # IPv6 ranges
        ipaddress.ip_network("::1/128"),  # Loopback
        ipaddress.ip_network("::/128"),  # Unspecified address
        ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6 addresses
        ipaddress.ip_network("100::/64"),  # Discard prefix
        ipaddress.ip_network("2001::/23"),  # IETF Protocol Assignments
        ipaddress.ip_network("2001:db8::/32"),  # Documentation
        ipaddress.ip_network("fc00::/7"),  # Unique local addresses (ULA)
        ipaddress.ip_network("fe80::/10"),  # Link-local
        ipaddress.ip_network("ff00::/8"),  # Multicast
    ]


def is_ssrf_protection_enabled() -> bool:
    """Check if SSRF protection is enabled in settings.

    Returns:
        bool: True if SSRF protection is enabled, False otherwise.
    """
    # Read directly from environment variable to support test mocking with patch.dict()
    # This ensures tests can override the protection state without settings service caching issues
    import os

    env_value = os.getenv("LANGFLOW_SSRF_PROTECTION_ENABLED")
    if env_value is not None:
        # Environment variable is set - use it (supports test mocking)
        return env_value.lower() in ("true", "1", "yes", "on")

    # Fall back to settings service for non-test scenarios
    return get_settings_service().settings.ssrf_protection_enabled


def get_allowed_hosts() -> list[str]:
    """Get list of allowed hosts and/or CIDR ranges for SSRF protection.

    Returns:
        list[str]: Stripped hostnames or CIDR blocks from settings, or empty list if unset.
    """
    # Read directly from environment variable to support test mocking with patch.dict()
    # This ensures tests can override the allowlist without settings service caching issues
    import os

    env_value = os.getenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "")
    if env_value:
        # Parse comma-separated list from environment variable
        return [host.strip() for host in env_value.split(",") if host.strip()]

    # Fall back to settings service for non-test scenarios
    settings_service = get_settings_service()
    if settings_service:
        allowed_hosts = settings_service.settings.ssrf_allowed_hosts
        if allowed_hosts:
            return [host.strip() for host in allowed_hosts if host and host.strip()]

    return []


def is_host_allowed(hostname: str, ip: str | None = None) -> bool:
    """Check if a hostname or IP is in the allowed hosts list.

    Args:
        hostname: Hostname to check
        ip: Optional IP address to check

    Returns:
        bool: True if hostname or IP is in the allowed list, False otherwise.
    """
    allowed_hosts = get_allowed_hosts()
    if not allowed_hosts:
        return False

    # Check hostname match
    if hostname in allowed_hosts:
        return True

    # Check if hostname matches any wildcard patterns
    for allowed in allowed_hosts:
        if allowed.startswith("*."):
            # Wildcard domain matching
            domain_suffix = allowed[1:]  # Remove the *
            if hostname.endswith(domain_suffix) or hostname == domain_suffix[1:]:
                return True

    # Check IP-based matching if IP is provided
    if ip:
        try:
            ip_obj = ipaddress.ip_address(ip)

            # Check exact IP match
            if ip in allowed_hosts:
                return True

            # Check CIDR range match
            for allowed in allowed_hosts:
                try:
                    # Try to parse as CIDR network
                    if "/" in allowed:
                        network = ipaddress.ip_network(allowed, strict=False)
                        if ip_obj in network:
                            return True
                except (ValueError, ipaddress.AddressValueError):
                    # Not a valid CIDR, skip
                    continue

        except (ValueError, ipaddress.AddressValueError):
            # Invalid IP, skip IP-based checks
            pass

    return False


# Transition prefixes that embed an IPv4 target. Their embedded IPv4 is re-checked against the
# blocklist (below) rather than blocking the whole prefix, which would cut off legitimate public
# egress on IPv6-only / DNS64 networks (where public IPv4 services are reached via 64:ff9b::/96).
_SIXTO4_PREFIX = ipaddress.ip_network("2002::/16")
_NAT64_WELL_KNOWN_PREFIX = ipaddress.ip_network("64:ff9b::/96")


def _embedded_ipv4(ip_obj: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """Return the IPv4 embedded in a 6to4 or well-known NAT64 address, else None.

    6to4 (RFC 3056) carries the IPv4 in bytes 2-5 (``2002:AABB:CCDD::/48`` -> ``AA.BB.CC.DD``); the
    NAT64 well-known ``64:ff9b::/96`` (RFC 6052) carries it in the low 32 bits. Local-use NAT64
    (``64:ff9b:1::/48``, RFC 8215) uses a deployment-chosen prefix length, so its embedded IPv4
    can't be located reliably and isn't decoded here.
    """
    if ip_obj in _SIXTO4_PREFIX:
        return ipaddress.IPv4Address(ip_obj.packed[2:6])
    if ip_obj in _NAT64_WELL_KNOWN_PREFIX:
        return ipaddress.IPv4Address(ip_obj.packed[12:16])
    return None


def is_ip_blocked(ip: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is in a blocked range.

    Args:
        ip: IP address to check (string or ipaddress object)

    Returns:
        bool: True if IP is in a blocked range, False otherwise.
    """
    try:
        ip_obj = ipaddress.ip_address(ip) if isinstance(ip, str) else ip
    except (ValueError, ipaddress.AddressValueError):
        # If we can't parse the IP, treat it as blocked for safety
        return True

    # Check against all blocked ranges
    if any(ip_obj in blocked_range for blocked_range in get_blocked_ip_ranges()):
        return True

    # A 6to4 / NAT64 address is only as safe as the IPv4 it encodes: re-check the embedded IPv4
    # so a transition prefix can't reach a blocked target, while a public IPv4 target (the
    # legitimate NAT64/6to4 case) still passes.
    if isinstance(ip_obj, ipaddress.IPv6Address):
        embedded = _embedded_ipv4(ip_obj)
        if embedded is not None:
            return is_ip_blocked(embedded)

    return False


def resolve_hostname(hostname: str) -> list[str]:
    """Resolve a hostname to its IP addresses.

    Args:
        hostname: Hostname to resolve

    Returns:
        list[str]: List of resolved IP addresses

    Raises:
        SSRFProtectionError: If hostname cannot be resolved
    """
    try:
        # Get address info for both IPv4 and IPv6
        addr_info = socket.getaddrinfo(hostname, None)

        # Extract unique IP addresses
        ips = []
        for info in addr_info:
            ip = info[4][0]
            # Remove IPv6 zone ID if present (e.g., "fe80::1%eth0" -> "fe80::1")
            if "%" in ip:
                ip = ip.split("%")[0]
            if ip not in ips:
                ips.append(ip)

        if not ips:
            msg = f"Unable to resolve hostname: {hostname}"
            raise SSRFProtectionError(msg)
    except socket.gaierror as e:
        msg = f"DNS resolution failed for {hostname}: {e}"
        raise SSRFProtectionError(msg) from e
    except Exception as e:
        msg = f"Error resolving hostname {hostname}: {e}"
        raise SSRFProtectionError(msg) from e

    return ips


def _validate_url_scheme(scheme: str) -> None:
    """Validate that URL scheme is http or https.

    Args:
        scheme: URL scheme to validate

    Raises:
        SSRFProtectionError: If scheme is invalid
    """
    if scheme not in ("http", "https"):
        msg = f"Invalid URL scheme '{scheme}'. Only http and https are allowed."
        raise SSRFProtectionError(msg)


def _validate_hostname_exists(hostname: str | None) -> str:
    """Validate that hostname exists in the URL.

    Args:
        hostname: Hostname to validate (may be None)

    Returns:
        str: The validated hostname

    Raises:
        SSRFProtectionError: If hostname is missing
    """
    if not hostname:
        msg = "URL must contain a valid hostname"
        raise SSRFProtectionError(msg)
    return hostname


def _validate_direct_ip_address(hostname: str) -> bool:
    """Validate a direct IP address in the URL.

    Args:
        hostname: Hostname that may be an IP address

    Returns:
        bool: True if hostname is a direct IP and validation passed,
              False if hostname is not an IP (caller should continue with DNS resolution)

    Raises:
        SSRFProtectionError: If IP is blocked
    """
    try:
        ip_obj = ipaddress.ip_address(hostname)
    except ValueError:
        # Not an IP address, it's a hostname - caller should continue with DNS resolution
        return False

    # It's a direct IP address
    # Check if IP is in allowlist
    if is_host_allowed(hostname, str(ip_obj)):
        logger.debug("IP address %s is in allowlist, bypassing SSRF checks", hostname)
        return True

    if is_ip_blocked(ip_obj):
        msg = (
            f"Access to IP address {hostname} is blocked by SSRF protection. "
            "To allow this IP, add it to LANGFLOW_SSRF_ALLOWED_HOSTS environment variable."
        )
        raise SSRFProtectionError(msg)

    # Direct IP is allowed (public IP)
    return True


def _validate_hostname_resolution(hostname: str) -> None:
    """Resolve hostname and validate resolved IPs are not blocked.

    Args:
        hostname: Hostname to resolve and validate

    Raises:
        SSRFProtectionError: If resolved IPs are blocked
    """
    # Resolve hostname to IP addresses
    try:
        resolved_ips = resolve_hostname(hostname)
    except SSRFProtectionError:
        # Re-raise SSRF errors as-is
        raise
    except Exception as e:
        msg = f"Failed to resolve hostname {hostname}: {e}"
        raise SSRFProtectionError(msg) from e

    # Check if any resolved IP is blocked
    blocked_ips = []
    for ip in resolved_ips:
        # Check if this specific IP is in the allowlist
        if is_host_allowed(hostname, ip):
            logger.debug("Resolved IP %s for hostname %s is in allowlist, bypassing SSRF checks", ip, hostname)
            return

        if is_ip_blocked(ip):
            blocked_ips.append(ip)

    if blocked_ips:
        msg = (
            f"Hostname {hostname} resolves to blocked IP address(es): {', '.join(blocked_ips)}. "
            "To allow this hostname, add it to LANGFLOW_SSRF_ALLOWED_HOSTS environment variable."
        )
        raise SSRFProtectionError(msg)


def validate_url_for_ssrf(url: str, *, warn_only: bool = False) -> None:
    """Validate a URL to prevent SSRF attacks.

    This function performs the following checks:
    1. Validates the URL scheme (only http/https allowed)
    2. Validates hostname exists
    3. Checks if hostname/IP is in allowlist
    4. If direct IP: validates it's not in blocked ranges
    5. If hostname: resolves to IPs and validates they're not in blocked ranges

    Args:
        url: URL to validate
        warn_only: If True, only log warnings instead of raising errors (default: False)

    Raises:
        SSRFProtectionError: If the URL is blocked due to SSRF protection (only if warn_only=False)
        ValueError: If the URL is malformed
    """
    # Skip validation if SSRF protection is disabled
    if not is_ssrf_protection_enabled():
        return

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        msg = f"Invalid URL format: {e}"
        raise ValueError(msg) from e

    try:
        # Validate scheme (raises SSRFProtectionError for any non-http/https scheme)
        _validate_url_scheme(parsed.scheme)

        # Validate hostname exists
        hostname = _validate_hostname_exists(parsed.hostname)

        # Check if hostname/IP is in allowlist (early return if allowed)
        if is_host_allowed(hostname):
            logger.debug("Hostname %s is in allowlist, bypassing SSRF checks", hostname)
            return

        # Validate direct IP address or resolve hostname
        is_direct_ip = _validate_direct_ip_address(hostname)
        if is_direct_ip:
            # Direct IP was handled (allowed or exception raised)
            return

        # Not a direct IP, resolve hostname and validate
        _validate_hostname_resolution(hostname)
    except SSRFProtectionError as e:
        if warn_only:
            logger.warning("SSRF Protection Warning: %s [URL: %s]", str(e), url)
            logger.warning(
                "This request will be blocked when SSRF protection is enforced in the next major version. "
                "Please review your API Request components."
            )
            return
        raise


def is_connector_ssrf_validation_enabled() -> bool:
    """Whether SSRF validation is enabled for tenant-controlled CONNECTOR host/URL components.

    Separate gate from the global ``ssrf_protection_enabled``. Defaults to True so connector
    components (vector stores, SQL DBs, Glean/AstraDB-CQL tools, model-provider discovery) follow
    the same internal-host policy unless an operator explicitly disables it.
    """
    import os

    env_value = os.getenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED")
    if env_value is not None:
        return env_value.lower() in ("true", "1", "yes", "on")
    try:
        return bool(get_settings_service().settings.connector_ssrf_validation_enabled)
    except Exception:  # noqa: BLE001 - settings may be unavailable; default to enabled
        logger.warning(
            "Could not read connector_ssrf_validation_enabled setting; treating connector SSRF "
            "validation as ENABLED (fail-closed to default). Connector URLs will be validated."
        )
        return True


def is_connector_loopback_allowed() -> bool:
    """Whether a literal loopback host is allowed for CONNECTOR / model-provider URLs.

    Connector and model-provider components routinely target a *local* service — Ollama and
    LM Studio default to ``http://localhost:11434`` / ``http://localhost:1234`` and local vector
    stores bind to loopback — so loopback is allowed by default (True). Cloud-metadata and
    RFC1918 ranges are blocked regardless. A multi-tenant deployer, where a tenant pointing a
    connector at the *server's* loopback is an SSRF vector, sets this to False to block loopback
    too. Defaults to True (lenient single-tenant default) if settings are unavailable.
    """
    import os

    env_value = os.getenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK")
    if env_value is not None:
        return env_value.lower() in ("true", "1", "yes", "on")
    try:
        return bool(get_settings_service().settings.connector_ssrf_allow_loopback)
    except Exception:  # noqa: BLE001 - settings may be unavailable; default to allowed (single-tenant default)
        return True


def _is_loopback_host(hostname: str) -> bool:
    """True if ``hostname`` is a literal loopback reference (``localhost`` or a loopback IP).

    Only literal forms are matched (``localhost``, ``127.0.0.0/8``, ``::1``). A hostname that
    merely *resolves* to loopback is intentionally NOT matched, so it still flows through the full
    SSRF check — defeating a DNS-rebinding trick that points a public-looking host at loopback.
    """
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _connector_url_has_loopback_exemption(url: str) -> bool:
    """Validate connector URL shape and return whether its literal host is exempt."""
    if not is_ssrf_protection_enabled():
        return False

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        msg = (
            f"Connector URL must be an http(s) URL with a host for SSRF validation; got {url!r}. "
            "Use an explicit scheme (e.g. 'http://host:port'); to reach an internal host, also add "
            "it to LANGFLOW_SSRF_ALLOWED_HOSTS (allowlisting alone does not permit a scheme-less host)."
        )
        raise SSRFProtectionError(msg)

    return is_connector_loopback_allowed() and _is_loopback_host(parsed.hostname)


def validate_connector_url_for_ssrf(url: str) -> None:
    """SSRF-validate a tenant-controlled connector URL unless connector validation is disabled.

    Defers to :func:`validate_url_for_ssrf`, which still respects ``ssrf_protection_enabled`` and
    the allowlist, for the actual host policy. Operators can set
    ``connector_ssrf_validation_enabled=false`` to preserve legacy localhost/private-network
    connector behavior.

    DNS-rebinding residual: unlike the API Request component (which uses
    :func:`validate_and_resolve_url` to pin the validated IP), connectors hand the URL to a
    third-party client (chromadb, pymilvus, qdrant-client, SQLAlchemy, the ollama client, ...)
    that re-resolves DNS at connect time and exposes no hook to dial a pre-resolved IP without
    breaking TLS SNI / cert validation. So this guard is validate-then-connect and a
    TOCTOU/DNS-rebinding attacker with a fast-flipping record could still slip an internal IP
    past it. The high-value targets (cloud metadata, RFC1918 literals) are literal IPs with no
    DNS to rebind and are blocked identically here.

    Raises:
        SSRFProtectionError: If connector validation is enabled and the host is blocked, or the
            URL is not an http(s) URL with a host (the only shape this guard can validate).
    """
    if not is_connector_ssrf_validation_enabled():
        return
    # Connectors commonly target a local service (Ollama / LM Studio default to localhost,
    # local vector stores bind to loopback). Allow a literal loopback host by default; a
    # multi-tenant deployer sets connector_ssrf_allow_loopback=false to block it too. Only a
    # literal loopback reference is exempted — a hostname that resolves to loopback still goes
    # through the full check below, so DNS-rebinding cannot abuse this.
    if _connector_url_has_loopback_exemption(url):
        return
    validate_url_for_ssrf(url)


def validate_and_resolve_connector_url(url: str) -> tuple[str, list[str]]:
    """Validate a connector URL and return IPs for DNS-pinned HTTP clients.

    This applies the same connector policy as :func:`validate_connector_url_for_ssrf`, including
    the literal-loopback exemption, while retaining DNS pinning for non-exempt hosts used by HTTP
    connector clients.

    Args:
        url: Connector URL to validate.

    Returns:
        The original URL and validated IP addresses. The IP list is empty when connector
        validation is disabled, global SSRF protection is disabled, the host is allowlisted, or
        the literal-loopback exemption applies.

    Raises:
        SSRFProtectionError: If connector validation is enabled and the URL is blocked or malformed.
        ValueError: If the URL format is invalid.
    """
    if not is_connector_ssrf_validation_enabled() or _connector_url_has_loopback_exemption(url):
        return url, []
    return validate_and_resolve_url(url)


# SQLAlchemy dialects that read/write the local filesystem instead of connecting over the
# network. A multi-tenant deployer must never let a tenant-supplied DB URL open these
# (e.g. sqlite:////etc/passwd, or ATTACH to read/write arbitrary server files).
_LOCAL_FILE_DB_DIALECTS = frozenset({"sqlite", "duckdb", "access", "shell"})


def validate_database_url_for_ssrf(url: str, *, validate_network_host: bool = True) -> None:
    """Validate a SQLAlchemy database URL against SSRF and local-file access.

    Unlike :func:`validate_url_for_ssrf` (which only guards http/https and returns early for
    other schemes), this guards arbitrary DB URIs on two axes, each with its own toggle:

    * Network dialects (postgresql, mysql, ...) must resolve to a host that is not an
      internal/blocked IP — guarded by SSRF protection (``LANGFLOW_SSRF_PROTECTION_ENABLED``,
      default on), so a tenant cannot reach the control-plane DB or other internal services.
    * Local-file-backed dialects (sqlite, duckdb, ...) read/write the server filesystem and
      are blocked only when ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS`` is on (default off), so
      single-tenant sqlite usage keeps working while multi-tenant deployments can disable it.

    Args:
        url: The SQLAlchemy database URL to validate.
        validate_network_host: When False, the network-host SSRF check is skipped (the local-file
            dialect restriction still applies). Used by the connector-gated wrapper so the
            host SSRF check is opt-in.

    Raises:
        SSRFProtectionError: If the URL targets a blocked IP, or a local-file dialect while
            local file access is restricted.
        ValueError: If the URL is malformed.
    """
    ssrf_on = is_ssrf_protection_enabled() and validate_network_host
    file_restricted = is_local_file_access_restricted()
    if not ssrf_on and not file_restricted:
        return

    try:
        parsed = urlparse(url)
    except Exception as e:
        msg = f"Invalid database URL format: {e}"
        raise ValueError(msg) from e

    # SQLAlchemy schemes look like "postgresql+psycopg2"; reduce to the dialect.
    dialect = (parsed.scheme or "").lower().split("+", 1)[0]
    if dialect in _LOCAL_FILE_DB_DIALECTS:
        if file_restricted:
            msg = (
                f"Database dialect '{dialect}' accesses the local filesystem and is not permitted "
                "(LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true). Use a network database (e.g. postgresql, mysql)."
            )
            raise SSRFProtectionError(msg)
        # Not restricted: local-file DBs are allowed (single-tenant default).
        return

    # Network dialect: host SSRF validation only applies when SSRF protection is enabled.
    if not ssrf_on:
        return

    hostname = parsed.hostname
    if not hostname:
        # A network dialect with no host cannot be validated -> fail closed.
        msg = "Database URL must contain a network host."
        raise SSRFProtectionError(msg)

    # Reuse the same allowlist + blocked-range checks as HTTP SSRF validation.
    if _validate_direct_ip_address(hostname):
        return
    _validate_hostname_resolution(hostname)


def validate_connector_database_url_for_ssrf(url: str) -> None:
    """DB-URL validation for connector components (e.g. the SQL Database components).

    The network-host SSRF check follows ``connector_ssrf_validation_enabled`` (default on). The
    local-file dialect restriction still honors ``LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS`` regardless,
    since that is a separate control.

    Raises:
        SSRFProtectionError: If connector validation is on and the host is blocked, or a local-file
            dialect is used while local file access is restricted.
        ValueError: If the URL is malformed.
    """
    validate_database_url_for_ssrf(url, validate_network_host=is_connector_ssrf_validation_enabled())


# Git remote-helper transport syntax (``ext::``, ``fd::``, bare ``::address``). The ``ext``
# helper runs an arbitrary shell command, so this whole syntax is treated as hostile.
_GIT_REMOTE_HELPER_RE = re.compile(r"^[A-Za-z0-9+.\-]*::")

# Real network transports git understands. Anything else (file, ext, fd, ...) is rejected.
_ALLOWED_GIT_SCHEMES = frozenset({"http", "https", "git", "ssh", "git+ssh", "git+http", "git+https"})


def validate_git_repository_url(url: str) -> None:
    """Validate a Git repository URL before it is handed to ``git clone``.

    ``git``/GitPython accept far more than network URLs, and the repository URL is fully
    tenant-controlled in a multi-tenant deployment:

    * ``ext::sh -c '<cmd>'`` (and any ``<helper>::`` remote-helper transport) executes an
      arbitrary command on the server => RCE.
    * a leading ``-`` is parsed by git as an option => argument injection.
    * ``file://`` and bare local paths clone a repository off the server filesystem =>
      arbitrary local file disclosure.

    The first two are always blocked (no legitimate use, direct RCE/injection). Local-file
    clones are blocked when SSRF protection (default on) or local-file restriction is enabled,
    so single-tenant local-repo workflows keep working only when both are off. Network
    transports have their host validated against the SSRF blocked ranges.

    Raises:
        SSRFProtectionError: If the URL uses a dangerous transport or targets a blocked host.
        ValueError: If the URL is empty or malformed.
    """
    if not isinstance(url, str) or not url.strip():
        msg = "Git repository URL must be a non-empty string."
        raise ValueError(msg)
    url = url.strip()

    # Always-blocked: remote-helper transports (RCE) and git option injection. These are
    # rejected regardless of SSRF/file-access toggles because they have no legitimate use.
    if url.startswith("-"):
        msg = "Git repository URL may not start with '-' (git option injection)."
        raise SSRFProtectionError(msg)
    if _GIT_REMOTE_HELPER_RE.match(url):
        msg = "Git remote-helper transports (e.g. 'ext::', 'fd::') are not permitted."
        raise SSRFProtectionError(msg)

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()

    # Scheme allowlist is ALWAYS enforced (independent of the SSRF/file toggles): non-network
    # schemes such as ``ext://`` invoke the git-remote-<scheme> helper (RCE) and ``gopher://``
    # etc. are dangerous transports, not a network-policy choice. ``file`` is handled just below.
    if scheme and scheme != "file" and scheme not in _ALLOWED_GIT_SCHEMES:
        msg = f"Git URL scheme '{scheme}' is not permitted."
        raise SSRFProtectionError(msg)

    # Local-filesystem clones (file:// or a bare path) read arbitrary server files.
    pre_colon = url.split(":", 1)[0]
    is_local_path = scheme == "file" or (scheme == "" and ("/" in pre_colon or url.startswith(("/", ".", "~"))))
    if is_local_path:
        if is_ssrf_protection_enabled() or is_local_file_access_restricted():
            msg = "Cloning local-filesystem Git repositories is not permitted."
            raise SSRFProtectionError(msg)
        return

    # Network transports: host SSRF validation only applies when SSRF protection is enabled.
    if not is_ssrf_protection_enabled():
        return

    # scp-like syntax (git@host:path) has no scheme; the host is before the first ':'.
    hostname = (url.split("@", 1)[-1].split(":", 1)[0] or None) if scheme == "" else parsed.hostname

    if not hostname:
        msg = "Git repository URL must contain a network host."
        raise SSRFProtectionError(msg)

    if _validate_direct_ip_address(hostname):
        return
    _validate_hostname_resolution(hostname)


def validate_and_resolve_url(url: str) -> tuple[str, list[str]]:
    """Validate URL for SSRF and return validated IP addresses for DNS pinning.

    This function is the core of DNS pinning-based SSRF protection. It performs
    comprehensive validation and returns the validated IP addresses that should
    be used for the actual HTTP request, preventing DNS rebinding attacks.

    DNS Rebinding Attack Prevention:
        Without DNS pinning, an attacker can exploit the time gap between validation
        and the actual HTTP request:
        1. Validation: DNS returns public IP (8.8.8.8) → passes security check
        2. [Attacker changes DNS with TTL=0]
        3. HTTP request: DNS returns internal IP (127.0.0.1) → bypasses protection

        With DNS pinning (this function):
        1. Validation: DNS returns public IP (8.8.8.8) → passes security check
        2. Function returns: (url, ['8.8.8.8']) → IP is pinned
        3. HTTP request: Uses pinned IP directly → no new DNS lookup → secure

    Args:
        url: URL to validate (e.g., "http://example.com/api")

    Returns:
        Tuple of (original_url, list_of_validated_ips):
        - original_url: The input URL unchanged
        - list_of_validated_ips: List of validated IP addresses to use for DNS pinning
          Returns empty list if:
          - SSRF protection is disabled
          - Host is in the allowlist (e.g., localhost for Ollama)
          (a non-http/https scheme raises SSRFProtectionError rather than returning)

    Raises:
        SSRFProtectionError: If URL is blocked by SSRF protection
        ValueError: If URL format is invalid

    Example:
        >>> # Public domain - returns validated IPs for pinning
        >>> url, ips = validate_and_resolve_url("http://example.com")
        >>> print(ips)  # ['93.184.216.34']

        >>> # Localhost (if in allowlist) - returns empty list (no pinning needed)
        >>> url, ips = validate_and_resolve_url("http://localhost:8080")
        >>> print(ips)  # []

        >>> # Private IP - raises SSRFProtectionError
        >>> url, ips = validate_and_resolve_url("http://192.168.1.1")
        # Raises: SSRFProtectionError("Access to IP address 192.168.1.1 is blocked...")
    """
    # ============================================================================
    # Step 1: Check if SSRF protection is enabled
    # ============================================================================
    if not is_ssrf_protection_enabled():
        # Protection is disabled - return empty list (no DNS pinning)
        return url, []

    # ============================================================================
    # Step 2: Parse and validate URL format
    # ============================================================================
    try:
        parsed = urlparse(url)
    except Exception as e:
        msg = f"Invalid URL format: {e}"
        raise ValueError(msg) from e

    try:
        # ============================================================================
        # Step 3: Validate URL scheme (raises SSRFProtectionError for any non-http/https scheme)
        # ============================================================================
        _validate_url_scheme(parsed.scheme)

        # ============================================================================
        # Step 4: Extract and validate hostname
        # ============================================================================
        hostname = _validate_hostname_exists(parsed.hostname)

        # ============================================================================
        # Step 5: Check allowlist (early return for trusted hosts)
        # ============================================================================
        # Allowlisted hosts bypass all SSRF checks and DNS pinning
        # This is used for legitimate internal services like Ollama (localhost)
        if is_host_allowed(hostname):
            logger.debug(f"Hostname {hostname} is in allowlist, bypassing SSRF checks and DNS pinning")
            return url, []

        # ============================================================================
        # Step 6: Handle direct IP addresses
        # ============================================================================
        # Check if the hostname is already an IP address (no DNS resolution needed)
        try:
            ip_obj = ipaddress.ip_address(hostname)

            # Check if this specific IP is in the allowlist
            if is_host_allowed(hostname, str(ip_obj)):
                logger.debug(f"IP {hostname} is in allowlist")
                return url, []

            # Check if IP is in blocked ranges (private IPs, localhost, etc.)
            if is_ip_blocked(ip_obj):
                msg = (
                    f"Access to IP address {hostname} is blocked by SSRF protection. "
                    "To allow this IP, add it to LANGFLOW_SSRF_ALLOWED_HOSTS environment variable."
                )
                raise SSRFProtectionError(msg)
            # Direct IP is public and allowed - return it for DNS pinning
            # (Even though it's already an IP, we return it for consistency)
            logger.debug(f"Direct IP {hostname} validated, will use for DNS pinning")
            return url, [hostname]  # noqa: TRY300

        except ValueError:
            # Not an IP address, it's a hostname - continue to DNS resolution
            pass

        # ============================================================================
        # Step 7: Resolve hostname to IP addresses
        # ============================================================================
        # This is the critical step for DNS pinning - we resolve DNS here during
        # validation, and the returned IPs will be used for the actual HTTP request
        resolved_ips = resolve_hostname(hostname)
        blocked_ips = []

        # ============================================================================
        # Step 8: Validate all resolved IPs
        # ============================================================================
        # Security: We must check ALL resolved IPs before making any decisions.
        # A hostname might resolve to multiple IPs (e.g., [8.8.8.8, 192.168.1.1]).
        # If we return early on the first allowlisted IP, we skip validation of
        # remaining IPs, which could include blocked/internal addresses.
        #
        # Strategy:
        # 1. Collect all allowlisted IPs and all blocked IPs
        # 2. If ANY IP is blocked → block the entire hostname (security first)
        # 3. If some IPs are allowlisted but others are not → use only allowlisted IPs for pinning
        # 4. If all IPs are public (none blocked, none allowlisted) → use all for pinning
        allowed_ips = []
        for ip in resolved_ips:
            # Check if this resolved IP is in the allowlist
            if is_host_allowed(hostname, ip):
                allowed_ips.append(ip)
            # Check if IP is in blocked ranges
            elif is_ip_blocked(ip):
                blocked_ips.append(ip)

        # ============================================================================
        # Step 9: Block if any resolved IPs are private/internal
        # ============================================================================
        # Security: If ANY resolved IP is blocked, we block the entire hostname.
        # This prevents attacks where a hostname resolves to both safe and unsafe IPs.
        if blocked_ips:
            msg = (
                f"Hostname {hostname} resolves to blocked IP address(es): {', '.join(blocked_ips)}. "
                "To allow this hostname, add it to LANGFLOW_SSRF_ALLOWED_HOSTS environment variable."
            )
            raise SSRFProtectionError(msg)

        # ============================================================================
        # Step 9b: Handle partially allowlisted IPs
        # ============================================================================
        # If some (but not all) IPs are allowlisted, use only the allowlisted ones for pinning
        if allowed_ips:
            logger.debug(
                f"Hostname {hostname} has {len(allowed_ips)} allowlisted IP(s) out of {len(resolved_ips)} total. "
                f"Using allowlisted IPs for DNS pinning: {allowed_ips}"
            )
            return url, allowed_ips
        # ============================================================================
        # Step 10: Return validated IPs for DNS pinning
        # ============================================================================
        # All IPs are public and safe - return them for DNS pinning
        # The HTTP client will use these IPs directly, preventing DNS rebinding
        logger.debug(f"Hostname {hostname} validated, resolved to {resolved_ips}, will use for DNS pinning")
        return url, resolved_ips  # noqa: TRY300

    except SSRFProtectionError:
        # Re-raise SSRF errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors in SSRFProtectionError
        msg = f"Error validating URL: {e}"
        raise SSRFProtectionError(msg) from e
