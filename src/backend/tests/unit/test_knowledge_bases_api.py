import io
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from httpx import AsyncClient
from langflow.api.utils.kb_helpers import (
    KBAnalysisHelper,
    KBIngestionHelper,
    KBStorageHelper,
)


@pytest.fixture
def sample_text_file():
    """Create an in-memory text file for testing."""
    content = (
        "This is the first paragraph of content. It contains enough text to be split into chunks.\n\n"
        "This is the second paragraph. It discusses a different topic entirely.\n\n"
        "This is the third paragraph. It wraps up the document with some final thoughts.\n\n"
        "And here is a fourth paragraph to ensure we have enough text for chunking with smaller sizes."
    )
    return ("test_document.txt", content)


@pytest.fixture
def empty_text_file():
    """Create an empty in-memory text file for testing."""
    return ("empty.txt", "")


@pytest.fixture
def whitespace_text_file():
    """Create a whitespace-only in-memory text file for testing."""
    return ("whitespace.txt", "   \n\n   \t   ")


@pytest.fixture
def mock_kb_path(tmp_path):
    kb_dir = tmp_path / "test_kb"
    kb_dir.mkdir()
    return kb_dir


class TestKnowledgeBaseHelpers:
    """Tests for helper functions in kb_helpers.py via class methods."""

    def test_get_directory_size(self, mock_kb_path):
        (mock_kb_path / "file1.txt").write_text("hello")
        (mock_kb_path / "file2.txt").write_text("world")
        nested = mock_kb_path / "nested"
        nested.mkdir()
        (nested / "file3.txt").write_text("!!!")

        size = KBStorageHelper.get_directory_size(mock_kb_path)
        assert size == 13

    def test_detect_embedding_provider_from_config(self, mock_kb_path):
        config_file = mock_kb_path / "config.json"
        config_file.write_text(json.dumps({"provider": "openai"}))
        assert KBAnalysisHelper._detect_embedding_provider(mock_kb_path) == "OpenAI"

    def test_detect_embedding_provider_from_chroma(self, mock_kb_path):
        # The logic checks for "chroma" directory or specific config keys
        (mock_kb_path / "chroma").mkdir()
        assert KBAnalysisHelper._detect_embedding_provider(mock_kb_path) == "Chroma"

    def test_detect_embedding_provider_fallback(self, mock_kb_path):
        assert KBAnalysisHelper._detect_embedding_provider(mock_kb_path) == "Unknown"

    def test_detect_embedding_model_from_config(self, mock_kb_path):
        config_file = mock_kb_path / "config.json"
        config_file.write_text(json.dumps({"model": "text-embedding-3-small"}))
        assert KBAnalysisHelper._detect_embedding_model(mock_kb_path) == "text-embedding-3-small"

    def test_detect_embedding_model_fallback(self, mock_kb_path):
        assert KBAnalysisHelper._detect_embedding_model(mock_kb_path) == "Unknown"

    def test_calculate_text_metrics(self):
        df = pd.DataFrame({"text": ["hello world", "foo bar baz"]})
        words, chars = KBAnalysisHelper._calculate_text_metrics(df, ["text"])
        assert words == 5
        assert chars == 22


class TestGetKBMetaData:
    """Tests for KBAnalysisHelper.get_metadata function."""

    def test_get_metadata_fast_success(self, mock_kb_path):
        metadata_file = mock_kb_path / "embedding_metadata.json"
        sample_meta = {
            "chunks": 10,
            "words": 100,
            "characters": 500,
            "avg_chunk_size": 50.0,
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-3-small",
            "id": "test-uuid",
            "size": 1024,
            "source_types": [],
            "chunk_size": None,
            "chunk_overlap": None,
            "separator": None,
        }
        metadata_file.write_text(json.dumps(sample_meta))

        result = KBAnalysisHelper.get_metadata(mock_kb_path, fast=True)
        assert result["chunks"] == 10
        assert result["embedding_provider"] == "OpenAI"

    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper._detect_embedding_provider")
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper._detect_embedding_model")
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_directory_size")
    def test_get_metadata_slow_path(self, mock_size, mock_model, mock_provider, mock_kb_path):
        mock_size.return_value = 2048
        mock_provider.return_value = "Anthropic"
        mock_model.return_value = "claude-embed"

        result = KBAnalysisHelper.get_metadata(mock_kb_path, fast=False)

        assert result["size"] == 2048
        assert result["embedding_provider"] == "Anthropic"
        assert (mock_kb_path / "embedding_metadata.json").exists()


