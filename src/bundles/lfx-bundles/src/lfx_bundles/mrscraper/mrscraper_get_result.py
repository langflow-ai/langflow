"""MrScraper Get Result Detail, retired in Langflow 1.13.0."""

from lfx.base.mrscraper.retired import MrscraperGetResult as RetiredMrscraperGetResultComponent


class MrscraperGetResult(RetiredMrscraperGetResultComponent):
    """Keep bundle discovery and the saved-node identity of the retired component."""


__all__ = ["MrscraperGetResult"]
