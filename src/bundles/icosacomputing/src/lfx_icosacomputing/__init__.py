"""lfx-icosacomputing: Icosacomputing bundle.

Distribution unit ``lfx-icosacomputing``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:icosacomputing:<Class>@official``.
"""

from lfx_icosacomputing.components.icosacomputing.combinatorial_reasoner import CombinatorialReasonerComponent

__all__ = [
    "CombinatorialReasonerComponent",
]
