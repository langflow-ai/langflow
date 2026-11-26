"""Shared plumbing for the WebRouter components.

WebRouter is an open-source library that puts one interface in front of several
web search and page extraction providers and falls back between them. With no
key set it uses the providers' keyless tiers. A provider key in the Langflow
server's environment, such as ``TAVILY_API_KEY`` or ``EXA_API_KEY``, adds that
provider to the routing; a key entered in a component goes to the provider named
in the same component.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

    from web_router import WebRouter

DOCUMENTATION_URL = "https://docs.webrouter.net"
DEFAULT_TIMEOUT_SECONDS = 30.0

PROVIDER_INFO = (
    "Optional. A provider to send every call to, such as tavily, exa or firecrawl. "
    "Leave empty to let WebRouter pick one and fall back to the next if a call fails."
)
API_KEY_INFO = (
    "Optional. An API key for the provider named in Provider. Without one, WebRouter uses the "
    "keyless tiers and any provider keys set in the Langflow server's environment."
)

_INSTALL_HINT = 'WebRouter is not installed. Install it with: pip install "lfx-bundles[webrouter]" (Python 3.11+).'
_LIST_SEPARATORS = re.compile(r"[\s,]+")

T = TypeVar("T")


class WebRouterComponentError(Exception):
    """A WebRouter call could not be made or failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def split_list(value: Any) -> list[str]:
    """Split a comma-, space- or newline-separated input (or a list) into its non-empty items."""
    items = value if isinstance(value, list) else [value]
    return [part for item in items for part in _LIST_SEPARATORS.split(str(item or "")) if part]


def call_router(provider: Any, api_key: Any, action: Callable[[WebRouter, str | None], T]) -> T:
    """Open a ``WebRouter``, run ``action(router, provider)`` and close the router.

    ``provider`` is passed to ``action`` as a lowercase name, or ``None`` to let WebRouter pick.
    A key given with a provider goes to that provider through ``provider_config``.

    Raises:
        WebRouterComponentError: When ``webrouter`` is not installed, a key is given without a provider,
            or WebRouter raises; the API key is redacted from the message.
    """
    try:
        from web_router import WebRouter, WebRouterError
    except ImportError as exc:
        raise WebRouterComponentError(_INSTALL_HINT) from exc

    name = str(provider or "").strip().lower() or None
    key = secret_value(api_key)
    if key and name is None:
        msg = "Set Provider to the provider this API key belongs to, or clear the API key."
        raise WebRouterComponentError(msg)
    provider_config = {name: {"api_key": key}} if key and name else None
    try:
        with WebRouter(provider_config=provider_config) as router:
            return action(router, name)
    except WebRouterError as exc:
        detail = str(exc).replace(key, "***") if key else str(exc)
        msg = f"WebRouter call failed: {detail}"
        raise WebRouterComponentError(msg) from exc
