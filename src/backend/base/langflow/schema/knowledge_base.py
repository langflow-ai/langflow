from datetime import datetime
from typing import Any

from pydantic import BaseModel


class KnowledgeBaseInfo(BaseModel):
    id: str
    dir_name: str = ""
    name: str
    embedding_provider: str | None = "Unknown"
    embedding_model: str | None = "Unknown"
    size: int = 0
    words: int = 0
    characters: int = 0
    chunks: int = 0
    avg_chunk_size: float = 0.0
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    separator: str | None = None
    status: str = "empty"
    failure_reason: str | None = None
    last_job_id: str | None = None
    source_types: list[str] = []
    column_config: list[dict] | None = None


class BulkDeleteRequest(BaseModel):
    kb_names: list[str]


class ColumnConfigItem(BaseModel):
    column_name: str
    vectorize: bool = False
    identifier: bool = False


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    embedding_provider: str
    embedding_model: str
    column_config: list[ColumnConfigItem] | None = None


class AddSourceRequest(BaseModel):
    source_name: str
    files: list[str]  # List of file paths or file IDs


class ChunkInfo(BaseModel):
    id: str
    content: str
    char_count: int
    metadata: dict | None = None


class PaginatedChunkResponse(BaseModel):
    chunks: list[ChunkInfo]
    total: int
    page: int
    limit: int
    total_pages: int


class IngestionRunItemInfo(BaseModel):
    """Per-item outcome inside a run (``ingestion_run.items`` row shape)."""

    item_id: str
    display_name: str
    status: str
    chunks_created: int = 0
    error_message: str | None = None


class IngestionRunInfo(BaseModel):
    """Lightweight row shape for run-list endpoints.

    Excludes the full per-item array so list responses stay small even
    for KBs with many large runs. Clients fetch the detail endpoint
    when the user drills into a specific run.
    """

    id: str
    kb_name: str
    kb_id: str | None = None
    job_id: str | None = None
    source_type: str
    status: str
    error_message: str | None = None
    total_items: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    total_bytes: int = 0
    chunks_created: int = 0
    started_at: datetime
    finished_at: datetime | None = None


class IngestionRunDetail(IngestionRunInfo):
    """Full run row including per-item breakdown + source config.

    Returned by ``GET /{kb_name}/runs/{run_id}`` so the UI can render
    a file-by-file drill-down with individual error messages.
    """

    source_config: dict[str, Any] = {}
    items: list[IngestionRunItemInfo] = []


class PaginatedIngestionRunResponse(BaseModel):
    runs: list[IngestionRunInfo]
    total: int
    page: int
    limit: int
    total_pages: int


class ConnectorCatalogEntry(BaseModel):
    """Published metadata for a registered ingestion source.

    Drives the UI's connector picker — one card per registered source
    type. Excludes file_upload because that path is wired through the
    dedicated upload modal, not the generic connector flow.
    """

    source_type: str
    display_name: str
    description: str = ""
    icon: str | None = None
    requires_credentials: bool = False


class ConnectorIngestRequest(BaseModel):
    """Body payload for the generic ``POST /{kb}/ingest/connector`` route."""

    source_type: str
    source_config: dict[str, Any] = {}
    source_name: str = ""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separator: str = ""
