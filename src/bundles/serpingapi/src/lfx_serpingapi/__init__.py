"""lfx-serpingapi: Serping API Search bundle.

This package is the distribution unit ``lfx-serpingapi``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``SerpingApiSearchComponent`` under the
namespaced ID ``ext:serpingapi:SerpingApiSearchComponent@official``.

Serping API (https://serpingapi.com) is a Google SERP API; the component
calls its search endpoint directly with ``httpx`` and needs only a
user-supplied API key, so the bundle carries no vendor SDK dependency.
"""

from lfx_serpingapi.components.serpingapi.serpingapi_search import SerpingApiSearchComponent

__all__ = ["SerpingApiSearchComponent"]
