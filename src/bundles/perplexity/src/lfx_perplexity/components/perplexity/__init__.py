"""Lazy component re-exports for the ``perplexity`` bundle.

Mirrors the pre-extraction layout of ``lfx.components.perplexity`` so saved
flows that referenced the module-level class
(e.g. ``lfx.components.perplexity.<Class>``) keep resolving via the
migration table after rewrite to
``lfx_perplexity.components.perplexity.<Class>``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .perplexity import PerplexityComponent

_dynamic_imports = {
    "PerplexityComponent": "perplexity",
}

__all__ = [
    "PerplexityComponent",
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
