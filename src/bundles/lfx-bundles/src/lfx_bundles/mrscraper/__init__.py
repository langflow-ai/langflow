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
    from .mrscraper_get_screenshot import MrscraperGetScreenshot
    from .mrscraper_run_ai_scraper import MrscraperRunAiScraper
    from .mrscraper_run_manual_scraper import MrscraperRunManualScraper
    from .mrscraper_scrape_brand import MrscraperScrapeBrand
    from .mrscraper_scrape_json import MrscraperScrapeJson
    from .mrscraper_scrape_markdown import MrscraperScrapeMarkdown
    from .mrscraper_web_search import MrscraperWebSearch

# The seven services, plus the placeholders that keep components retired in
# 1.13.0 discoverable so their saved nodes still load.
_dynamic_imports = {
    "MrscraperAccount": "mrscraper_account",
    "MrscraperAiScraper": "mrscraper_ai_scraper",
    "MrscraperBatchScrape": "mrscraper_batch_scrape",
    "MrscraperCrawlWebsite": "mrscraper_crawl_website",
    "MrscraperFetchHtml": "mrscraper_fetch_html",
    "MrscraperGetResult": "mrscraper_get_result",
    "MrscraperGetResults": "mrscraper_get_results",
    "MrscraperGetScreenshot": "mrscraper_get_screenshot",
    "MrscraperRunAiScraper": "mrscraper_run_ai_scraper",
    "MrscraperRunManualScraper": "mrscraper_run_manual_scraper",
    "MrscraperScrapeBrand": "mrscraper_scrape_brand",
    "MrscraperScrapeJson": "mrscraper_scrape_json",
    "MrscraperScrapeMarkdown": "mrscraper_scrape_markdown",
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
    "MrscraperGetScreenshot",
    "MrscraperRunAiScraper",
    "MrscraperRunManualScraper",
    "MrscraperScrapeBrand",
    "MrscraperScrapeJson",
    "MrscraperScrapeMarkdown",
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
