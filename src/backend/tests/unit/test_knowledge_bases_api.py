import io
import json
import uuid
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from httpx import AsyncClient
from langchain_core.documents import Document
from langflow.api.utils import knowledge_base_service
from langflow.api.utils.kb_helpers import (
    KBAnalysisHelper,
    KBIngestionHelper,
    KBStorageHelper,
)
from lfx.base.knowledge_bases.backends.base import BackendConfigurationError


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


@pytest.fixture
def seed_kb(active_user):
    """Create a ``knowledge_base`` row — the only thing that makes a KB exist.

    Every route resolves identity, embedding config, and backend routing from
    this row, so tests seed it rather than writing an on-disk sidecar.
    """

    async def _seed(name: str, *, backend_type: str = "chroma", backend_config: dict | None = None, **kwargs):
        return await knowledge_base_service.create_record(
            user_id=active_user.id,
            name=name,
            model_selection=kwargs.pop("model_selection", {"name": "model", "provider": "OpenAI"}),
            backend_type=backend_type,
            backend_config=backend_config or {},
            **kwargs,
        )

    return _seed


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

    def test_calculate_text_metrics(self):
        df = pd.DataFrame({"text": ["hello world", "foo bar baz"]})
        words, chars = KBAnalysisHelper._calculate_text_metrics(df, ["text"])
        assert words == 5
        assert chars == 22

    @pytest.mark.parametrize(
        "name",
        [
            "my_kb",
            "docs v1.2",  # dots are fine — not a traversal segment
            "a.b.c",
            "kb_2024",
        ],
    )
    def test_validate_kb_name_accepts_legitimate_names(self, name):
        from langflow.api.utils.kb_helpers import validate_kb_name

        validate_kb_name(name)  # must not raise

    @pytest.mark.parametrize(
        "name",
        [
            "",
            ".",
            "..",
            "../victim_user/evil_kb",
            "../../etc/passwd",
            "a/b",
            "a\\b",
            "/var/evil",  # absolute path — dropped to the leading '/' separator
            "kb\x00name",
        ],
    )
    def test_validate_kb_name_rejects_traversal_and_separators(self, name):
        from langflow.api.utils.kb_helpers import validate_kb_name

        with pytest.raises(ValueError):  # noqa: PT011
            validate_kb_name(name)


