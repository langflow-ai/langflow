"""lfx-desearch: Desearch search bundle.

This package is the distribution unit ``lfx-desearch``.  At runtime Langflow's
loader discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the Desearch components under namespaced IDs such as
``ext:desearch:DesearchWebSearchComponent@official``.

Desearch (https://desearch.ai) offers web search, AI search and X search over
one API key; the components call the Desearch REST API directly with ``httpx``,
so the bundle carries no vendor SDK dependency.
"""

from lfx_desearch.components.desearch import (
    DesearchAISearchComponent,
    DesearchWebSearchComponent,
    DesearchXSearchComponent,
)

__all__ = ["DesearchAISearchComponent", "DesearchWebSearchComponent", "DesearchXSearchComponent"]
