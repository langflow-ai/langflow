"""Unit tests for ``ChromaBackend``.

Uses the in-process Chroma persistence to exercise the real backend rather
than mocking it out — this is the code path every other KB feature relies
on, so we want a real integration signal. Kept fast by scoping to
tmp_path-backed collections with tiny document sets.
"""

from __future__ import annotations

import gc
import re
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

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
    PostgresBackend,
)
from lfx.base.knowledge_bases.backends.base import (
    METADATA_KEY_JOB_ID,
    METADATA_KEY_SOURCE,
    METADATA_KEY_SOURCE_TYPE,
)
from lfx.base.knowledge_bases.backends.chroma import LEGACY_SHARED_COLLECTION_KEY
from lfx.base.knowledge_bases.backends.naming import owner_scoped_collection_name
from lfx.base.knowledge_bases.validation import is_valid_collection_name


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

    def test_distance_score_is_normalized_to_higher_is_better(self, tmp_path: Path) -> None:
        backend = ChromaBackend(kb_name="scores", kb_path=tmp_path)
        assert backend.normalize_score(0.25) == -0.25

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


_CLOUD_OWNER = UUID("7a0c2f7e-5f1b-4b8e-9d0c-2b1f6f3c9e41")


class TestChromaCloudMode:
    """Unit tests for ChromaBackend cloud mode — all network calls are mocked."""

    def _cloud_backend(self, tmp_path: Path, cfg: dict | None = None) -> ChromaCloudBackend:
        return ChromaCloudBackend(
            kb_name="cloud_test_kb",
            kb_path=tmp_path / "cloud_test_kb",
            backend_config=cfg or _CLOUD_CONFIG,
            embedding_function=_DeterministicEmbeddings(),
            user_id=_CLOUD_OWNER,
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
            collection_name=owner_scoped_collection_name(_CLOUD_OWNER, "cloud_test_kb"),
            embedding_function=bk.embedding_function,
            collection_configuration={"embedding_function": None},
        )

    def test_get_cloud_client_passes_optional_host_port(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from unittest.mock import patch

        # The custom host now goes through connector SSRF validation; allowlist
        # it so the test exercises the pass-through without a DNS lookup.
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "custom.host.example")
        monkeypatch.setenv("LANGFLOW_KB_ALLOWED_HOSTS", "custom.host.example")
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

    # ---- SSRF and destination policy -------------------------------------

    @pytest.fixture
    def ssrf_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pin the destination knobs so the tests don't depend on ambient settings.

        The hosts under test are approved for the exclusive destination gate so
        each assertion measures the *address* policy. The gate itself is covered
        by ``test_custom_host_needs_operator_approval`` below.
        """
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
        monkeypatch.setenv(
            "LANGFLOW_KB_ALLOWED_HOSTS",
            "169.254.169.254,10.0.0.5,chroma.internal.example",
        )
        monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", raising=False)

    def _cloud_backend_with_host(self, tmp_path: Path, cloud_host: str) -> ChromaCloudBackend:
        """Cloud backend whose credential lookups are stubbed, leaving only the host checks."""
        from unittest.mock import AsyncMock

        bk = ChromaCloudBackend(
            kb_name="cloud_kb",
            kb_path=tmp_path / "cloud_kb",
            backend_config={"mode": "cloud", "cloud_host": cloud_host},
            embedding_function=_DeterministicEmbeddings(),
        )
        bk.resolve_required_secret = AsyncMock(return_value="k")
        bk.resolve_secret = AsyncMock(return_value=None)
        return bk

    @pytest.mark.parametrize("hostile_host", ["169.254.169.254", "10.0.0.5"])
    async def test_resolve_secrets_rejects_ssrf_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hostile_host: str
    ):
        """Tenant-controlled cloud_host must not reach internal/metadata IPs.

        Regression guard for the KB Chroma Cloud SSRF (CWE-918): cloud_host /
        cloud_port come straight from the request body's backend_config and
        were handed to chromadb.CloudClient unvalidated, letting a tenant point
        the server at 169.254.169.254 / RFC1918 targets.

        The check lives in ``_resolve_secrets``, which ``ensure_ready`` runs before
        anything can build a client, so it covers test-connection, create, ingest,
        retrieval and delete from one place. It is deliberately *not* repeated in
        ``_get_cloud_client``: ``vector_store`` builds lazily from a sync property,
        so a validator call there is a blocking DNS lookup on the event loop.
        """
        from unittest.mock import AsyncMock

        from lfx.utils.ssrf_protection import SSRFProtectionError

        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
        monkeypatch.setenv(
            "LANGFLOW_KB_ALLOWED_HOSTS",
            "169.254.169.254,10.0.0.5,chroma.internal.example",
        )
        monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
        bk = ChromaCloudBackend(
            kb_name="cloud_kb",
            kb_path=tmp_path / "cloud_kb",
            backend_config={"mode": "cloud", "cloud_host": hostile_host},
            embedding_function=_DeterministicEmbeddings(),
        )
        bk.resolve_required_secret = AsyncMock(return_value="k")
        bk.resolve_secret = AsyncMock(return_value=None)
        with (
            patch("chromadb.CloudClient") as mock_cloud,
            pytest.raises(SSRFProtectionError, match="blocked"),
        ):
            await bk._resolve_secrets()
        mock_cloud.assert_not_called()

    @pytest.mark.usefixtures("ssrf_env")
    async def test_resolve_secrets_rejects_hostname_resolving_to_private_ip(self, tmp_path: Path):
        from lfx.utils.ssrf_protection import SSRFProtectionError

        bk = self._cloud_backend_with_host(tmp_path, "chroma.internal.example")
        with (
            patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["10.1.2.3"]),
            patch("chromadb.CloudClient") as mock_cloud,
            pytest.raises(SSRFProtectionError, match="blocked"),
        ):
            await bk._resolve_secrets()
        mock_cloud.assert_not_called()

    @pytest.mark.usefixtures("ssrf_env")
    async def test_default_cloud_host_needs_no_validation(self, tmp_path: Path):
        """No ``cloud_host`` means chromadb's fixed public default, which has no tenant input."""
        from unittest.mock import AsyncMock

        bk = self._cloud_backend(tmp_path)
        bk.resolve_required_secret = AsyncMock(return_value="k")
        bk.resolve_secret = AsyncMock(return_value=None)
        with patch("lfx.utils.ssrf_protection.resolve_hostname") as mock_resolve:
            await bk._resolve_secrets()
        mock_resolve.assert_not_called()

    @pytest.mark.usefixtures("ssrf_env")
    async def test_test_connection_reports_ssrf_block(self, tmp_path: Path):
        """A blocked host surfaces as a failed probe typed ``SSRFProtectionError``."""
        bk = self._cloud_backend_with_host(tmp_path, "169.254.169.254")
        with patch("chromadb.CloudClient") as mock_cloud:
            result = await bk.test_connection()
        assert result.ok is False
        assert result.details["type"] == "SSRFProtectionError"
        assert "blocked" in result.message
        mock_cloud.assert_not_called()

    @pytest.mark.usefixtures("ssrf_env")
    async def test_custom_host_needs_operator_approval(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A public-looking custom host is still refused — the KB list is exclusive.

        chromadb builds its own httpx client inside ``CloudClient`` and dials during
        construction, so the address validated here cannot be pinned for the connection
        that follows. ``cloud_host`` is a testing-only knob upstream, so requiring
        approval leaves the ordinary Chroma Cloud path alone.
        """
        from lfx.utils.ssrf_protection import SSRFProtectionError

        monkeypatch.delenv("LANGFLOW_KB_ALLOWED_HOSTS", raising=False)
        bk = self._cloud_backend_with_host(tmp_path, "rebind.attacker.example")
        with (
            patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["93.184.216.34"]),
            patch("chromadb.CloudClient") as mock_cloud,
            pytest.raises(SSRFProtectionError, match="not an approved destination"),
        ):
            await bk._resolve_secrets()
        mock_cloud.assert_not_called()

    @pytest.mark.usefixtures("ssrf_env")
    async def test_approved_custom_host_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGFLOW_KB_ALLOWED_HOSTS", "chroma.corp.example")
        bk = self._cloud_backend_with_host(tmp_path, "chroma.corp.example")
        with patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["93.184.216.34"]):
            await bk._resolve_secrets()
        assert bk._resolved_api_key == "k"  # pragma: allowlist secret

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

        mock_client.delete_collection.assert_called_once_with(
            name=owner_scoped_collection_name(_CLOUD_OWNER, "cloud_test_kb")
        )

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


class TestChromaCloudCollectionIsolation:
    """Each owner's Chroma Cloud knowledge base must get its own collection.

    Every user whose credentials resolve to the same tenant and database shares
    one collection namespace, and KB names are only unique per user. Naming the
    collection after the KB let two users' same-named KBs read, count, and delete
    each other's chunks. The collection is now owner-scoped unless an explicit
    ``collection_name`` override is configured.
    """

    def _make(self, kb_name: str, backend_config: dict, user_id: UUID | str | None) -> ChromaCloudBackend:
        backend = ChromaCloudBackend(kb_name=kb_name, backend_config=backend_config, user_id=user_id)
        backend._resolved_api_key = "k"
        return backend

    def _built_collection(self, backend: ChromaCloudBackend) -> str:
        with (
            patch("chromadb.CloudClient", return_value=MagicMock()),
            patch("lfx.base.knowledge_bases.backends.chroma.Chroma", return_value=MagicMock()) as fake_chroma,
        ):
            backend._build_vector_store()
        return fake_chroma.call_args.kwargs["collection_name"]

    def test_same_kb_name_for_different_owners_gets_different_collections(self) -> None:
        first = self._built_collection(self._make("docs", {"mode": "cloud"}, uuid4()))
        second = self._built_collection(self._make("docs", {"mode": "cloud"}, uuid4()))
        assert first != second

    def test_collection_matches_pgvector_and_is_a_valid_chroma_name(self) -> None:
        owner = uuid4()
        collection = self._built_collection(self._make("Team Docs", {"mode": "cloud"}, owner))
        assert collection == PostgresBackend(kb_name="Team Docs", user_id=owner).collection_name
        assert re.fullmatch(r"lf_[0-9a-f]{24}", collection)
        assert is_valid_collection_name(collection)

    def test_string_and_uuid_owner_ids_resolve_to_the_same_collection(self) -> None:
        owner = uuid4()
        from_uuid = self._built_collection(self._make("docs", {"mode": "cloud"}, owner))
        from_string = self._built_collection(self._make("docs", {"mode": "cloud"}, str(owner).upper()))
        assert from_uuid == from_string

    def test_missing_owner_fails_closed(self) -> None:
        with pytest.raises(ValueError, match="valid user_id"):
            self._built_collection(self._make("docs", {"mode": "cloud"}, None))

    def test_explicit_collection_name_overrides_derivation(self) -> None:
        backend = self._make("docs", {"mode": "cloud", "collection_name": "docs"}, uuid4())
        assert self._built_collection(backend) == "docs"

    def test_override_cannot_target_another_owners_scoped_collection(self) -> None:
        victim = owner_scoped_collection_name(uuid4(), "docs")
        backend = self._make("docs", {"mode": "cloud", "collection_name": victim}, uuid4())
        with pytest.raises(ValueError, match="reserved for owner-scoped"):
            self._built_collection(backend)

    async def test_delete_collection_uses_the_resolved_collection(self) -> None:
        owner = uuid4()
        client = MagicMock()
        backend = self._make("docs", {"mode": "cloud"}, owner)
        backend._secrets_resolved = True
        with patch.object(backend, "_get_cloud_client", return_value=client):
            await backend.delete_collection()
        client.delete_collection.assert_called_once_with(name=owner_scoped_collection_name(owner, "docs"))

    async def test_delete_collection_without_owner_touches_nothing(self) -> None:
        client = MagicMock()
        backend = self._make("docs", {"mode": "cloud"}, None)
        backend._secrets_resolved = True
        with (
            patch.object(backend, "_get_cloud_client", return_value=client),
            pytest.raises(ValueError, match="valid user_id"),
        ):
            await backend.delete_collection()
        client.delete_collection.assert_not_called()

    def test_shared_legacy_collection_marker_warns(self) -> None:
        owner = uuid4()
        backend = self._make("docs", {"mode": "cloud", LEGACY_SHARED_COLLECTION_KEY: "docs"}, owner)
        with patch("lfx.base.knowledge_bases.backends.chroma.logger") as fake_logger:
            collection = self._built_collection(backend)
        assert collection == owner_scoped_collection_name(owner, "docs")
        fake_logger.warning.assert_called_once()
        assert "docs" in fake_logger.warning.call_args.args

    def test_no_warning_without_the_marker(self) -> None:
        backend = self._make("docs", {"mode": "cloud"}, uuid4())
        with patch("lfx.base.knowledge_bases.backends.chroma.logger") as fake_logger:
            self._built_collection(backend)
        fake_logger.warning.assert_not_called()


class TestChromaEmbeddedDocuments:
    """Write chunks with precomputed vectors, the path a KB migration uses."""

    async def _read_all(self, bk: ChromaLocalBackend) -> list[IngestedDocument]:
        out: list[IngestedDocument] = []
        async for batch in bk.iter_documents(batch_size=2, include_embeddings=True):
            out.extend(batch)
        return out

    async def test_iter_documents_returns_store_ids(self, backend: ChromaBackend):
        await backend.add_documents(
            [Document(id="chunk-a", page_content="alpha", metadata={"n": 1})],
        )
        docs = await self._read_all(backend)
        assert [d.id for d in docs] == ["chunk-a"]

    async def test_copy_between_stores_preserves_vectors_without_an_embedder(
        self, backend: ChromaBackend, tmp_path: Path
    ):
        await backend.add_documents(
            [
                Document(id="chunk-a", page_content="alpha", metadata={"n": 1}),
                Document(id="chunk-b", page_content="beta", metadata={"n": 2}),
                Document(id="chunk-c", page_content="gamma", metadata={"n": 3}),
            ]
        )
        source = await self._read_all(backend)

        target_path = tmp_path / "target_kb"
        target_path.mkdir()
        # No embedding function: nothing on this path may call a model.
        target = ChromaLocalBackend(kb_name="target_kb", kb_path=target_path)
        try:
            await target.add_embedded_documents(source)
            copied = {d.id: d for d in await self._read_all(target)}
        finally:
            await target.teardown()
            gc.collect()

        assert set(copied) == {"chunk-a", "chunk-b", "chunk-c"}
        for original in source:
            got = copied[original.id]
            assert got.content == original.content
            assert got.metadata == original.metadata
            assert got.embedding == pytest.approx(original.embedding)

    async def test_rewriting_the_same_batch_upserts(self, tmp_path: Path):
        path = tmp_path / "upsert_kb"
        path.mkdir()
        bk = ChromaLocalBackend(kb_name="upsert_kb", kb_path=path)
        docs = [
            IngestedDocument(id=f"c{i}", content=f"doc {i}", metadata={"i": i}, embedding=[i / 10] * 4)
            for i in range(5)
        ]
        try:
            await bk.add_embedded_documents(docs)
            await bk.add_embedded_documents(docs)
            assert await bk.count() == 5
        finally:
            await bk.teardown()
            gc.collect()

    async def test_rejects_a_document_without_an_embedding(self, tmp_path: Path):
        path = tmp_path / "reject_kb"
        path.mkdir()
        bk = ChromaLocalBackend(kb_name="reject_kb", kb_path=path)
        try:
            with pytest.raises(ValueError, match="embedding"):
                await bk.add_embedded_documents([IngestedDocument(id="x", content="no vector")])
        finally:
            await bk.teardown()
            gc.collect()
