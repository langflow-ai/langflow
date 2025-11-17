"""Data module - backwards compatibility alias for data_source.

This module provides backwards compatibility by forwarding all imports
to data_source where the actual data components are located.
"""

from __future__ import annotations

from typing import Any

from lfx.components._importing import import_mod

# Replicate the same dynamic imports as data_source
_dynamic_imports = {
    "APIRequestComponent": "api_request",
    "CSVToDataComponent": "csv_to_data",
    "JSONToDataComponent": "json_to_data",
    "MockDataGeneratorComponent": "mock_data",
    "NewsSearchComponent": "news_search",
    "RSSReaderComponent": "rss",
    "URLComponent": "url",
    "WebSearchComponent": "web_search",
    # File and Directory components are in files_and_knowledge, forward them for backwards compatibility
    "FileComponent": ("file", "files_and_knowledge"),
    "DirectoryComponent": ("directory", "files_and_knowledge"),
}

__all__ = [
    "APIRequestComponent",
    "CSVToDataComponent",
    "DirectoryComponent",
    "FileComponent",
    "JSONToDataComponent",
    "MockDataGeneratorComponent",
    "NewsSearchComponent",
    "RSSReaderComponent",
    "URLComponent",
    "WebSearchComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Forward attribute access to data_source components."""
    # Handle submodule access for backwards compatibility
    # e.g., lfx.components.data.directory -> lfx.components.files_and_knowledge.directory
    if attr_name == "directory":
        from importlib import import_module

        result = import_module("lfx.components.files_and_knowledge.directory")
        globals()[attr_name] = result
        return result
    if attr_name == "file":
        from importlib import import_module

        result = import_module("lfx.components.files_and_knowledge.file")
        globals()[attr_name] = result
        return result
    # Data source components were moved to data_source
    if attr_name == "news_search":
        from importlib import import_module

        result = import_module("lfx.components.data_source.news_search")
        globals()[attr_name] = result
        return result
    if attr_name == "rss":
        from importlib import import_module

        result = import_module("lfx.components.data_source.rss")
        globals()[attr_name] = result
        return result
    if attr_name == "web_search":
        from importlib import import_module

        result = import_module("lfx.components.data_source.web_search")
        globals()[attr_name] = result
        return result
    # SQLComponent was moved to utilities
    if attr_name == "sql_executor":
        from importlib import import_module

        result = import_module("lfx.components.utilities.sql_executor")
        globals()[attr_name] = result
        return result

    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)

    mapping = _dynamic_imports[attr_name]

    # Handle FileComponent and DirectoryComponent which are in files_and_knowledge
    if isinstance(mapping, tuple):
        module_name, package = mapping
        try:
            result = import_mod(attr_name, module_name, f"lfx.components.{package}")
        except (ModuleNotFoundError, ImportError, AttributeError) as e:
            msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
            raise AttributeError(msg) from e
    else:
        # Import from data_source using the correct package path
        package = "lfx.components.data_source"
        try:
            result = import_mod(attr_name, mapping, package)
        except (ModuleNotFoundError, ImportError, AttributeError) as e:
            msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
            raise AttributeError(msg) from e

    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    """Return directory of available components."""
    return list(__all__)
