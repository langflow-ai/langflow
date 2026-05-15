"""Lazy component re-exports for the ``twelvelabs`` bundle.

Mirrors the pre-extraction layout of ``lfx.components.twelvelabs`` so saved
flows that referenced the module-level class
(e.g. ``lfx.components.twelvelabs.<Class>``) keep resolving via the
migration table after rewrite to
``lfx_twelvelabs.components.twelvelabs.<Class>``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .convert_astra_results import ConvertAstraToTwelveLabs
    from .pegasus_index import IndexCreationError, PegasusIndexVideo, TaskError, TaskTimeoutError
    from .split_video import SplitVideoComponent
    from .text_embeddings import TwelveLabsTextEmbeddings, TwelveLabsTextEmbeddingsComponent
    from .twelvelabs_pegasus import TwelveLabsPegasus
    from .video_embeddings import TwelveLabsVideoEmbeddings, TwelveLabsVideoEmbeddingsComponent
    from .video_file import VideoFileComponent

_dynamic_imports = {
    "ConvertAstraToTwelveLabs": "convert_astra_results",
    "IndexCreationError": "pegasus_index",
    "PegasusIndexVideo": "pegasus_index",
    "SplitVideoComponent": "split_video",
    "TaskError": "pegasus_index",
    "TaskTimeoutError": "pegasus_index",
    "TwelveLabsPegasus": "twelvelabs_pegasus",
    "TwelveLabsTextEmbeddings": "text_embeddings",
    "TwelveLabsTextEmbeddingsComponent": "text_embeddings",
    "TwelveLabsVideoEmbeddings": "video_embeddings",
    "TwelveLabsVideoEmbeddingsComponent": "video_embeddings",
    "VideoFileComponent": "video_file",
}

__all__ = [
    "ConvertAstraToTwelveLabs",
    "IndexCreationError",
    "PegasusIndexVideo",
    "SplitVideoComponent",
    "TaskError",
    "TaskTimeoutError",
    "TwelveLabsPegasus",
    "TwelveLabsTextEmbeddings",
    "TwelveLabsTextEmbeddingsComponent",
    "TwelveLabsVideoEmbeddings",
    "TwelveLabsVideoEmbeddingsComponent",
    "VideoFileComponent",
]


def __getattr__(attr_name: str) -> Any:
    if attr_name not in _dynamic_imports:
        msg = f"module {__name__!r} has no attribute {attr_name!r}"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import {attr_name!r} from {__name__!r}: {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
