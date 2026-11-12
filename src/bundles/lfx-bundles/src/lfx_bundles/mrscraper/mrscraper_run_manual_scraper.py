"""MrScraper Run Manual Scraper, retired in Langflow 1.13.0."""

from lfx.base.mrscraper.retired import MrscraperRunManualScraper as RetiredMrscraperRunManualScraperComponent


class MrscraperRunManualScraper(RetiredMrscraperRunManualScraperComponent):
    """Keep bundle discovery and the saved-node identity of the retired component."""


__all__ = ["MrscraperRunManualScraper"]
