"""Connector SSRF policy for tenant-supplied model-provider base URLs.

Model-provider components (OpenAI, Anthropic, vLLM, and provider bundles generally) expose
an editable "API base" / "base URL" field and hand it straight to a provider SDK
constructor. The SDK then performs a server-side request to that host **carrying the
operator's stored provider credential**, so an unvalidated field is both an SSRF primitive
and a credential-exfiltration primitive.

This module is the single seam where those components apply the repository's existing
connector SSRF policy (``lfx.utils.ssrf_protection`` /
``lfx.utils.ssrf_httpx``), so a new provider bundle picks up the guard by importing one
helper rather than copy-pasting a call site. Credential-bearing provider URLs intentionally
use a stricter default than ordinary connectors: literal loopback is blocked unless the
operator explicitly trusts it through ``LANGFLOW_SSRF_ALLOWED_HOSTS``. The global and
connector validation kill switches retain their existing behavior.

Scope note: this policy blocks *internal* destinations (cloud metadata, RFC1918, and
loopback). It does not, and cannot, decide whether an arbitrary *public* host is a
legitimate OpenAI-compatible provider, so pointing a provider component at an
attacker-controlled public endpoint still forwards the configured credential. Restricting
which hosts a stored provider credential may be sent to is a separate, additive control.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.ssrf_httpx import (
    ssrf_protected_strict_openai_clients_for_url,
    ssrf_safe_strict_httpx_post,
    validate_strict_url_for_ssrf_or_raise,
)

if TYPE_CHECKING:
    import httpx

__all__ = [
    "openai_compatible_client_kwargs",
    "provider_httpx_clients",
    "provider_safe_httpx_post",
    "validate_provider_base_url",
]


def _is_provider_default(base_url: str | None, default_url: str | None) -> bool:
    """Whether ``base_url`` is absent or is just the provider's own canonical endpoint.

    Components commonly pre-populate the base-URL field with the provider default (and some
    write it back into the build config), so the default arrives as an explicit value on nearly
    every build. That value is server-chosen rather than tenant-chosen and points at the
    provider's public API, so there is nothing for the connector policy to constrain --
    skipping it keeps the common path free of a DNS round-trip and of pinned clients.
    """
    if not base_url:
        return True
    if not default_url:
        return False
    return base_url.rstrip("/") == default_url.rstrip("/")


def validate_provider_base_url(base_url: str | None, *, default_url: str | None = None) -> None:
    """Apply connector SSRF policy to a tenant-supplied provider base URL.

    Use this only for configuration or preflight paths that do not later connect to
    ``base_url``. Credential-bearing network calls must use :func:`provider_httpx_clients`,
    :func:`provider_safe_httpx_post`, or :func:`openai_compatible_client_kwargs` so the
    actual connection stays pinned to the validated IP.

    Args:
        base_url: The tenant-supplied base URL, or None/empty to use the provider default.
        default_url: The provider's own canonical endpoint, which is skipped as a no-op.

    Raises:
        ValueError: If the URL is blocked by SSRF policy or is not a validatable http(s) URL.
    """
    if _is_provider_default(base_url, default_url):
        return
    validate_strict_url_for_ssrf_or_raise(base_url)


def provider_httpx_clients(
    base_url: str | None, *, default_url: str | None = None
) -> dict[str, httpx.Client | httpx.AsyncClient]:
    """Return strict, DNS-pinned clients for a credential-bearing provider SDK."""
    if _is_provider_default(base_url, default_url):
        return {}
    return ssrf_protected_strict_openai_clients_for_url(base_url)


def provider_safe_httpx_post(url: str, **request_kwargs: Any) -> httpx.Response:
    """POST to a provider URL with strict validation and connection-time DNS pinning."""
    return ssrf_safe_strict_httpx_post(url, **request_kwargs)


def openai_compatible_client_kwargs(base_url: str | None, *, default_url: str | None = None) -> dict[str, Any]:
    """Validate ``base_url`` and return DNS-pinned httpx clients for an OpenAI-compatible SDK.

    Returns the ``http_client`` / ``http_async_client`` kwargs understood by ``ChatOpenAI``,
    ``OpenAIEmbeddings`` and the other OpenAI-compatible LangChain classes. The clients pin
    the hostname to the IPs validated here, which closes the DNS-rebinding window that plain
    validate-then-connect leaves open, and disable redirect following so a permitted host
    cannot 302 the request into an internal one.

    Returns an empty dict when there is nothing to enforce (no base URL, or SSRF protection
    disabled), so callers can unconditionally ``update()`` the result into their SDK
    parameters and leave the default-endpoint path byte-for-byte unchanged.

    Args:
        base_url: The tenant-supplied base URL, or None/empty to use the provider default.
        default_url: The provider's own canonical endpoint, which is skipped as a no-op.

    Returns:
        Client kwargs to merge into the SDK constructor call; empty when nothing to enforce.

    Raises:
        ValueError: If the URL is blocked by SSRF policy or is not a validatable http(s) URL.
    """
    if _is_provider_default(base_url, default_url):
        return {}
    return provider_httpx_clients(base_url)
