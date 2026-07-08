"""SSRF-protected helpers for ``httpx`` call sites."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_ssrf_protection_enabled,
    validate_and_resolve_url,
    validate_url_for_ssrf,
)
from lfx.utils.ssrf_transport import (
    SSRFProtectedSyncTransport,
    SSRFProtectedTransport,
    create_ssrf_protected_client,
    create_ssrf_protected_sync_client,
)


def validate_url_for_ssrf_or_raise(url: str) -> None:
    """Validate a user URL and raise a UI-facing error when it is blocked."""
    try:
        validate_url_for_ssrf(url, warn_only=False)
    except SSRFProtectionError as e:
        msg = f"SSRF Protection: {e}"
        raise ValueError(msg) from e


def _raise_if_following_redirects(request_kwargs: dict[str, Any]) -> None:
    if request_kwargs.get("follow_redirects"):
        msg = "SSRF-protected httpx helpers do not support automatic redirect following."
        raise SSRFProtectionError(msg)


def _async_client_for_url(url: str, validated_ips: list[str]) -> httpx.AsyncClient:
    if is_ssrf_protection_enabled() and validated_ips:
        hostname = urlparse(url).hostname
        if hostname:
            return create_ssrf_protected_client(hostname=hostname, validated_ips=validated_ips)
    return httpx.AsyncClient()


def _sync_client_for_url(url: str, validated_ips: list[str]) -> httpx.Client:
    if is_ssrf_protection_enabled() and validated_ips:
        hostname = urlparse(url).hostname
        if hostname:
            return create_ssrf_protected_sync_client(hostname=hostname, validated_ips=validated_ips)
    return httpx.Client()


def ssrf_protected_httpx_client_kwargs_for_url(url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return sync/async httpx kwargs that enforce SSRF protection for SDK clients."""
    try:
        validated_url, validated_ips = validate_and_resolve_url(url)
    except SSRFProtectionError as e:
        msg = f"SSRF Protection: {e}"
        raise ValueError(msg) from e

    if not is_ssrf_protection_enabled():
        return {}, {}

    sync_kwargs: dict[str, Any] = {"follow_redirects": False}
    async_kwargs: dict[str, Any] = {"follow_redirects": False}

    hostname = urlparse(validated_url).hostname
    if hostname and validated_ips:
        ip_list = list(validated_ips)
        sync_kwargs["transport"] = SSRFProtectedSyncTransport(pinned_ips={hostname: ip_list})
        async_kwargs["transport"] = SSRFProtectedTransport(pinned_ips={hostname: ip_list})

    return sync_kwargs, async_kwargs


def ssrf_protected_openai_clients_for_url(url: str) -> dict[str, httpx.Client | httpx.AsyncClient]:
    """Return pinned sync and async clients for OpenAI-compatible LangChain components."""
    sync_kwargs, async_kwargs = ssrf_protected_httpx_client_kwargs_for_url(url)
    if not sync_kwargs and not async_kwargs:
        return {}
    return {
        "http_client": httpx.Client(**sync_kwargs),
        "http_async_client": httpx.AsyncClient(**async_kwargs),
    }


async def ssrf_safe_async_get(url: str, **request_kwargs: Any) -> httpx.Response:
    """Perform an async GET with SSRF validation and DNS pinning."""
    _raise_if_following_redirects(request_kwargs)
    validated_url, validated_ips = validate_and_resolve_url(url)
    async with _async_client_for_url(validated_url, validated_ips) as client:
        return await client.get(url=validated_url, **request_kwargs)


async def ssrf_safe_async_post(url: str, **request_kwargs: Any) -> httpx.Response:
    """Perform an async POST with SSRF validation and DNS pinning."""
    _raise_if_following_redirects(request_kwargs)
    validated_url, validated_ips = validate_and_resolve_url(url)
    async with _async_client_for_url(validated_url, validated_ips) as client:
        return await client.post(url=validated_url, **request_kwargs)


def ssrf_safe_httpx_get(url: str, **request_kwargs: Any) -> httpx.Response:
    """Perform a synchronous GET with SSRF validation and DNS pinning."""
    _raise_if_following_redirects(request_kwargs)
    validated_url, validated_ips = validate_and_resolve_url(url)
    with _sync_client_for_url(validated_url, validated_ips) as client:
        return client.get(url=validated_url, **request_kwargs)


def ssrf_safe_httpx_post(url: str, **request_kwargs: Any) -> httpx.Response:
    """Perform a synchronous POST with SSRF validation and DNS pinning."""
    _raise_if_following_redirects(request_kwargs)
    validated_url, validated_ips = validate_and_resolve_url(url)
    with _sync_client_for_url(validated_url, validated_ips) as client:
        return client.post(url=validated_url, **request_kwargs)
