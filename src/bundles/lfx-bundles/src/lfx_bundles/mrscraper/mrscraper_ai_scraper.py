"""MrScraper AI Agent Scraper, retired in Langflow 1.13.0."""

from lfx.base.mrscraper.retired import MrscraperAiScraper as RetiredMrscraperAiScraperComponent


class MrscraperAiScraper(RetiredMrscraperAiScraperComponent):
    """Keep bundle discovery and the saved-node identity of the retired component."""


__all__ = ["MrscraperAiScraper"]
