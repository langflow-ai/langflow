"""lfx-specstream: SpecStream bundle.

This package is the distribution unit ``lfx-specstream``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``SpecStreamFindListComponent`` under the
namespaced ID ``ext:specstream:SpecStreamFindListComponent@official``.

SpecStream (https://specstream.ai) returns structured rows for a request
written in plain words.  The component calls its HTTP API directly with
``httpx`` and needs only a user-supplied API key, so the bundle carries no
vendor SDK dependency.
"""

from lfx_specstream.components.specstream.find_list import SpecStreamFindListComponent

__all__ = ["SpecStreamFindListComponent"]
