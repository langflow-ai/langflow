"""lfx-wolframalpha: WolframAlpha bundle.

Distribution unit ``lfx-wolframalpha``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:wolframalpha:<Class>@official``.
"""

from lfx_wolframalpha.components.wolframalpha.wolfram_alpha_api import WolframAlphaAPIComponent

__all__ = [
    "WolframAlphaAPIComponent",
]
