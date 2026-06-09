"""Utilities for lfx package."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.utils.flow_requirements import (
        generate_requirements_from_file,
        generate_requirements_from_flow,
        generate_requirements_txt,
    )

__all__ = [
    "generate_requirements_from_file",
    "generate_requirements_from_flow",
    "generate_requirements_txt",
]


def __getattr__(name: str):
    if name in __all__:
        from lfx.utils import flow_requirements

        return getattr(flow_requirements, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
