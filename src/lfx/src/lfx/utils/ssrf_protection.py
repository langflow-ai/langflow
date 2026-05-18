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
import socket
from urllib.parse import urlparse

from lfx.logging import logger
from lfx.services.deps import get_settings_service


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


def is_ip_blocked(ip: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is in a blocked range.

    Args:
        ip: IP address to check (string or ipaddress object)

    Returns:
        bool: True if IP is in a blocked range, False otherwise.
    """
    try:
        ip_obj = ipaddress.ip_address(ip) if isinstance(ip, str) else ip

        # Check against all blocked ranges
        return any(ip_obj in blocked_range for blocked_range in get_blocked_ip_ranges())
    except (ValueError, ipaddress.AddressValueError):
        # If we can't parse the IP, treat it as blocked for safety
        return True


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
        # Validate scheme
        _validate_url_scheme(parsed.scheme)
        if parsed.scheme not in ("http", "https"):
            return

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
          - URL scheme is not http/https

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
        # Step 3: Validate URL scheme (only http/https allowed)
        # ============================================================================
        _validate_url_scheme(parsed.scheme)
        if parsed.scheme not in ("http", "https"):
            # Non-HTTP schemes (ftp, file, etc.) are not subject to SSRF protection
            return url, []

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
