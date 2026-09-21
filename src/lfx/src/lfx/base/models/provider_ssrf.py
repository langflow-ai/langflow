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

An *absent* key is the same problem wearing a disguise: a component that hands its SDK
``api_key=None`` has not opted out of sending a credential, it has delegated the choice, and
the SDK then loads ``OPENAI_API_KEY`` (or ``NVIDIA_API_KEY``, ...) straight out of the server
process environment while keeping the tenant's destination. Call sites therefore name the
variable their SDK reads via ``sdk_env_fallback`` so the guard judges what will actually be
sent rather than what the component happened to pass.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from lfx.services.deps import get_settings_service
from lfx.utils.secrets import secret_value_to_str
from lfx.utils.ssrf_httpx import (
    ssrf_protected_strict_httpx_client_kwargs_for_url,
    ssrf_protected_strict_openai_clients_for_url,
    ssrf_safe_strict_httpx_post,
    validate_strict_url_for_ssrf_or_raise,
)
from lfx.utils.ssrf_protection import is_host_allowed, is_ssrf_protection_enabled

if TYPE_CHECKING:
    from collections.abc import Sequence

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


def _require_https_for_credentialed_endpoint(base_url: str | None) -> None:
    """Refuse a plaintext endpoint that the operator's provider credential is sent to.

    Every caller of this module hands ``base_url`` to an SDK that attaches a stored
    provider API key to the request. Over ``http://`` that key crosses the network in
    cleartext (CWE-319), so a tenant who can edit the field can downgrade the operator's
    credential off TLS without needing an SSRF target at all - the host may be perfectly
    public and still leak the key to anyone on the path.

    The one exception is a host the *operator* explicitly allowlisted via
    ``ssrf_allowed_hosts``: that is a deliberate deployment decision (a plaintext internal
    gateway on a trusted segment), not something a tenant can arrange, and the SSRF policy
    already requires it for such a host. Provider defaults never reach here - callers skip
    them before calling this.

    Raises:
        ValueError: If the endpoint uses a scheme other than https and its host is not
            operator-allowlisted.
    """
    if not base_url or not is_ssrf_protection_enabled():
        # With connector SSRF protection off the operator has opted out of this
        # policy wholesale; this check is part of it, not a separate control.
        return
    parsed = urlparse(str(base_url).strip())
    if parsed.scheme == "https":
        return
    hostname = parsed.hostname
    if parsed.scheme == "http" and hostname and is_host_allowed(hostname):
        return
    msg = (
        f"Provider endpoint {base_url!r} must use https. The configured provider credential "
        "is sent to this endpoint, and a plaintext connection would transmit it in the clear. "
        "Use an https endpoint, or have an operator allowlist the host via "
        "LANGFLOW_SSRF_ALLOWED_HOSTS if a plaintext internal gateway is intended."
    )
    raise ValueError(msg)


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
    _require_https_for_credentialed_endpoint(base_url)


_MODEL_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\\-]*$")


def validate_provider_model_identifier(value: str | None, *, field_name: str = "endpoint") -> None:
    """Validate a provider field that names a *model*, not an HTTP endpoint.

    Some SDKs call a model identifier an "endpoint" and append it to their own
    configured API host (Qianfan builds ``/chat/{endpoint}``). Such a field is
    not a URL: running it through the base-URL SSRF guard rejects every
    legitimate value, while what actually needs preventing is a value that
    changes the origin or escapes the path the SDK builds.

    Accepts the identifier shape those SDKs document (``ernie-3.5-8k-0329``,
    ``completions_pro``) and rejects anything carrying a scheme, authority,
    path separator, traversal sequence, query, fragment or control character.

    Raises:
        ValueError: If the value is non-empty and is not a bare identifier.
    """
    if value is None or not str(value).strip():
        return
    candidate = str(value).strip()
    if not _MODEL_IDENTIFIER_RE.match(candidate) or ".." in candidate:
        msg = (
            f"Invalid {field_name} '{candidate}': expected a model identifier such as "
            "'ernie-3.5-8k-0329', not a URL or path. The provider SDK appends this value to "
            "its own API host, so it must not contain a scheme, host, path separator or "
            "traversal sequence."
        )
        raise ValueError(msg)


