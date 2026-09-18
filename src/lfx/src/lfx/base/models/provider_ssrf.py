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

Credential-egress note: the SSRF policy blocks *internal* destinations (cloud metadata,
RFC1918, and loopback). It does not, and cannot, decide whether an arbitrary *public* host
is a legitimate OpenAI-compatible provider. That second check is
:func:`ensure_credential_endpoint_allowed`: when the credential a component is about to
send resolves to a value held in the server process environment (provisioned by the
operator, deliberately unreadable by the tenant), the destination must be one the operator
sanctioned -- the component's own default endpoint, or a host in
``LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS``. A tenant-supplied key is unaffected, so
bring-your-own-key flows against custom endpoints keep working.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from lfx.services.deps import get_settings_service
from lfx.utils.secrets import secret_value_to_str
from lfx.utils.ssrf_httpx import (
    ssrf_protected_strict_openai_clients_for_url,
    ssrf_safe_strict_httpx_post,
    validate_strict_url_for_ssrf_or_raise,
)

if TYPE_CHECKING:
    import httpx

__all__ = [
    "ensure_credential_endpoint_allowed",
    "get_provider_credential_allowed_hosts",
    "is_env_sourced_credential",
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


# Minimum length for an environment value to be treated as a credential. Shorter values
# (booleans, log levels, paths such as "localhost") are too collision-prone to fail
# closed on; real provider API keys are well above this.
_MIN_ENV_CREDENTIAL_LENGTH = 8


def is_env_sourced_credential(value: Any) -> bool:
    """Whether ``value`` exactly matches a value held in the server process environment.

    Both routes that put an operator-provisioned provider key into a tenant's flow — the
    seeded credential variables (``store_environment_variables``) and the load-from-DB
    environment fallback (``fallback_to_env_var``) — copy the value verbatim out of
    ``os.environ``, so an exact value match identifies the credential as the operator's
    regardless of which route delivered it. A tenant cannot arrange a false positive
    without already knowing the value they are not allowed to read.

    Accepts plain strings and ``SecretStr``-style wrappers. Values shorter than
    ``_MIN_ENV_CREDENTIAL_LENGTH`` never match.
    """
    text = secret_value_to_str(value)
    if not text or len(text) < _MIN_ENV_CREDENTIAL_LENGTH:
        return False
    return any(text == env_value for env_value in os.environ.values() if len(env_value) >= _MIN_ENV_CREDENTIAL_LENGTH)


def get_provider_credential_allowed_hosts() -> list[str]:
    """Operator-configured hosts that may receive server-environment provider credentials.

    Read directly from ``LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS`` first (supporting
    test overrides via ``patch.dict``), then from the settings service.
    """
    env_value = os.getenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "")
    if env_value:
        return [entry.strip().lower() for entry in env_value.split(",") if entry.strip()]

    settings_service = get_settings_service()
    if settings_service:
        allowed = getattr(settings_service.settings, "provider_credential_allowed_hosts", None)
        if allowed:
            return [entry.strip().lower() for entry in allowed if entry and entry.strip()]
    return []


def _host_is_allowlisted(base_url: str, allowed_hosts: list[str]) -> bool:
    parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False
    host_port = f"{hostname}:{parsed.port}" if parsed.port else hostname
    for entry in allowed_hosts:
        if entry in {hostname, host_port}:
            return True
        if entry.startswith("*.") and hostname.endswith(entry[1:]):
            return True
    return False


def ensure_credential_endpoint_allowed(api_key: Any, base_url: str | None, *, default_url: str | None = None) -> None:
    """Refuse to forward a server-environment credential to a tenant-chosen endpoint.

    Model-provider components resolve their ``api_key`` field from the server process
    environment by default and then send it, in an ``Authorization`` header, to whatever
    ``base_url`` the flow author set. The tenant may *use* that key but may not *read* it
    (outputs are scrubbed), so letting them pick the destination voids the guarantee: the
    key leaves the deployment to an address the operator never sanctioned.

    This is a no-op when the destination is the provider's own default endpoint (or
    absent), when the destination host is in
    ``LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS``, or when the key is not
    environment-sourced (a tenant's own key may go wherever the SSRF policy permits).

    Args:
        api_key: The resolved credential about to be sent (string or secret wrapper).
        base_url: The tenant-supplied base URL, or None/empty for the provider default.
        default_url: The provider's own canonical endpoint, which is always allowed.

    Raises:
        ValueError: If the credential is environment-sourced and the destination is a
            non-default, non-allowlisted endpoint.
    """
    if api_key is None or not secret_value_to_str(api_key):
        return
    if not base_url or _is_provider_default(base_url, default_url):
        return
    if _host_is_allowlisted(base_url, get_provider_credential_allowed_hosts()):
        return
    if is_env_sourced_credential(api_key):
        host = urlparse(base_url).hostname
        display_host = host if isinstance(host, str) else base_url
        msg = (
            f"Refusing to send a server-provisioned API credential to the non-default endpoint "
            f"'{display_host}'. This component's API key resolves to a value from the server environment, "
            "which may only be sent to the provider's default endpoint or to a host the operator "
            "has allowlisted via LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS. "
            "Set an explicit API key to use a custom endpoint."
        )
        raise ValueError(msg)
