"""Lazy component re-exports for the ``google_search`` bundle.

Mirrors the pre-extraction layout of ``lfx.components.google`` for the
slice of components this bundle owns.  Saved flows that referenced
``lfx.components.google.<file>.<Class>`` resolve via the migration
table after rewrite to ``lfx_google_search.components.google_search.<file>.<Class>``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .google_search_api_core import GoogleSearchAPICore
    from .google_serper_api_core import GoogleSerperAPICore

_dynamic_imports = {
    "GoogleSearchAPICore": "google_search_api_core",
    "GoogleSerperAPICore": "google_serper_api_core",
}

__all__ = [
    "GoogleSearchAPICore",
    "GoogleSerperAPICore",
]


def __getattr__(attr_name: str) -> Any:
    if attr_name not in _dynamic_imports:
        msg = f"module {__name__!r} has no attribute {attr_name!r}"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import {attr_name!r} from {__name__!r}: {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
