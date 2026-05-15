"""lfx-vlmrun: Vlmrun bundle.

Distribution unit ``lfx-vlmrun``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:vlmrun:<Class>@official``.
"""

from lfx_vlmrun.components.vlmrun.vlmrun_transcription import VLMRunTranscription

__all__ = [
    "VLMRunTranscription",
]
