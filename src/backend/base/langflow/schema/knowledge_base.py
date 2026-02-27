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
