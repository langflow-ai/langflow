"""lfx-notdiamond: Notdiamond bundle.

Distribution unit ``lfx-notdiamond``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:notdiamond:<Class>@official``.
"""

from lfx_notdiamond.components.notdiamond.notdiamond import NotDiamondComponent

__all__ = [
    "NotDiamondComponent",
]
