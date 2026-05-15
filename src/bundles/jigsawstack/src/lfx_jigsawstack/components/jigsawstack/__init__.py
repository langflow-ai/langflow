"""Lazy component re-exports for the ``jigsawstack`` bundle.

Mirrors the pre-extraction layout of ``lfx.components.jigsawstack`` so saved
flows that referenced the module-level class
(e.g. ``lfx.components.jigsawstack.<Class>``) keep resolving via the
migration table after rewrite to
``lfx_jigsawstack.components.jigsawstack.<Class>``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .ai_scrape import JigsawStackAIScraperComponent
    from .ai_web_search import JigsawStackAIWebSearchComponent
    from .file_read import JigsawStackFileReadComponent
    from .file_upload import JigsawStackFileUploadComponent
    from .image_generation import JigsawStackImageGenerationComponent
    from .nsfw import JigsawStackNSFWComponent
    from .object_detection import JigsawStackObjectDetectionComponent
    from .sentiment import JigsawStackSentimentComponent
    from .text_to_sql import JigsawStackTextToSQLComponent
    from .text_translate import JigsawStackTextTranslateComponent
    from .vocr import JigsawStackVOCRComponent

_dynamic_imports = {
    "JigsawStackAIScraperComponent": "ai_scrape",
    "JigsawStackAIWebSearchComponent": "ai_web_search",
    "JigsawStackFileReadComponent": "file_read",
    "JigsawStackFileUploadComponent": "file_upload",
    "JigsawStackImageGenerationComponent": "image_generation",
    "JigsawStackNSFWComponent": "nsfw",
    "JigsawStackObjectDetectionComponent": "object_detection",
    "JigsawStackSentimentComponent": "sentiment",
    "JigsawStackTextToSQLComponent": "text_to_sql",
    "JigsawStackTextTranslateComponent": "text_translate",
    "JigsawStackVOCRComponent": "vocr",
}

__all__ = [
    "JigsawStackAIScraperComponent",
    "JigsawStackAIWebSearchComponent",
    "JigsawStackFileReadComponent",
    "JigsawStackFileUploadComponent",
    "JigsawStackImageGenerationComponent",
    "JigsawStackNSFWComponent",
    "JigsawStackObjectDetectionComponent",
    "JigsawStackSentimentComponent",
    "JigsawStackTextToSQLComponent",
    "JigsawStackTextTranslateComponent",
    "JigsawStackVOCRComponent",
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
