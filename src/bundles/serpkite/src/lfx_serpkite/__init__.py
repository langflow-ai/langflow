"""lfx-serpkite: SerpKite Search bundle.

This package is the distribution unit ``lfx-serpkite``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``SerpKiteSearchComponent`` under the
namespaced ID ``ext:serpkite:SerpKiteSearchComponent@official``.

SerpKite (https://serpkite.com) is a Google SERP API; the component
calls its search endpoint directly with ``httpx`` and needs only a
user-supplied API key, so the bundle carries no vendor SDK dependency.
"""

from lfx_serpkite.components.serpkite.serpkite_search import SerpKiteSearchComponent

__all__ = ["SerpKiteSearchComponent"]
