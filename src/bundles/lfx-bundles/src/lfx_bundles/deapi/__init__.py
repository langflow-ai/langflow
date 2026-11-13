from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from .deapi_image_generation import DeapiImageGenerationComponent
    from .deapi_text_to_speech import DeapiTextToSpeechComponent
    from .deapi_transcription import DeapiTranscriptionComponent
    from .deapi_video_generation import DeapiVideoGenerationComponent

_dynamic_imports = {
    "DeapiImageGenerationComponent": "deapi_image_generation",
    "DeapiTextToSpeechComponent": "deapi_text_to_speech",
    "DeapiTranscriptionComponent": "deapi_transcription",
    "DeapiVideoGenerationComponent": "deapi_video_generation",
}

__all__ = [
    "DeapiImageGenerationComponent",
    "DeapiTextToSpeechComponent",
    "DeapiTranscriptionComponent",
    "DeapiVideoGenerationComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import deAPI components on attribute access."""
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
