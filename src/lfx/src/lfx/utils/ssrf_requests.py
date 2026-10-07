"""SSRF-protected helpers with a synchronous ``requests`` response interface.

The httpx-based components (``api_request``, ``url``) route user-controlled URLs
through SSRF validation. Components built on the synchronous ``requests`` library
need the same protection. This module provides a ``requests.Response`` wrapper
that validates and pins the IP for the initial URL and every redirect hop, so a
public URL cannot reach internal services by DNS rebinding or redirecting to them.

``requests.get`` follows redirects by default, so validating only the initial URL is
insufficient: a public URL could redirect to ``http://169.254.169.254/`` (cloud
metadata), loopback, or an RFC1918 address. ``ssrf_safe_get`` disables automatic
redirects and re-applies :func:`validate_and_resolve_url` to each ``Location`` before
following it. With protection disabled, the host explicitly allowlisted, or an
environment proxy selected, the existing ``requests.get`` path is used. Proxied
requests require the deployment proxy to enforce the egress policy.
"""

from __future__ import annotations

import os
import ssl
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import requests

from lfx.utils.ssrf_protection import SSRFProtectionError, validate_and_resolve_url
from lfx.utils.ssrf_transport import SSRFProtectedSyncTransport, pin_host_for_url

# HTTP status codes that represent a redirect carrying a Location header (RFC 9110).
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})

# Maximum number of redirects to follow before failing (matches requests' default).
DEFAULT_MAX_REDIRECTS = 30

# Credential-bearing headers that must not be forwarded to a different host on a
# redirect. ``requests`` strips these in ``Session.rebuild_auth``/``rebuild_proxies``
# when it follows redirects itself; because we follow redirects manually with
# ``allow_redirects=False`` we must reproduce that protection. Compared lowercase.
SENSITIVE_REDIRECT_HEADERS = frozenset({"authorization", "cookie", "proxy-authorization"})


def _pinned_get(
    url: str,
    validated_ips: list[str],
    *,
    timeout: float | tuple[float, float],
    headers: dict | None,
    params: dict | None,
) -> requests.Response:
    """Fetch through the validated IPs without changing the caller's response type."""
    if isinstance(timeout, tuple):
        connect_timeout, read_timeout = timeout
        httpx_timeout = httpx.Timeout(
            connect=connect_timeout, read=read_timeout, write=read_timeout, pool=connect_timeout
        )
    else:
        httpx_timeout = httpx.Timeout(timeout)

    # Preserve Requests' default headers, notably its User-Agent, for existing feeds.
    request_headers = requests.structures.CaseInsensitiveDict(requests.utils.default_headers())
    if headers:
        request_headers.update(headers)

    try:
        # Requests uses these CA bundle overrides; httpx's defaults use different
        # variable names, so pass the Requests setting into the pinned transport.
        ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE")
        verify: bool | ssl.SSLContext
        if ca_bundle:
            # httpx deprecates passing CA paths as strings. Requests accepts both
            # files and OpenSSL certificate directories for these overrides.
            verify = (
                ssl.create_default_context(capath=ca_bundle)
                if Path(ca_bundle).is_dir()
                else ssl.create_default_context(cafile=ca_bundle)
            )
        else:
            verify = True
        transport = SSRFProtectedSyncTransport(pinned_ips={pin_host_for_url(url): validated_ips}, verify=verify)
        with httpx.Client(transport=transport) as client:
            result = client.get(
                url, timeout=httpx_timeout, headers=request_headers, params=params, follow_redirects=False
            )
    except httpx.InvalidURL as exc:
        raise requests.exceptions.InvalidURL(str(exc)) from exc
    except httpx.ConnectTimeout as exc:
        raise requests.ConnectTimeout(str(exc)) from exc
    except httpx.ReadTimeout as exc:
        raise requests.ReadTimeout(str(exc)) from exc
    except httpx.TimeoutException as exc:
        raise requests.Timeout(str(exc)) from exc
    except httpx.ConnectError as exc:
        raise requests.ConnectionError(str(exc)) from exc
    except httpx.RequestError as exc:
        raise requests.RequestException(str(exc)) from exc

    response = requests.Response()
    response.status_code = result.status_code
    response.headers = requests.structures.CaseInsensitiveDict(result.headers)
    response.url = str(result.url)
    response.reason = result.reason_phrase
    response.encoding = requests.utils.get_encoding_from_headers(response.headers)
    response._content = result.content  # noqa: SLF001 - adapt the buffered httpx body to Requests
    response._content_consumed = True  # noqa: SLF001
    response.request = requests.Request("GET", url, headers=request_headers, params=params).prepare()
    return response


