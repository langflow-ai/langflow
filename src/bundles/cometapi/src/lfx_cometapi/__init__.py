"""lfx-cometapi: Cometapi bundle.

Distribution unit ``lfx-cometapi``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:cometapi:<Class>@official``.
"""

from lfx_cometapi.components.cometapi.cometapi import CometAPIComponent

__all__ = [
    "CometAPIComponent",
]
