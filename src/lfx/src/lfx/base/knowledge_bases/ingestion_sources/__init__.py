"""Ingestion-source abstraction for Knowledge Bases.

Ingestion sources supply items to ``KBIngestionHelper.perform_ingestion``.
The same helper handles chunking, embedding, and vector-store writes
regardless of where the items came from — file upload, local folder
walk, or a future cloud connector (Google Drive, S3, OneDrive,
SharePoint).

Public surface:

* ``KBIngestionSource`` — base class every source subclasses.
* ``IngestionItem`` / ``IngestionItemContent`` — per-item metadata and
  fetched bytes.
* ``IngestionSummary`` — aggregate outcome of a run (counts, bytes,
  errors) persisted in the ``ingestion_run`` DB table.
* ``SourceType`` — the canonical source-type identifier enum.
* ``register_source`` / ``create_source`` / ``registered_sources`` —
  the registry entry points.

Built-in sources (``FileUploadSource``, ``FolderSource``) register on
import so call sites don't have to remember to import them separately.
"""

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    IngestionItemResult,
    IngestionItemStatus,
    IngestionSummary,
    KBIngestionSource,
    SourceType,
)
from lfx.base.knowledge_bases.ingestion_sources.file_upload import FileUploadSource
from lfx.base.knowledge_bases.ingestion_sources.folder import FolderSource
from lfx.base.knowledge_bases.ingestion_sources.registry import (
    create_source,
    get_source_class,
    register_source,
    registered_sources,
)

# Register built-in sources on import.
register_source(SourceType.FILE_UPLOAD, FileUploadSource)
register_source(SourceType.FOLDER, FolderSource)

__all__ = [
    "FileUploadSource",
    "FolderSource",
    "IngestionItem",
    "IngestionItemContent",
    "IngestionItemResult",
    "IngestionItemStatus",
    "IngestionSummary",
    "KBIngestionSource",
    "SourceType",
    "create_source",
    "get_source_class",
    "register_source",
    "registered_sources",
]
