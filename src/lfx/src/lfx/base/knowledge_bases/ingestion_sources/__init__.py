"""Ingestion-source abstraction for Knowledge Bases.

Ingestion sources supply items to ``KBIngestionHelper.perform_ingestion``.
The same helper handles chunking, embedding, and vector-store writes
regardless of where the items came from — file upload, local folder
walk, or a future cloud connector.

Public surface:

* ``KBIngestionSource`` — base class every source subclasses.
* ``IngestionItem`` / ``IngestionItemContent`` — per-item metadata and
  fetched bytes.
* ``IngestionSummary`` — aggregate outcome of a run (counts, bytes,
  errors) persisted in the ``ingestion_run`` DB table.
* ``SourceType`` — the canonical source-type identifier enum.
* ``register_source`` / ``create_source`` / ``registered_sources`` —
  the registry entry points.

In this phase only **file_upload** and **folder** are registered. The
S3 / Google Drive / OneDrive / SharePoint classes are preserved as
stubs so the framework wiring (enum values, type imports, DB-stored
``source_type`` strings on existing ``ingestion_run`` rows) keeps
round-tripping, but they are not instantiable through ``create_source``
and the picker UI hides them. Reinstate by restoring the full source
class and re-adding ``register_source(...)`` for that source below.
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
    registered_source_keys,
    registered_sources,
)
from lfx.base.knowledge_bases.ingestion_sources.s3 import S3Source
from lfx.base.knowledge_bases.ingestion_sources.sharepoint import SharePointSource

# Register the supported built-in sources on import. S3Source /
# GoogleDriveSource / OneDriveSource / SharePointSource are intentionally
# NOT registered while they're stubbed out — see each module's docstring.
register_source(SourceType.FILE_UPLOAD, FileUploadSource)
register_source(SourceType.FOLDER, FolderSource)

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
    "registered_source_keys",
    "registered_sources",
]
