"""Import-safe upgrade report contracts and isolated checker modules."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langflow.upgrade_check.reader import (
        SourceCatalogPolicy,
        SourceDatabase,
        SourceDatabaseError,
        SourceFlow,
        SourceFlowVersion,
        SourceProject,
        SourceUser,
        open_source,
        read_connection,
        read_only_connection,
    )

__all__ = [
    "SourceCatalogPolicy",
    "SourceDatabase",
    "SourceDatabaseError",
    "SourceFlow",
    "SourceFlowVersion",
    "SourceProject",
    "SourceUser",
    "open_source",
    "read_connection",
    "read_only_connection",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from importlib import import_module

        return getattr(import_module("langflow.upgrade_check.reader"), name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
