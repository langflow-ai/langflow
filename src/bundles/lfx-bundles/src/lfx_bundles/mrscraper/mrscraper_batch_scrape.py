"""MrScraper Batch Scrape URLs, retired in Langflow 1.13.0."""

from lfx.base.mrscraper.retired import MrscraperBatchScrape as RetiredMrscraperBatchScrapeComponent


class MrscraperBatchScrape(RetiredMrscraperBatchScrapeComponent):
    """Keep bundle discovery and the saved-node identity of the retired component."""


__all__ = ["MrscraperBatchScrape"]
