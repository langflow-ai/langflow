"""lfx-langwatch: Langwatch bundle.

Distribution unit ``lfx-langwatch``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:langwatch:<Class>@official``.
"""

from lfx_langwatch.components.langwatch.langwatch import LangWatchComponent

__all__ = [
    "LangWatchComponent",
]
