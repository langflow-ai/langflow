"""Unit tests for ``ChromaBackend``.

Uses the in-process Chroma persistence to exercise the real backend rather
than mocking it out — this is the code path every other KB feature relies
on, so we want a real integration signal. Kept fast by scoping to
tmp_path-backed collections with tiny document sets.
"""

from __future__ import annotations

import gc
from typing import TYPE_CHECKING

import chromadb.errors
import pytest

if TYPE_CHECKING:
    from pathlib import Path
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from lfx.base.knowledge_bases.backends import (
    BackendType,
    ChromaBackend,
    ChromaCloudBackend,
    ChromaLocalBackend,
    IngestedDocument,
)
from lfx.base.knowledge_bases.backends.base import (
    METADATA_KEY_JOB_ID,
    METADATA_KEY_SOURCE,
    METADATA_KEY_SOURCE_TYPE,
)


class _DeterministicEmbeddings(Embeddings):
    """Hash-based embedder so tests don't need OpenAI/HF credentials.

    Produces a small fixed-length vector whose components are derived from
    the text — stable across runs, distinct enough that nearest-neighbour
    search returns sensible orderings for short inputs.
    """

    DIMENSION = 8

    def _embed(self, text: str) -> list[float]:
        h = abs(hash(text))
        return [((h >> (i * 4)) & 0xF) / 15.0 for i in range(self.DIMENSION)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@pytest.fixture
async def backend(tmp_path: Path):
    """Create a backend; async teardown runs after the test unconditionally."""
    (tmp_path / "unit_test_kb").mkdir(parents=True, exist_ok=True)
    bk = ChromaBackend(
        kb_name="unit_test_kb",
        kb_path=tmp_path / "unit_test_kb",
        embedding_function=_DeterministicEmbeddings(),
    )
    try:
        yield bk
    finally:
        await bk.teardown()
        gc.collect()


class TestChromaBackendLifecycle:
    """Smoke tests covering construction, lazy build, and teardown."""

    def test_backend_type_constant(self, backend: ChromaBackend):
        assert backend.backend_type is BackendType.CHROMA

    def test_vector_store_is_lazy(self, tmp_path: Path):
        bk = ChromaBackend(
            kb_name="lazy_kb",
            kb_path=tmp_path / "lazy_kb",
            embedding_function=_DeterministicEmbeddings(),
        )
        assert bk._vector_store is None
        # Touching the property triggers _build_vector_store.
        (tmp_path / "lazy_kb").mkdir(parents=True, exist_ok=True)
        _ = bk.vector_store
        assert bk._vector_store is not None

    async def test_teardown_is_idempotent(self, backend: ChromaBackend):
        """Teardown must be safe from ``finally`` blocks even if never touched."""
        await backend.teardown()
        await backend.teardown()  # second call should not raise


class TestChromaBackendDocumentLifecycle:
    """End-to-end: add → count → iter → search → delete."""

    async def test_add_documents_is_noop_on_empty_list(self, backend: ChromaBackend):
        await backend.add_documents([])
        assert await backend.count() == 0

    async def test_add_and_count(self, backend: ChromaBackend):
        docs = [
            Document(
                page_content=f"content {i}",
                metadata={METADATA_KEY_SOURCE: "test", METADATA_KEY_SOURCE_TYPE: "file_upload"},
            )
            for i in range(3)
        ]
        await backend.add_documents(docs)
        assert await backend.count() == 3

    async def test_iter_documents_yields_batches(self, backend: ChromaBackend):
        docs = [Document(page_content=f"content {i}", metadata={METADATA_KEY_SOURCE: f"src{i}"}) for i in range(5)]
        await backend.add_documents(docs)

        batches: list[list[IngestedDocument]] = [batch async for batch in backend.iter_documents(batch_size=2)]
        total = sum(len(b) for b in batches)
        assert total == 5
        # All items should be ``IngestedDocument`` instances with metadata preserved.
        all_contents = [item.content for batch in batches for item in batch]
        assert set(all_contents) == {f"content {i}" for i in range(5)}

    async def test_iter_documents_returns_empty_for_empty_collection(self, backend: ChromaBackend):
        batches = [batch async for batch in backend.iter_documents()]
        assert batches == []

    async def test_similarity_search_returns_tuples(self, backend: ChromaBackend):
        await backend.add_documents(
            [
                Document(page_content="alpha", metadata={}),
                Document(page_content="beta", metadata={}),
            ]
        )
        results = await backend.similarity_search("alpha", k=2)
        assert len(results) == 2
        # Default (no scores) path should return zero-score sentinel tuples.
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
        assert all(score == 0.0 for _, score in results)

    async def test_similarity_search_with_scores(self, backend: ChromaBackend):
        await backend.add_documents(
            [Document(page_content="alpha", metadata={}), Document(page_content="beta", metadata={})]
        )
        results = await backend.similarity_search("alpha", k=1, with_scores=True)
        assert len(results) == 1
        _doc, score = results[0]
        # Any real float score is fine; we just confirm Chroma's actual score plumbs through.
        assert isinstance(score, float)

    async def test_delete_by_removes_matching_documents(self, backend: ChromaBackend):
        """Per-job rollback is the critical correctness property here."""
        await backend.add_documents(
            [
                Document(
                    page_content="job-a doc",
                    metadata={METADATA_KEY_JOB_ID: "job-a", METADATA_KEY_SOURCE: "a"},
                ),
                Document(
                    page_content="job-b doc",
                    metadata={METADATA_KEY_JOB_ID: "job-b", METADATA_KEY_SOURCE: "b"},
                ),
            ]
        )
        assert await backend.count() == 2
        await backend.delete_by({METADATA_KEY_JOB_ID: "job-a"})
        assert await backend.count() == 1

        # Only the job-b doc should remain.
        remaining = [item async for batch in backend.iter_documents() for item in batch]
        assert len(remaining) == 1
        assert remaining[0].metadata.get(METADATA_KEY_JOB_ID) == "job-b"


class TestChromaBackendStorage:
    async def test_storage_size_reports_nonzero_after_ingest(self, backend: ChromaBackend):
        await backend.add_documents([Document(page_content="hello world", metadata={})])
        size = await backend.storage_size_bytes()
        assert size > 0

    async def test_storage_size_is_zero_for_missing_path(self, tmp_path: Path):
        bk = ChromaBackend(
            kb_name="ghost_kb",
            kb_path=tmp_path / "does_not_exist",
            embedding_function=_DeterministicEmbeddings(),
        )
        assert await bk.storage_size_bytes() == 0


# ---------------------------------------------------------------------------
# Cloud mode tests
# ---------------------------------------------------------------------------


_CLOUD_CONFIG: dict = {
    "mode": "cloud",
    "tenant_variable": "MY_CHROMA_TENANT",
    "database_variable": "MY_CHROMA_DATABASE",
    "api_key_variable": "MY_CHROMA_API_KEY",  # pragma: allowlist secret
}


class TestChromaCloudMode:
    """Unit tests for ChromaBackend cloud mode — all network calls are mocked."""

    def _cloud_backend(self, tmp_path: Path, cfg: dict | None = None) -> ChromaCloudBackend:
        return ChromaCloudBackend(
            kb_name="cloud_test_kb",
            kb_path=tmp_path / "cloud_test_kb",
            backend_config=cfg or _CLOUD_CONFIG,
            embedding_function=_DeterministicEmbeddings(),
        )

    # ---- mode detection --------------------------------------------------

    def test_is_cloud_true_when_mode_is_cloud(self, tmp_path: Path):
        bk = self._cloud_backend(tmp_path)
        assert bk._is_cloud is True

    def test_is_cloud_false_when_mode_is_local(self, tmp_path: Path):
        bk = ChromaLocalBackend(
            kb_name="local_kb",
            kb_path=tmp_path / "local_kb",
            embedding_function=_DeterministicEmbeddings(),
        )
        assert bk._is_cloud is False

    def test_is_cloud_false_by_default(self, tmp_path: Path):
        bk = ChromaLocalBackend(
            kb_name="default_kb",
            kb_path=tmp_path / "default_kb",
            embedding_function=_DeterministicEmbeddings(),
        )
        assert bk._is_cloud is False

    # ---- credential resolution -------------------------------------------

    async def test_resolve_secrets_api_key_is_required(self, tmp_path: Path):
        from unittest.mock import AsyncMock, patch

        bk = self._cloud_backend(tmp_path)
        with (
            patch.object(bk, "resolve_required_secret", new_callable=AsyncMock, return_value="key") as mock_req,
            patch.object(bk, "resolve_secret", new_callable=AsyncMock, return_value=None),
        ):
            await bk._resolve_secrets()

        # Only API key goes through resolve_required_secret.
        calls = [c.args[0] for c in mock_req.call_args_list]
        assert calls == ["MY_CHROMA_API_KEY"]

    async def test_resolve_secrets_tenant_database_are_optional(self, tmp_path: Path):
        from unittest.mock import AsyncMock, patch

        bk = self._cloud_backend(tmp_path)
        with (
            patch.object(bk, "resolve_required_secret", new_callable=AsyncMock, return_value="key"),
            patch.object(bk, "resolve_secret", new_callable=AsyncMock, return_value=None) as mock_opt,
        ):
            await bk._resolve_secrets()

        # Tenant and database use resolve_secret (optional).
        opt_calls = [c.args[0] for c in mock_opt.call_args_list]
        assert "MY_CHROMA_TENANT" in opt_calls
        assert "MY_CHROMA_DATABASE" in opt_calls

    async def test_resolve_secrets_defaults_to_env_var_names(self, tmp_path: Path):
        from unittest.mock import AsyncMock, patch

        bk = ChromaCloudBackend(
            kb_name="cloud_kb",
            kb_path=tmp_path / "cloud_kb",
            backend_config={"mode": "cloud"},
            embedding_function=_DeterministicEmbeddings(),
        )
        with (
            patch.object(bk, "resolve_required_secret", new_callable=AsyncMock, return_value="key") as mock_req,
            patch.object(bk, "resolve_secret", new_callable=AsyncMock, return_value=None) as mock_opt,
        ):
            await bk._resolve_secrets()

        assert [c.args[0] for c in mock_req.call_args_list] == ["CHROMA_API_KEY"]
        opt_calls = [c.args[0] for c in mock_opt.call_args_list]
        assert "CHROMA_TENANT" in opt_calls
        assert "CHROMA_DATABASE" in opt_calls

    async def test_resolve_secrets_noop_in_local_mode(self, tmp_path: Path):
        from unittest.mock import AsyncMock, patch

        bk = ChromaLocalBackend(
            kb_name="local_kb",
            kb_path=tmp_path / "local_kb",
            embedding_function=_DeterministicEmbeddings(),
        )
        with (
            patch.object(bk, "resolve_required_secret", new_callable=AsyncMock) as mock_req,
            patch.object(bk, "resolve_secret", new_callable=AsyncMock) as mock_opt,
        ):
            await bk._resolve_secrets()

        mock_req.assert_not_called()
        mock_opt.assert_not_called()

    # ---- client construction ---------------------------------------------

    def test_build_vector_store_uses_cloud_client(self, tmp_path: Path):
        from unittest.mock import MagicMock, patch

        bk = self._cloud_backend(tmp_path)
        bk._resolved_tenant = "t"
        bk._resolved_database = "d"
        bk._resolved_api_key = "k"

        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = MagicMock()

        with (
            patch("chromadb.CloudClient", return_value=mock_client) as mock_cloud,
            patch("chromadb.PersistentClient") as mock_local,
            patch("lfx.base.knowledge_bases.backends.chroma.Chroma", return_value=MagicMock()) as mock_chroma,
        ):
            bk._build_vector_store()

        mock_cloud.assert_called_once()
        mock_local.assert_not_called()
        mock_chroma.assert_called_once_with(
            client=mock_client,
            collection_name="cloud_test_kb",
            embedding_function=bk.embedding_function,
            collection_configuration={"embedding_function": None},
        )

    def test_get_cloud_client_passes_optional_host_port(self, tmp_path: Path):
        from unittest.mock import patch

        bk = ChromaCloudBackend(
            kb_name="cloud_kb",
            kb_path=tmp_path / "cloud_kb",
            backend_config={
                "mode": "cloud",
                "cloud_host": "custom.host.example",
                "cloud_port": "8080",
            },
            embedding_function=_DeterministicEmbeddings(),
        )
        bk._resolved_tenant = "t"
        bk._resolved_database = "d"
        bk._resolved_api_key = "k"

        with patch("chromadb.CloudClient") as mock_cloud:
            bk._get_cloud_client()

        _, kwargs = mock_cloud.call_args
        assert kwargs["cloud_host"] == "custom.host.example"
        assert kwargs["cloud_port"] == 8080

    def test_get_cloud_client_omits_host_port_when_not_configured(self, tmp_path: Path):
        from unittest.mock import patch

        bk = self._cloud_backend(tmp_path)
        bk._resolved_tenant = "t"
        bk._resolved_database = "d"
        bk._resolved_api_key = "k"

        with patch("chromadb.CloudClient") as mock_cloud:
            bk._get_cloud_client()

        _, kwargs = mock_cloud.call_args
        assert "cloud_host" not in kwargs
        assert "cloud_port" not in kwargs

    # ---- test_connection -------------------------------------------------

    async def test_test_connection_cloud_success(self, tmp_path: Path):
        from unittest.mock import AsyncMock, MagicMock, patch

        bk = self._cloud_backend(tmp_path)

        mock_client = MagicMock()
        with (
            patch.object(bk, "_resolve_secrets", new_callable=AsyncMock),
            patch.object(bk, "_get_cloud_client", return_value=mock_client),
        ):
            result = await bk.test_connection()

        assert result.ok is True
        assert "Cloud" in result.message
        mock_client.heartbeat.assert_called()

    async def test_test_connection_cloud_failure(self, tmp_path: Path):
        from unittest.mock import AsyncMock, patch

        bk = self._cloud_backend(tmp_path)

        with (
            patch.object(bk, "_resolve_secrets", new_callable=AsyncMock),
            patch.object(bk, "_get_cloud_client", side_effect=ValueError("bad api key")),
        ):
            result = await bk.test_connection()

        assert result.ok is False
        assert "bad api key" in result.message

    async def test_test_connection_cloud_credential_error_is_caught(self, tmp_path: Path):
        from unittest.mock import AsyncMock, patch

        bk = self._cloud_backend(tmp_path)

        with patch.object(
            bk,
            "_resolve_secrets",
            new_callable=AsyncMock,
            side_effect=ValueError("Required credential variable 'MY_CHROMA_API_KEY' is not configured."),
        ):
            result = await bk.test_connection()

        assert result.ok is False
        assert "MY_CHROMA_API_KEY" in result.message

    # ---- teardown / storage ----------------------------------------------

    async def test_teardown_cloud_does_not_touch_shared_registry(self, tmp_path: Path):
        from chromadb.api.shared_system_client import SharedSystemClient

        bk = self._cloud_backend(tmp_path)
        original_registry = dict(SharedSystemClient._identifier_to_system)
        await bk.teardown()
        assert SharedSystemClient._identifier_to_system == original_registry

    async def test_storage_size_zero_in_cloud_mode(self, tmp_path: Path):
        bk = self._cloud_backend(tmp_path)
        assert await bk.storage_size_bytes() == 0

    async def test_delete_collection_calls_client_delete_collection(self, tmp_path: Path):
        from unittest.mock import AsyncMock, MagicMock, patch

        bk = self._cloud_backend(tmp_path)
        mock_client = MagicMock()

        with (
            patch.object(bk, "ensure_ready", new_callable=AsyncMock),
            patch.object(bk, "_get_cloud_client", return_value=mock_client),
        ):
            await bk.delete_collection()

        mock_client.delete_collection.assert_called_once_with(name="cloud_test_kb")

    async def test_delete_collection_propagates_cloud_errors(self, tmp_path: Path):
        """Cloud errors must bubble up so the route can surface a warning."""
        from unittest.mock import AsyncMock, patch

        bk = self._cloud_backend(tmp_path)

        with (
            patch.object(bk, "ensure_ready", new_callable=AsyncMock),
            patch.object(bk, "_get_cloud_client", side_effect=chromadb.errors.ChromaError("gone")),
            pytest.raises(chromadb.errors.ChromaError),
        ):
            await bk.delete_collection()
