from __future__ import annotations

__all__ = ["data_to_text", "docs_to_data", "messages_to_text", "safe_convert"]

_EXPORTS = frozenset(__all__)


def __getattr__(name: str):
    if name in _EXPORTS:
        from . import data as _data

        val = getattr(_data, name)
        globals()[name] = val
        return val
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
