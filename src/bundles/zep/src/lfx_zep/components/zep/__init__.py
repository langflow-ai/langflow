"""Lazy component re-exports for the ``zep`` bundle.

Mirrors the pre-extraction layout of ``lfx.components.zep`` so saved
flows that referenced the module-level class
(e.g. ``lfx.components.zep.<Class>``) keep resolving via the
migration table after rewrite to
``lfx_zep.components.zep.<Class>``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .zep import ZepChatMemory

_dynamic_imports = {
    "ZepChatMemory": "zep",
}

__all__ = [
    "ZepChatMemory",
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
