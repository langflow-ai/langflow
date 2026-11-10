from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from .genmagic_image_generation import GenMagicImageGenerationComponent
    from .genmagic_model import GenMagicModelComponent
    from .genmagic_text_to_speech import GenMagicTextToSpeechComponent
    from .genmagic_video_generation import GenMagicVideoGenerationComponent
    from .genmagic_video_status import GenMagicVideoStatusComponent

_dynamic_imports = {
    "GenMagicImageGenerationComponent": "genmagic_image_generation",
    "GenMagicModelComponent": "genmagic_model",
    "GenMagicTextToSpeechComponent": "genmagic_text_to_speech",
    "GenMagicVideoGenerationComponent": "genmagic_video_generation",
    "GenMagicVideoStatusComponent": "genmagic_video_status",
}

__all__ = [
    "GenMagicImageGenerationComponent",
    "GenMagicModelComponent",
    "GenMagicTextToSpeechComponent",
    "GenMagicVideoGenerationComponent",
    "GenMagicVideoStatusComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import GenMagic components on attribute access."""
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
    """List the lazily imported names, so ``dir()`` and autocompletion show the components."""
    return list(__all__)
