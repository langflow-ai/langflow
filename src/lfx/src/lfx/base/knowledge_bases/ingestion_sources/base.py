"""Base types for Knowledge Base ingestion sources.

Keeps concerns separate:

* ``IngestionItem`` — lightweight descriptor yielded by ``list_items``.
  Cheap to produce so a source can enumerate items without fetching bytes.
* ``IngestionItemContent`` — the actual bytes, fetched lazily by
  ``fetch_content(item)``. Split so sources whose item listing is cheap
  (a directory walk) but content fetch is expensive (an HTTP round-trip
  to Google Drive) don't pay for content until it's needed.
* ``IngestionSummary`` — mutable run-level counters that ``perform_ingestion``
  updates as items succeed or fail. Persisted to the ``ingestion_run``
  table at the end of the run (Phase 2 visibility).
* ``KBIngestionSource`` — the ABC. Subclasses declare their ``source_type``
  class attribute (enum value, also written on every chunk's
  ``source_type`` metadata key) and implement ``list_items`` +
  ``fetch_content``. Optional hooks: ``validate_config`` and
  ``describe`` for UI display.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID


class SourceType(str, Enum):
    """Canonical source-type identifiers.

    Values are lowercase and double as the ``source_type`` tag written
    onto every chunk document in the vector store. Phase 3 adds
    ``GOOGLE_DRIVE``, ``S3``, ``ONEDRIVE``, ``SHAREPOINT``, and
    ``IBM_COS``; Phase 4 may add ``URL`` for live-scraper ingestion.
    """

    FILE_UPLOAD = "file_upload"
    FOLDER = "folder"
    FLOW_COMPONENT = "flow_component"  # KnowledgeIngestion flow component
    TEMPLATE = "template"  # Reserved — existing flow-template ingestion path
    S3 = "s3"
    GOOGLE_DRIVE = "google_drive"  # Reserved for Phase 3B
    ONEDRIVE = "onedrive"  # Reserved for Phase 3C
    SHAREPOINT = "sharepoint"  # Reserved for Phase 3C
    IBM_COS = "ibm_cos"  # Reserved for Phase 3C


class IngestionItemStatus(str, Enum):
    """Per-item outcome within a run."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"  # e.g. empty file, duplicate, filtered extension


