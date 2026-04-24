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
from lfx.base.knowledge_bases.ingestion_sources.connector_base import (
    KBConnectorSource,
    OAuthConnectorBase,
)
from lfx.base.knowledge_bases.ingestion_sources.file_upload import FileUploadSource
from lfx.base.knowledge_bases.ingestion_sources.folder import FolderSource
from lfx.base.knowledge_bases.ingestion_sources.google_drive import GoogleDriveSource
from lfx.base.knowledge_bases.ingestion_sources.microsoft_graph import (
    MicrosoftGraphSource,
)
from lfx.base.knowledge_bases.ingestion_sources.onedrive import OneDriveSource
from lfx.base.knowledge_bases.ingestion_sources.registry import (
    create_source,
    get_source_class,
    register_source,
    registered_sources,
)
from lfx.base.knowledge_bases.ingestion_sources.s3 import S3Source
from lfx.base.knowledge_bases.ingestion_sources.sharepoint import SharePointSource

# Register built-in sources on import.
register_source(SourceType.FILE_UPLOAD, FileUploadSource)
register_source(SourceType.FOLDER, FolderSource)
register_source(SourceType.S3, S3Source)
register_source(SourceType.GOOGLE_DRIVE, GoogleDriveSource)
register_source(SourceType.ONEDRIVE, OneDriveSource)
register_source(SourceType.SHAREPOINT, SharePointSource)

__all__ = [
    "FileUploadSource",
    "FolderSource",
    "GoogleDriveSource",
    "IngestionItem",
    "IngestionItemContent",
    "IngestionItemResult",
    "IngestionItemStatus",
    "IngestionSummary",
    "KBConnectorSource",
    "KBIngestionSource",
    "MicrosoftGraphSource",
    "OAuthConnectorBase",
    "OneDriveSource",
    "S3Source",
    "SharePointSource",
    "SourceType",
    "create_source",
    "get_source_class",
    "register_source",
    "registered_sources",
]
