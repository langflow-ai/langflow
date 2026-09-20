"""SSRF-protected helpers for ``httpx`` call sites."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_connector_ssrf_validation_enabled,
    is_ssrf_protection_enabled,
    validate_and_resolve_connector_url,
    validate_and_resolve_url,
    validate_connector_url_for_ssrf,
    validate_url_for_ssrf,
)
from lfx.utils.ssrf_transport import (
    SSRFProtectedSyncTransport,
    SSRFProtectedTransport,
    create_ssrf_protected_client,
    create_ssrf_protected_sync_client,
)

# HTTP redirect responses carrying a Location header (RFC 9110).
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
DEFAULT_MAX_REDIRECTS = 20


def validate_url_for_ssrf_or_raise(url: str) -> None:
    """Validate a connector URL and raise a UI-facing error when it is blocked."""
    try:
        validate_connector_url_for_ssrf(url)
    except SSRFProtectionError as e:
        msg = f"SSRF Protection: {e}"
        raise ValueError(msg) from e


def validate_strict_url_for_ssrf_or_raise(url: str) -> None:
    """Validate a credential-bearing provider URL without the connector loopback exemption."""
    try:
        if is_connector_ssrf_validation_enabled():
            validate_url_for_ssrf(url)
    except SSRFProtectionError as e:
        msg = f"SSRF Protection: {e}"
        raise ValueError(msg) from e


def _validate_and_resolve_strict_url(url: str) -> tuple[str, list[str]]:
    """Resolve a credential-bearing provider URL without the connector loopback exemption."""
    if not is_connector_ssrf_validation_enabled():
        return url, []
    return validate_and_resolve_url(url)


def _raise_if_following_redirects(request_kwargs: dict[str, Any]) -> None:
    if request_kwargs.get("follow_redirects"):
        msg = "SSRF-protected httpx helpers do not support automatic redirect following."
        raise SSRFProtectionError(msg)


def _transport_host(url: str) -> str:
    """Return the IDNA-normalized host httpx/httpcore uses for connections."""
    return httpx.URL(url).raw_host.decode("ascii")


def _async_client_for_url(url: str, validated_ips: list[str]) -> httpx.AsyncClient:
    if is_ssrf_protection_enabled() and validated_ips:
        hostname = _transport_host(url)
        if hostname:
            return create_ssrf_protected_client(hostname=hostname, validated_ips=validated_ips)
    return httpx.AsyncClient()


def _sync_client_for_url(url: str, validated_ips: list[str]) -> httpx.Client:
    if is_ssrf_protection_enabled() and validated_ips:
        hostname = _transport_host(url)
        if hostname:
            return create_ssrf_protected_sync_client(hostname=hostname, validated_ips=validated_ips)
    return httpx.Client()


def _httpx_client_kwargs_for_validated_url(
    validated_url: str, validated_ips: list[str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build sync and async client kwargs for an already validated URL."""
    if not is_ssrf_protection_enabled():
        return {}, {}

    sync_kwargs: dict[str, Any] = {"follow_redirects": False}
    async_kwargs: dict[str, Any] = {"follow_redirects": False}

    hostname = _transport_host(validated_url)
    if hostname and validated_ips:
        ip_list = list(validated_ips)
        sync_kwargs["transport"] = SSRFProtectedSyncTransport(pinned_ips={hostname: ip_list})
        async_kwargs["transport"] = SSRFProtectedTransport(pinned_ips={hostname: ip_list})

    return sync_kwargs, async_kwargs


