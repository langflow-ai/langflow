from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from .mrscraper_account import MrscraperAccount
    from .mrscraper_ai_scraper import MrscraperAiScraper
    from .mrscraper_batch_scrape import MrscraperBatchScrape
    from .mrscraper_crawl_website import MrscraperCrawlWebsite
    from .mrscraper_fetch_html import MrscraperFetchHtml
    from .mrscraper_get_result import MrscraperGetResult
    from .mrscraper_get_results import MrscraperGetResults
    from .mrscraper_run_ai_scraper import MrscraperRunAiScraper
    from .mrscraper_run_manual_scraper import MrscraperRunManualScraper
    from .mrscraper_web_search import MrscraperWebSearch

# The AI, crawl, batch, rerun and result components were retired in 1.13.0. They stay
# importable so saved nodes report their replacement instead of failing to load.
_dynamic_imports = {
    "MrscraperAccount": "mrscraper_account",
    "MrscraperAiScraper": "mrscraper_ai_scraper",
    "MrscraperBatchScrape": "mrscraper_batch_scrape",
    "MrscraperCrawlWebsite": "mrscraper_crawl_website",
    "MrscraperFetchHtml": "mrscraper_fetch_html",
    "MrscraperGetResult": "mrscraper_get_result",
    "MrscraperGetResults": "mrscraper_get_results",
    "MrscraperRunAiScraper": "mrscraper_run_ai_scraper",
    "MrscraperRunManualScraper": "mrscraper_run_manual_scraper",
    "MrscraperWebSearch": "mrscraper_web_search",
}

__all__ = [
    "MrscraperAccount",
    "MrscraperAiScraper",
    "MrscraperBatchScrape",
    "MrscraperCrawlWebsite",
    "MrscraperFetchHtml",
    "MrscraperGetResult",
    "MrscraperGetResults",
    "MrscraperRunAiScraper",
    "MrscraperRunManualScraper",
    "MrscraperWebSearch",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import MrScraper components on attribute access."""
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