class TestPreviewChunks:
    """Tests for the POST /knowledge_bases/preview-chunks endpoint."""

    async def test_preview_chunks_basic(self, client: AsyncClient, logged_in_headers, sample_text_file):
        file_name, file_content = sample_text_file
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
            data={
                "chunk_size": "100",
                "chunk_overlap": "20",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert len(data["files"]) == 1


class TestKnowledgeBaseAPI:
    """Tests for KR CRUD endpoints."""

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_knowledge_base(
        self, mock_root, mock_fresh_client, client: AsyncClient, logged_in_headers, tmp_path
    ):
        mock_fresh_client.return_value = MagicMock()
        mock_root.return_value = tmp_path
        kb_name = "New_KB"
        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": kb_name,
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New KB"

    async def test_create_kb_name_too_short(self, client: AsyncClient, logged_in_headers):
        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "ab",
                "embedding_provider": "OpenAI",
                "embedding_model": "model",
            },
        )
        assert response.status_code == 400
        assert "at least 3 characters" in response.json()["detail"]

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_duplicate_kb(self, mock_root, client: AsyncClient, logged_in_headers, tmp_path):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        (kb_user_path / "Duplicate_KB").mkdir()

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "Duplicate KB",
                "embedding_provider": "OpenAI",
                "embedding_model": "model",
            },
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.get_job_service")
    async def test_list_knowledge_bases(
        self, mock_job_service, mock_meta, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True, exist_ok=True)
        (kb_user_path / "KB1").mkdir(exist_ok=True)

        mock_meta.return_value = {
            "chunks": 10,
            "words": 100,
            "characters": 500,
            "avg_chunk_size": 50.0,
            "embedding_provider": "OpenAI",
            "embedding_model": "model",
            "id": str(uuid.uuid4()),
            "size": 1024,
            "source_types": [],
            "column_config": None,
        }

        mock_job_service_inst = MagicMock()
        mock_job_service.return_value = mock_job_service_inst
        mock_job_service_inst.get_latest_jobs_by_asset_ids = AsyncMock(return_value={})

        response = await client.get("api/v1/knowledge_bases", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_get_knowledge_base_detail(self, mock_root, client: AsyncClient, logged_in_headers, tmp_path):
        mock_root.return_value = tmp_path
        kb_path = tmp_path / "activeuser" / "Detail_KB"
        kb_path.mkdir(parents=True)

        meta = {
            "chunks": 5,
            "words": 50,
            "characters": 250,
            "avg_chunk_size": 50.0,
            "embedding_provider": "OpenAI",
            "embedding_model": "model",
            "id": "uuid",
            "size": 100,
        }
        (kb_path / "embedding_metadata.json").write_text(json.dumps(meta))

        response = await client.get("api/v1/knowledge_bases/Detail_KB", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["chunks"] == 5
        assert data["name"] == "Detail KB"

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.teardown_storage")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_knowledge_base(
        self, mock_root, mock_teardown, client: AsyncClient, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "To_Delete").mkdir(parents=True, exist_ok=True)

        response = await client.delete("api/v1/knowledge_bases/To_Delete", headers=logged_in_headers)
        assert response.status_code == 200
        mock_teardown.assert_called_once()

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.teardown_storage")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_knowledge_bases(
        self, mock_root, mock_teardown, client: AsyncClient, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        (kb_user_path / "KB1").mkdir()
        (kb_user_path / "KB2").mkdir()

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["KB1", "KB2", "NonExistent"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert "NonExistent" in data["not_found"]
        assert mock_teardown.called

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.v1.knowledge_bases.get_job_service")
    @patch("langflow.api.v1.knowledge_bases.get_task_service")
    async def test_ingest_files(
        self,
        mock_task,
        mock_job,
        mock_meta,
        mock_root,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
        sample_text_file,
    ):
        mock_root.return_value = tmp_path
        kb_path = tmp_path / "activeuser" / "Ingest-KB"
        kb_path.mkdir(parents=True, exist_ok=True)

        mock_meta.return_value = {
            "embedding_provider": "OpenAI",
            "embedding_model": "model",
            "chunks": 0,
            "id": str(uuid.uuid4()),
        }

        file_name, file_content = sample_text_file

        mock_task_inst = MagicMock()
        mock_task.return_value = mock_task_inst
        mock_task_inst.fire_and_forget_task = AsyncMock(return_value=None)

        mock_job_inst = MagicMock()
        mock_job.return_value = mock_job_inst
        mock_job_inst.create_job = AsyncMock(return_value=MagicMock(job_id=uuid.uuid4()))

        response = await client.post(
            "api/v1/knowledge_bases/Ingest-KB/ingest",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
            data={"source_name": "test-source"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_ingest_non_existent_kb(self, mock_root, client: AsyncClient, logged_in_headers, tmp_path):
        mock_root.return_value = tmp_path
        response = await client.post(
            "api/v1/knowledge_bases/NonExistent/ingest",
            headers=logged_in_headers,
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        )
        assert response.status_code == 404

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    async def test_ingest_invalid_config(self, mock_meta, mock_root, client: AsyncClient, logged_in_headers, tmp_path):
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "Invalid-KB").mkdir(parents=True)
        mock_meta.return_value = {"embedding_provider": None, "embedding_model": None}

        response = await client.post(
            "api/v1/knowledge_bases/Invalid-KB/ingest",
            headers=logged_in_headers,
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        )
        assert response.status_code == 400
        assert "Invalid embedding configuration" in response.json()["detail"]

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.Chroma")
    async def test_get_chunks_pagination_and_search(
        self, mock_chroma, mock_root, mock_fresh_client, client: AsyncClient, logged_in_headers, tmp_path
    ):
        mock_fresh_client.return_value = MagicMock()
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / "activeuser" / "KB1"
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "chroma.sqlite3").write_text("dummy")

        mock_collection = MagicMock()
        # Set up for page 1 search
        mock_collection.get.return_value = {
            "ids": ["1", "2"],
            "documents": ["content 1", "content 2"],
            "metadatas": [{}, {}],
        }
        mock_chroma.return_value._collection = mock_collection

        # Test search
        response = await client.get("api/v1/knowledge_bases/KB1/chunks?search=content", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["chunks"]) == 2
        mock_collection.get.assert_called_with(
            include=["documents", "metadatas"], where_document={"$contains": "content"}
        )

        # Test pagination (page 2)
        mock_collection.count.return_value = 25
        mock_collection.get.return_value = {
            "ids": ["11"],
            "documents": ["page 2 content"],
            "metadatas": [{}],
        }
        response = await client.get("api/v1/knowledge_bases/KB1/chunks?page=2&limit=10", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        mock_collection.get.assert_called_with(include=["documents", "metadatas"], limit=10, offset=10)


class TestPerformIngestionTask:
    """Tests for the internal KBIngestionHelper.perform_ingestion background task."""

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.utils.kb_helpers.Chroma")
    @patch("langflow.api.utils.kb_helpers.KBIngestionHelper._build_embeddings", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_directory_size")
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics")
    async def test_perform_ingestion_success(
        self,
        mock_update,
        mock_size,
        mock_meta,
        mock_build,
        mock_chroma,
        mock_fresh_client,
        mock_kb_path,
        sample_text_file,
    ):
        mock_fresh_client.return_value = MagicMock()
        mock_update.return_value = None
        mock_embeddings = MagicMock()
        mock_build.return_value = mock_embeddings

        mock_chroma_inst = MagicMock()
        mock_chroma.return_value = mock_chroma_inst
        mock_chroma_inst.aadd_documents = AsyncMock()

        mock_meta.return_value = {"chunks": 5, "size": 100, "source_types": []}
        mock_size.return_value = 100

        file_name, file_content = sample_text_file
        files_data = [(file_name, file_content.encode())]

        result = await KBIngestionHelper.perform_ingestion(
            kb_name="test_kb",
            kb_path=mock_kb_path,
            files_data=files_data,
            chunk_size=100,
            chunk_overlap=20,
            separator="\n",
            source_name="src",
            current_user=MagicMock(),
            embedding_provider="OpenAI",
            embedding_model="model",
            task_job_id=uuid.uuid4(),
            job_service=AsyncMock(),
        )

        assert result["files_processed"] == 1
        mock_chroma_inst.aadd_documents.assert_called()

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.utils.kb_helpers.Chroma")
    @patch("langflow.api.utils.kb_helpers.KBIngestionHelper._build_embeddings", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.KBIngestionHelper.cleanup_chroma_chunks_by_job", new_callable=AsyncMock)
    async def test_perform_ingestion_rollback(
        self, mock_cleanup, mock_build, mock_chroma, mock_fresh_client, mock_kb_path
    ):
        mock_fresh_client.return_value = MagicMock()
        mock_chroma_inst = MagicMock()
        mock_chroma.return_value = mock_chroma_inst
        mock_chroma_inst.aadd_documents = AsyncMock(side_effect=Exception("Chroma error"))
        mock_chroma_inst.adelete = AsyncMock()

        files_data = [("test.txt", b"content")]
        job_id = uuid.uuid4()

        with pytest.raises(Exception, match="Chroma error"):
            await KBIngestionHelper.perform_ingestion(
                kb_name="test_kb",
                kb_path=mock_kb_path,
                files_data=files_data,
                chunk_size=100,
                chunk_overlap=20,
                separator="\n",
                source_name="src",
                current_user=MagicMock(),
                embedding_provider="OpenAI",
                embedding_model="model",
                task_job_id=job_id,
                job_service=AsyncMock(),
            )

        mock_build.assert_called_once()
        mock_cleanup.assert_called_once_with(job_id, mock_kb_path, "test_kb")


class TestCancelIngestion:
    """Tests for the cancel_ingestion endpoint."""

    @patch("langflow.api.v1.knowledge_bases.KBIngestionHelper.cleanup_chroma_chunks_by_job")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    async def test_cancel_ingestion_success(
        self, mock_meta, mock_root, mock_cleanup, client: AsyncClient, logged_in_headers, tmp_path
    ):
        from unittest.mock import patch as mock_patch

        from langflow.services.deps import get_service
        from langflow.services.schema import ServiceType

        mock_root.return_value = tmp_path
        kb_path = tmp_path / "activeuser" / "Test_KB"
        kb_path.mkdir(parents=True, exist_ok=True)

        job_id = uuid.uuid4()
        asset_id = uuid.uuid4()

        mock_meta.return_value = {"id": str(asset_id)}

        mock_job = MagicMock()
        mock_job.job_id = job_id
        mock_job.status = MagicMock()
        mock_job.status.value = "running"

        mock_job_service_inst = MagicMock()
        mock_job_service_inst.get_latest_jobs_by_asset_ids = AsyncMock(return_value={asset_id: mock_job})
        mock_job_service_inst.update_job_status = AsyncMock()

        mock_task_service_inst = MagicMock()
        mock_task_service_inst.revoke_task = AsyncMock(return_value=True)

        mock_cleanup.return_value = AsyncMock()

        original_get_service = get_service

        def get_service_side_effect(service_type, default=None):
            if service_type == ServiceType.JOB_SERVICE:
                return mock_job_service_inst
            if service_type == ServiceType.TASK_SERVICE:
                return mock_task_service_inst
            return original_get_service(service_type, default)

        with mock_patch("langflow.services.deps.get_service", side_effect=get_service_side_effect):
            response = await client.post(
                "api/v1/knowledge_bases/Test_KB/cancel",
                headers=logged_in_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert "cancelled successfully" in data["message"]
            mock_task_service_inst.revoke_task.assert_called_once_with(job_id)
            mock_job_service_inst.update_job_status.assert_called_once()

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.get_job_service")
    async def test_cancel_ingestion_not_found(
        self, mock_job_service, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_path = tmp_path / "activeuser" / "Test_KB"
        kb_path.mkdir(parents=True, exist_ok=True)
        # Create metadata so asset ID check passes
        (kb_path / "embedding_metadata.json").write_text(json.dumps({"id": str(uuid.uuid4())}))

        mock_job_service_inst = MagicMock()
        mock_job_service.return_value = mock_job_service_inst
        mock_job_service_inst.get_latest_jobs_by_asset_ids = AsyncMock(return_value={})

        response = await client.post(
            "api/v1/knowledge_bases/Test_KB/cancel",
            headers=logged_in_headers,
        )

        assert response.status_code == 404
        assert "no ingestion job found" in response.json()["detail"].lower()

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_cancel_ingestion_kb_not_found(self, mock_root, client: AsyncClient, logged_in_headers, tmp_path):
        mock_root.return_value = tmp_path

        response = await client.post(
            "api/v1/knowledge_bases/NonExistent_KB/cancel",
            headers=logged_in_headers,
        )

        assert response.status_code == 404
