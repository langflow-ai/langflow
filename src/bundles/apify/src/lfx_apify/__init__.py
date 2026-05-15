"""lfx-apify: Apify bundle.

Distribution unit ``lfx-apify``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:apify:<Class>@official``.
"""

from lfx_apify.components.apify.apify_actor import ApifyActorsComponent

__all__ = [
    "ApifyActorsComponent",
]
