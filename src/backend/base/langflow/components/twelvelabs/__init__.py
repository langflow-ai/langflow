from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from .convert_astra_results import ConvertAstraToTwelveLabs
    from .pegasus_index import PegasusIndexVideo
    from .split_video import SplitVideoComponent
    from .text_embeddings import TwelveLabsTextEmbeddingsComponent
    from .twelvelabs_pegasus import TwelveLabsPegasus
    from .video_embeddings import TwelveLabsVideoEmbeddingsComponent
    from .video_file import VideoFileComponent

_dynamic_imports = {
    "ConvertAstraToTwelveLabs": "convert_astra_results",
    "PegasusIndexVideo": "pegasus_index",
    "SplitVideoComponent": "split_video",
    "TwelveLabsPegasus": "twelvelabs_pegasus",
    "TwelveLabsTextEmbeddingsComponent": "text_embeddings",
    "TwelveLabsVideoEmbeddingsComponent": "video_embeddings",
    "VideoFileComponent": "video_file",
}

__all__ = [
    "ConvertAstraToTwelveLabs",
    "PegasusIndexVideo",
    "SplitVideoComponent",
    "TwelveLabsPegasus",
    "TwelveLabsTextEmbeddingsComponent",
    "TwelveLabsVideoEmbeddingsComponent",
    "VideoFileComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import twelvelabs components on attribute access."""
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
