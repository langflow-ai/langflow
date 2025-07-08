from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from .firecrawl_crawl_api import FirecrawlCrawlApi
    from .firecrawl_extract_api import FirecrawlExtractApi
    from .firecrawl_map_api import FirecrawlMapApi
    from .firecrawl_scrape_api import FirecrawlScrapeApi

_dynamic_imports = {
    "FirecrawlCrawlApi": "firecrawl_crawl_api",
    "FirecrawlExtractApi": "firecrawl_extract_api",
    "FirecrawlMapApi": "firecrawl_map_api",
    "FirecrawlScrapeApi": "firecrawl_scrape_api",
}

__all__ = [
    "FirecrawlCrawlApi",
    "FirecrawlExtractApi",
    "FirecrawlMapApi",
    "FirecrawlScrapeApi",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import firecrawl components on attribute access."""
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
