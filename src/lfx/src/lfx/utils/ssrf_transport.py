"""Custom httpx transport with DNS pinning for SSRF protection.

This module provides a custom httpx transport that pins DNS resolution to validated
IP addresses, preventing DNS rebinding attacks that could bypass SSRF protection.

The implementation uses a custom AsyncNetworkBackend to intercept TCP connections
and connect to the pinned IP address while preserving the original hostname for
TLS SNI (Server Name Indication) and certificate verification.
"""

import ssl
from collections.abc import Iterable

import httpcore
import httpx
from httpx import URL, Proxy
from httpx._config import create_ssl_context

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

    def __init__(self, pinned_ips: dict[str, list[str]], backend: httpcore.AsyncNetworkBackend | None = None):
        """Initialize the DNS pinning backend.

        Args:
            pinned_ips: Dictionary mapping hostnames to list of validated IP addresses
            backend: Underlying network backend (defaults to AnyIOBackend for asyncio)
        """
        self.pinned_ips = pinned_ips
        # Use httpcore's default async backend (AnyIOBackend) if none provided
        # This is the public API recommended in httpcore documentation
        if backend is None:
            backend = httpcore.AnyIOBackend()
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
        # Check if this hostname has pinned IPs
        if host in self.pinned_ips:
            pinned_ips = self.pinned_ips[host]

            # Security: If host is in pinned_ips but list is empty, fail rather than bypass
            if not pinned_ips:
                msg = f"DNS pinning: Host {host} is marked for pinning but has no pinned IPs"
                logger.error(msg)
                raise RuntimeError(msg)

            logger.debug(f"DNS pinning: Connecting to pinned IPs {pinned_ips} for hostname {host}")

            # Try each pinned IP in order (supports dual-stack and load balancing)
            # The TLS layer will still use the original hostname for SNI and cert verification
            last_error = None
            for pinned_ip in pinned_ips:
                try:
                    logger.debug(f"DNS pinning: Attempting connection to {pinned_ip}")
                    return await self._backend.connect_tcp(
                        host=pinned_ip,
                        port=port,
                        timeout=timeout,
                        local_address=local_address,
                        socket_options=socket_options,
                    )
                except (OSError, TimeoutError) as e:
                    last_error = e
                    logger.debug(f"DNS pinning: Failed to connect to {pinned_ip}: {e}")
                    continue

            # All pinned IPs failed, raise the last error
            # This should never be None since we checked for empty list above
            if last_error is None:
                msg = f"DNS pinning: All pinned IPs failed for {host} but no error was captured"
                raise RuntimeError(msg)
            raise last_error

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

    def __init__(
        self,
        pinned_ips: dict[str, list[str]],
        verify: bool | str | ssl.SSLContext = True,  # noqa: FBT001, FBT002
        cert: tuple[str, str] | tuple[str, str, str] | str | None = None,
        trust_env: bool = True,  # noqa: FBT001, FBT002
        http1: bool = True,  # noqa: FBT001, FBT002
        http2: bool = False,  # noqa: FBT001, FBT002
        limits: httpx.Limits = httpx.Limits(),  # noqa: B008
        proxy: httpx._types.ProxyTypes | None = None,
        uds: str | None = None,
        local_address: str | None = None,
        retries: int = 0,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ):
        """Initialize transport with pinned DNS mappings.

        Args:
            pinned_ips: Dictionary mapping hostnames to list of validated IP addresses.
                       Example: {"example.com": ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"]}
            verify: SSL verification settings
            cert: Client certificate
            trust_env: Whether to trust environment variables for proxy config
            http1: Enable HTTP/1.1
            http2: Enable HTTP/2
            limits: Connection pool limits
            proxy: Proxy configuration
            uds: Unix domain socket path
            local_address: Local address to bind to
            retries: Number of retries
            socket_options: Socket options
        """
        # Create custom network backend with DNS pinning
        network_backend = DNSPinningNetworkBackend(pinned_ips=pinned_ips)

        # Create SSL context (same as parent class)
        ssl_context = create_ssl_context(verify=verify, cert=cert, trust_env=trust_env)

        # Handle proxy (same as parent class)
        if proxy is not None:
            proxy = Proxy(url=proxy) if isinstance(proxy, (str, URL)) else proxy

        # Create pool with our custom network backend
        # We replicate the parent's logic but add network_backend parameter
        if proxy is None:
            self._pool = httpcore.AsyncConnectionPool(
                ssl_context=ssl_context,
                max_connections=limits.max_connections,
                max_keepalive_connections=limits.max_keepalive_connections,
                keepalive_expiry=limits.keepalive_expiry,
                http1=http1,
                http2=http2,
                uds=uds,
                local_address=local_address,
                retries=retries,
                socket_options=socket_options,
                network_backend=network_backend,  # Our custom backend!
            )
        else:
            # For proxy scenarios, we'd need to handle HTTPProxy/SOCKSProxy
            # For now, raise an error as DNS pinning with proxies needs special handling
            msg = "DNS pinning with proxies is not currently supported"
            raise NotImplementedError(msg)

        self.pinned_ips = pinned_ips
        logger.debug(f"Created SSRF protected transport with pinned IPs: {pinned_ips}")


def create_ssrf_protected_client(
    hostname: str, validated_ips: list[str] | tuple[str, ...], **client_kwargs
) -> httpx.AsyncClient:
    """Create an httpx client with DNS pinning for SSRF protection.

    Args:
        hostname: The hostname to pin
        validated_ips: List of validated IP addresses to use for this hostname.
                      IPs will be tried in order for dual-stack/load-balanced hosts.
        **client_kwargs: Additional arguments for AsyncClient (e.g., timeout, headers)

    Returns:
        Configured AsyncClient with DNS pinning
    """
    # Convert to list if tuple
    ip_list = list(validated_ips) if isinstance(validated_ips, tuple) else validated_ips
    transport = SSRFProtectedTransport(pinned_ips={hostname: ip_list})
    return httpx.AsyncClient(transport=transport, **client_kwargs)
