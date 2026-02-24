from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .camb_audio_separation import CambAudioSeparationComponent
    from .camb_text_to_sound import CambTextToSoundComponent
    from .camb_transcribe import CambTranscribeComponent
    from .camb_translate import CambTranslateComponent
    from .camb_translated_tts import CambTranslatedTTSComponent
    from .camb_tts import CambTTSComponent
    from .camb_voice_clone import CambVoiceCloneComponent
    from .camb_voice_list import CambVoiceListComponent

_dynamic_imports = {
    "CambAudioSeparationComponent": "camb_audio_separation",
    "CambTextToSoundComponent": "camb_text_to_sound",
    "CambTranscribeComponent": "camb_transcribe",
    "CambTranslateComponent": "camb_translate",
    "CambTranslatedTTSComponent": "camb_translated_tts",
    "CambTTSComponent": "camb_tts",
    "CambVoiceCloneComponent": "camb_voice_clone",
    "CambVoiceListComponent": "camb_voice_list",
}

__all__ = [
    "CambAudioSeparationComponent",
    "CambTextToSoundComponent",
    "CambTranscribeComponent",
    "CambTranslateComponent",
    "CambTranslatedTTSComponent",
    "CambTTSComponent",
    "CambVoiceCloneComponent",
    "CambVoiceListComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import CAMB AI components on attribute access."""
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
