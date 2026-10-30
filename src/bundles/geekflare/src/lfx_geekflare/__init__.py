"""lfx-geekflare: Geekflare bundle.

This package is the distribution unit ``lfx-geekflare``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers the components under namespaced IDs such as
``ext:geekflare:GeekflareSearchComponent@official``.

Geekflare (https://geekflare.com) provides web search (including the full
Google results page), page scraping, and website diagnostics APIs; the
components call them directly with ``httpx`` and need only a user-supplied
API key, so the bundle carries no vendor SDK dependency.
"""

from lfx_geekflare.components.geekflare import (
    GeekflareScrapeComponent,
    GeekflareSearchComponent,
    GeekflareWebsiteCheckComponent,
)

__all__ = ["GeekflareScrapeComponent", "GeekflareSearchComponent", "GeekflareWebsiteCheckComponent"]
