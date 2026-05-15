"""lfx-wikipedia: Wikipedia bundle.

Distribution unit ``lfx-wikipedia``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:wikipedia:<Class>@official``.
"""

from lfx_wikipedia.components.wikipedia.wikidata import WikidataComponent
from lfx_wikipedia.components.wikipedia.wikipedia import WikipediaComponent

__all__ = [
    "WikidataComponent",
    "WikipediaComponent",
]
