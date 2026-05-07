"""Custom httpx transport with DNS pinning for SSRF protection.

This module provides a custom httpx transport that pins DNS resolution to validated
IP addresses, preventing DNS rebinding attacks that could bypass SSRF protection.

The implementation uses a custom AsyncNetworkBackend to intercept TCP connections
and connect to the pinned IP address while preserving the original hostname for
TLS SNI (Server Name Indication) and certificate verification.
"""

from collections.abc import Iterable

import httpcore
import httpx

from lfx.logging import logger


class DNSPinningNetworkBackend(httpcore.AsyncNetworkBackend):
    """Network backend that pins DNS resolution to validated IP addresses.

    This backend intercepts TCP connection attempts and redirects them to pinned
    IP addresses while preserving the original hostname for TLS SNI and certificate
    verification. This prevents DNS rebinding attacks without breaking HTTPS.

    How it works:
    1. When httpcore tries to connect to a hostname, we intercept the connect_tcp() call
    2. If the hostname has a pinned IP, we connect to that IP instead
    3. The original hostname is preserved for TLS handshake (SNI) and cert verification
    4. This prevents DNS rebinding while maintaining full HTTPS compatibility
    """

    def __init__(self, pinned_ips: dict[str, str], backend: httpcore.AsyncNetworkBackend | None = None):
        """Initialize the DNS pinning backend.

        Args:
            pinned_ips: Dictionary mapping hostnames to validated IP addresses
            backend: Underlying network backend (defaults to AutoBackend)
        """
        self.pinned_ips = pinned_ips
        # Use the actual auto backend implementation, not the base class
        if backend is None:
            from httpcore._backends.auto import AutoBackend

            backend = AutoBackend()
        self._backend = backend
        logger.debug(f"Created DNS pinning network backend with pinned IPs: {pinned_ips}")

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        """Connect to TCP socket, using pinned IP if available.

        This method intercepts connection attempts and redirects to pinned IPs
        while preserving the original hostname for TLS.

        Args:
            host: Hostname to connect to (may be replaced with pinned IP)
            port: Port number
            timeout: Connection timeout
            local_address: Local address to bind to
            socket_options: Socket options

        Returns:
            Network stream for the connection
        """
        # Check if this hostname has a pinned IP
        if host in self.pinned_ips:
            pinned_ip = self.pinned_ips[host]
            logger.debug(f"DNS pinning: Connecting to pinned IP {pinned_ip} for hostname {host}")

            # Connect to the pinned IP instead of the hostname
            # The TLS layer will still use the original hostname for SNI and cert verification
            return await self._backend.connect_tcp(
                host=pinned_ip,
                port=port,
                timeout=timeout,
                local_address=local_address,
                socket_options=socket_options,
            )

        # No pinned IP, use normal connection
        return await self._backend.connect_tcp(
            host=host,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        """Connect to Unix socket (pass through to underlying backend)."""
        return await self._backend.connect_unix_socket(
            path=path,
            timeout=timeout,
            socket_options=socket_options,
        )

    async def sleep(self, seconds: float) -> None:
        """Sleep for specified duration (pass through to underlying backend)."""
        await self._backend.sleep(seconds)


class SSRFProtectedTransport(httpx.AsyncHTTPTransport):
    """HTTP transport that pins DNS resolution to validated IPs.

    This transport prevents DNS rebinding attacks by using a custom network backend
    that connects to pinned IP addresses while preserving the original hostname for
    TLS SNI and certificate verification.

    Unlike the naive approach of rewriting URLs (which breaks HTTPS), this implementation
    works at the network layer to ensure both security and compatibility.

    Example:
        >>> pinned_ips = {"example.com": "93.184.216.34"}
        >>> transport = SSRFProtectedTransport(pinned_ips=pinned_ips)
        >>> async with httpx.AsyncClient(transport=transport) as client:
        ...     # Request to example.com will connect to 93.184.216.34
        ...     # But TLS will still verify against example.com certificate
        ...     response = await client.get("https://example.com/path")
    """

    def __init__(self, pinned_ips: dict[str, str], **kwargs):
        """Initialize transport with pinned DNS mappings.

        Args:
            pinned_ips: Dictionary mapping hostnames to validated IP addresses.
                       Example: {"example.com": "93.184.216.34"}
            **kwargs: Additional arguments passed to AsyncHTTPTransport
        """
        # Create custom network backend with DNS pinning
        network_backend = DNSPinningNetworkBackend(pinned_ips=pinned_ips)

        # Create connection pool with custom network backend
        # AsyncHTTPTransport doesn't expose network_backend parameter directly,
        # so we need to create the pool ourselves
        pool = httpcore.AsyncConnectionPool(network_backend=network_backend)

        # Initialize parent transport with custom pool
        super().__init__(**kwargs)
        self._pool = pool

        self.pinned_ips = pinned_ips
        logger.debug(f"Created SSRF protected transport with pinned IPs: {pinned_ips}")


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
