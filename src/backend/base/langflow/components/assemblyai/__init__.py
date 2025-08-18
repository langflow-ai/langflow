from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from .assemblyai_get_subtitles import AssemblyAIGetSubtitles
    from .assemblyai_lemur import AssemblyAILeMUR
    from .assemblyai_list_transcripts import AssemblyAIListTranscripts
    from .assemblyai_poll_transcript import AssemblyAITranscriptionJobPoller
    from .assemblyai_start_transcript import AssemblyAITranscriptionJobCreator

_dynamic_imports = {
    "AssemblyAIGetSubtitles": "assemblyai_get_subtitles",
    "AssemblyAILeMUR": "assemblyai_lemur",
    "AssemblyAIListTranscripts": "assemblyai_list_transcripts",
    "AssemblyAITranscriptionJobCreator": "assemblyai_start_transcript",
    "AssemblyAITranscriptionJobPoller": "assemblyai_poll_transcript",
}

__all__ = [
    "AssemblyAIGetSubtitles",
    "AssemblyAILeMUR",
    "AssemblyAIListTranscripts",
    "AssemblyAITranscriptionJobCreator",
    "AssemblyAITranscriptionJobPoller",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import assemblyai components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
