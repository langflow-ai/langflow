"""lfx-groq: Groq bundle.

Distribution unit ``lfx-groq``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:groq:<Class>@official``.
"""

from lfx_groq.components.groq.groq import GroqModel

__all__ = [
    "GroqModel",
]
