"""lfx-maritalk: Maritalk bundle.

Distribution unit ``lfx-maritalk``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:maritalk:<Class>@official``.
"""

from lfx_maritalk.components.maritalk.maritalk import MaritalkModelComponent

__all__ = [
    "MaritalkModelComponent",
]
