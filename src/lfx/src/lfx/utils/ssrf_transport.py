"""Custom httpx transport with DNS pinning for SSRF protection.

This module provides a custom httpx transport that pins DNS resolution to validated
IP addresses, preventing DNS rebinding attacks that could bypass SSRF protection.
"""

from urllib.parse import urlparse

import httpx

from lfx.logging import logger


class SSRFProtectedTransport(httpx.AsyncHTTPTransport):
    """HTTP transport that pins DNS resolution to validated IPs.

    This transport prevents DNS rebinding attacks by ensuring that the HTTP request
    uses the same IP address that was validated during SSRF protection checks.

    The transport works by:
    1. Accepting a mapping of hostnames to validated IP addresses
    2. Intercepting HTTP requests
    3. Replacing the hostname in the URL with the pinned IP
    4. Preserving the original hostname in the Host header (for virtual hosting/SNI)

    Example:
        >>> pinned_ips = {"example.com": "93.184.216.34"}
        >>> transport = SSRFProtectedTransport(pinned_ips=pinned_ips)
        >>> async with httpx.AsyncClient(transport=transport) as client:
        ...     # Request to example.com will use 93.184.216.34
        ...     response = await client.get("https://example.com/path")
    """

    def __init__(self, pinned_ips: dict[str, str], **kwargs):
        """Initialize transport with pinned DNS mappings.

        Args:
            pinned_ips: Dictionary mapping hostnames to validated IP addresses.
                       Example: {"example.com": "93.184.216.34"}
            **kwargs: Additional arguments passed to AsyncHTTPTransport
        """
        super().__init__(**kwargs)
        self.pinned_ips = pinned_ips
        logger.debug(f"Created SSRF protected transport with pinned IPs: {pinned_ips}")

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle HTTP request with DNS pinning.

        This method intercepts the request, checks if the hostname should be pinned,
        and if so, replaces it with the validated IP address while preserving the
        original hostname in the Host header.

        Args:
            request: The HTTP request to handle

        Returns:
            The HTTP response
        """
        # Extract hostname from the request URL
        parsed_url = urlparse(str(request.url))
        hostname = parsed_url.hostname

        if hostname and hostname in self.pinned_ips:
            pinned_ip = self.pinned_ips[hostname]
            logger.debug(f"DNS pinning: Using validated IP {pinned_ip} for hostname {hostname}")

            # Replace hostname with pinned IP in the URL
            # We need to handle both IPv4 and IPv6 addresses
            original_url = str(request.url)

            # For IPv6, we need to wrap it in brackets
            pinned_ip_for_url = f"[{pinned_ip}]" if ":" in pinned_ip and not pinned_ip.startswith("[") else pinned_ip

            # Replace the hostname in the URL
            # Handle both with and without port
            if parsed_url.port:
                # URL has explicit port
                pinned_url = original_url.replace(
                    f"//{hostname}:{parsed_url.port}", f"//{pinned_ip_for_url}:{parsed_url.port}", 1
                )
            else:
                # URL uses default port
                pinned_url = original_url.replace(f"//{hostname}", f"//{pinned_ip_for_url}", 1)

            # Update the request URL
            request.url = httpx.URL(pinned_url)

            # Preserve original hostname in Host header for virtual hosting and SNI
            request.headers["Host"] = hostname

            logger.debug(f"DNS pinning: Rewrote URL from {original_url} to {pinned_url}")

        # Call the parent class to handle the actual request
        return await super().handle_async_request(request)


def create_ssrf_protected_client(hostname: str, validated_ip: str, **client_kwargs) -> httpx.AsyncClient:
    """Create an httpx client with DNS pinning for SSRF protection.

    Args:
        hostname: The hostname to pin
        validated_ip: The validated IP address to use for this hostname
        **client_kwargs: Additional arguments for AsyncClient (e.g., timeout, headers)

    Returns:
        Configured AsyncClient with DNS pinning
    """
    transport = SSRFProtectedTransport(pinned_ips={hostname: validated_ip})
    return httpx.AsyncClient(transport=transport, **client_kwargs)
