"""lfx-exa: Exa Search bundle.

This package is the distribution unit ``lfx-exa``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers ``ExaSearchToolkit`` under the namespaced
ID ``ext:exa:ExaSearchToolkit@official``.

Graduated out of the manifest-less ``lfx-bundles`` metapackage when the
component was modernized onto the ``exa-py`` SDK (the metapackage copy
still used the deprecated ``metaphor-python`` client).  The bundle name
(``exa``) and class name are unchanged, so the canonical component ID --
and every migration-table entry pointing at it -- is stable across the
move.
"""

from lfx_exa.components.exa.exa_search import ExaSearchToolkit

__all__ = ["ExaSearchToolkit"]
