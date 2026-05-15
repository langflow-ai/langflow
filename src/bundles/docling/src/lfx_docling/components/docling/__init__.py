"""Lazy component re-exports for the ``docling`` bundle.

Mirrors the pre-extraction layout of ``lfx.components.docling`` so saved
flows that referenced the module-level class
(e.g. ``lfx.components.docling.<Class>``) keep resolving via the
migration table after rewrite to
``lfx_docling.components.docling.<Class>``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .chunk_docling_document import ChunkDoclingDocumentComponent
    from .docling_inline import DoclingInlineComponent
    from .docling_remote import DoclingRemoteComponent
    from .export_docling_document import ExportDoclingDocumentComponent

_dynamic_imports = {
    "ChunkDoclingDocumentComponent": "chunk_docling_document",
    "DoclingInlineComponent": "docling_inline",
    "DoclingRemoteComponent": "docling_remote",
    "ExportDoclingDocumentComponent": "export_docling_document",
}

__all__ = [
    "ChunkDoclingDocumentComponent",
    "DoclingInlineComponent",
    "DoclingRemoteComponent",
    "ExportDoclingDocumentComponent",
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