def refuse_redirects(session: requests.Session) -> requests.Session:
    """Make ``session`` raise instead of following a redirect, and return it.

    Some provider SDKs own their ``requests.Session`` and expose no way to pass request
    kwargs, so :func:`ssrf_safe_get`'s validate-every-hop loop cannot be applied to them.
    Refusing outright is the workable equivalent: an inference API answering a redirect to
    ``/chat/completions`` is not a flow any provider supports, while ``requests`` keeps the
    ``Authorization`` header across a same-host redirect -- including one that changes port
    or downgrades to cleartext -- so following one can hand the credential to a different
    service on a host the operator did sanction.

    The session's own configuration (TLS verification, adapters, proxies) is left intact;
    only redirect resolution is replaced.

    Args:
        session: The session to harden. It is modified in place.

    Returns:
        requests.Session: The same session, for use as a drop-in factory result.
    """

    def resolve_redirects(response, request, *, yield_requests: bool = False, **kwargs):  # noqa: ARG001
        # ``Session.send`` probes for a follow-up request with yield_requests=True even when
        # it is not following redirects; that probe is not an egress and must not raise.
        if yield_requests or not response.is_redirect:
            return iter(())
        location = response.headers.get("Location", "")
        msg = (
            f"Refusing to follow the redirect from {response.url} to '{location}'. "
            "This provider transport cannot re-validate a redirect target, and a same-host "
            "redirect keeps the Authorization header, so following it could send the "
            "credential to an unvalidated destination."
        )
        raise SSRFProtectionError(msg)

    session.resolve_redirects = resolve_redirects
    return session


def refuse_aiohttp_redirects(session: Any) -> Any:
    """Make an ``aiohttp.ClientSession`` raise instead of following a redirect, and return it.

    The asynchronous counterpart of :func:`refuse_redirects`, for SDKs that run their
    streaming and async inference over ``aiohttp`` while their blocking calls go through
    ``requests``. Hardening only the ``requests`` side leaves the async path free to follow
    a redirect, which is the same credential- and prompt-disclosure hole in a different
    transport: ``aiohttp`` follows redirects by default and, like ``requests``, keeps the
    ``Authorization`` header when the hop stays on the same hostname.

    ``aiohttp`` decides redirects inside ``ClientSession._request``, and the SDK calls
    ``session.get``/``session.post`` without forwarding request kwargs, so the policy is
    installed by wrapping that method on the instance: every request is issued with
    ``allow_redirects=False`` and a redirect response is refused rather than returned, so a
    caller cannot resume the hop by reading ``Location`` itself.

    The session's own configuration (connector, TLS context, timeouts, headers) is left
    intact; only redirect resolution is replaced. ``aiohttp`` is not imported here -- the
    session is duck-typed -- so this module stays importable without it.

    Args:
        session: The ``aiohttp.ClientSession`` to harden. It is modified in place.

    Returns:
        The same session, for use as a drop-in factory result.
    """
    # Redirects are decided inside ClientSession._request; aiohttp exposes no public seam.
    original_request = session._request  # noqa: SLF001

    async def guarded_request(method: str, url: Any, **kwargs: Any):
        kwargs["allow_redirects"] = False
        response = await original_request(method, url, **kwargs)
        if response.status in REDIRECT_STATUS_CODES:
            location = response.headers.get("Location", "")
            response.close()
            msg = (
                f"Refusing to follow the redirect from {response.url} to '{location}'. "
                "This provider transport cannot re-validate a redirect target, and a same-host "
                "redirect keeps the Authorization header, so following it could send the "
                "credential to an unvalidated destination."
            )
            raise SSRFProtectionError(msg)
        return response

    session._request = guarded_request  # noqa: SLF001
    return session


