"""lfx-docling: Docling bundle.

Distribution unit ``lfx-docling``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:docling:<Class>@official``.
"""

from lfx_docling.components.docling.chunk_docling_document import ChunkDoclingDocumentComponent
from lfx_docling.components.docling.docling_inline import DoclingInlineComponent
from lfx_docling.components.docling.docling_remote import DoclingRemoteComponent
from lfx_docling.components.docling.export_docling_document import ExportDoclingDocumentComponent

__all__ = [
    "ChunkDoclingDocumentComponent",
    "DoclingInlineComponent",
    "DoclingRemoteComponent",
    "ExportDoclingDocumentComponent",
]
