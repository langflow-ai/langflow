"""lfx-novita: Novita bundle.

Distribution unit ``lfx-novita``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:novita:<Class>@official``.
"""

from lfx_novita.components.novita.novita import NovitaModelComponent

__all__ = [
    "NovitaModelComponent",
]
