import io
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from httpx import AsyncClient
from langflow.api.utils import knowledge_base_service
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

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_directory_size")
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics")
    def test_get_metadata_fast_recounts_stale_zero_chunk_metadata(
        self, mock_update_metrics, mock_get_directory_size, mock_kb_path
    ):
        metadata_file = mock_kb_path / "embedding_metadata.json"
        sample_meta = {
            "chunks": 0,
            "words": 0,
            "characters": 0,
            "avg_chunk_size": 0.0,
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-3-small",
            "id": "test-uuid",
            "size": 128,
            "source_types": [],
            "chunk_size": None,
            "chunk_overlap": None,
            "separator": None,
        }
        metadata_file.write_text(json.dumps(sample_meta))
        (mock_kb_path / "chroma.sqlite3").write_text("")
        mock_get_directory_size.return_value = 4096

        def populate_metrics(_kb_path, metadata):
            metadata.update({"chunks": 2, "words": 3, "characters": 14, "avg_chunk_size": 7.0})

        mock_update_metrics.side_effect = populate_metrics

        result = KBAnalysisHelper.get_metadata(mock_kb_path, fast=True)
        stored_metadata = json.loads(metadata_file.read_text())

        assert result["chunks"] == 2
        assert result["words"] == 3
        assert result["characters"] == 14
        assert result["avg_chunk_size"] == 7.0
        assert result["size"] == 4096
        assert stored_metadata["chunks"] == 2
        assert stored_metadata["size"] == 4096
        mock_update_metrics.assert_called_once()
        mock_get_directory_size.assert_called_once_with(mock_kb_path)

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
        self, mock_root, mock_fresh_client, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        mock_fresh_client.return_value = MagicMock()
        mock_root.return_value = tmp_path
        kb_name = "New_KB"
        model_selection = {
            "id": "text-embedding-3-small",
            "name": "text-embedding-3-small",
            "provider": "OpenAI",
            "metadata": {"model_type": "embeddings"},
        }
        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": kb_name,
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
                "model_selection": model_selection,
                "backend_type": "opensearch",
                "backend_config": {"index_name": "new_kb_index"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New KB"
        assert data["backend_type"] == "opensearch"
        assert data["backend_config"] == {"index_name": "new_kb_index"}
        mock_fresh_client.return_value.create_collection.assert_called_once_with(
            name=kb_name,
            configuration={"embedding_function": None},
            embedding_function=None,
        )
        record = await knowledge_base_service.get_by_user_and_name(active_user.id, kb_name)
        assert record is not None
        assert record.model_selection == model_selection
        metadata = json.loads((tmp_path / active_user.username / kb_name / "embedding_metadata.json").read_text())
        assert metadata["model_selection"] == model_selection

    async def test_create_knowledge_base_rejects_unknown_backend(self, client: AsyncClient, logged_in_headers):
        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "Bad_Backend_KB",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
                "backend_type": "not-a-backend",
            },
        )

        assert response.status_code == 422
        assert "unknown vector-store backend" in response.text.lower()

    async def test_create_knowledge_base_rejects_missing_backend_config(self, client: AsyncClient, logged_in_headers):
        # OpenSearch is the only non-Chroma backend exposed for new KB
        # creation in this phase (mongodb / astra / postgres are stubbed),
        # so it's the one path where ``_REQUIRED_BACKEND_CONFIG`` still
        # rejects an empty ``backend_config``.
        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "Missing_Backend_Config_KB",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
                "backend_type": "opensearch",
                "backend_config": {},
            },
        )

        assert response.status_code == 422
        assert "index_name" in response.text

    async def test_create_knowledge_base_rejects_stubbed_backend(self, client: AsyncClient, logged_in_headers):
        """Stubbed backends fail at the schema layer with a "not enabled" message.

        The ``BackendType`` enum still includes ``mongodb``/``astra``/``postgres``
        for DB row compatibility, but ``validate_backend_type`` rejects them so
        a user posting one gets a clear 422 instead of a successful create
        followed by ingest-time NotImplementedError.
        """
        for stubbed in ("mongodb", "astra", "postgres"):
            response = await client.post(
                "api/v1/knowledge_bases",
                headers=logged_in_headers,
                json={
                    "name": f"Stubbed_{stubbed}_KB",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "text-embedding-3-small",
                    "backend_type": stubbed,
                    # Provide config that *would* have been valid pre-stub
                    # so the rejection is unambiguously about the backend
                    # being disabled, not about missing required fields.
                    "backend_config": {
                        "collection_name": "x",
                        "database": "x",
                        "collection": "x",
                    },
                },
            )

            assert response.status_code == 422, (stubbed, response.text)
            assert "not enabled" in response.text.lower(), (stubbed, response.text)

    async def test_test_connection_chroma_returns_ok(self, client: AsyncClient, logged_in_headers):
        """Chroma succeeds against a transient temp dir.

        The endpoint builds the backend in a tempfile that is cleaned
        up before the response is returned, so no on-disk state
        outlasts the request.
        """
        response = await client.post(
            "api/v1/knowledge_bases/test-connection",
            headers=logged_in_headers,
            json={"backend_type": "chroma", "backend_config": {}},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True
        assert "Chroma" in body["message"]

    async def test_test_connection_rejects_unknown_backend(self, client: AsyncClient, logged_in_headers):
        response = await client.post(
            "api/v1/knowledge_bases/test-connection",
            headers=logged_in_headers,
            json={"backend_type": "not-a-backend", "backend_config": {}},
        )
        assert response.status_code == 422
        assert "unknown vector-store backend" in response.text.lower()

    async def test_test_connection_rejects_missing_required_field(self, client: AsyncClient, logged_in_headers):
        response = await client.post(
            "api/v1/knowledge_bases/test-connection",
            headers=logged_in_headers,
            json={"backend_type": "opensearch", "backend_config": {}},
        )
        assert response.status_code == 422
        assert "index_name" in response.text

    async def test_test_connection_returns_failure_for_unreachable_opensearch(
        self, client: AsyncClient, logged_in_headers
    ):
        """Reachability failures return HTTP 200 with ``ok=False``.

        Credential and connectivity failures are an *expected* result,
        not an error condition — the frontend differentiates by the
        ``ok`` field rather than the HTTP status code.
        """
        response = await client.post(
            "api/v1/knowledge_bases/test-connection",
            headers=logged_in_headers,
            json={
                "backend_type": "opensearch",
                "backend_config": {
                    "url_variable": "OPENSEARCH_URL_TEST_DOES_NOT_EXIST",
                    "index_name": "any_idx",
                },
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is False
        assert body["message"]

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_kb_path_traversal_single_level(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """Single-level traversal '../victim_user/evil_kb' in POST must be blocked with 400/403.

        VULNERABILITY: the create endpoint builds kb_path = kb_root_path / kb_user / kb_name
        without resolve() or is_relative_to(), so '../victim_user/evil_kb' escapes the user dir.
        """
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser").mkdir(parents=True)
        victim_dir = tmp_path / "victim_user" / "evil_kb"

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "../victim_user/evil_kb",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
            },
        )

        assert response.status_code in (400, 403), (
            f"VULNERABILITY CONFIRMED: create endpoint accepted traversal payload with status {response.status_code}"
        )
        assert not victim_dir.exists(), (
            "VULNERABILITY CONFIRMED: path traversal created a directory outside the user's KB root"
        )

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_kb_path_traversal_absolute_path(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """Absolute path in kb_name must be blocked — e.g. '/tmp/evil'.

        VULNERABILITY: kb_root_path / kb_user / '/tmp/evil' resolves to '/tmp/evil' in Python
        because Path drops all previous components when a segment starts with '/'.
        """
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser").mkdir(parents=True)
        evil_dir = tmp_path / "evil_absolute"

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": str(evil_dir),
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
            },
        )

        assert response.status_code in (400, 403), (
            f"VULNERABILITY CONFIRMED: create endpoint accepted absolute path payload "
            f"with status {response.status_code}"
        )
        assert not evil_dir.exists(), (
            "VULNERABILITY CONFIRMED: absolute path in kb_name created a directory outside the KB root"
        )

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_kb_path_traversal_prefix_ambiguity(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """Prefix-ambiguity attack on create: user='activeuser', target dir='activeuser_evil'.

        With startswith('/root/activeuser'), the path '/root/activeuser_evil/secret_kb'
        incorrectly passes because the string starts with '/root/activeuser'.
        is_relative_to() closes this gap and must block the request with 400/403.
        """
        mock_root.return_value = tmp_path

        (tmp_path / "activeuser").mkdir(parents=True)
        victim_kb = tmp_path / "activeuser_evil" / "secret_kb"
        victim_kb.mkdir(parents=True)

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "../activeuser_evil/secret_kb",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
            },
        )

        assert response.status_code in (400, 403), (
            "VULNERABILITY CONFIRMED: prefix-ambiguity bypass succeeded on create endpoint — "
            "startswith() may still be in use instead of is_relative_to()"
        )
        assert not (tmp_path / "activeuser_evil" / "secret_kb_new").exists(), (
            "VULNERABILITY CONFIRMED: prefix-ambiguity attack created a directory outside the user's KB root"
        )

    @patch("langflow.api.v1.knowledge_bases.logger.warning")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_kb_path_traversal_logs_warning(
        self, mock_root, mock_warning, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """A traversal attempt on create must emit a warning log with user= and kb_name= context."""
        mock_root.return_value = tmp_path

        (tmp_path / "activeuser").mkdir(parents=True)
        (tmp_path / "victim_user" / "secret_kb").mkdir(parents=True)

        await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "../victim_user/secret_kb",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
            },
        )

        mock_warning.assert_called_once()
        warning_args = mock_warning.call_args[0]
        all_args_str = str(warning_args)
        assert "user=" in all_args_str, "Warning log must contain 'user=' in the format string"
        assert "kb_name=" in all_args_str, "Warning log must contain 'kb_name=' in the format string"

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
    async def test_create_duplicate_kb_rejects_existing_db_row_without_directory(
        self,
        mock_root,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        mock_root.return_value = tmp_path
        await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="Duplicate_DB_KB",
            model_selection={"name": "model", "provider": "OpenAI"},
        )

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "Duplicate DB KB",
                "embedding_provider": "OpenAI",
                "embedding_model": "model",
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
        assert not (tmp_path / active_user.username / "Duplicate_DB_KB").exists()

    @patch("langflow.api.v1.knowledge_bases.knowledge_base_service.backfill_from_disk", new_callable=AsyncMock)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_list_knowledge_bases(
        self, mock_root, mock_backfill, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        from langflow.api.utils import knowledge_base_service

        mock_root.return_value = tmp_path
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="KB1",
            model_selection={"name": "model", "provider": "OpenAI"},
            backend_type="opensearch",
            backend_config={"index_name": "kb1_index"},
        )
        await knowledge_base_service.update_stats(
            record.id,
            chunks=10,
            words=100,
            characters=500,
            size_bytes=1024,
        )

        response = await client.get("api/v1/knowledge_bases", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        kb = next(kb for kb in data if kb["id"] == str(record.id))
        assert kb["backend_type"] == "opensearch"
        assert kb["backend_config"] == {"index_name": "kb1_index"}
        assert kb["size"] == 1024
        mock_backfill.assert_not_awaited()

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_list_and_detail_reflect_cleared_db_separator(
        self,
        mock_root,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        mock_root.return_value = tmp_path
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="Cleared_Separator_KB",
            model_selection={"name": "model", "provider": "OpenAI"},
            separator="\n",
        )
        await knowledge_base_service.update_stats(
            record.id,
            chunks=3,
            words=30,
            characters=300,
            size_bytes=2048,
            chunk_size=512,
            chunk_overlap=64,
            separator=None,
        )

        list_response = await client.get("api/v1/knowledge_bases", headers=logged_in_headers)
        assert list_response.status_code == 200
        listed = next(kb for kb in list_response.json() if kb["id"] == str(record.id))
        assert listed["chunk_size"] == 512
        assert listed["chunk_overlap"] == 64
        assert listed["separator"] is None

        detail_response = await client.get(
            "api/v1/knowledge_bases/Cleared_Separator_KB",
            headers=logged_in_headers,
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["chunk_size"] == 512
        assert detail["chunk_overlap"] == 64
        assert detail["separator"] is None

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_list_knowledge_bases_falls_back_to_disk_when_user_has_no_rows(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True, exist_ok=True)
        kb_path = kb_user_path / "KB1"
        kb_path.mkdir(exist_ok=True)
        (kb_path / "embedding_metadata.json").write_text(
            json.dumps(
                {
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
                    "backend_type": "opensearch",
                    "backend_config": {"index_name": "kb1_index"},
                }
            )
        )

        response = await client.get("api/v1/knowledge_bases", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(
            kb["backend_type"] == "opensearch" and kb["backend_config"] == {"index_name": "kb1_index"} for kb in data
        )

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
            "backend_type": "postgres",
            "backend_config": {"collection_name": "detail_kb"},
        }
        (kb_path / "embedding_metadata.json").write_text(json.dumps(meta))

        response = await client.get("api/v1/knowledge_bases/Detail_KB", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["chunks"] == 5
        assert data["name"] == "Detail KB"
        assert data["backend_type"] == "postgres"
        assert data["backend_config"] == {"collection_name": "detail_kb"}

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_get_knowledge_base_detail_prefers_db_row_when_dir_missing(
        self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        from langflow.api.utils import knowledge_base_service

        mock_root.return_value = tmp_path
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="DB_Only_KB",
            model_selection={"name": "model", "provider": "OpenAI"},
            backend_type="opensearch",
            backend_config={"index_name": "db_only_index"},
        )
        await knowledge_base_service.update_stats(
            record.id,
            chunks=5,
            words=50,
            characters=250,
            size_bytes=100,
        )

        response = await client.get("api/v1/knowledge_bases/DB_Only_KB", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(record.id)
        assert data["chunks"] == 5
        assert data["backend_type"] == "opensearch"
        assert data["backend_config"] == {"index_name": "db_only_index"}

    @patch("langflow.api.v1.knowledge_bases.knowledge_base_service.create_record", new_callable=AsyncMock)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_knowledge_base_rolls_back_when_db_persist_fails(
        self,
        mock_root,
        mock_fresh_client,
        mock_create_record,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
    ):
        mock_root.return_value = tmp_path
        mock_fresh_client.return_value = MagicMock()
        mock_create_record.side_effect = RuntimeError("db unavailable")

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "Rollback KB",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
            },
        )

        assert response.status_code == 500
        assert not (tmp_path / "activeuser" / "Rollback_KB").exists()

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.create_backend")
    @patch("langflow.api.v1.knowledge_bases.knowledge_base_service.delete_by_user_and_name", new_callable=AsyncMock)
    @patch("langflow.api.v1.knowledge_bases.knowledge_base_service.get_by_user_and_name", new_callable=AsyncMock)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_knowledge_base(
        self,
        mock_root,
        mock_get_record,
        mock_delete_record,
        mock_create_backend,
        mock_delete,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
    ):
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "To_Delete").mkdir(parents=True, exist_ok=True)
        mock_get_record.return_value = MagicMock(
            backend_type="opensearch",
            backend_config={"index_name": "to_delete_index"},
        )
        backend = MagicMock()
        backend.ensure_ready = AsyncMock()
        backend.delete_collection = AsyncMock()
        backend.teardown = AsyncMock()
        mock_create_backend.return_value = backend

        response = await client.delete("api/v1/knowledge_bases/To_Delete", headers=logged_in_headers)
        assert response.status_code == 200
        mock_create_backend.assert_called_once()
        backend.ensure_ready.assert_awaited_once()
        backend.delete_collection.assert_awaited_once()
        backend.teardown.assert_awaited_once()
        mock_delete.assert_called_once()
        mock_delete_record.assert_awaited_once()

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.create_backend")
    @patch("langflow.api.v1.knowledge_bases.knowledge_base_service.delete_by_user_and_name", new_callable=AsyncMock)
    @patch("langflow.api.v1.knowledge_bases.knowledge_base_service.get_by_user_and_name", new_callable=AsyncMock)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_knowledge_base_survives_remote_backend_auth_failure(
        self,
        mock_root,
        mock_get_record,
        mock_delete_record,  # noqa: ARG002 - patch fixture; presence is the assertion
        mock_create_backend,
        mock_delete,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
    ):
        """Remote-backend cleanup failure must not block local delete.

        Regression for the Astra delete bug: a missing/stale Astra
        token used to raise ``ValueError`` from
        ``backend.ensure_ready`` which propagated as HTTP 500. The KB
        directory + DB row were never cleaned up and the UI showed
        the entry indefinitely. The fix makes remote cleanup
        best-effort and surfaces the failure as a ``warning`` field
        alongside the successful local delete.
        """
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser" / "Stuck_Astra").mkdir(parents=True, exist_ok=True)
        mock_get_record.return_value = MagicMock(
            backend_type="astra",
            backend_config={"collection_name": "stuck_astra"},
        )
        backend = MagicMock()
        backend.ensure_ready = AsyncMock(
            side_effect=ValueError("Required credential variable 'ASTRA_DB_APPLICATION_TOKEN' is not configured.")
        )
        backend.delete_collection = AsyncMock()
        backend.teardown = AsyncMock()
        mock_create_backend.return_value = backend

        response = await client.delete("api/v1/knowledge_bases/Stuck_Astra", headers=logged_in_headers)

        # Local cleanup still runs and succeeds.
        assert response.status_code == 200
        assert mock_delete.called
        # Teardown runs even though ensure_ready threw.
        backend.teardown.assert_awaited_once()
        # delete_collection is skipped because ensure_ready raised.
        backend.delete_collection.assert_not_awaited()
        # Response carries a user-facing warning so the UI can tell
        # the operator the remote resources need manual cleanup.
        data = response.json()
        assert "warning" in data
        assert "astra" in data["warning"].lower()
        assert "manual" in data["warning"].lower()

    @patch("langflow.api.v1.knowledge_bases.create_backend")
    @patch("langflow.api.v1.knowledge_bases.knowledge_base_service.delete_by_user_and_name", new_callable=AsyncMock)
    @patch("langflow.api.v1.knowledge_bases.knowledge_base_service.get_by_user_and_name", new_callable=AsyncMock)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_knowledge_base_cleans_up_orphan_db_row(
        self,
        mock_root,
        mock_get_record,
        mock_delete_record,
        mock_create_backend,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
    ):
        """Dangling DB row must still be deletable even when kb_path is gone.

        Regression for the Astra delete bug: remote-backed KBs whose
        local ``embedding_metadata.json`` directory is missing (partial
        creation failure, manual cleanup, legacy import) were 404ing on
        delete because ``_resolve_kb_path`` requires the dir to exist.
        The list endpoint, meanwhile, reads from the DB row and kept
        showing the entry — so the UI was stuck.
        """
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser").mkdir(parents=True, exist_ok=True)
        # The KB has a DB row but NO on-disk directory. This is the
        # orphan case the test is regressing.
        mock_get_record.return_value = MagicMock(
            backend_type="astra",
            backend_config={"collection_name": "orphan_astra"},
        )
        backend = MagicMock()
        backend.ensure_ready = AsyncMock()
        backend.delete_collection = AsyncMock()
        backend.teardown = AsyncMock()
        mock_create_backend.return_value = backend

        response = await client.delete("api/v1/knowledge_bases/Orphan_KB", headers=logged_in_headers)

        assert response.status_code == 200
        # Remote collection + DB row both cleaned up.
        backend.ensure_ready.assert_awaited_once()
        backend.delete_collection.assert_awaited_once()
        backend.teardown.assert_awaited_once()
        mock_delete_record.assert_awaited_once()

    @patch("langflow.api.v1.knowledge_bases.knowledge_base_service.get_by_user_and_name", new_callable=AsyncMock)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_knowledge_base_truly_missing_still_404s(
        self,
        mock_root,
        mock_get_record,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
    ):
        """No directory AND no DB row → still 404.

        The orphan cleanup must not mask genuine not-found cases —
        those should keep returning 404 so callers can distinguish a
        typo from a dangling row.
        """
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser").mkdir(parents=True, exist_ok=True)
        mock_get_record.return_value = None

        response = await client.delete("api/v1/knowledge_bases/Nonexistent", headers=logged_in_headers)
        assert response.status_code == 404

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_knowledge_base_cancels_inflight_ingestion(
        self,
        mock_root,
        mock_delete,  # noqa: ARG002
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        """Deleting a KB while ingestion is in flight must cancel the job.

        Regression for the "deleted KB reappears after ~5s" bug.
        Without cancellation, the background ingestion keeps writing
        chunks via the backend's persistent client, which auto-recreates
        the KB directory after rmtree. The list endpoint's disk-fallback
        path then re-discovers the recreated dir and the KB pops back
        into the UI.

        Verifies that:
        - Any ``QUEUED``/``IN_PROGRESS`` job for the KB transitions to
          ``CANCELLED`` with a ``finished_timestamp`` set.
        - The KB row itself is removed.
        """
        from langflow.services.database.models.jobs.model import JobStatus, JobType
        from langflow.services.deps import get_job_service

        mock_root.return_value = tmp_path
        kb_name = "Inflight_Ingest_KB"

        # Seed a real KB row + sidecar so the delete endpoint takes
        # the normal "directory present" branch.
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name=kb_name,
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
        )
        kb_dir = tmp_path / active_user.username / kb_name
        kb_dir.mkdir(parents=True)
        (kb_dir / "embedding_metadata.json").write_text(json.dumps({"id": str(record.id)}))

        # Seed an in-flight ingestion job for that KB.
        job_service = get_job_service()
        job_id = uuid.uuid4()
        await job_service.create_job(
            job_id=job_id,
            flow_id=job_id,
            job_type=JobType.INGESTION,
            asset_id=record.id,
            asset_type="knowledge_base",
            user_id=active_user.id,
        )
        await job_service.update_job_status(job_id, JobStatus.IN_PROGRESS)

        response = await client.delete(
            f"api/v1/knowledge_bases/{kb_name}",
            headers=logged_in_headers,
        )

        assert response.status_code == 200

        cancelled_job = await job_service.get_job_by_job_id(job_id)
        assert cancelled_job is not None
        assert cancelled_job.status == JobStatus.CANCELLED
        assert cancelled_job.finished_timestamp is not None

        # The KB row is gone — the ingestion can no longer rehydrate
        # it because its next ``is_job_cancelled`` poll will trip.
        refetched = await knowledge_base_service.get_by_user_and_name(active_user.id, kb_name)
        assert refetched is None

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_delete_knowledge_base_leaves_unrelated_jobs_alone(
        self,
        mock_root,
        mock_delete,  # noqa: ARG002
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        """Cancel-on-delete must scope strictly to the deleted KB.

        A user with multiple KBs ingesting in parallel should not see
        their OTHER ingestions cancelled when one KB is deleted. The
        scope is enforced via ``(asset_id, asset_type)`` — this test
        regresses against an over-broad query that would match every
        ``IN_PROGRESS`` job.
        """
        from langflow.services.database.models.jobs.model import JobStatus, JobType
        from langflow.services.deps import get_job_service

        mock_root.return_value = tmp_path
        kb_name = "Target_KB"
        other_kb_name = "Untouched_KB"

        target = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name=kb_name,
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
        )
        other = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name=other_kb_name,
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
        )
        for r in (target, other):
            d = tmp_path / active_user.username / r.name
            d.mkdir(parents=True)
            (d / "embedding_metadata.json").write_text(json.dumps({"id": str(r.id)}))

        job_service = get_job_service()
        target_job_id = uuid.uuid4()
        other_job_id = uuid.uuid4()
        for jid, asset_id in ((target_job_id, target.id), (other_job_id, other.id)):
            await job_service.create_job(
                job_id=jid,
                flow_id=jid,
                job_type=JobType.INGESTION,
                asset_id=asset_id,
                asset_type="knowledge_base",
                user_id=active_user.id,
            )
            await job_service.update_job_status(jid, JobStatus.IN_PROGRESS)

        response = await client.delete(
            f"api/v1/knowledge_bases/{kb_name}",
            headers=logged_in_headers,
        )
        assert response.status_code == 200

        target_job = await job_service.get_job_by_job_id(target_job_id)
        other_job = await job_service.get_job_by_job_id(other_job_id)
        assert target_job is not None
        assert target_job.status == JobStatus.CANCELLED
        assert other_job is not None
        assert other_job.status == JobStatus.IN_PROGRESS

    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_knowledge_bases(
        self, mock_root, mock_delete, client: AsyncClient, logged_in_headers, tmp_path
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
        assert mock_delete.called

    @patch("langflow.api.v1.knowledge_bases.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_skips_memory_base_kbs(
        self,
        mock_root,
        mock_delete,
        mock_meta,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
    ):
        # Memory-Base KBs in a bulk request must be reported back as
        # ``memory_base_skipped`` and NOT touched on disk; non-MB KBs in
        # the same request still delete normally.
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        (kb_user_path / "PlainKB").mkdir()
        (kb_user_path / "MBKB").mkdir()

        def fake_meta(kb_path, **_kwargs):
            if kb_path.name == "MBKB":
                return {
                    "id": "00000000-0000-0000-0000-0000000000cc",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "text-embedding-3-small",
                    "source_types": ["memory"],
                }
            return {
                "id": "00000000-0000-0000-0000-0000000000dd",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
            }

        mock_meta.side_effect = fake_meta

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["PlainKB", "MBKB"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert data.get("memory_base_skipped") == "MBKB"
        # delete_storage must only have been called for the non-MB KB.
        deleted_paths = [call.args[0].name for call in mock_delete.call_args_list]
        assert "PlainKB" in deleted_paths
        assert "MBKB" not in deleted_paths

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_path_traversal_single_level(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """Single-level traversal '../victim_user/secret_kb' must be blocked with 403."""
        mock_root.return_value = tmp_path

        (tmp_path / "activeuser").mkdir(parents=True)
        victim_kb = tmp_path / "victim_user" / "secret_kb"
        victim_kb.mkdir(parents=True)

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["../victim_user/secret_kb"]},
        )

        assert response.status_code == 403, (
            f"VULNERABILITY CONFIRMED: server accepted traversal payload with status {response.status_code}"
        )
        assert victim_kb.exists(), "VULNERABILITY CONFIRMED: path traversal deleted another user's KB"

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_path_traversal_multi_level(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """Multi-level traversal '../../other_path' must also be blocked."""
        mock_root.return_value = tmp_path

        (tmp_path / "activeuser").mkdir(parents=True)
        victim_kb = tmp_path / "other_root" / "secret_kb"
        victim_kb.mkdir(parents=True)

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["../../other_root/secret_kb"]},
        )

        assert response.status_code == 403
        assert victim_kb.exists(), "VULNERABILITY CONFIRMED: multi-level traversal deleted data outside user dir"

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_path_traversal_prefix_ambiguity(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """Prefix-ambiguity attack: user='activeuser', target dir='activeuser_evil'.

        With startswith('/root/activeuser'), the path '/root/activeuser_evil/kb' incorrectly
        passes because the string starts with '/root/activeuser'. is_relative_to() closes this gap.
        """
        mock_root.return_value = tmp_path

        (tmp_path / "activeuser").mkdir(parents=True)
        victim_kb = tmp_path / "activeuser_evil" / "secret_kb"
        victim_kb.mkdir(parents=True)

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["../activeuser_evil/secret_kb"]},
        )

        assert response.status_code == 403, (
            "VULNERABILITY CONFIRMED: prefix-ambiguity bypass succeeded — "
            "startswith() may still be in use instead of is_relative_to()"
        )
        assert victim_kb.exists(), "VULNERABILITY CONFIRMED: prefix-ambiguity attack deleted another user's KB"

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_path_traversal_encoded_sequences(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """URL-encoded traversal sequences in the JSON body must not bypass path validation.

        '%2e%2e%2f' in a JSON body is NOT decoded by Python's Path — it is treated as a
        literal directory name, so Path.resolve() keeps it inside the user directory.
        The endpoint must return 404 (no such literal dir) rather than 200.
        """
        mock_root.return_value = tmp_path

        (tmp_path / "activeuser").mkdir(parents=True)
        victim_kb = tmp_path / "victim_user" / "secret_kb"
        victim_kb.mkdir(parents=True)

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["%2e%2e%2fvictim_user%2fsecret_kb"]},
        )

        # The encoded string is not a real directory — expect 404, not 200
        assert response.status_code == 404
        assert victim_kb.exists(), "VULNERABILITY CONFIRMED: encoded traversal deleted another user's KB"

    @patch("langflow.api.v1.knowledge_bases.logger")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_path_traversal_logs_warning(
        self, mock_root, mock_logger, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """A traversal attempt must emit a warning log with user context."""
        mock_root.return_value = tmp_path

        (tmp_path / "activeuser").mkdir(parents=True)
        (tmp_path / "victim_user" / "secret_kb").mkdir(parents=True)

        await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["../victim_user/secret_kb"]},
        )

        mock_logger.warning.assert_called_once()
        warning_args = mock_logger.warning.call_args[0]
        assert "activeuser" in str(warning_args), "Warning log must include the requesting user"

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

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.create_backend")
    async def test_get_chunks_pagination_and_search(
        self, mock_create_backend, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """Chunks endpoint streams through ``backend.iter_documents`` now.

        Old Chroma ``_collection.get`` assertions replaced with a mock
        backend that yields a fixed set of ``IngestedDocument``s — this
        keeps the test backend-agnostic and exercises the new filter +
        paginate-in-Python path that works across Chroma / Mongo /
        Astra / Postgres.
        """
        from lfx.base.knowledge_bases.backends.base import IngestedDocument

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / "activeuser" / "KB1"
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "chroma.sqlite3").write_text("dummy")

        # 25 documents: ids "0" through "24". Two of them contain the
        # substring "needle"; the rest read as "doc N".
        documents = [
            IngestedDocument(
                content="needle match" if idx in {3, 7} else f"doc {idx}",
                metadata={"_id": str(idx)},
            )
            for idx in range(25)
        ]

        async def _iter_documents(*, batch_size: int = 1000, include_embeddings: bool = False):  # noqa: ARG001
            yield documents

        backend = MagicMock()
        backend.iter_documents = _iter_documents
        backend.teardown = AsyncMock()
        mock_create_backend.return_value = backend

        # Search filters client-side and finds both "needle" rows.
        response = await client.get("api/v1/knowledge_bases/KB1/chunks?search=needle", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert [chunk["content"] for chunk in data["chunks"]] == ["needle match", "needle match"]
        assert data["total"] == 2

        # Pagination: page 2 of 10 returns ids "10" through "19".
        response = await client.get("api/v1/knowledge_bases/KB1/chunks?page=2&limit=10", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["total"] == 25
        assert [chunk["id"] for chunk in data["chunks"]] == [str(i) for i in range(10, 20)]

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_get_chunks_non_existent_kb_returns_404(
        self,
        mock_root,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
    ):
        mock_root.return_value = tmp_path

        response = await client.get("api/v1/knowledge_bases/MissingKB/chunks", headers=logged_in_headers)

        assert response.status_code == 404

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.create_backend")
    async def test_get_chunks_metadata_filter(
        self, mock_create_backend, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """``meta_<key>`` query params filter chunks by user-supplied tags.

        Each chunk's user metadata is stored as a JSON string under
        ``source_metadata``. The endpoint decodes that JSON, then AND-matches
        every ``meta_<key>`` value passed by the client. Repeating the same
        key OR-s its values.
        """
        import json as _json

        from lfx.base.knowledge_bases.backends.base import IngestedDocument

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / "activeuser" / "KB1"
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "chroma.sqlite3").write_text("dummy")

        documents = [
            IngestedDocument(
                content="invoice doc",
                metadata={"_id": "1", "source_metadata": _json.dumps({"tag": "invoice", "year": 2026})},
            ),
            IngestedDocument(
                content="report doc",
                metadata={"_id": "2", "source_metadata": _json.dumps({"tag": "report"})},
            ),
            IngestedDocument(
                content="invoice doc 2",
                metadata={"_id": "3", "source_metadata": _json.dumps({"tag": ["invoice", "audit"]})},
            ),
            IngestedDocument(
                content="legacy chunk",
                metadata={"_id": "4"},  # pre-metadata era — no source_metadata at all
            ),
        ]

        async def _iter_documents(*, batch_size: int = 1000, include_embeddings: bool = False):  # noqa: ARG001
            yield documents

        backend = MagicMock()
        backend.iter_documents = _iter_documents
        backend.teardown = AsyncMock()
        mock_create_backend.return_value = backend

        # Single-key string match returns both invoice chunks (one literal, one array).
        response = await client.get(
            "api/v1/knowledge_bases/KB1/chunks",
            params={"meta_tag": "invoice"},
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.json()
        data = response.json()
        assert sorted(chunk["id"] for chunk in data["chunks"]) == ["1", "3"]

        # AND filter: tag=invoice + year=2026 narrows to id 1.
        response = await client.get(
            "api/v1/knowledge_bases/KB1/chunks",
            params=[("meta_tag", "invoice"), ("meta_year", "2026")],
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.json()
        data = response.json()
        assert [chunk["id"] for chunk in data["chunks"]] == ["1"]

        # OR within a key: tag in {report, audit} returns the report doc and
        # the audit-tagged invoice doc.
        response = await client.get(
            "api/v1/knowledge_bases/KB1/chunks",
            params=[("meta_tag", "report"), ("meta_tag", "audit")],
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.json()
        data = response.json()
        assert sorted(chunk["id"] for chunk in data["chunks"]) == ["2", "3"]

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.create_backend")
    async def test_get_metadata_keys_returns_distinct_user_keys(
        self, mock_create_backend, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """``/metadata/keys`` returns distinct user keys + sample values, hides reserved."""
        import json as _json

        from lfx.base.knowledge_bases.backends.base import IngestedDocument

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / "activeuser" / "KB1"
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "chroma.sqlite3").write_text("dummy")

        documents = [
            IngestedDocument(
                content="doc",
                metadata={
                    "_id": "1",
                    "source_metadata": _json.dumps(
                        {
                            # Reserved keys must be excluded from the response.
                            "file_name": "report.pdf",
                            "source": "file_upload",
                            "chunk_index": 0,
                            # User keys.
                            "year": "2020",
                            "dept": "engineering",
                            "tags": ["urgent", "review"],
                        }
                    ),
                },
            ),
            IngestedDocument(
                content="doc 2",
                metadata={
                    "_id": "2",
                    "source_metadata": _json.dumps({"file_name": "doc2.pdf", "year": "2021", "tags": "audit"}),
                },
            ),
            IngestedDocument(
                content="legacy",
                metadata={"_id": "3"},  # pre-metadata era — should be ignored
            ),
        ]

        async def _iter_documents(*, batch_size: int = 1000, include_embeddings: bool = False):  # noqa: ARG001
            yield documents

        backend = MagicMock()
        backend.iter_documents = _iter_documents
        backend.teardown = AsyncMock()
        mock_create_backend.return_value = backend

        response = await client.get(
            "api/v1/knowledge_bases/KB1/metadata/keys",
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.json()
        data = response.json()
        # Reserved keys hidden; user keys surface with insertion-ordered values.
        assert set(data["keys"].keys()) == {"year", "dept", "tags"}
        assert data["keys"]["year"] == ["2020", "2021"]
        assert data["keys"]["dept"] == ["engineering"]
        # Array-valued metadata expands one distinct value per array entry,
        # union-ed with the second doc's "audit" string.
        assert sorted(data["keys"]["tags"]) == ["audit", "review", "urgent"]
        assert data["truncated"] is False

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.create_backend")
    async def test_get_metadata_keys_caps_distinct_values_per_key(
        self, mock_create_backend, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """Distinct values per key are capped — response sets ``truncated=true``."""
        import json as _json

        from langflow.api.v1.knowledge_bases import KB_METADATA_KEYS_VALUES_CAP
        from lfx.base.knowledge_bases.backends.base import IngestedDocument

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / "activeuser" / "KB1"
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "chroma.sqlite3").write_text("dummy")

        documents = [
            IngestedDocument(
                content=f"doc {idx}",
                metadata={"_id": str(idx), "source_metadata": _json.dumps({"variant": str(idx)})},
            )
            for idx in range(KB_METADATA_KEYS_VALUES_CAP + 5)
        ]

        async def _iter_documents(*, batch_size: int = 1000, include_embeddings: bool = False):  # noqa: ARG001
            yield documents

        backend = MagicMock()
        backend.iter_documents = _iter_documents
        backend.teardown = AsyncMock()
        mock_create_backend.return_value = backend

        response = await client.get(
            "api/v1/knowledge_bases/KB1/metadata/keys",
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.json()
        data = response.json()
        assert len(data["keys"]["variant"]) == KB_METADATA_KEYS_VALUES_CAP
        assert data["truncated"] is True

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_get_metadata_keys_empty_kb_returns_empty_response(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """Empty Chroma KB short-circuits before booting the backend client."""
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / "activeuser" / "KB1"
        kb_dir.mkdir(parents=True, exist_ok=True)
        # No chroma.sqlite3 / chroma / index files → short-circuit path.

        response = await client.get(
            "api/v1/knowledge_bases/KB1/metadata/keys",
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.json()
        assert response.json() == {"keys": {}, "truncated": False}


class TestPerformIngestionTask:
    """Tests for the internal KBIngestionHelper.perform_ingestion background task."""

    @patch("langflow.api.utils.ingestion_run_service.finalize_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.mark_running", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.create_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.create_backend")
    @patch("langflow.api.utils.kb_helpers.KBIngestionHelper.build_embeddings", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_directory_size")
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics")
    async def test_perform_ingestion_success(
        self,
        mock_update,
        mock_size,
        mock_meta,
        mock_build,
        mock_backend_cls,
        mock_create_run,
        mock_mark_running,
        mock_finalize_run,
        mock_kb_path,
        sample_text_file,
    ):
        mock_update.return_value = None
        mock_embeddings = MagicMock()
        mock_build.return_value = mock_embeddings

        mock_backend = MagicMock()
        mock_backend.add_documents = AsyncMock()
        mock_backend.teardown = AsyncMock()
        mock_backend.raw_langchain_store = MagicMock(return_value=MagicMock())
        mock_backend_cls.return_value = mock_backend

        run_id = uuid.uuid4()
        mock_create_run.return_value = run_id
        mock_meta.return_value = {"chunks": 5, "size": 100, "source_types": []}
        mock_size.return_value = 100

        file_name, file_content = sample_text_file
        files_data = [(file_name, file_content.encode())]

        current_user = MagicMock()
        current_user.id = uuid.uuid4()

        result = await KBIngestionHelper.perform_ingestion(
            kb_name="test_kb",
            kb_path=mock_kb_path,
            files_data=files_data,
            chunk_size=100,
            chunk_overlap=20,
            separator="\n",
            source_name="src",
            current_user=current_user,
            model_selection={"name": "model", "provider": "OpenAI"},
            task_job_id=uuid.uuid4(),
            job_service=AsyncMock(),
        )

        assert result["ingestion_run_id"] == str(run_id)
        mock_backend.add_documents.assert_called()
        mock_backend.teardown.assert_awaited()
        mock_create_run.assert_awaited_once()
        mock_mark_running.assert_awaited_once_with(run_id)
        mock_finalize_run.assert_awaited_once()

        # Finalize should mark the run SUCCEEDED when every item lands.
        finalize_kwargs = mock_finalize_run.await_args.kwargs
        from lfx.base.knowledge_bases.ingestion_sources.base import IngestionRunStatus

        assert finalize_kwargs["status"] is IngestionRunStatus.SUCCEEDED
        assert finalize_kwargs["summary"].succeeded == 1
        assert finalize_kwargs["summary"].failed == 0

        # Every chunk should carry the default ingestion-source-type tag so
        # Phase 2 visibility tooling can key off origin.
        written_docs = [doc for call in mock_backend.add_documents.call_args_list for doc in call.args[0]]
        assert written_docs, "expected at least one chunk document to be written"
        assert all(doc.metadata.get("source_type") == "file_upload" for doc in written_docs)

    @patch("langflow.api.utils.ingestion_run_service.finalize_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.mark_running", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.create_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.create_backend")
    @patch("langflow.api.utils.kb_helpers.KBIngestionHelper.build_embeddings", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_directory_size")
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics_via_backend", new_callable=AsyncMock)
    async def test_perform_ingestion_skipped_only_is_partial(
        self,
        mock_update_metrics,  # noqa: ARG002
        mock_size,
        mock_meta,
        mock_build,
        mock_backend_cls,
        mock_create_run,
        mock_mark_running,  # noqa: ARG002
        mock_finalize_run,
        mock_kb_path,
        whitespace_text_file,
    ):
        """Files with no extractable text are SKIPPED.

        Regression test for the QA-reported bug where a run that
        produced 0 successful items but 1 skipped item was finalized
        as SUCCEEDED. The expected outcome is PARTIAL so the UI can
        signal that nothing was actually ingested.
        """
        mock_embeddings = MagicMock()
        mock_build.return_value = mock_embeddings

        mock_backend = MagicMock()
        mock_backend.add_documents = AsyncMock()
        mock_backend.teardown = AsyncMock()
        mock_backend.raw_langchain_store = MagicMock(return_value=MagicMock())
        mock_backend_cls.return_value = mock_backend

        run_id = uuid.uuid4()
        mock_create_run.return_value = run_id
        mock_meta.return_value = {"chunks": 0, "size": 0, "source_types": []}
        mock_size.return_value = 0

        file_name, file_content = whitespace_text_file
        files_data = [(file_name, file_content.encode())]

        current_user = MagicMock()
        current_user.id = uuid.uuid4()

        await KBIngestionHelper.perform_ingestion(
            kb_name="test_kb",
            kb_path=mock_kb_path,
            files_data=files_data,
            chunk_size=100,
            chunk_overlap=20,
            separator="\n",
            source_name="src",
            current_user=current_user,
            model_selection={"name": "model", "provider": "OpenAI"},
            task_job_id=uuid.uuid4(),
            job_service=AsyncMock(),
        )

        from lfx.base.knowledge_bases.ingestion_sources.base import IngestionRunStatus

        mock_finalize_run.assert_awaited_once()
        finalize_kwargs = mock_finalize_run.await_args.kwargs
        assert finalize_kwargs["status"] is IngestionRunStatus.PARTIAL
        assert finalize_kwargs["summary"].succeeded == 0
        assert finalize_kwargs["summary"].failed == 0
        assert finalize_kwargs["summary"].skipped == 1
        # No docs should have been written when every item was skipped.
        mock_backend.add_documents.assert_not_called()

    @patch("langflow.api.utils.ingestion_run_service.finalize_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.mark_running", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.create_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.knowledge_base_service.get_by_user_and_name", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.create_backend")
    @patch("langflow.api.utils.kb_helpers.KBIngestionHelper.build_embeddings", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.get_metadata")
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_directory_size")
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics_via_backend", new_callable=AsyncMock)
    async def test_perform_ingestion_routes_through_configured_backend(
        self,
        mock_update_metrics,
        mock_size,
        mock_meta,
        mock_build,
        mock_create_backend,
        mock_get_kb,
        mock_create_run,
        mock_mark_running,  # noqa: ARG002
        mock_finalize_run,  # noqa: ARG002
        mock_kb_path,
        sample_text_file,
    ):
        mock_embeddings = MagicMock()
        mock_build.return_value = mock_embeddings

        kb_record = MagicMock()
        kb_record.id = uuid.uuid4()
        kb_record.backend_type = "opensearch"
        kb_record.backend_config = {"index_name": "kb_idx", "url_variable": "OPENSEARCH_URL"}
        mock_get_kb.return_value = kb_record

        mock_backend = MagicMock()
        mock_backend.add_documents = AsyncMock()
        mock_backend.teardown = AsyncMock()
        mock_create_backend.return_value = mock_backend

        run_id = uuid.uuid4()
        mock_create_run.return_value = run_id
        mock_meta.return_value = {"chunks": 0, "size": 0, "source_types": []}
        mock_size.return_value = 0

        file_name, file_content = sample_text_file
        current_user = MagicMock()
        current_user.id = uuid.uuid4()

        result = await KBIngestionHelper.perform_ingestion(
            kb_name="test_kb",
            kb_path=mock_kb_path,
            files_data=[(file_name, file_content.encode())],
            chunk_size=100,
            chunk_overlap=20,
            separator="\n",
            source_name="src",
            current_user=current_user,
            model_selection={"name": "model", "provider": "OpenAI"},
            task_job_id=uuid.uuid4(),
            job_service=AsyncMock(),
        )

        assert result["ingestion_run_id"] == str(run_id)
        mock_create_run.assert_awaited_once()
        assert mock_create_run.await_args.kwargs["kb_id"] == kb_record.id
        mock_create_backend.assert_called_once()
        assert mock_create_backend.call_args.args == ("opensearch",)
        backend_kwargs = mock_create_backend.call_args.kwargs
        assert backend_kwargs["backend_config"] == kb_record.backend_config
        assert backend_kwargs["embedding_function"] is mock_embeddings
        assert backend_kwargs["user_id"] == current_user.id
        mock_update_metrics.assert_awaited_once_with(mock_meta.return_value, mock_backend)

    @patch("langflow.api.utils.ingestion_run_service.finalize_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.mark_running", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.create_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.create_backend")
    @patch("langflow.api.utils.kb_helpers.KBIngestionHelper.build_embeddings", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.KBIngestionHelper.cleanup_chroma_chunks_by_job", new_callable=AsyncMock)
    async def test_perform_ingestion_rollback(
        self,
        mock_cleanup,
        mock_build,
        mock_backend_cls,
        mock_create_run,
        mock_mark_running,  # noqa: ARG002 — patched to keep ingestion_run DB calls out of this test
        mock_finalize_run,
        mock_kb_path,
    ):
        """Write-loop errors that exhaust retries must propagate and trigger rollback."""
        mock_backend = MagicMock()
        mock_backend.add_documents = AsyncMock(side_effect=Exception("Chroma error"))
        mock_backend.teardown = AsyncMock()
        mock_backend.raw_langchain_store = MagicMock(return_value=MagicMock())
        mock_backend_cls.return_value = mock_backend
        mock_create_run.return_value = uuid.uuid4()

        files_data = [("test.txt", b"content")]
        job_id = uuid.uuid4()

        current_user = MagicMock()
        current_user.id = uuid.uuid4()

        with pytest.raises(Exception, match="Chroma error"):
            await KBIngestionHelper.perform_ingestion(
                kb_name="test_kb",
                kb_path=mock_kb_path,
                files_data=files_data,
                chunk_size=100,
                chunk_overlap=20,
                separator="\n",
                source_name="src",
                current_user=current_user,
                model_selection={"name": "model", "provider": "OpenAI"},
                task_job_id=job_id,
                job_service=AsyncMock(),
            )

        mock_build.assert_called_once()
        # Rollback now threads optional backend info through so
        # non-Chroma backends can clean up; assert by positional tuple.
        mock_cleanup.assert_called_once()
        call_args = mock_cleanup.call_args
        assert call_args.args == (job_id, mock_kb_path, "test_kb")
        mock_backend.teardown.assert_awaited()
        # The run row must still be finalized even on error so the
        # visibility UI doesn't show stuck RUNNING rows.
        mock_finalize_run.assert_awaited_once()
        finalize_kwargs = mock_finalize_run.await_args.kwargs
        from lfx.base.knowledge_bases.ingestion_sources.base import IngestionRunStatus

        assert finalize_kwargs["status"] is IngestionRunStatus.FAILED
        assert finalize_kwargs["error_message"] == "Chroma error"


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
