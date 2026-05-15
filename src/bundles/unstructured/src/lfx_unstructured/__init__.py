"""lfx-unstructured: Unstructured bundle.

Distribution unit ``lfx-unstructured``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:unstructured:<Class>@official``.
"""

from lfx_unstructured.components.unstructured.unstructured import UnstructuredComponent

__all__ = [
    "UnstructuredComponent",
]