def ssrf_protected_httpx_client_kwargs_for_url(url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return sync/async httpx kwargs that enforce connector SSRF protection for SDK clients."""
    try:
        validated_url, validated_ips = validate_and_resolve_connector_url(url)
    except SSRFProtectionError as e:
        msg = f"SSRF Protection: {e}"
        raise ValueError(msg) from e
    return _httpx_client_kwargs_for_validated_url(validated_url, validated_ips)


def ssrf_protected_strict_httpx_client_kwargs_for_url(url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return pinned client kwargs while denying provider loopback unless explicitly allowlisted."""
    try:
        validated_url, validated_ips = _validate_and_resolve_strict_url(url)
    except SSRFProtectionError as e:
        msg = f"SSRF Protection: {e}"
        raise ValueError(msg) from e
    return _httpx_client_kwargs_for_validated_url(validated_url, validated_ips)


def _openai_clients_from_kwargs(
    sync_kwargs: dict[str, Any], async_kwargs: dict[str, Any]
) -> dict[str, httpx.Client | httpx.AsyncClient]:
    """Build OpenAI-compatible sync and async clients from validated kwargs."""
    if not sync_kwargs and not async_kwargs:
        return {}
    return {
        "http_client": httpx.Client(**sync_kwargs),
        "http_async_client": httpx.AsyncClient(**async_kwargs),
    }


def ssrf_protected_openai_clients_for_url(url: str) -> dict[str, httpx.Client | httpx.AsyncClient]:
    """Return pinned sync and async clients for OpenAI-compatible LangChain components."""
    return _openai_clients_from_kwargs(*ssrf_protected_httpx_client_kwargs_for_url(url))


def ssrf_protected_strict_openai_clients_for_url(url: str) -> dict[str, httpx.Client | httpx.AsyncClient]:
    """Return pinned clients while denying provider loopback unless explicitly allowlisted."""
    return _openai_clients_from_kwargs(*ssrf_protected_strict_httpx_client_kwargs_for_url(url))


async def ssrf_safe_async_get(url: str, **request_kwargs: Any) -> httpx.Response:
    """Perform an async GET with connector SSRF validation and DNS pinning."""
    _raise_if_following_redirects(request_kwargs)
    validated_url, validated_ips = validate_and_resolve_connector_url(url)
    async with _async_client_for_url(validated_url, validated_ips) as client:
        return await client.get(url=validated_url, **request_kwargs)


async def ssrf_safe_async_post(url: str, **request_kwargs: Any) -> httpx.Response:
    """Perform an async POST with connector SSRF validation and DNS pinning."""
    _raise_if_following_redirects(request_kwargs)
    validated_url, validated_ips = validate_and_resolve_connector_url(url)
    async with _async_client_for_url(validated_url, validated_ips) as client:
        return await client.post(url=validated_url, **request_kwargs)


def _same_origin(first_url: str, second_url: str) -> bool:
    first = httpx.URL(first_url)
    second = httpx.URL(second_url)
    return (first.scheme, first.raw_host, first.port) == (second.scheme, second.raw_host, second.port)


def _is_safe_https_upgrade(previous_url: str, next_url: str) -> bool:
    """Match httpx's authorization-preserving HTTP-to-HTTPS redirect exception."""
    previous = httpx.URL(previous_url)
    next_ = httpx.URL(next_url)
    return (
        previous.scheme == "http"
        and previous.raw_host == next_.raw_host
        and previous.port is None
        and next_.scheme == "https"
        and next_.port is None
    )


def _headers_for_redirect(headers: Any, previous_url: str, next_url: str) -> httpx.Headers | None:
    if headers is None:
        return None

    redirect_headers = httpx.Headers(headers)
    if _same_origin(previous_url, next_url):
        return redirect_headers

    # Match httpx's safe HTTP-to-HTTPS authorization exception, while never
    # replaying caller-supplied cookies or proxy credentials across origins.
    if not _is_safe_https_upgrade(previous_url, next_url):
        redirect_headers.pop("Authorization", None)
    redirect_headers.pop("Cookie", None)
    redirect_headers.pop("Proxy-Authorization", None)
    return redirect_headers


def _request_kwargs_for_redirect(request_kwargs: dict[str, Any], previous_url: str, next_url: str) -> dict[str, Any]:
    if _same_origin(previous_url, next_url):
        return request_kwargs

    redirect_kwargs = request_kwargs.copy()
    redirect_kwargs.pop("cookies", None)
    if not _is_safe_https_upgrade(previous_url, next_url):
        redirect_kwargs.pop("auth", None)
    return redirect_kwargs


def ssrf_safe_httpx_get(
    url: str,
    *,
    follow_redirects: bool = False,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    **request_kwargs: Any,
) -> httpx.Response:
    """Perform a synchronous GET with connector SSRF validation and DNS pinning.

    When redirects are requested, they are followed manually so each target is
    independently validated and connected through a transport pinned to the IPs
    returned by that validation. Credentials are not forwarded across origins,
    except authorization on a same-host, standard-port HTTP-to-HTTPS upgrade.
    """
    current_url = url
    supplied_headers = request_kwargs.pop("headers", None)
    current_headers = httpx.Headers(supplied_headers) if supplied_headers is not None else None
    current_params = request_kwargs.pop("params", None)
    current_request_kwargs = request_kwargs

    for _ in range(max_redirects + 1):
        validated_url, validated_ips = validate_and_resolve_connector_url(current_url)
        with _sync_client_for_url(validated_url, validated_ips) as client:
            response = client.get(
                url=validated_url,
                headers=current_headers,
                params=current_params,
                follow_redirects=False,
                **current_request_kwargs,
            )

        location = response.headers.get("location")
        if not follow_redirects or response.status_code not in REDIRECT_STATUS_CODES or not location:
            return response

        next_url = urljoin(validated_url, location)
        current_headers = _headers_for_redirect(current_headers, validated_url, next_url)
        current_request_kwargs = _request_kwargs_for_redirect(current_request_kwargs, validated_url, next_url)
        current_url = next_url
        # Redirect locations carry their own query string; initial params apply once.
        current_params = None

    msg = f"Exceeded the maximum of {max_redirects} redirects while requesting {url}"
    raise SSRFProtectionError(msg)


def ssrf_safe_httpx_get_bounded(
    url: str,
    *,
    max_bytes: int,
    follow_redirects: bool = False,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    **request_kwargs: Any,
) -> bytes:
    """GET with connector SSRF validation, refusing a body larger than ``max_bytes``.

    :func:`ssrf_safe_httpx_get` buffers the whole response before a caller can measure it, so
    a size check on the returned content has already paid the memory cost. This streams
    instead and abandons the transfer as soon as the cap is passed, so a hostile endpoint
    cannot exhaust memory by answering an allowed request with an unbounded body.

    Redirects are validated per hop exactly as in :func:`ssrf_safe_httpx_get`; only the final
    response is streamed.

    Raises:
        SSRFProtectionError: if a hop fails validation or the redirect budget is exhausted.
        ValueError: if the body exceeds ``max_bytes``.
    """
    current_url = url
    supplied_headers = request_kwargs.pop("headers", None)
    current_headers = httpx.Headers(supplied_headers) if supplied_headers is not None else None
    current_params = request_kwargs.pop("params", None)
    current_request_kwargs = request_kwargs

    for _ in range(max_redirects + 1):
        validated_url, validated_ips = validate_and_resolve_connector_url(current_url)
        with (
            _sync_client_for_url(validated_url, validated_ips) as client,
            client.stream(
                "GET",
                url=validated_url,
                headers=current_headers,
                params=current_params,
                follow_redirects=False,
                **current_request_kwargs,
            ) as response,
        ):
            location = response.headers.get("location")
            is_redirect = response.status_code in REDIRECT_STATUS_CODES and bool(location)
            if not follow_redirects or not is_redirect:
                response.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        msg = f"Response from {url} exceeds the maximum size of {max_bytes} bytes"
                        raise ValueError(msg)
                    chunks.append(chunk)
                return b"".join(chunks)

        next_url = urljoin(validated_url, location)
        current_headers = _headers_for_redirect(current_headers, validated_url, next_url)
        current_request_kwargs = _request_kwargs_for_redirect(current_request_kwargs, validated_url, next_url)
        current_url = next_url
        # Redirect locations carry their own query string; initial params apply once.
        current_params = None

    msg = f"Exceeded the maximum of {max_redirects} redirects while requesting {url}"
    raise SSRFProtectionError(msg)


def ssrf_safe_httpx_post(url: str, **request_kwargs: Any) -> httpx.Response:
    """Perform a synchronous POST with connector SSRF validation and DNS pinning."""
    _raise_if_following_redirects(request_kwargs)
    validated_url, validated_ips = validate_and_resolve_connector_url(url)
    with _sync_client_for_url(validated_url, validated_ips) as client:
        return client.post(url=validated_url, **request_kwargs)


def ssrf_safe_strict_httpx_post(url: str, **request_kwargs: Any) -> httpx.Response:
    """POST to a credential-bearing provider URL with strict validation and DNS pinning."""
    _raise_if_following_redirects(request_kwargs)
    validated_url, validated_ips = _validate_and_resolve_strict_url(url)
    with _sync_client_for_url(validated_url, validated_ips) as client:
        return client.post(url=validated_url, **request_kwargs)