class IngestionRunStatus(str, Enum):
    """Run-level outcome surfaced in the UI.

    Distinct from ``JobStatus`` (queued/in_progress/completed/...) —
    that one describes scheduling lifecycle. This one describes the
    ingestion *outcome* (did every file land?). Persisted on
    ``Job.job_metadata.status`` after the migration that dropped the
    ``ingestion_run`` table; the values are kept lowercase strings so
    they survive the JSON round-trip without coercion.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"  # some items failed but run completed
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class IngestionItem:
    """Metadata for a single item a source intends to ingest.

    ``item_id`` is the stable identifier within the source — filename for
    FileUploadSource, absolute path for FolderSource, object key for S3
    later. It must be unique within a single ``list_items`` invocation;
    the ingestion machinery uses it to key per-item error reporting.
    """

    item_id: str
    display_name: str
    mime_type: str | None = None
    source_url: str | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)
    size_bytes: int | None = None


@dataclass(frozen=True)
class IngestionItemContent:
    """Fetched bytes plus the filename text-extraction should key off.

    ``file_name`` is intentionally distinct from ``IngestionItem.display_name``
    — text extractors dispatch on the filename extension, so this always
    carries a usable suffix even if the source reports a different
    display name (e.g. "Annual Report" as display, "2025-annual.pdf" as
    file_name).
    """

    raw_bytes: bytes
    file_name: str


@dataclass
class IngestionItemResult:
    """Per-item result recorded on the run summary."""

    item_id: str
    display_name: str
    status: IngestionItemStatus
    chunks_created: int = 0
    error_message: str | None = None


@dataclass
class IngestionSummary:
    """Aggregate + per-item outcome of one ingestion run.

    Mutable by design: ``perform_ingestion`` creates a summary at the
    start of a run, updates counters and ``items`` as each item is
    processed, and persists the final state to the ``ingestion_run``
    table when the run ends (success, failure, or cancellation).
    """

    kb_name: str
    source_type: str
    user_id: UUID | None = None
    job_id: UUID | None = None
    total_items: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    total_bytes: int = 0
    chunks_created: int = 0
    items: list[IngestionItemResult] = field(default_factory=list)
    source_config: dict[str, Any] = field(default_factory=dict)
    # User-supplied run-level metadata (tags, categories, custom fields).
    # Populated when the API caller supplied a ``metadata`` payload;
    # persisted onto the ``ingestion_run`` row alongside ``source_config``
    # so the run-history UI can render the tags applied to the batch.
    user_metadata: dict[str, Any] = field(default_factory=dict)

    def record_item(self, result: IngestionItemResult, *, size_bytes: int = 0) -> None:
        """Register ``result`` and update aggregate counters.

        Centralised so callers can't update counters without appending
        the detail row (the detail rows are what the Phase 2 drill-down
        renders; out-of-sync counters would be confusing).
        """
        self.items.append(result)
        self.total_items += 1
        self.total_bytes += size_bytes
        self.chunks_created += result.chunks_created
        if result.status is IngestionItemStatus.SUCCEEDED:
            self.succeeded += 1
        elif result.status is IngestionItemStatus.FAILED:
            self.failed += 1
        elif result.status is IngestionItemStatus.SKIPPED:
            self.skipped += 1


class KBIngestionSource(ABC):
    """Base class for Knowledge Base ingestion sources.

    Sources are instantiated per-run. They are not cached: the registry
    hands back the class, and the caller constructs an instance with the
    user's id and the source-specific ``source_config`` dict.

    Credential resolution for connector sources (Phase 3) happens inside
    the source's own implementation using Langflow's
    ``variable_service`` — credentials do NOT live on the ABC to avoid
    forcing simple sources (file upload, folder walk) to implement
    secret-lookup plumbing they don't need.
    """

    source_type: ClassVar[SourceType]
    display_name: ClassVar[str]
    description: ClassVar[str] = ""
    icon: ClassVar[str | None] = None
    requires_credentials: ClassVar[bool] = False

    def __init__(self, user_id: UUID | str | None, source_config: dict[str, Any]) -> None:
        self.user_id = user_id
        self.source_config = source_config or {}

    async def validate_config(self) -> None:  # noqa: B027 — intentional default no-op
        """Validate ``source_config``. Default: no-op.

        Sources that need config validation (e.g. FolderSource's
        allow-list check, cloud connectors' credential presence)
        override this. Raises ``ValueError`` with a human-readable
        message on failure; ``perform_ingestion`` surfaces the message
        on the ingestion run's ``error_message``.
        """

    @abstractmethod
    def list_items(self) -> AsyncIterator[IngestionItem]:
        """Yield every item the source intends to ingest.

        Must be implemented as an async generator. Listing should not
        fetch item bytes — keep ``fetch_content`` in control of that so
        callers can apply rate-limiting, parallelism, and
        cancellation around the expensive step.
        """

    @abstractmethod
    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        """Fetch the bytes + filename for ``item``.

        Called once per item that survives validation/filtering. May
        raise ``OSError`` / ``IOError`` on transient failures — the
        caller records the item as ``FAILED`` in that case and moves on
        rather than aborting the run.
        """

    def describe(self) -> dict[str, Any]:
        """UI-facing snapshot of this source's configuration.

        Redacts any credential-bearing fields. Default impl returns the
        class-level metadata plus ``source_config`` (caller is
        responsible for not putting raw secrets in ``source_config`` —
        cloud connectors should store credential *references*, not
        credential values).
        """
        return {
            "source_type": self.source_type.value,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "requires_credentials": self.requires_credentials,
            "config": dict(self.source_config),
        }
