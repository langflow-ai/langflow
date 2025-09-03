"""LangFlow Components module."""

from __future__ import annotations

from typing import Any

from lfx.components import __all__ as _lfx_all

__all__: list[str] = list(_lfx_all)


def __getattr__(attr_name: str) -> Any:
    """Forward attribute access to lfx.components."""
    from lfx import components

    return getattr(components, attr_name)


def __dir__() -> list[str]:
    """Forward dir() to lfx.components."""
    return list(__all__)