def provider_httpx_clients(
    base_url: str | None, *, default_url: str | None = None
) -> dict[str, httpx.Client | httpx.AsyncClient]:
    """Return strict, DNS-pinned clients for a credential-bearing provider SDK."""
    if _is_provider_default(base_url, default_url):
        return {}
    clients = ssrf_protected_strict_openai_clients_for_url(base_url)
    _require_https_for_credentialed_endpoint(base_url)
    return clients


def provider_httpx_client_kwargs(
    base_url: str | None, *, default_url: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the pinned sync/async httpx *kwargs* for a provider endpoint.

    Use this instead of :func:`provider_httpx_clients` when the SDK only builds
    its own clients lazily (``if not self.client:``). Such an SDK configures
    base URL, auth headers and timeout inside that same branch, so handing it a
    ready-made client silently drops all of them. Taking the kwargs lets the
    caller construct a client that satisfies the SDK's contract *and* keeps the
    DNS pinning and redirect suppression.

    Returns two empty dicts when there is nothing to enforce (default endpoint,
    or SSRF protection disabled), so the caller leaves that path untouched.
    """
    if _is_provider_default(base_url, default_url):
        return {}, {}
    client_kwargs = ssrf_protected_strict_httpx_client_kwargs_for_url(base_url)
    _require_https_for_credentialed_endpoint(base_url)
    return client_kwargs


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


def is_env_sourced_credential(value: Any) -> bool:
    """Whether ``value`` exactly matches a value held in the server process environment.

    Both routes that put an operator-provisioned provider key into a tenant's flow — the
    seeded credential variables (``store_environment_variables``) and the load-from-DB
    environment fallback (``fallback_to_env_var``) — copy the value verbatim out of
    ``os.environ``, so an exact value match identifies the credential as the operator's
    regardless of which route delivered it. A tenant cannot arrange a false positive
    without already knowing the value they are not allowed to read.

    Every non-empty environment value counts, with no minimum length. A short
    operator-provisioned key (a LiteLLM virtual key, a self-hosted NIM token) is still the
    operator's, and neither the LiteLLM nor the local-provider component imposes a length
    floor of its own, so exempting short values would forward exactly those keys to a
    tenant-chosen endpoint. The cost of erring the other way is bounded: a tenant whose own
    key happens to equal some short environment value is merely refused a custom endpoint.

    Accepts plain strings and ``SecretStr``-style wrappers.
    """
    text = secret_value_to_str(value)
    if not text:
        return False
    return any(text == env_value for env_value in os.environ.values())


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


def _parse_allowlist_entry(entry: str) -> tuple[str, bool]:
    """Split an allowlist entry into its host pattern and whether it opts into cleartext.

    An entry is a bare host (``api.example.com``), a ``host:port`` pair, or a wildcard
    (``*.example.com``). Writing it with an explicit ``http://`` scheme is how an operator
    states that they accept the credential reaching that host in cleartext; every other
    form requires HTTPS.
    """
    allows_cleartext = entry.startswith("http://")
    pattern = entry.split("://", 1)[1] if "://" in entry else entry
    return pattern.rstrip("/"), allows_cleartext


def _matching_allowlist_entry(base_url: str, allowed_hosts: list[str]) -> str | None:
    """The allowlist entry covering ``base_url``'s host, or None when none does."""
    parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return None
    host_port = f"{hostname}:{parsed.port}" if parsed.port else hostname
    for entry in allowed_hosts:
        pattern, _ = _parse_allowlist_entry(entry)
        if pattern in {hostname, host_port}:
            return entry
        if pattern.startswith("*.") and hostname.endswith(pattern[1:]):
            return entry
    return None


def _host_is_allowlisted(base_url: str, allowed_hosts: list[str]) -> bool:
    return _matching_allowlist_entry(base_url, allowed_hosts) is not None


def _first_set_env_var(names: str | Sequence[str] | None) -> str | None:
    """The first of ``names`` that holds a non-empty value in the server environment."""
    if not names:
        return None
    candidates = (names,) if isinstance(names, str) else names
    return next((name for name in candidates if os.environ.get(name, "").strip()), None)


def _env_credential_reason(api_key: Any, sdk_env_fallback: str | Sequence[str] | None) -> str | None:
    """Why the credential this call is about to put on the wire is the operator's, or None.

    Two distinct routes send an operator-provisioned key. The component may hand the SDK a
    key it resolved from the environment itself, which :func:`is_env_sourced_credential`
    recognizes by value. Or the component may hand the SDK *nothing* — ``None`` rather than
    an empty string — in which case the SDK resolves a credential of its own from
    ``sdk_env_fallback`` and the destination receives a key the component never saw. The
    second route carries no value for a value-based check to inspect, so it is judged by
    whether the variable the SDK reads is set.

    An empty string is not the same as ``None``: it is a credential the component is
    deliberately withholding, and the provider SDKs treat it as "no key" rather than
    substituting one from the environment, so nothing of the operator's can leave.
    """
    if api_key is not None:
        text = secret_value_to_str(api_key)
        if not text:
            return None
        if not is_env_sourced_credential(text):
            return None
        return "This component's API key resolves to a value from the server environment"

    fallback_var = _first_set_env_var(sdk_env_fallback)
    if fallback_var is None:
        return None
    return (
        f"This component has no API key set, so the provider SDK falls back to ${fallback_var} "
        "from the server environment"
    )


def ensure_credential_endpoint_allowed(
    api_key: Any,
    base_url: str | None,
    *,
    default_url: str | None = None,
    sdk_env_fallback: str | Sequence[str] | None = None,
) -> None:
    """Refuse to forward a server-environment credential to a tenant-chosen endpoint.

    Model-provider components resolve their ``api_key`` field from the server process
    environment by default and then send it, in an ``Authorization`` header, to whatever
    ``base_url`` the flow author set. The tenant may *use* that key but may not *read* it
    (outputs are scrubbed), so letting them pick the destination voids the guarantee: the
    key leaves the deployment to an address the operator never sanctioned.

    This is a no-op when the destination is the provider's own default endpoint (or
    absent), when the destination host is in ``LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS``,
    or when the credential is not environment-sourced (a tenant's own key may go wherever
    the SSRF policy permits). An allowlisted host is additionally held to HTTPS unless the
    operator wrote the entry with an explicit ``http://`` scheme, so a sanctioned
    destination cannot receive the credential in cleartext by accident.

    Args:
        api_key: The credential this component will hand the SDK — the same expression the
            SDK constructor receives. ``None`` means the component is passing no key and the
            SDK will resolve one itself; an empty string means no credential is sent at all.
        base_url: The tenant-supplied base URL, or None/empty for the provider default.
        default_url: The provider's own canonical endpoint, which is always allowed.
        sdk_env_fallback: Environment variable name(s) the provider SDK reads when the
            component passes no key (``OPENAI_API_KEY`` for the OpenAI-compatible SDKs,
            ``NVIDIA_API_KEY`` for ``ChatNVIDIA``). Required for the guard to see the
            absent-key route; omitting it leaves that route unchecked.

    Raises:
        ValueError: If the credential is environment-sourced and the destination is a
            non-default, non-allowlisted endpoint, or is allowlisted but reached over
            cleartext HTTP without an explicit opt-in.
    """
    if not base_url or _is_provider_default(base_url, default_url):
        return

    reason = _env_credential_reason(api_key, sdk_env_fallback)
    if reason is None:
        return

    parsed = urlparse(base_url)
    display_host = parsed.hostname if isinstance(parsed.hostname, str) else base_url
    entry = _matching_allowlist_entry(base_url, get_provider_credential_allowed_hosts())

    if entry is None:
        msg = (
            f"Refusing to send a server-provisioned API credential to the non-default endpoint "
            f"'{display_host}'. {reason}, which may only be sent to the provider's default endpoint "
            "or to a host the operator has allowlisted via LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS. "
            "Set an explicit API key to use a custom endpoint."
        )
        raise ValueError(msg)

    if parsed.scheme.lower() == "http" and not _parse_allowlist_entry(entry)[1]:
        msg = (
            f"Refusing to send a server-provisioned API credential to '{display_host}' over cleartext "
            f"HTTP. {reason}, so the request must use HTTPS. Use an https:// base URL, or, if this "
            f"deployment genuinely requires cleartext to that host, write the allowlist entry with an "
            f"explicit scheme ('http://{entry}') in LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS."
        )
        raise ValueError(msg)
