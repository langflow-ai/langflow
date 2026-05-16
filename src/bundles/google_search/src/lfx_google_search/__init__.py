"""lfx-google-search: Google Search bundle.

Distribution unit ``lfx-google-search``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:google_search:<Class>@official``.

Part of the Google split: 9 components from the in-tree ``google/``
directory were partitioned across 4 lfx-google-* bundles by audience
(GenAI / Workspace / BigQuery / Search).
"""

from lfx_google_search.components.google_search.google_search_api_core import GoogleSearchAPICore
from lfx_google_search.components.google_search.google_serper_api_core import GoogleSerperAPICore

__all__ = [
    "GoogleSearchAPICore",
    "GoogleSerperAPICore",
]