class TestWriteDocumentsRetry:
    """The ingest retry loop must skip permanent, operator-actionable errors.

    Missing-extension and dimension-mismatch surface as ``BackendConfigurationError``;
    retrying them only burns the ~20s backoff budget on a call that cannot succeed.
    """

    @staticmethod
    def _fresh_job_service():
        # ``is_job_cancelled`` treats a missing job as "not cancelled".
        service = MagicMock()
        service.get_job_by_job_id = AsyncMock(return_value=None)
        return service

    async def test_backend_configuration_error_is_not_retried(self):
        backend = MagicMock()
        backend.add_documents = AsyncMock(side_effect=BackendConfigurationError("missing extension"))

        with (
            patch("langflow.api.utils.kb_helpers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            pytest.raises(BackendConfigurationError),
        ):
            await KBIngestionHelper.write_documents_to_backend(
                documents=[Document(page_content="a")],
                backend=backend,
                task_job_id=uuid.uuid4(),
                job_service=self._fresh_job_service(),
            )

        assert backend.add_documents.await_count == 1  # raised on the first attempt
        mock_sleep.assert_not_awaited()  # and never backed off

    async def test_transient_error_is_retried(self):
        backend = MagicMock()
        backend.add_documents = AsyncMock(side_effect=[RuntimeError("boom"), None])

        with patch("langflow.api.utils.kb_helpers.asyncio.sleep", new_callable=AsyncMock):
            written = await KBIngestionHelper.write_documents_to_backend(
                documents=[Document(page_content="a")],
                backend=backend,
                task_job_id=uuid.uuid4(),
                job_service=self._fresh_job_service(),
            )

        assert written == 1
        assert backend.add_documents.await_count == 2  # retried once, then succeeded


class TestProductionProfileRejectsLocalChroma:
    """Local Chroma is a dev-only backend: its vectors live on the serving box's disk."""

    @pytest.fixture
    def prod_profile(self, client, monkeypatch):  # noqa: ARG002
        """Switch the running app to the production profile.

        Depends on ``client`` so it is applied *after* the app fixture
        initializes services — that init rebuilds the settings service and would
        otherwise discard the patch.
        """
        from langflow.services.deps import get_settings_service

        monkeypatch.setattr(get_settings_service().settings, "deployment_profile", "prod")

    async def test_create_knowledge_base_with_explicit_local_chroma_is_rejected(
        self,
        prod_profile,  # noqa: ARG002 — fixture applied for its side effect
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
        monkeypatch,
    ):
        from langflow.api.v1 import knowledge_bases as kb_api

        # Point at an empty root so a stray directory from another run cannot
        # make this pass or fail for the wrong reason.
        monkeypatch.setattr(kb_api.KBStorageHelper, "get_root_path", MagicMock(return_value=tmp_path))
        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "Prod_Local_KB",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
                "backend_type": "chroma",
                "backend_config": {},
            },
        )
        assert response.status_code == 422, response.json()
        assert "production deployment profile" in response.json()["detail"]
        # Nothing was persisted — the rejection happens before any state is created.
        assert await knowledge_base_service.get_by_user_and_name(active_user.id, "Prod_Local_KB") is None

    async def test_create_knowledge_base_with_chroma_cloud_is_allowed(
        self,
        prod_profile,  # noqa: ARG002 — fixture applied for its side effect
        client: AsyncClient,
        logged_in_headers,
        active_user,
    ):
        """Chroma *Cloud* is a remote store and stays available under prod.

        Both modes share ``backend_type="chroma"``; only ``backend_config["mode"]``
        distinguishes them, so this guards against the guard being too broad.
        """
        from lfx.base.knowledge_bases.backends.base import TestConnectionResult
        from lfx.base.knowledge_bases.backends.chroma import ChromaCloudBackend

        connection_result = TestConnectionResult(ok=True, message="Connected")
        with patch.object(ChromaCloudBackend, "test_connection", new=AsyncMock(return_value=connection_result)):
            response = await client.post(
                "api/v1/knowledge_bases",
                headers=logged_in_headers,
                json={
                    "name": "Prod_Cloud_KB",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "text-embedding-3-small",
                    "backend_type": "chroma",
                    "backend_config": {"mode": "cloud"},
                },
            )
        assert response.status_code == 201, response.json()
        record = await knowledge_base_service.get_by_user_and_name(active_user.id, "Prod_Cloud_KB")
        assert record is not None
        assert record.backend_config == {"mode": "cloud"}

    async def test_dev_profile_still_allows_local_chroma(
        self, client: AsyncClient, logged_in_headers, active_user, tmp_path, monkeypatch
    ):
        """The default profile is unaffected — local Chroma keeps working for dev."""
        from langflow.api.v1 import knowledge_bases as kb_api
        from langflow.services.deps import get_settings_service

        monkeypatch.setattr(get_settings_service().settings, "deployment_profile", "dev")
        monkeypatch.setattr(kb_api.KBStorageHelper, "get_root_path", MagicMock(return_value=tmp_path))
        monkeypatch.setattr(kb_api.KBStorageHelper, "get_fresh_chroma_client", MagicMock())

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "Dev_Local_KB",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
                "backend_type": "chroma",
                "backend_config": {},
            },
        )
        assert response.status_code == 201, response.json()
        assert (tmp_path / active_user.username / "Dev_Local_KB").is_dir()

    async def test_create_memory_base_with_local_chroma_is_rejected(
        self,
        prod_profile,  # noqa: ARG002 — fixture applied for its side effect
    ):
        from langflow.services.memory_base.kb_path_helpers import BackendProvisioningError
        from langflow.services.memory_base.service import MemoryBaseService

        payload = MagicMock(backend_type="chroma", backend_config={})
        with pytest.raises(BackendProvisioningError, match="production deployment profile"):
            await MemoryBaseService().create(payload, user_id=uuid.uuid4())


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

    async def test_preview_chunks_rejects_overlap_larger_than_size(
        self, client: AsyncClient, logged_in_headers, sample_text_file
    ):
        """Reject overlap > size — it fails the splitter — with a clear 422.

        Both values stay within their own Form bounds, so this exercises the
        cross-field guard rather than the per-field ge/le validation (which
        would 422 with a generic pydantic message).
        """
        file_name, file_content = sample_text_file
        response = await client.post(
            "api/v1/knowledge_bases/preview-chunks",
            headers=logged_in_headers,
            files={"files": (file_name, io.BytesIO(file_content.encode()), "text/plain")},
            data={"chunk_size": "100", "chunk_overlap": "200"},
        )

        assert response.status_code == 422, response.text
        assert "chunk size" in response.json()["detail"].lower()


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
        from lfx.base.knowledge_bases.backends.base import TestConnectionResult
        from lfx.base.knowledge_bases.backends.opensearch import OpenSearchBackend

        connection_result = TestConnectionResult(ok=True, message="Connected")
        with patch.object(OpenSearchBackend, "test_connection", new=AsyncMock(return_value=connection_result)):
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
        mock_fresh_client.assert_not_called()
        record = await knowledge_base_service.get_by_user_and_name(active_user.id, kb_name)
        assert record is not None
        assert record.model_selection == model_selection
        assert record.backend_type == "opensearch"
        # A remote-backed KB touches no local storage at all: no directory, and
        # certainly no metadata sidecar.
        assert not (tmp_path / active_user.username / kb_name).exists()

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_legacy_request_without_model_selection(
        self,
        mock_root,
        mock_fresh_client,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
        monkeypatch,
    ):
        from langflow.api.v1 import knowledge_bases as kb_api

        mock_fresh_client.return_value = MagicMock()
        mock_root.return_value = tmp_path
        policy_check = MagicMock()
        monkeypatch.setattr(kb_api, "require_model_provider", policy_check)
        kb_name = "Legacy_KB_No_Selection"

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
        record = await knowledge_base_service.get_by_user_and_name(active_user.id, kb_name)
        assert record is not None
        assert record.model_selection == {
            "name": "text-embedding-3-small",
            "provider": "OpenAI",
        }
        policy_check.assert_called_once()

    async def test_create_rejects_disagreeing_embedding_providers_before_storage_or_db(
        self, client: AsyncClient, logged_in_headers, monkeypatch
    ):
        from langflow.api.v1 import knowledge_bases as kb_api

        root_path = MagicMock()
        guard = AsyncMock()
        policy_check = MagicMock()
        monkeypatch.setattr(kb_api.KBStorageHelper, "get_root_path", root_path)
        monkeypatch.setattr(kb_api, "_guard_kb_action", guard)
        monkeypatch.setattr(kb_api, "require_model_provider", policy_check)

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "Spoofed Provider KB",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
                "model_selection": {
                    "name": "text-embedding-3-small",
                    "provider": "Anthropic",
                },
            },
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Model provider not found"}
        root_path.assert_not_called()
        guard.assert_not_awaited()
        policy_check.assert_not_called()

    async def test_create_denied_embedding_provider_is_hidden_before_storage_or_db(
        self, client: AsyncClient, logged_in_headers, monkeypatch
    ):
        from langflow.api.v1 import knowledge_bases as kb_api
        from lfx.services.model_provider_policy import ModelProviderPolicyError, ModelProviderPolicyPurpose

        root_path = MagicMock()
        guard = AsyncMock()
        policy_check = MagicMock(
            side_effect=ModelProviderPolicyError("anthropic", ModelProviderPolicyPurpose.CONFIGURE)
        )
        monkeypatch.setattr(kb_api.KBStorageHelper, "get_root_path", root_path)
        monkeypatch.setattr(kb_api, "_guard_kb_action", guard)
        monkeypatch.setattr(kb_api, "require_model_provider", policy_check)

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "Denied Provider KB",
                "embedding_provider": "Anthropic",
                "embedding_model": "claude-embed",
                "model_selection": {"name": "claude-embed", "provider": "Anthropic"},
            },
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Model provider not found"}
        root_path.assert_not_called()
        guard.assert_not_awaited()
        policy_check.assert_called_once_with(
            user_id=ANY,
            provider="Anthropic",
            purpose=ModelProviderPolicyPurpose.CONFIGURE,
        )

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

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_fresh_chroma_client")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_knowledge_base_opensearch_without_index_name(
        self, mock_root, mock_fresh_client, client: AsyncClient, logged_in_headers, tmp_path
    ):
        # OpenSearch KBs no longer require an ``index_name`` in
        # ``backend_config``: the backend derives a unique index per KB from
        # its name and creates it lazily on first write. An empty
        # ``backend_config`` must therefore be accepted, not rejected.
        from lfx.base.knowledge_bases.backends.base import TestConnectionResult
        from lfx.base.knowledge_bases.backends.opensearch import OpenSearchBackend

        mock_fresh_client.return_value = MagicMock()
        mock_root.return_value = tmp_path
        connection_result = TestConnectionResult(ok=True, message="Connected")
        with patch.object(OpenSearchBackend, "test_connection", new=AsyncMock(return_value=connection_result)):
            response = await client.post(
                "api/v1/knowledge_bases",
                headers=logged_in_headers,
                json={
                    "name": "OpenSearch_No_Index_KB",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "text-embedding-3-small",
                    "backend_type": "opensearch",
                    "backend_config": {},
                },
            )

        assert response.status_code == 201, response.text
        data = response.json()
        assert data["backend_type"] == "opensearch"
        # No shared index pinned into the config — the index is derived per-KB.
        assert "index_name" not in data["backend_config"]
        mock_fresh_client.assert_not_called()

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_knowledge_base_postgres_persists_backend(
        self,
        mock_root,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
    ):
        from lfx.base.knowledge_bases.backends.base import TestConnectionResult
        from lfx.base.knowledge_bases.backends.postgres import PostgresBackend

        mock_root.return_value = tmp_path
        connection_result = TestConnectionResult(ok=True, message="Connected")
        with patch.object(PostgresBackend, "test_connection", new=AsyncMock(return_value=connection_result)):
            response = await client.post(
                "api/v1/knowledge_bases",
                headers=logged_in_headers,
                json={
                    "name": "Postgres_KB",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "text-embedding-3-small",
                    "backend_type": "postgres",
                    "backend_config": {},
                },
            )

        assert response.status_code == 201, response.text
        assert response.json()["backend_type"] == "postgres"
        assert response.json()["backend_config"] == {}
        record = await knowledge_base_service.get_by_user_and_name(active_user.id, "Postgres_KB")
        assert record is not None
        assert record.backend_type == "postgres"
        assert record.backend_config == {}

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_create_knowledge_base_rejects_unreachable_remote_backend(
        self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        """A KB create against an unreachable remote backend is refused with 422.

        The availability gate now covers every remote backend, not just pgvector,
        mirroring the Memory Base path: an OpenSearch cluster (or Chroma Cloud,
        Mongo, Astra) that fails its connectivity probe is rejected up front
        instead of persisting a KB that only errors on first ingestion.
        """
        from lfx.base.knowledge_bases.backends.base import TestConnectionResult
        from lfx.base.knowledge_bases.backends.opensearch import OpenSearchBackend

        mock_root.return_value = tmp_path
        connection_result = TestConnectionResult(ok=False, message="Could not reach the cluster.")
        with patch.object(OpenSearchBackend, "test_connection", new=AsyncMock(return_value=connection_result)):
            response = await client.post(
                "api/v1/knowledge_bases",
                headers=logged_in_headers,
                json={
                    "name": "Unreachable_OS_KB",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "text-embedding-3-small",
                    "backend_type": "opensearch",
                    "backend_config": {"index_name": "unreachable_idx"},
                },
            )

        assert response.status_code == 422, response.text
        assert "could not reach the cluster" in response.text.lower()
        # The gate runs before persistence, so nothing is left behind.
        record = await knowledge_base_service.get_by_user_and_name(active_user.id, "Unreachable_OS_KB")
        assert record is None

    async def test_create_knowledge_base_rejects_stubbed_backend(self, client: AsyncClient, logged_in_headers):
        """Stubbed backends fail at the schema layer with a "not enabled" message.

        The ``BackendType`` enum still includes ``mongodb``/``astra`` for DB row
        compatibility, but ``validate_backend_type`` rejects them so a user
        posting one gets a clear 422 instead of a successful create followed by
        ingest-time NotImplementedError. (``postgres`` is now creation-enabled.)
        """
        for stubbed in ("mongodb", "astra"):
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

    async def test_test_connection_does_not_require_index_name(self, client: AsyncClient, logged_in_headers):
        # ``index_name`` is no longer a required field — the index is derived
        # per-KB and created lazily — so a config without it must pass request
        # validation (no 422) and reach the connectivity check. With no
        # OPENSEARCH_URL secret configured in the test env, that check reports
        # ok=False, but the request itself is accepted.
        response = await client.post(
            "api/v1/knowledge_bases/test-connection",
            headers=logged_in_headers,
            json={"backend_type": "opensearch", "backend_config": {}},
        )
        assert response.status_code == 200, response.text
        assert response.json()["ok"] is False

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

    @pytest.mark.parametrize(
        ("backend_type", "backend_config"),
        [
            ("opensearch", {}),
            ("postgres", {}),
            ("chroma", {"mode": "cloud"}),
        ],
    )
    async def test_create_kb_path_traversal_blocked_on_remote_backend(
        self, client: AsyncClient, logged_in_headers, active_user, backend_type, backend_config
    ):
        """Traversal names must be rejected on remote backends too — regression for the bypass.

        Remote backends resolve no local path, so the containment guard in
        ``resolve_local_store_path`` never runs for them. Name validation must
        therefore happen before backend routing, otherwise a name like
        ``../victim_user/evil_kb`` is accepted and persisted verbatim (no 422
        connectivity check is ever reached because the traversal name is caught
        first).
        """
        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": "../victim_user/evil_kb",
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
                "backend_type": backend_type,
                "backend_config": backend_config,
            },
        )

        assert response.status_code == 403, (
            f"VULNERABILITY CONFIRMED: traversal name accepted on {backend_type!r} with status {response.status_code}"
        )
        # Nothing was persisted under the crafted name.
        assert await knowledge_base_service.get_by_user_and_name(active_user.id, "../victim_user/evil_kb") is None

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

    @pytest.mark.parametrize(
        "name",
        ["Q&A docs", "catálogo-produtos", "trailing_", "docs..v2", "127.0.0.1", "a" * 513],
    )
    async def test_create_kb_rejects_chroma_incompatible_name_before_persistence(
        self,
        name,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        monkeypatch,
    ):
        from langflow.api.v1 import knowledge_bases as kb_api

        root_path = MagicMock()
        monkeypatch.setattr(kb_api.KBStorageHelper, "get_root_path", root_path)

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": name,
                "embedding_provider": "OpenAI",
                "embedding_model": "model",
            },
        )

        assert response.status_code == 400, response.text
        assert "3-512 characters" in response.json()["detail"]
        root_path.assert_not_called()
        normalized_name = name.strip().replace(" ", "_")
        assert await knowledge_base_service.get_by_user_and_name(active_user.id, normalized_name) is None

    @pytest.mark.parametrize("name", ["docs.v2", "a" * 100, "topology+collection"])
    async def test_create_kb_accepts_full_chroma_name_contract(
        self,
        name,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        tmp_path,
        monkeypatch,
    ):
        from langflow.api.v1 import knowledge_bases as kb_api

        mock_chroma_client = MagicMock()
        monkeypatch.setattr(kb_api.KBStorageHelper, "get_root_path", MagicMock(return_value=tmp_path))
        monkeypatch.setattr(
            kb_api.KBStorageHelper,
            "get_fresh_chroma_client",
            MagicMock(return_value=mock_chroma_client),
        )

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": name,
                "embedding_provider": "OpenAI",
                "embedding_model": "model",
            },
        )

        assert response.status_code == 201, response.text
        mock_chroma_client.create_collection.assert_called_once()
        assert await knowledge_base_service.get_by_user_and_name(active_user.id, name) is not None

    async def test_create_kb_rejects_name_too_long_for_local_chroma(
        self,
        client: AsyncClient,
        logged_in_headers,
        active_user,
        monkeypatch,
    ):
        from langflow.api.v1 import knowledge_bases as kb_api

        root_path = MagicMock()
        monkeypatch.setattr(kb_api.KBStorageHelper, "get_root_path", root_path)
        name = "a" * 256

        response = await client.post(
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={
                "name": name,
                "embedding_provider": "OpenAI",
                "embedding_model": "model",
            },
        )

        assert response.status_code == 400, response.text
        assert "at most 255 characters for local Chroma storage" in response.json()["detail"]
        root_path.assert_not_called()
        assert await knowledge_base_service.get_by_user_and_name(active_user.id, name) is None

    async def test_create_kb_does_not_apply_chroma_rules_to_postgres(
        self,
        client: AsyncClient,
        logged_in_headers,
        active_user,
    ):
        from lfx.base.knowledge_bases.backends.base import TestConnectionResult
        from lfx.base.knowledge_bases.backends.postgres import PostgresBackend

        connection_result = TestConnectionResult(ok=True, message="Connected")
        with patch.object(PostgresBackend, "test_connection", new=AsyncMock(return_value=connection_result)):
            response = await client.post(
                "api/v1/knowledge_bases",
                headers=logged_in_headers,
                json={
                    "name": "Q&A_docs",
                    "embedding_provider": "OpenAI",
                    "embedding_model": "model",
                    "backend_type": "postgres",
                    "backend_config": {},
                },
            )

        assert response.status_code == 201, response.text
        record = await knowledge_base_service.get_by_user_and_name(active_user.id, "Q&A_docs")
        assert record is not None
        assert record.backend_type == "postgres"

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
    async def test_list_ignores_kb_directories_with_no_database_row(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """A sidecar-only directory is invisible: the ``knowledge_base`` row is the authority.

        The list endpoint used to disk-scan when a user had zero rows. That made
        the result depend on which replica served the request and re-surfaced
        directories whose bytes survived a delete. Adopting a legacy directory is
        now an explicit operator action (``langflow reconcile-kb-from-disk``).
        """
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True, exist_ok=True)
        kb_path = kb_user_path / "Orphan_Dir_KB"
        kb_path.mkdir(exist_ok=True)
        (kb_path / "embedding_metadata.json").write_text(
            json.dumps(
                {
                    "chunks": 10,
                    "embedding_provider": "OpenAI",
                    "embedding_model": "model",
                    "id": str(uuid.uuid4()),
                    "backend_type": "opensearch",
                    "backend_config": {"index_name": "kb1_index"},
                }
            )
        )

        response = await client.get("api/v1/knowledge_bases", headers=logged_in_headers)
        assert response.status_code == 200
        assert not any(kb["dir_name"] == "Orphan_Dir_KB" for kb in response.json())

    async def test_remote_backed_kb_is_listable_without_any_local_storage(
        self, client: AsyncClient, logged_in_headers, active_user, tmp_path, monkeypatch
    ):
        """The enterprise shape: no local KB directory anywhere, everything still works.

        ``knowledge_bases_dir`` points at a path that does not exist, so any code
        path that still reached for the filesystem would fail loudly here.
        """
        from langflow.api.v1 import knowledge_bases as kb_api

        missing_root = tmp_path / "does" / "not" / "exist"
        monkeypatch.setattr(kb_api.KBStorageHelper, "get_root_path", MagicMock(return_value=missing_root))

        await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="Remote_Only_KB",
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
            backend_type="opensearch",
            backend_config={"index_name": "remote_only"},
        )

        listing = await client.get("api/v1/knowledge_bases", headers=logged_in_headers)
        assert listing.status_code == 200
        assert any(kb["dir_name"] == "Remote_Only_KB" for kb in listing.json())

        detail = await client.get("api/v1/knowledge_bases/Remote_Only_KB", headers=logged_in_headers)
        assert detail.status_code == 200
        assert detail.json()["backend_type"] == "opensearch"
        assert not missing_root.exists()

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_get_knowledge_base_detail(
        self, mock_root, client: AsyncClient, logged_in_headers, active_user, tmp_path
    ):
        mock_root.return_value = tmp_path
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="Detail_KB",
            model_selection={"name": "model", "provider": "OpenAI"},
            backend_type="postgres",
            backend_config={"collection_name": "detail_kb"},
            chunks=5,
            words=50,
            characters=250,
            size_bytes=100,
        )
        assert record is not None

        response = await client.get("api/v1/knowledge_bases/Detail_KB", headers=logged_in_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["chunks"] == 5
        assert data["name"] == "Detail KB"
        assert data["backend_type"] == "postgres"
        assert data["backend_config"] == {"collection_name": "detail_kb"}

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_get_knowledge_base_detail_404s_for_directory_without_row(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path
    ):
        """A directory with a sidecar but no row does not exist as far as the API is concerned."""
        mock_root.return_value = tmp_path
        kb_path = tmp_path / "activeuser" / "Sidecar_Only_KB"
        kb_path.mkdir(parents=True)
        (kb_path / "embedding_metadata.json").write_text(
            json.dumps({"embedding_provider": "OpenAI", "embedding_model": "model"})
        )

        response = await client.get("api/v1/knowledge_bases/Sidecar_Only_KB", headers=logged_in_headers)
        assert response.status_code == 404

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
        mock_delete_record.assert_awaited_once()
        # An OpenSearch-backed KB has no local storage to remove, so the
        # filesystem is never touched — not even to check.
        mock_delete.assert_not_called()
        assert mock_create_backend.call_args.kwargs["kb_path"] is None

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

        # The row delete still runs and succeeds. Astra keeps nothing on this
        # box, so there is no local storage step to run.
        assert response.status_code == 200
        assert not mock_delete.called
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
        """A remote-backed KB with no local directory must still be deletable.

        Regression for the Astra delete bug: the endpoint used to require the
        directory to exist, so a remote-backed KB (which never has one) 404'd on
        delete while the list endpoint — reading the DB row — kept showing it.
        The UI was stuck. Existence is the row's call now, so this is the normal
        path rather than a special case.
        """
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser").mkdir(parents=True, exist_ok=True)
        # A row, and no on-disk directory — the ordinary shape for a
        # remote-backed KB.
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

        # A row is all a KB needs to exist; the local-Chroma directory is
        # created here only so the storage-cleanup step has something to remove.
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name=kb_name,
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
        )
        (tmp_path / active_user.username / kb_name).mkdir(parents=True)

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
        self, mock_root, mock_delete, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        for name in ("KB1", "KB2"):
            (kb_user_path / name).mkdir()
            await seed_kb(name)

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

    @patch("langflow.api.utils.knowledge_base_service.get_by_user_and_name")
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_skips_memory_base_kbs(
        self,
        mock_root,
        mock_delete,
        mock_get_record,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
    ):
        # Memory-Base KBs in a bulk request must be reported back as
        # ``memory_base_skipped`` and NOT touched on disk; non-MB KBs in
        # the same request still delete normally.
        #
        # Detection is DB-backed: Memory Bases no longer write the on-disk
        # sidecar, so the marker is read from the ``knowledge_base`` row's
        # ``source_types`` (via ``get_by_user_and_name``), not ``get_metadata``.
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)
        (kb_user_path / "PlainKB").mkdir()
        (kb_user_path / "MBKB").mkdir()

        def fake_record(_user_id, name):
            # ``user_id`` a non-UUID so ``_guard_kb_action`` keeps the actor as
            # the owner; ``source_types`` carries the Memory-Base marker on MBKB.
            return MagicMock(
                id=uuid.uuid4(),
                user_id=MagicMock(),
                source_types=["memory"] if name == "MBKB" else [],
                backend_type="chroma",
                backend_config={},
                model_selection={"name": "m", "provider": "OpenAI"},
            )

        mock_get_record.side_effect = fake_record

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

    @patch("langflow.api.v1.knowledge_bases.create_backend")
    @patch("langflow.api.utils.knowledge_base_service.get_by_user_and_name")
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.delete_storage", return_value=True)
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_skips_memory_base_with_missing_local_dir(
        self,
        mock_root,
        mock_delete,
        mock_get_record,
        mock_create_backend,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
    ):
        # A remote-backed Memory Base with no local directory must still be
        # protected: the DB-backed guard runs FIRST, so neither the remote
        # collection nor the KB row is ever touched for it.
        mock_root.return_value = tmp_path
        kb_user_path = tmp_path / "activeuser"
        kb_user_path.mkdir(parents=True)  # note: no "MBKB" subdir — it is remote-backed

        def fake_record(_user_id, name):
            if name == "MBKB":
                return MagicMock(
                    id=uuid.uuid4(),
                    user_id=MagicMock(),
                    source_types=["memory"],
                    backend_type="opensearch",
                    backend_config={"index_name": "mb_index"},
                )
            return None

        mock_get_record.side_effect = fake_record

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["MBKB"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0
        assert data.get("memory_base_skipped") == "MBKB"
        # Neither the remote collection nor local storage is touched.
        mock_create_backend.assert_not_called()
        mock_delete.assert_not_called()

    @pytest.mark.parametrize(
        ("kb_name", "victim_relpath"),
        [
            # Single-level traversal into another user's namespace.
            ("../victim_user/secret_kb", "victim_user/secret_kb"),
            # Multi-level traversal out of the KB root entirely.
            ("../../other_root/secret_kb", "other_root/secret_kb"),
            # Prefix ambiguity: "activeuser_evil" starts with "activeuser", so a
            # startswith() containment check would wrongly accept it. is_relative_to() does not.
            ("../activeuser_evil/secret_kb", "activeuser_evil/secret_kb"),
            # URL-encoded sequences are NOT decoded by Path — they stay a literal
            # directory name and resolve harmlessly inside the user directory.
            ("%2e%2e%2fvictim_user%2fsecret_kb", "victim_user/secret_kb"),
        ],
    )
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_traversal_name_without_a_row_is_not_found(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path, kb_name, victim_relpath
    ):
        """A traversal payload resolves no row, so no path is ever built from it.

        Existence is now decided by the ``knowledge_base`` table before any path
        is constructed, which makes traversal unreachable rather than merely
        rejected: the request 404s having touched no filesystem at all. The
        containment guard still exists for the case a row's *name* traverses —
        see ``test_bulk_delete_rejects_traversal_when_a_row_carries_the_name``.
        """
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser").mkdir(parents=True)
        victim_kb = tmp_path / victim_relpath
        victim_kb.mkdir(parents=True)

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": [kb_name]},
        )

        assert response.status_code == 404, (
            f"VULNERABILITY CONFIRMED: server accepted traversal payload with status {response.status_code}"
        )
        assert victim_kb.exists(), "VULNERABILITY CONFIRMED: path traversal deleted another user's KB"

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_rejects_traversal_when_a_row_carries_the_name(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        """The containment guard still fires when a row's own name traverses.

        A user can create a KB whose *name* is a traversal string, which gives it
        a legitimate row. Path resolution must still refuse to build a path
        outside their namespace from it.
        """
        mock_root.return_value = tmp_path
        (tmp_path / "activeuser").mkdir(parents=True)
        victim_kb = tmp_path / "victim_user" / "secret_kb"
        victim_kb.mkdir(parents=True)
        await seed_kb("../victim_user/secret_kb")

        response = await client.request(
            "DELETE",
            "api/v1/knowledge_bases",
            headers=logged_in_headers,
            json={"kb_names": ["../victim_user/secret_kb"]},
        )

        assert response.status_code == 403
        assert victim_kb.exists(), "VULNERABILITY CONFIRMED: path traversal deleted another user's KB"

    @patch("langflow.api.v1.knowledge_bases.logger")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_bulk_delete_path_traversal_logs_warning(
        self, mock_root, mock_logger, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        """A traversal attempt must emit a warning log with user context."""
        mock_root.return_value = tmp_path

        (tmp_path / "activeuser").mkdir(parents=True)
        (tmp_path / "victim_user" / "secret_kb").mkdir(parents=True)
        # A row must exist for path resolution — and therefore the guard — to run.
        await seed_kb("../victim_user/secret_kb")

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
    @patch("langflow.api.v1.knowledge_bases.get_job_service")
    @patch("langflow.api.v1.knowledge_bases.get_task_service")
    async def test_ingest_files(
        self,
        mock_task,
        mock_job,
        mock_root,
        client: AsyncClient,
        logged_in_headers,
        tmp_path,
        sample_text_file,
        seed_kb,
    ):
        mock_root.return_value = tmp_path
        await seed_kb("Ingest-KB")

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
    async def test_ingest_invalid_config(self, mock_root, client: AsyncClient, logged_in_headers, tmp_path, seed_kb):
        mock_root.return_value = tmp_path
        # A row with no usable embedding selection is a 400, not a crash.
        await seed_kb("Invalid-KB", model_selection={})

        response = await client.post(
            "api/v1/knowledge_bases/Invalid-KB/ingest",
            headers=logged_in_headers,
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        )
        assert response.status_code == 400
        assert "Invalid embedding configuration" in response.json()["detail"]

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_ingest_rejects_overlap_larger_than_size(
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        """Ingest must reject overlap > size up front, before any upload work."""
        mock_root.return_value = tmp_path
        await seed_kb("Overlap-KB")

        response = await client.post(
            "api/v1/knowledge_bases/Overlap-KB/ingest",
            headers=logged_in_headers,
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")},
            data={"chunk_size": "100", "chunk_overlap": "200"},
        )
        assert response.status_code == 422, response.text
        assert "chunk size" in response.json()["detail"].lower()

    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    @patch("langflow.api.v1.knowledge_bases.create_backend")
    async def test_get_chunks_pagination_and_search(
        self, mock_create_backend, mock_root, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
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
        await seed_kb(kb_dir.name)

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
        self, mock_create_backend, mock_root, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
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
        await seed_kb(kb_dir.name)

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
        self, mock_create_backend, mock_root, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        """``/metadata/keys`` returns distinct user keys + sample values, hides reserved."""
        import json as _json

        from lfx.base.knowledge_bases.backends.base import IngestedDocument

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / "activeuser" / "KB1"
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "chroma.sqlite3").write_text("dummy")
        await seed_kb(kb_dir.name)

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
        self, mock_create_backend, mock_root, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        """Distinct values per key are capped — response sets ``truncated=true``."""
        import json as _json

        from langflow.api.v1.knowledge_bases import KB_METADATA_KEYS_VALUES_CAP
        from lfx.base.knowledge_bases.backends.base import IngestedDocument

        mock_root.return_value = tmp_path
        kb_dir = tmp_path / "activeuser" / "KB1"
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "chroma.sqlite3").write_text("dummy")
        await seed_kb(kb_dir.name)

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
        self, mock_root, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        """Empty local-Chroma KB short-circuits before booting the backend client."""
        mock_root.return_value = tmp_path
        kb_dir = tmp_path / "activeuser" / "KB1"
        kb_dir.mkdir(parents=True, exist_ok=True)
        # No chroma.sqlite3 / chroma / index files → short-circuit path.
        await seed_kb("KB1")

        response = await client.get(
            "api/v1/knowledge_bases/KB1/metadata/keys",
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.json()
        assert response.json() == {"keys": {}, "truncated": False}

    @patch("langflow.api.v1.knowledge_bases.create_backend")
    @patch("langflow.api.v1.knowledge_bases.KBStorageHelper.get_root_path")
    async def test_metadata_keys_reach_chroma_cloud_without_a_local_directory(
        self, mock_root, mock_create_backend, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        """A Chroma **Cloud** KB must not be short-circuited by a missing local dir.

        Both Chroma modes are stored as ``backend_type="chroma"`` and the
        discriminator is ``backend_config["mode"]``. A bare ``backend_type ==
        CHROMA`` check therefore read a cloud KB as local and returned an empty
        key set off a directory that should never exist for it.
        """
        from lfx.base.knowledge_bases.backends.base import IngestedDocument

        mock_root.return_value = tmp_path
        await seed_kb("Cloud_KB", backend_type="chroma", backend_config={"mode": "cloud"})

        async def _iter_documents(*, batch_size: int = 1000, include_embeddings: bool = False):  # noqa: ARG001
            yield [IngestedDocument(content="c", metadata={"source_metadata": json.dumps({"tag": "invoice"})})]

        backend = MagicMock()
        backend.iter_documents = _iter_documents
        backend.teardown = AsyncMock()
        mock_create_backend.return_value = backend

        response = await client.get(
            "api/v1/knowledge_bases/Cloud_KB/metadata/keys",
            headers=logged_in_headers,
        )
        assert response.status_code == 200, response.json()
        assert response.json()["keys"] == {"tag": ["invoice"]}
        # Cloud KBs resolve no local path at all.
        assert mock_create_backend.call_args.kwargs["kb_path"] is None


class TestPerformIngestionTask:
    """Tests for the internal KBIngestionHelper.perform_ingestion background task."""

    @patch("langflow.api.utils.ingestion_run_service.finalize_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.mark_running", new_callable=AsyncMock)
    @patch("langflow.api.utils.ingestion_run_service.create_run", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.create_backend")
    @patch("langflow.api.utils.kb_helpers.KBIngestionHelper.build_embeddings", new_callable=AsyncMock)
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_directory_size")
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics")
    async def test_perform_ingestion_success(
        self,
        mock_update,
        mock_size,
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
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_directory_size")
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics_via_backend", new_callable=AsyncMock)
    async def test_perform_ingestion_skipped_only_is_partial(
        self,
        mock_update_metrics,  # noqa: ARG002
        mock_size,
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
    @patch("langflow.api.utils.kb_helpers.KBStorageHelper.get_directory_size")
    @patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.update_text_metrics_via_backend", new_callable=AsyncMock)
    async def test_perform_ingestion_routes_through_configured_backend(
        self,
        mock_update_metrics,
        mock_size,
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
        # Metrics are recounted straight from the backend into a scratch dict,
        # then written to the row — there is no sidecar to read them back from.
        mock_update_metrics.assert_awaited_once()
        assert mock_update_metrics.await_args.args[1] is mock_backend

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
    async def test_cancel_ingestion_success(
        self, mock_root, mock_cleanup, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        from unittest.mock import patch as mock_patch

        from langflow.services.deps import get_service
        from langflow.services.schema import ServiceType

        mock_root.return_value = tmp_path
        kb_path = tmp_path / "activeuser" / "Test_KB"
        kb_path.mkdir(parents=True, exist_ok=True)

        job_id = uuid.uuid4()
        # ``asset_id`` is the KB row's id — the indexed column behind job.asset_id.
        asset_id = (await seed_kb("Test_KB")).id

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
        self, mock_job_service, mock_root, client: AsyncClient, logged_in_headers, tmp_path, seed_kb
    ):
        mock_root.return_value = tmp_path
        kb_path = tmp_path / "activeuser" / "Test_KB"
        kb_path.mkdir(parents=True, exist_ok=True)
        await seed_kb("Test_KB")

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
