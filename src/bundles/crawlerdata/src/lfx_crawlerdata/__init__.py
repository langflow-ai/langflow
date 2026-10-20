"""lfx-crawlerdata: CrawlerData Search bundle.

This package is the distribution unit ``lfx-crawlerdata``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``CrawlerDataSearchComponent`` under the
namespaced ID ``ext:crawlerdata:CrawlerDataSearchComponent@official``.

CrawlerData (https://crawlerdata.com) is a Google Search (SERP) API; the
component calls its jobs endpoint directly with ``httpx`` and needs only a
user-supplied API key, so the bundle carries no vendor SDK dependency.
"""

from lfx_crawlerdata.components.crawlerdata.crawlerdata_search import CrawlerDataSearchComponent

__all__ = ["CrawlerDataSearchComponent"]
