from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from .context_crawl import ContextCrawlWebsiteComponent
    from .context_extract import ContextExtractStructuredDataComponent
    from .context_news import ContextSearchNewsComponent
    from .context_retrieve_brand import ContextRetrieveBrandComponent
    from .context_scrape import ContextScrapeMarkdownComponent
    from .context_search import ContextSearchWebComponent

_dynamic_imports = {
    "ContextCrawlWebsiteComponent": "context_crawl",
    "ContextExtractStructuredDataComponent": "context_extract",
    "ContextRetrieveBrandComponent": "context_retrieve_brand",
    "ContextScrapeMarkdownComponent": "context_scrape",
    "ContextSearchNewsComponent": "context_news",
    "ContextSearchWebComponent": "context_search",
}

__all__ = [
    "ContextCrawlWebsiteComponent",
    "ContextExtractStructuredDataComponent",
    "ContextRetrieveBrandComponent",
    "ContextScrapeMarkdownComponent",
    "ContextSearchNewsComponent",
    "ContextSearchWebComponent",
]


def __getattr__(attr_name: str) -> Any:
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as exc:
        msg = f"Could not import '{attr_name}' from '{__name__}': {exc}"
        raise AttributeError(msg) from exc
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
