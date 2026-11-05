"""Check a source database against this release before upgrading to it."""

from importlib import import_module

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


def __getattr__(name: str):
    if name not in __all__:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    return getattr(import_module("langflow.upgrade_check.reader"), name)
