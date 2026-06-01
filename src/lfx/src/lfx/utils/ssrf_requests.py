"""SSRF-protected helpers for the synchronous ``requests`` library.

The httpx-based components (``api_request``, ``url``) route user-controlled URLs
through SSRF validation. Components built on the synchronous ``requests`` library
need the same protection. This module provides a drop-in ``requests.get`` wrapper
that validates the initial URL and re-validates every redirect hop, so a public URL
cannot reach internal services either directly or by redirecting to them.

``requests.get`` follows redirects by default, so validating only the initial URL is
insufficient: a public URL could redirect to ``http://169.254.169.254/`` (cloud
metadata), loopback, or an RFC1918 address. ``ssrf_safe_get`` disables automatic
redirects and re-applies :func:`validate_url_for_ssrf` to each ``Location`` before
following it. All validation is a no-op when SSRF protection is disabled, so behavior
is unchanged for operators who have not enabled it.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import requests

from lfx.utils.ssrf_protection import SSRFProtectionError, validate_url_for_ssrf

# HTTP status codes that represent a redirect carrying a Location header (RFC 9110).
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})

# Maximum number of redirects to follow before failing (matches requests' default).
DEFAULT_MAX_REDIRECTS = 30

# Credential-bearing headers that must not be forwarded to a different host on a
# redirect. ``requests`` strips these in ``Session.rebuild_auth``/``rebuild_proxies``
# when it follows redirects itself; because we follow redirects manually with
# ``allow_redirects=False`` we must reproduce that protection. Compared lowercase.
SENSITIVE_REDIRECT_HEADERS = frozenset({"authorization", "cookie", "proxy-authorization"})


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
        timeout: Timeout passed to ``requests.get`` (seconds, or a (connect, read) tuple).
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
        # Validate scheme, resolve the host, and check it against the SSRF denylist.
        # No-op when SSRF protection is disabled.
        validate_url_for_ssrf(current_url, warn_only=False)

        response = requests.get(
            current_url,
            timeout=timeout,
            headers=current_headers,
            params=current_params,
            # Never let requests auto-follow redirects; each hop is validated above.
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
