from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.data_source.api_request import APIRequestComponent
    from lfx.components.data_source.csv_to_data import CSVToDataComponent
    from lfx.components.data_source.json_to_data import JSONToDataComponent
    from lfx.components.data_source.mock_data import MockDataGeneratorComponent
    from lfx.components.data_source.news_search import NewsSearchComponent
    from lfx.components.data_source.rss import RSSReaderComponent
    from lfx.components.data_source.url import URLComponent
    from lfx.components.data_source.web_search import WebSearchComponent

_dynamic_imports = {
    "APIRequestComponent": "api_request",
    "CSVToDataComponent": "csv_to_data",
    "JSONToDataComponent": "json_to_data",
    "MockDataGeneratorComponent": "mock_data",
    "NewsSearchComponent": "news_search",
    "RSSReaderComponent": "rss",
    "URLComponent": "url",
    "WebSearchComponent": "web_search",
}

__all__ = [
    "APIRequestComponent",
    "CSVToDataComponent",
    "JSONToDataComponent",
    "MockDataGeneratorComponent",
    "NewsSearchComponent",
    "RSSReaderComponent",
    "URLComponent",
    "WebSearchComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import data source components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
