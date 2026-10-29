"""lfx-bowmark: Bowmark bundle.

This package is the distribution unit ``lfx-bowmark``.  At runtime Langflow's
loader discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers ``BowmarkLibraryComponent`` and ``BowmarkRunComponent`` under the
namespaced IDs ``ext:bowmark:<ClassName>@official``.

Bowmark (https://bowmark.ai) runs tasks on live websites and returns typed
results.  The components call its HTTP API (``/v1/library`` and ``/v1/run``)
directly with ``httpx`` and need only a user-supplied API key, so the bundle
carries no vendor SDK dependency.
"""

from lfx_bowmark.components.bowmark.bowmark_library import BowmarkLibraryComponent
from lfx_bowmark.components.bowmark.bowmark_run import BowmarkRunComponent

__all__ = ["BowmarkLibraryComponent", "BowmarkRunComponent"]