def ssrf_safe_get(
    url: str,
    *,
    timeout: float | tuple[float, float],
    headers: dict | None = None,
    params: dict | None = None,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> requests.Response:
    """Perform a GET request with SSRF validation on the initial URL and every redirect hop.

    Automatic redirect following is disabled and handled manually so that each redirect
    target is re-validated against the SSRF denylist (private/loopback/link-local ranges,
    cloud metadata endpoints, non-http(s) schemes) before a connection is made.

    Args:
        url: The URL to fetch.
        timeout: Timeout in seconds, or a (connect, read) tuple.
        headers: Optional request headers, forwarded on every hop. Credential-bearing
            headers (Authorization, Cookie, Proxy-Authorization) are dropped when a
            redirect crosses to a different host, so they are not leaked to an unrelated
            origin. The caller's dict is never mutated.
        params: Optional query parameters for the initial request only (redirect targets
            carry their own query string in the ``Location`` header).
        max_redirects: Maximum number of redirects to follow before raising.

    Returns:
        requests.Response: The final response after following any validated redirects.

    Raises:
        SSRFProtectionError: If the initial URL or any redirect target is blocked by SSRF
            protection, or if the redirect limit is exceeded.
        requests.RequestException: For underlying network/HTTP errors (propagated).
    """
    current_url = url
    current_params = params
    current_headers = headers

    for _ in range(max_redirects + 1):
        # Use the IPs returned by this validation for the connection itself. A second
        # hostname lookup inside Requests could otherwise rebind to an internal IP.
        validated_url, validated_ips = validate_and_resolve_url(current_url)
        # An explicit HTTP(S) proxy resolves the destination on the proxy side.
        # Our direct pinned transport would silently bypass that proxy, including
        # mandatory egress controls. Preserve the Requests path for proxy users;
        # the deployment proxy must block internal destinations and DNS rebinding.
        proxies = requests.utils.get_environ_proxies(validated_url)
        selected_proxy = requests.utils.select_proxy(validated_url, proxies)
        if validated_ips and not selected_proxy:
            response = _pinned_get(
                validated_url, validated_ips, timeout=timeout, headers=current_headers, params=current_params
            )
        else:
            # Protection is disabled, the host is explicitly allowlisted, or
            # this URL is routed through an environment proxy.
            response = requests.get(
                validated_url,
                timeout=timeout,
                headers=current_headers,
                params=current_params,
                allow_redirects=False,
            )

        location = response.headers.get("Location")
        if response.status_code in REDIRECT_STATUS_CODES and location:
            # Resolve relative redirects against the current URL. The redirect target
            # carries its own query string, so the initial params are not reused.
            previous_url = current_url
            current_url = urljoin(current_url, location)
            current_params = None
            # Drop credential-bearing headers when the redirect crosses to a different
            # host, so caller-supplied Authorization/Cookie/Proxy-Authorization are not
            # leaked to an unrelated origin. Build a new dict; never mutate the caller's.
            if current_headers and urlparse(previous_url).hostname != urlparse(current_url).hostname:
                current_headers = {
                    name: value
                    for name, value in current_headers.items()
                    if name.lower() not in SENSITIVE_REDIRECT_HEADERS
                }
            continue

        return response

    msg = f"Exceeded the maximum of {max_redirects} redirects while requesting {url}"
    raise SSRFProtectionError(msg)
