"""Pin the NVIDIA SDK's native streaming transports to the validated provider addresses."""

from __future__ import annotations

import socket
from contextvars import ContextVar
from functools import cache
from ipaddress import ip_address
from typing import TYPE_CHECKING

import aiohttp
from aiohttp.abc import ResolveResult
from lfx.utils.ssrf_protection import SSRFProtectionError
from requests.utils import select_proxy
from urllib3.exceptions import ConnectTimeoutError
from yarl import URL

if TYPE_CHECKING:
    from collections.abc import Sequence

    import requests


def is_pinned_origin(base_url: str, request_url: str, *, trusted_origins: tuple[str, ...] = ()) -> bool:
    """Select the pinned connection or an explicitly trusted NVIDIA origin."""

    def origin(url: str) -> tuple[str, str | None, int | None]:
        parsed = URL(url)
        return parsed.scheme, parsed.raw_host, parsed.port

    target = origin(request_url)
    if target == origin(base_url):
        return True
    if any(target == origin(url) for url in trusted_origins):
        return False
    msg = "Refusing a request outside the validated provider origin."
    raise SSRFProtectionError(msg)


def pin_requests_session(
    session: requests.Session, base_url: str, ips: Sequence[str], *, trusted_origins: tuple[str, ...] = ()
) -> requests.Session:
    """Pin new TCP sockets for the configured origin, preserving the SDK session's adapters."""
    addresses = tuple(str(ip_address(ip)) for ip in ips)
    if not addresses:
        msg = "At least one validated IP address is required for DNS pinning."
        raise SSRFProtectionError(msg)

    @cache
    def pinned_connection_type(connection_type):
        class PinnedConnection(connection_type):
            def _new_conn(self):
                # urllib3 uses the host again after TCP connects for the Host header,
                # TLS SNI, and certificate verification. Only substitute it for the dial.
                hostname = self.host
                try:
                    for index, address in enumerate(addresses):
                        self.host = address
                        try:
                            return super()._new_conn()
                        except ConnectTimeoutError:
                            # Includes NewConnectionError. Retry only socket establishment,
                            # before any request body or credentials have been written.
                            if index == len(addresses) - 1:
                                raise
                finally:
                    self.host = hostname

        return PinnedConnection

    def protect_pool_factory(get_pool):
        def guarded_pool(request, verify, proxies=None, cert=None):
            pin = is_pinned_origin(base_url, request.url, trusted_origins=trusted_origins)
            if pin and select_proxy(request.url, proxies or {}):
                msg = "Cannot pin a provider connection through a proxy."
                raise SSRFProtectionError(msg)
            pool = get_pool(request, verify, proxies=proxies, cert=cert)
            if pin:
                # The SDK creates a fresh session for each operation. Its native pool
                # keeps the original TLS settings, timeouts, and streaming behavior.
                pool.ConnectionCls = pinned_connection_type(type(pool).ConnectionCls)
            return pool

        return guarded_pool

    for adapter in session.adapters.values():
        get_pool = getattr(adapter, "get_connection_with_tls_context", None)
        if not callable(get_pool):
            msg = "Provider DNS pinning requires a Requests 2.32.2 or newer HTTPAdapter."
            raise SSRFProtectionError(msg)
        adapter.get_connection_with_tls_context = protect_pool_factory(get_pool)
    return session


def pin_aiohttp_session(
    session: aiohttp.ClientSession, base_url: str, ips: Sequence[str], *, trusted_origins: tuple[str, ...] = ()
) -> aiohttp.ClientSession:
    """Route new connections for the validated origin to its addresses, keeping the SDK's TLS and streaming settings."""
    connector = session.connector
    if not isinstance(connector, aiohttp.TCPConnector) or not ips:
        msg = "Cannot pin the provider session without a TCP connector and validated addresses."
        raise SSRFProtectionError(msg)

    # aiohttp exposes the resolver only when constructing a connector. The SDK owns
    # that constructor, so scope these two hooks to its fresh connector instance.
    create_connection = connector._create_connection  # noqa: SLF001
    resolve_host = connector._resolve_host  # noqa: SLF001
    addresses = tuple(str(ip_address(ip)) for ip in ips)
    use_pins = ContextVar("use_pinned_addresses", default=True)

    async def guarded_connection(req, traces, timeout):
        pinned = is_pinned_origin(base_url, str(req.url), trusted_origins=trusted_origins)
        if pinned and req.proxy is not None:
            msg = "Cannot pin the provider destination through an HTTP proxy."
            raise SSRFProtectionError(msg)
        token = use_pins.set(pinned)
        try:
            return await create_connection(req, traces, timeout)
        finally:
            use_pins.reset(token)

    async def pinned_resolution(host, port, traces=None):
        if not use_pins.get():
            return await resolve_host(host, port, traces)
        return [
            ResolveResult(
                hostname=host,
                host=ip,
                port=port,
                family=socket.AF_INET6 if ":" in ip else socket.AF_INET,
                proto=socket.IPPROTO_TCP,
                flags=socket.AI_NUMERICHOST,
            )
            for ip in addresses
        ]

    connector._create_connection = guarded_connection  # noqa: SLF001
    connector._resolve_host = pinned_resolution  # noqa: SLF001
    return session
