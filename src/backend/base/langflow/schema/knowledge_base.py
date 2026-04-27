from datetime import datetime
from typing import Any

from lfx.base.knowledge_bases.backends import BackendType
from pydantic import BaseModel, Field, field_validator, model_validator

from langflow.utils.kb_constants import MAX_CHUNK_OVERLAP, MAX_CHUNK_SIZE, MIN_CHUNK_OVERLAP, MIN_CHUNK_SIZE

_REQUIRED_BACKEND_CONFIG: dict[str, tuple[str, ...]] = {
    BackendType.OPENSEARCH.value: ("index_name",),
}

# Backends the API accepts for *new* KB creation. Other ``BackendType``
# values exist as stubs so existing DB rows referencing them can still
# be read back, but creating a new KB on a stubbed backend would just
# fail at ingest time. Reject up front instead.
_CREATION_ALLOWED_BACKENDS: frozenset[str] = frozenset(
    {BackendType.CHROMA.value, BackendType.OPENSEARCH.value}
)


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
    source_types: list[str] = Field(default_factory=list)
    column_config: list[dict] | None = None
    backend_type: str = "chroma"
    backend_config: dict[str, Any] = Field(default_factory=dict)


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
    model_selection: dict[str, Any] | list[dict[str, Any]] | None = None
    column_config: list[ColumnConfigItem] | None = None
    # Phase 4 additions. Default keeps existing KBs on Chroma.
    backend_type: str = "chroma"
    backend_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("backend_type")
    @classmethod
    def validate_backend_type(cls, value: str) -> str:
        normalized = value or BackendType.CHROMA.value
        try:
            backend = BackendType(normalized).value
        except ValueError as exc:
            allowed = ", ".join(sorted(_CREATION_ALLOWED_BACKENDS))
            msg = f"Unknown vector-store backend {normalized!r}. Expected one of: {allowed}."
            raise ValueError(msg) from exc
        if backend not in _CREATION_ALLOWED_BACKENDS:
            allowed = ", ".join(sorted(_CREATION_ALLOWED_BACKENDS))
            msg = (
                f"Vector-store backend {backend!r} is not enabled in this build. "
                f"Available backends: {allowed}."
            )
            raise ValueError(msg)
        return backend

    @model_validator(mode="after")
    def validate_backend_config(self) -> "CreateKnowledgeBaseRequest":
        required_keys = _REQUIRED_BACKEND_CONFIG.get(self.backend_type, ())
        missing = [key for key in required_keys if not str(self.backend_config.get(key) or "").strip()]
        if missing:
            msg = f"{self.backend_type} backend requires backend_config field(s): {', '.join(missing)}."
            raise ValueError(msg)
        return self


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

    source_config: dict[str, Any] = Field(default_factory=dict)
    items: list[IngestionRunItemInfo] = Field(default_factory=list)


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
    source_config: dict[str, Any] = Field(default_factory=dict)
    source_name: str = ""
    chunk_size: int = Field(1000, ge=MIN_CHUNK_SIZE, le=MAX_CHUNK_SIZE)
    chunk_overlap: int = Field(200, ge=MIN_CHUNK_OVERLAP, le=MAX_CHUNK_OVERLAP)
    separator: str = ""
