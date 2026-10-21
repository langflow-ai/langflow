"""Shared HTTP plumbing for the Figranium components.

Figranium is a self-hostable browser-automation server; every component takes the
instance URL and an ``x-api-key`` credential, so the request path lives here.
Outbound calls go through Langflow's SSRF-protected httpx helpers: literal
loopback hosts stay reachable for the common self-hosted setup, internal and
cloud-metadata ranges are blocked while SSRF protection is enabled, and other
private hosts can be allowlisted with ``LANGFLOW_SSRF_ALLOWED_HOSTS``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx
from lfx.utils.ssrf_httpx import ssrf_safe_httpx_get, ssrf_safe_httpx_post
from lfx.utils.ssrf_protection import SSRFProtectionError

DEFAULT_TIMEOUT_SECONDS = 120.0
DOCUMENTATION_URL = "https://docs.figranium.dev"

# Upper bound on the response text echoed into an error message, so a URL that
# answers with an HTML page does not flood the component status.
_ERROR_DETAIL_LIMIT = 500
_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})


BASE_URL_INFO = (
    "Base URL of your Figranium instance, for example https://figranium.example.com "
    "or http://localhost:11345 for a local install."
)
API_KEY_INFO = "Figranium API key, sent as the x-api-key header."  # pragma: allowlist secret


def normalize_base_url(value: Any) -> str:
    """Return ``value`` as an absolute http(s) URL without a trailing slash.

    Raises:
        ValueError: If the URL is empty, has no host, or uses a scheme other than http(s).
    """
    base_url = str(value or "").strip().rstrip("/")
    if not base_url:
        msg = "Figranium URL is required."
        raise ValueError(msg)
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        msg = f"Figranium URL must be an absolute http(s) URL such as https://figranium.example.com; got {base_url!r}."
        raise ValueError(msg)
    return base_url


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        return str(value.get_secret_value() or "")
    return str(value or "")


def extract_items(payload: Any, key: str) -> list[dict[str, Any]]:
    """Return the dict entries of a list response, whether wrapped under ``key`` or bare.

    Figranium wraps its list endpoints (``{"tasks": [...]}``, ``{"executions": [...]}``).
    A bare array is accepted as well so an unwrapped response still yields rows
    instead of a silently empty output.
    """
    items = payload.get(key) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _error_detail(response: httpx.Response) -> str:
    """Pull a short, human-readable detail out of a Figranium error response."""
    detail = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        detail = str(body.get("message") or body.get("error") or "")
    if not detail:
        detail = response.text
    detail = " ".join(detail.split())
    if len(detail) > _ERROR_DETAIL_LIMIT:
        detail = detail[:_ERROR_DETAIL_LIMIT] + "..."
    return detail


def _status_error_message(response: httpx.Response) -> str:
    msg = f"Figranium API returned HTTP {response.status_code}"
    if response.status_code in _REDIRECT_STATUS_CODES:
        location = response.headers.get("location", "")
        target = f" to {location}" if location else ""
        return f"{msg}: the request was redirected{target}. Set Figranium URL to the address the instance answers on."
    detail = _error_detail(response)
    return f"{msg}: {detail}" if detail else msg


def _parse_json(response: httpx.Response) -> Any:
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        msg = (
            f"Figranium returned a non-JSON response (HTTP {response.status_code}); "
            "check that Figranium URL points at a Figranium instance."
        )
        raise ValueError(msg) from exc


class FigraniumAPIClient:
    """Minimal ``x-api-key`` client for Figranium's HTTP API."""

    def __init__(self, base_url: Any, api_key: Any, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.base_url = normalize_base_url(base_url)
        self.api_key = secret_value(api_key)
        if not self.api_key:
            msg = "Figranium API key is required."
            raise ValueError(msg)
        if timeout <= 0:
            msg = "Figranium request timeout must be a positive number of seconds."
            raise ValueError(msg)
        self.timeout = float(timeout)

    def get(self, path: str) -> Any:
        """GET ``path`` (relative to the base URL) and return the decoded JSON body."""
        return self._request("GET", path)

    def post(self, path: str, json: dict[str, Any]) -> Any:
        """POST ``json`` to ``path`` (relative to the base URL) and return the decoded JSON body."""
        return self._request("POST", path, json=json)

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        request_kwargs: dict[str, Any] = {
            "headers": {"x-api-key": self.api_key, "accept": "application/json"},
            "timeout": self.timeout,
        }
        if json is not None:
            request_kwargs["json"] = json
        try:
            if method == "GET":
                response = ssrf_safe_httpx_get(url, **request_kwargs)
            else:
                response = ssrf_safe_httpx_post(url, **request_kwargs)
            response.raise_for_status()
        except SSRFProtectionError as exc:
            msg = f"SSRF Protection: {exc}"
            raise ValueError(msg) from exc
        except httpx.HTTPStatusError as exc:
            raise ValueError(_status_error_message(exc.response)) from exc
        except httpx.TimeoutException as exc:
            msg = (
                f"Figranium did not respond within {self.timeout:g} seconds. Raise the timeout for long-running tasks."
            )
            raise ValueError(msg) from exc
        except httpx.HTTPError as exc:
            msg = f"Could not reach Figranium at {self.base_url}: {exc}"
            raise ValueError(msg) from exc
        return _parse_json(response)
