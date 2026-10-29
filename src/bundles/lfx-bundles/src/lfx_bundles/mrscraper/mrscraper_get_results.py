"""MrScraper Get Results, retired in Langflow 1.13.0."""

from lfx.base.mrscraper.retired import MrscraperGetResults as RetiredMrscraperGetResultsComponent


class MrscraperGetResults(RetiredMrscraperGetResultsComponent):
    """Keep bundle discovery and the saved-node identity of the retired component."""


__all__ = ["MrscraperGetResults"]
