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

In this phase only **file_upload** and **folder** are registered by
default. The S3 / OneDrive / SharePoint classes are preserved as stubs
so the framework wiring (enum values, type imports, DB-stored
``source_type`` strings on existing ``ingestion_run`` rows) keeps
round-tripping, but they are not instantiable through ``create_source``
and the picker UI hides them. Reinstate by restoring the full source
class and re-adding ``register_source(...)`` for that source below.

``GoogleDriveSource`` is implemented (INT-10) but stays **opt-in** until
INT-6 lands. It resolves a managed connection under a ``job_owner``
execution principal, and nothing in langflow-base stamps an execution
principal on a background job yet, so on a build without INT-6 every
resolution fails closed with ``connection-not-authorized`` — registering
it would only put a broken entry in the connector picker. Set
``LANGFLOW_KB_GOOGLE_DRIVE_ENABLED=true`` to register it anyway; once
INT-6 has merged, delete the switch and register it unconditionally.
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
# OneDriveSource / SharePointSource are intentionally NOT registered while
# they're stubbed out — see each module's docstring.
register_source(SourceType.FILE_UPLOAD, FileUploadSource)
register_source(SourceType.FOLDER, FolderSource)

GOOGLE_DRIVE_ENABLED_ENV_VAR = "LANGFLOW_KB_GOOGLE_DRIVE_ENABLED"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def google_drive_source_enabled() -> bool:
    """Return True when the operator opted the Drive source in.

    Temporary switch: the source needs INT-6's execution-principal stamping to
    resolve a connection from a background job. Remove this function and
    register the source unconditionally once INT-6 has merged.
    """
    # os.getenv, not safe_getenv: this is the server's own setting read from a
    # literal name in this module, not a tenant-supplied variable name, and
    # safe_getenv refuses every LANGFLOW_-prefixed name by design.
    import os

    return (os.getenv(GOOGLE_DRIVE_ENABLED_ENV_VAR) or "").casefold() in _TRUTHY


# The registry is populated at import time, so the decision is recorded here as
# well: a test cannot undo a registration by clearing the variable afterwards, and
# a machine that had the switch set when this module was first imported must still
# be able to assert the invariant (registered if and only if the switch was on).
GOOGLE_DRIVE_SOURCE_REGISTERED = google_drive_source_enabled()

if GOOGLE_DRIVE_SOURCE_REGISTERED:
    register_source(SourceType.GOOGLE_DRIVE, GoogleDriveSource)

__all__ = [
    "GOOGLE_DRIVE_ENABLED_ENV_VAR",
    "GOOGLE_DRIVE_SOURCE_REGISTERED",
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
    "google_drive_source_enabled",
    "register_source",
    "registered_source_keys",
    "registered_sources",
]
