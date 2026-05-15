"""lfx-serpapi: SerpAPI bundle.

Distribution unit ``lfx-serpapi``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:serpapi:<Class>@official``.
"""

from lfx_serpapi.components.serpapi.serp import SerpAPISchema, SerpComponent

__all__ = [
    "SerpAPISchema",
    "SerpComponent",
]
