"""Tests for langflow.schema.knowledge_base module."""

from langflow.schema.knowledge_base import (
    AddSourceRequest,
    BulkDeleteRequest,
    ChunkInfo,
    ColumnConfigItem,
    CreateKnowledgeBaseRequest,
    KnowledgeBaseInfo,
    PaginatedChunkResponse,
)


class TestKnowledgeBaseInfo:
    def test_defaults(self):
        kb = KnowledgeBaseInfo(id="kb1", name="My KB")
        assert kb.id == "kb1"
        assert kb.name == "My KB"
        assert kb.dir_name == ""
        assert kb.embedding_provider == "Unknown"
        assert kb.embedding_model == "Unknown"
        assert kb.size == 0
        assert kb.words == 0
        assert kb.characters == 0
        assert kb.chunks == 0
        assert kb.avg_chunk_size == 0.0
        assert kb.chunk_size is None
        assert kb.chunk_overlap is None
        assert kb.separator is None
        assert kb.status == "empty"
        assert kb.failure_reason is None
        assert kb.last_job_id is None
        assert kb.source_types == []
        assert kb.column_config is None

    def test_with_values(self):
        kb = KnowledgeBaseInfo(
            id="kb1",
            name="My KB",
            embedding_provider="OpenAI",
            embedding_model="text-embedding-3-small",
            size=1024,
            words=500,
            chunks=10,
            status="ready",
            source_types=["pdf", "txt"],
        )
        assert kb.embedding_provider == "OpenAI"
        assert kb.status == "ready"
        assert kb.source_types == ["pdf", "txt"]

    def test_model_dump(self):
        kb = KnowledgeBaseInfo(id="kb1", name="Test")
        d = kb.model_dump()
        assert "id" in d
        assert "name" in d
        assert d["status"] == "empty"


class TestBulkDeleteRequest:
    def test_creation(self):
        req = BulkDeleteRequest(kb_names=["kb1", "kb2"])
        assert req.kb_names == ["kb1", "kb2"]

    def test_empty_list(self):
        req = BulkDeleteRequest(kb_names=[])
        assert req.kb_names == []


class TestColumnConfigItem:
    def test_defaults(self):
        item = ColumnConfigItem(column_name="title")
        assert item.column_name == "title"
        assert item.vectorize is False
        assert item.identifier is False

    def test_with_flags(self):
        item = ColumnConfigItem(column_name="content", vectorize=True, identifier=True)
        assert item.vectorize is True
        assert item.identifier is True


class TestCreateKnowledgeBaseRequest:
    def test_basic(self):
        req = CreateKnowledgeBaseRequest(
            name="My KB",
            embedding_provider="OpenAI",
            embedding_model="text-embedding-3-small",
        )
        assert req.name == "My KB"
        assert req.embedding_provider == "OpenAI"
        assert req.column_config is None

    def test_with_column_config(self):
        req = CreateKnowledgeBaseRequest(
            name="My KB",
            embedding_provider="OpenAI",
            embedding_model="text-embedding-3-small",
            column_config=[ColumnConfigItem(column_name="title", vectorize=True)],
        )
        assert len(req.column_config) == 1
        assert req.column_config[0].column_name == "title"


class TestAddSourceRequest:
    def test_basic(self):
        req = AddSourceRequest(source_name="docs", files=["file1.pdf", "file2.txt"])
        assert req.source_name == "docs"
        assert len(req.files) == 2


class TestChunkInfo:
    def test_basic(self):
        chunk = ChunkInfo(id="c1", content="Hello world", char_count=11)
        assert chunk.id == "c1"
        assert chunk.content == "Hello world"
        assert chunk.char_count == 11
        assert chunk.metadata is None

    def test_with_metadata(self):
        chunk = ChunkInfo(id="c1", content="Hi", char_count=2, metadata={"source": "doc.pdf"})
        assert chunk.metadata["source"] == "doc.pdf"


class TestPaginatedChunkResponse:
    def test_basic(self):
        resp = PaginatedChunkResponse(
            chunks=[ChunkInfo(id="c1", content="x", char_count=1)],
            total=100,
            page=1,
            limit=50,
            total_pages=2,
        )
        assert len(resp.chunks) == 1
        assert resp.total == 100
        assert resp.total_pages == 2

    def test_empty(self):
        resp = PaginatedChunkResponse(chunks=[], total=0, page=1, limit=50, total_pages=0)
        assert resp.chunks == []
        assert resp.total == 0
