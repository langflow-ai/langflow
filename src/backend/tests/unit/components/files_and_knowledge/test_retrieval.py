"""Tests for ``KnowledgeBaseComponent`` after the unified-models port.

Pre-port this file was ~938 lines and tested a hand-rolled per-
provider ``_build_embeddings`` + ``_resolve_api_key`` +
``_resolve_provider_variables`` surface. All three are gone now —
retrieval delegates credential resolution to
``lfx.base.models.unified_models.get_embeddings`` (same as ingestion)
and vector access to the configured backend registry entry.

The rewritten suite covers the actual retrieval contract:

* ``_get_kb_metadata`` reading ``embedding_metadata.json``.
* ``_resolve_model_selection`` preferring ``model_selection`` over
  the legacy string fields, with a clear error when neither is
  present and the string doesn't map to a current catalog entry.
* ``retrieve_data`` orchestrating ``get_embeddings`` +
  backend-registry ``similarity_search`` against the right KB path.
* User-scoping + required-field guards that make retrieval safe
  across sessions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from lfx.base.knowledge_bases.backends import ChromaLocalBackend
from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases
from lfx.components.files_and_knowledge.retrieval import KnowledgeBaseComponent

from tests.base import ComponentTestBaseWithClient


class _DeterministicEmbeddings(Embeddings):
    """Hash-based embedder so the embedding join can be exercised without credentials.

    Uses ``hashlib`` (not the builtin ``hash``) so the vector for a given string is
    stable across processes — the ingest pass and the query pass must agree.
    """

    DIMENSION = 8

    def _embed(self, text: str) -> list[float]:
        digest = int(hashlib.sha256(text.encode()).hexdigest(), 16)
        return [((digest >> (i * 4)) & 0xF) / 15.0 for i in range(self.DIMENSION)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class TestKnowledgeBaseComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return KnowledgeBaseComponent

    @pytest.fixture(autouse=True)
    def mock_knowledge_base_path(self, tmp_path):
        """Pin the KB root at a fresh tmp dir for every test."""
        with patch("lfx.components.files_and_knowledge._kb_paths._KNOWLEDGE_BASES_ROOT_PATH", tmp_path):
            yield

    @pytest.fixture
    def default_kwargs(self, tmp_path, active_user):
        kb_name = "test_kb"
        kb_path = tmp_path / active_user.username / kb_name
        kb_path.mkdir(parents=True, exist_ok=True)

        metadata = {
            "embedding_provider": "HuggingFace",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "model_selection": {
                "name": "sentence-transformers/all-MiniLM-L6-v2",
                "provider": "HuggingFace",
                "metadata": {
                    "embedding_class": "HuggingFaceEmbeddings",
                    "param_mapping": {"model_name": "model"},
                },
            },
            "chunk_size": 1000,
            "created_at": "2026-04-01T00:00:00Z",
        }
        (kb_path / "embedding_metadata.json").write_text(json.dumps(metadata))

        return {
            "knowledge_base": kb_name,
            "kb_root_path": str(tmp_path),
            "search_query": "",
            "top_k": 5,
            "include_embeddings": False,
            "_user_id": active_user.id,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """New-style component: no legacy filenames."""
        return []

    # ---- update_build_config ----------------------------------------

    async def test_get_knowledge_bases_utility(self, tmp_path, active_user):
        (tmp_path / active_user.username / "kb1").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / "kb2").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / ".hidden").mkdir(parents=True, exist_ok=True)

        kb_list = await get_knowledge_bases(tmp_path, user_id=active_user.id)

        assert "test_kb" in kb_list
        assert "kb1" in kb_list
        assert "kb2" in kb_list
        assert ".hidden" not in kb_list

    async def test_get_knowledge_bases_db_first_hides_stale_disk_dirs(self, tmp_path, active_user):
        """DB-first listing hides on-disk dirs that have no matching DB row.

        Regression for the dropdown showing entries (e.g. ``api_baseline_*``,
        ``customer_sales_history_*``) that no longer exist on the Knowledge
        management page. Before the fix, the lfx helper scanned the disk
        unconditionally, so any directory left over from a delete that did
        not write the ``.kb_deleted`` sentinel (legacy delete, direct
        ``DELETE FROM knowledge_base``, DB reset, etc.) would re-surface in
        the canvas dropdown but not on the management page (which is
        DB-first). The two surfaces must agree.
        """
        from langflow.api.utils import knowledge_base_service

        # Disk has both a "real" KB (with a DB row) and a leftover stale dir.
        (tmp_path / active_user.username / "real_kb").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / "stale_dir").mkdir(parents=True, exist_ok=True)
        await knowledge_base_service.create_record(user_id=active_user.id, name="real_kb")

        kb_list = await get_knowledge_bases(tmp_path, user_id=active_user.id)

        assert "real_kb" in kb_list
        # ``stale_dir`` has no DB row → it's a phantom and must not show up.
        assert "stale_dir" not in kb_list

    async def test_get_knowledge_bases_skips_memory_base_associated_kbs(self, tmp_path, active_user):
        """Memory-base-associated KBs are filtered out of the generic KB list.

        Matches the listing endpoint's behavior — those KBs are exposed
        through the Memory Base APIs, not the generic KB dropdown.
        """
        from langflow.api.utils import knowledge_base_service

        await knowledge_base_service.create_record(user_id=active_user.id, name="regular_kb")
        await knowledge_base_service.create_record(user_id=active_user.id, name="memory_kb", source_types=["memory"])

        kb_list = await get_knowledge_bases(tmp_path, user_id=active_user.id)

        assert "regular_kb" in kb_list
        assert "memory_kb" not in kb_list

    async def test_update_build_config_populates_options(self, component_class, default_kwargs, tmp_path, active_user):
        component = component_class(**default_kwargs)

        (tmp_path / active_user.username / "kb1").mkdir(parents=True, exist_ok=True)
        (tmp_path / active_user.username / "kb2").mkdir(parents=True, exist_ok=True)

        build_config = {"knowledge_base": {"value": "test_kb", "options": []}}
        result = await component.update_build_config(build_config, None, "knowledge_base")

        assert "test_kb" in result["knowledge_base"]["options"]
        assert "kb1" in result["knowledge_base"]["options"]
        assert "kb2" in result["knowledge_base"]["options"]

    async def test_update_build_config_resets_stale_selection(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {"knowledge_base": {"value": "nonexistent_kb", "options": ["test_kb"]}}
        result = await component.update_build_config(build_config, None, "knowledge_base")
        assert result["knowledge_base"]["value"] is None

    # ---- _get_kb_metadata --------------------------------------------

    def test_get_kb_metadata_happy_path(self, component_class, default_kwargs, active_user):
        component = component_class(**default_kwargs)
        kb_path = Path(default_kwargs["kb_root_path"]) / active_user.username / default_kwargs["knowledge_base"]
        metadata = component._get_kb_metadata(kb_path)
        assert metadata["embedding_provider"] == "HuggingFace"
        assert metadata["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        # New-format KBs carry the full selection dict so retrieval can
        # pass it straight to get_embeddings.
        assert "model_selection" in metadata

    def test_get_kb_metadata_missing_file_returns_empty(self, component_class, default_kwargs, tmp_path, active_user):
        component = component_class(**default_kwargs)
        ghost = tmp_path / active_user.username / "ghost"
        ghost.mkdir(parents=True, exist_ok=True)
        assert component._get_kb_metadata(ghost) == {}

    def test_get_kb_metadata_corrupt_json_returns_empty(self, component_class, default_kwargs, tmp_path, active_user):
        component = component_class(**default_kwargs)
        kb_path = tmp_path / active_user.username / "bad_kb"
        kb_path.mkdir(parents=True, exist_ok=True)
        (kb_path / "embedding_metadata.json").write_text("{not json")
        assert component._get_kb_metadata(kb_path) == {}

    # ---- _resolve_model_selection ------------------------------------

    def test_resolve_model_selection_uses_new_format(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = {"name": "m", "provider": "p", "metadata": {}}
        assert component._resolve_model_selection({"model_selection": model}) == [model]

    def test_resolve_model_selection_accepts_list_shape(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = [{"name": "m", "provider": "p"}]
        assert component._resolve_model_selection({"model_selection": model}) == model

    def test_resolve_model_selection_falls_back_to_catalog_lookup(self, component_class, default_kwargs):
        """Fall back to catalog lookup for legacy KBs.

        No ``model_selection`` field, just ``embedding_model`` and
        ``embedding_provider`` strings — retrieval has to look the
        model up in the current unified-models catalog.
        """
        component = component_class(**default_kwargs)
        catalog_entry = {
            "name": "text-embedding-3-small",
            "provider": "OpenAI",
            "metadata": {"embedding_class": "OpenAIEmbeddings"},
        }
        with patch(
            "lfx.components.files_and_knowledge.knowledge.get_embedding_model_options",
            return_value=[catalog_entry],
        ):
            resolved = component._resolve_model_selection(
                {"embedding_model": "text-embedding-3-small", "embedding_provider": "OpenAI"}
            )
        assert resolved == [catalog_entry]

    def test_resolve_model_selection_hydrates_missing_embedding_class_from_catalog(
        self, component_class, default_kwargs
    ):
        """Partial model_selection must be completed from the unified-models catalog.

        Regression: KBs created through older frontends or third-party API
        clients sometimes persisted ``model_selection`` as just
        ``{name, provider}`` with an empty or missing ``metadata`` block.
        Retrieval would then fail with
        ``"No embedding class defined in metadata for <model>"`` even
        though the model is fully supported by the current runtime. The
        fix looks the model up by name in the catalog and merges the
        missing ``embedding_class`` / ``param_mapping`` entries.
        """
        component = component_class(**default_kwargs)
        persisted = {"name": "text-embedding-3-small", "provider": "OpenAI", "metadata": {}}
        catalog_entry = {
            "name": "text-embedding-3-small",
            "provider": "OpenAI",
            "metadata": {
                "embedding_class": "OpenAIEmbeddings",
                "param_mapping": {"api_key": "<mapped_openai_key>", "model": "model"},
            },
        }
        with patch(
            "lfx.components.files_and_knowledge.knowledge.get_embedding_model_options",
            return_value=[catalog_entry],
        ):
            resolved = component._resolve_model_selection({"model_selection": persisted})

        assert len(resolved) == 1
        resolved_metadata = resolved[0]["metadata"]
        # Missing fields were hydrated from the catalog…
        assert resolved_metadata["embedding_class"] == "OpenAIEmbeddings"
        assert resolved_metadata["param_mapping"] == {
            "api_key": "<mapped_openai_key>",
            "model": "model",
        }
        # …and the persisted top-level fields stay intact.
        assert resolved[0]["name"] == "text-embedding-3-small"
        assert resolved[0]["provider"] == "OpenAI"

    def test_resolve_model_selection_preserves_existing_metadata_over_catalog(self, component_class, default_kwargs):
        """Persisted metadata wins on conflict — catalog only fills gaps.

        Guards against silent drift for users who customised
        ``param_mapping`` or chose a specific ``embedding_class`` per KB.
        """
        component = component_class(**default_kwargs)
        persisted = {
            "name": "text-embedding-3-small",
            "provider": "OpenAI",
            "metadata": {
                "embedding_class": "CustomOpenAIEmbeddings",
                "param_mapping": {"api_key": "<mapped_custom_key>"},
            },
        }
        catalog_entry = {
            "name": "text-embedding-3-small",
            "provider": "OpenAI",
            "metadata": {
                "embedding_class": "OpenAIEmbeddings",
                "param_mapping": {"api_key": "<mapped_openai_key>"},
                "extra_flag": True,
            },
        }
        with patch(
            "lfx.components.files_and_knowledge.knowledge.get_embedding_model_options",
            return_value=[catalog_entry],
        ):
            resolved = component._resolve_model_selection({"model_selection": persisted})

        # Existing entries win (hydration fills gaps only). Both
        # ``has_class`` and ``has_mapping`` are true on the persisted
        # side, so ``_hydrate_model_metadata`` short-circuits without
        # touching ``extra_flag`` either.
        assert resolved[0]["metadata"]["embedding_class"] == "CustomOpenAIEmbeddings"
        assert resolved[0]["metadata"]["param_mapping"] == {"api_key": "<mapped_custom_key>"}
        assert "extra_flag" not in resolved[0]["metadata"]

    def test_resolve_model_selection_raises_when_legacy_model_unavailable(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with (
            patch(
                "lfx.components.files_and_knowledge.knowledge.get_embedding_model_options",
                return_value=[],
            ),
            pytest.raises(ValueError, match="no longer available"),
        ):
            component._resolve_model_selection(
                {"embedding_model": "text-embedding-ada-002", "embedding_provider": "OpenAI"}
            )

    def test_resolve_model_selection_raises_on_empty_metadata(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="no embedding model recorded"):
            component._resolve_model_selection({})

    # ---- retrieve_data orchestration ---------------------------------

    async def test_retrieve_data_missing_metadata_raises(self, component_class, default_kwargs, tmp_path, active_user):
        kb_path = tmp_path / active_user.username / default_kwargs["knowledge_base"]
        metadata_file = kb_path / "embedding_metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()

        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Metadata not found"):
            await component.retrieve_data()

    async def test_retrieve_data_missing_user_id_raises(self, component_class, default_kwargs):
        default_kwargs["_user_id"] = None
        component = component_class(**default_kwargs)
        mock_vertex = MagicMock()
        mock_vertex.graph.user_id = None
        component._vertex = mock_vertex

        with patch("lfx.components.files_and_knowledge.knowledge.session_scope") as mock_session_scope:
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match="User ID is required"):
                await component.retrieve_data()

    async def test_retrieve_data_missing_user_record_raises(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with (
            patch("lfx.components.files_and_knowledge.knowledge.session_scope") as mock_session_scope,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id",
                return_value=None,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match=r"User with ID .* not found"):
                await component.retrieve_data()

    async def test_retrieve_data_routes_query_with_scores(
        self,
        component_class,
        default_kwargs,
        tmp_path,  # noqa: ARG002 — reserved for future side-effect assertions
        active_user,
    ):
        """Score-carrying search path.

        With a search_query set, retrieve_data asks the backend for
        scores so the UI can render a relevance column.
        """
        default_kwargs["search_query"] = "find me"
        component = component_class(**default_kwargs)

        fake_doc = MagicMock()
        fake_doc.page_content = "hit"
        fake_doc.metadata = {"source": "s1"}

        user_record = MagicMock()
        user_record.username = active_user.username

        backend_instance = MagicMock()
        backend_instance.similarity_search = AsyncMock(return_value=[(fake_doc, 0.42)])
        backend_instance.teardown = AsyncMock()

        with (
            patch("lfx.components.files_and_knowledge.knowledge.session_scope") as mock_session_scope,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id",
                return_value=user_record,
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge.get_embeddings",
                return_value=MagicMock(),
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge.create_backend",
                return_value=backend_instance,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await component.retrieve_data()

        # similarity_search was called with_scores=True because
        # search_query is truthy.
        call_kwargs = backend_instance.similarity_search.await_args.kwargs
        assert call_kwargs["with_scores"] is True
        assert call_kwargs["query"] == "find me"
        assert call_kwargs["k"] == default_kwargs["top_k"]
        backend_instance.teardown.assert_awaited_once()
        assert len(result) == 1

    async def test_retrieve_data_no_query_skips_scores(self, component_class, default_kwargs, active_user):
        """No-query path skips scores.

        With search_query empty, retrieve_data asks for a
        non-scored search so the sentinel zero isn't surfaced as a
        meaningful relevance value.
        """
        default_kwargs["search_query"] = ""
        component = component_class(**default_kwargs)

        fake_doc = MagicMock()
        fake_doc.page_content = "all"
        fake_doc.metadata = {"source": "any"}

        user_record = MagicMock()
        user_record.username = active_user.username

        backend_instance = MagicMock()
        backend_instance.similarity_search = AsyncMock(return_value=[(fake_doc, 0.0)])
        backend_instance.teardown = AsyncMock()

        with (
            patch("lfx.components.files_and_knowledge.knowledge.session_scope") as mock_session_scope,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id",
                return_value=user_record,
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge.get_embeddings",
                return_value=MagicMock(),
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge.create_backend",
                return_value=backend_instance,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await component.retrieve_data()

        call_kwargs = backend_instance.similarity_search.await_args.kwargs
        assert call_kwargs["with_scores"] is False
        backend_instance.teardown.assert_awaited_once()
        assert len(result) == 1

    async def test_retrieve_data_tears_down_backend_on_error(self, component_class, default_kwargs, active_user):
        """Teardown on error.

        The backend's ``teardown`` must run even when
        ``similarity_search`` blows up — otherwise Chroma's SQLite
        handle leaks between tests.
        """
        component = component_class(**default_kwargs)

        user_record = MagicMock()
        user_record.username = active_user.username

        backend_instance = MagicMock()
        backend_instance.similarity_search = AsyncMock(side_effect=RuntimeError("boom"))
        backend_instance.teardown = AsyncMock()

        with (
            patch("lfx.components.files_and_knowledge.knowledge.session_scope") as mock_session_scope,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id",
                return_value=user_record,
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge.get_embeddings",
                return_value=MagicMock(),
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge.create_backend",
                return_value=backend_instance,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RuntimeError, match="boom"):
                await component.retrieve_data()

        backend_instance.teardown.assert_awaited_once()

    async def test_retrieve_data_passes_model_selection_to_unified_models(
        self, component_class, default_kwargs, active_user
    ):
        """Full ``model_selection`` is handed off unchanged.

        The dict persisted at ingest time should land in
        ``get_embeddings`` exactly as-is — that's the whole point of
        the unified-models port.
        """
        component = component_class(**default_kwargs)

        user_record = MagicMock()
        user_record.username = active_user.username

        backend_instance = MagicMock()
        backend_instance.similarity_search = AsyncMock(return_value=[])
        backend_instance.teardown = AsyncMock()

        with (
            patch("lfx.components.files_and_knowledge.knowledge.session_scope") as mock_session_scope,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id",
                return_value=user_record,
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge.get_embeddings",
                return_value=MagicMock(),
            ) as mock_get_embeddings,
            patch(
                "lfx.components.files_and_knowledge.knowledge.create_backend",
                return_value=backend_instance,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)

            await component.retrieve_data()

        # get_embeddings receives the full list-wrapped selection +
        # the chunk_size persisted alongside it.
        call_kwargs = mock_get_embeddings.call_args.kwargs
        assert isinstance(call_kwargs["model"], list)
        assert call_kwargs["model"][0]["name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert call_kwargs["chunk_size"] == 1000
        assert call_kwargs["user_id"] == default_kwargs["_user_id"]

    # ---- include_embeddings against a real Chroma backend ------------

    async def _retrieve_against_real_kb(self, component_class, default_kwargs, active_user, docs):
        """Populate a real Chroma KB with ``docs`` then run ``retrieve_data``.

        Uses an in-process Chroma backend (no mocks for the vector store) so the
        embedding-join path — ``similarity_search`` + ``iter_documents`` — is
        exercised end to end. Only the user/session/path/embedding-config plumbing
        is patched, mirroring the other ``retrieve_data`` tests in this module.
        """
        kb_path = Path(default_kwargs["kb_root_path"]) / active_user.username / default_kwargs["knowledge_base"]
        kb_path.mkdir(parents=True, exist_ok=True)
        embeddings = _DeterministicEmbeddings()

        # Pre-populate the KB through the real backend, then tear it down so the
        # retrieval pass opens its own client (matches production lifecycle).
        seed_backend = ChromaLocalBackend(
            kb_name=default_kwargs["knowledge_base"],
            kb_path=kb_path,
            embedding_function=embeddings,
        )
        try:
            await seed_backend.add_documents(docs)
        finally:
            await seed_backend.teardown()

        def _make_backend(*_args, **kwargs):
            return ChromaLocalBackend(
                kb_name=kwargs.get("kb_name", default_kwargs["knowledge_base"]),
                kb_path=kwargs.get("kb_path", kb_path),
                embedding_function=embeddings,
            )

        user_record = MagicMock()
        user_record.username = active_user.username

        component = component_class(**default_kwargs)
        with (
            patch("lfx.components.files_and_knowledge.knowledge.session_scope") as mock_session_scope,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id",
                return_value=user_record,
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge._get_knowledge_bases_root_path",
                return_value=Path(default_kwargs["kb_root_path"]),
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge.get_embeddings",
                return_value=embeddings,
            ),
            patch(
                "lfx.components.files_and_knowledge.knowledge.create_backend",
                side_effect=_make_backend,
            ),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            return await component.retrieve_data()

    async def test_include_embeddings_populates_for_upload_style_kb(self, component_class, default_kwargs, active_user):
        """Regression: ``include_embeddings`` must work for upload-populated KBs.

        Chunks ingested via direct file upload (``KBIngestionHelper``) carry no
        ``_id`` metadata key. The retrieval embedding-join used to key solely on
        ``_id``, so every such KB returned ``_embeddings: None``. The join now
        falls back to page content, so the vectors resolve.
        """
        default_kwargs["search_query"] = "chunk 1 text"
        default_kwargs["include_embeddings"] = True

        # Upload-style metadata — note the absence of any ``_id`` key.
        docs = [
            Document(
                page_content=f"chunk {i} text",
                metadata={"source": "f.txt", "file_name": "f.txt", "chunk_index": i},
            )
            for i in range(3)
        ]

        result = await self._retrieve_against_real_kb(component_class, default_kwargs, active_user, docs)

        rows = result.to_dict("records")
        assert len(rows) == 3
        for row in rows:
            assert "_embeddings" in row
            assert isinstance(row["_embeddings"], list)
            assert len(row["_embeddings"]) == _DeterministicEmbeddings.DIMENSION

    async def test_include_embeddings_populates_with_id_metadata(self, component_class, default_kwargs, active_user):
        """The ``_id``-keyed path (component-driven ingestion) keeps working."""
        default_kwargs["search_query"] = "chunk 1 text"
        default_kwargs["include_embeddings"] = True

        docs = [
            Document(
                page_content=f"chunk {i} text",
                metadata={"_id": hashlib.sha256(f"chunk {i} text".encode()).hexdigest(), "source": "s"},
            )
            for i in range(3)
        ]

        result = await self._retrieve_against_real_kb(component_class, default_kwargs, active_user, docs)

        rows = result.to_dict("records")
        assert len(rows) == 3
        for row in rows:
            assert isinstance(row["_embeddings"], list)
            assert len(row["_embeddings"]) == _DeterministicEmbeddings.DIMENSION

    async def test_include_embeddings_disabled_omits_embeddings(self, component_class, default_kwargs, active_user):
        """With the flag off, no ``_embeddings`` column is added."""
        default_kwargs["search_query"] = "chunk 1 text"
        default_kwargs["include_embeddings"] = False

        docs = [
            Document(page_content=f"chunk {i} text", metadata={"source": "f.txt", "chunk_index": i}) for i in range(3)
        ]

        result = await self._retrieve_against_real_kb(component_class, default_kwargs, active_user, docs)

        rows = result.to_dict("records")
        assert len(rows) == 3
        for row in rows:
            assert "_embeddings" not in row


class TestEmbeddingMatchKey:
    """Unit coverage for the ``_id``-or-content join key used by the embedding merge."""

    def test_prefers_id_when_present(self):
        from lfx.components.files_and_knowledge.knowledge import _embedding_match_key

        assert _embedding_match_key("some text", {"_id": "abc", "source": "s"}) == ("id", "abc")

    def test_falls_back_to_content_without_id(self):
        from lfx.components.files_and_knowledge.knowledge import _embedding_match_key

        assert _embedding_match_key("some text", {"source": "s"}) == ("content", "some text")

    def test_handles_missing_metadata(self):
        from lfx.components.files_and_knowledge.knowledge import _embedding_match_key

        assert _embedding_match_key("some text", None) == ("content", "some text")

    def test_id_and_content_key_spaces_do_not_collide(self):
        from lfx.components.files_and_knowledge.knowledge import _embedding_match_key

        # A chunk whose content equals another chunk's _id must not cross-match.
        id_key = _embedding_match_key("payload", {"_id": "payload"})
        content_key = _embedding_match_key("payload", {})
        assert id_key != content_key


class TestMetadataFilterHelpers:
    """Direct coverage for the JSON-decode + match helpers.

    Kept separate from the orchestration tests because the helpers don't
    need a component fixture or DB session — exercising them in isolation
    locks down the "AND across keys, OR within values" contract documented
    in the chunks endpoint, which retrieval mirrors.
    """

    def test_parse_returns_empty_when_unset(self):
        from lfx.components.files_and_knowledge.retrieval import _parse_metadata_filter

        assert _parse_metadata_filter(None) == {}
        assert _parse_metadata_filter("") == {}
        assert _parse_metadata_filter("   ") == {}

    def test_parse_normalizes_scalar_to_list(self):
        from lfx.components.files_and_knowledge.retrieval import _parse_metadata_filter

        assert _parse_metadata_filter('{"tag": "invoice"}') == {"tag": ["invoice"]}

    def test_parse_preserves_array_values(self):
        from lfx.components.files_and_knowledge.retrieval import _parse_metadata_filter

        assert _parse_metadata_filter('{"tag": ["a", "b"]}') == {"tag": ["a", "b"]}

    def test_parse_swallows_invalid_json(self):
        from lfx.components.files_and_knowledge.retrieval import _parse_metadata_filter

        # Malformed JSON returns an empty filter so retrieval falls back to
        # the unfiltered path rather than blowing up the canvas run.
        assert _parse_metadata_filter("{not-json") == {}

    def test_parse_swallows_non_dict(self):
        from lfx.components.files_and_knowledge.retrieval import _parse_metadata_filter

        assert _parse_metadata_filter("[1, 2, 3]") == {}

    def test_chunk_match_requires_every_key(self):
        import json

        from lfx.components.files_and_knowledge.retrieval import _chunk_matches_filter

        meta = {"source_metadata": json.dumps({"tag": "invoice", "year": "2026"})}
        assert _chunk_matches_filter(meta, {"tag": ["invoice"], "year": ["2026"]}) is True
        assert _chunk_matches_filter(meta, {"tag": ["report"]}) is False
        assert _chunk_matches_filter(meta, {"tag": ["invoice"], "owner": ["alice"]}) is False

    def test_chunk_match_array_value(self):
        import json

        from lfx.components.files_and_knowledge.retrieval import _chunk_matches_filter

        meta = {"source_metadata": json.dumps({"tag": ["invoice", "audit"]})}
        # Array stored, scalar filter — overlap returns True.
        assert _chunk_matches_filter(meta, {"tag": ["audit"]}) is True
        # Array stored, multi-select filter — any overlap returns True.
        assert _chunk_matches_filter(meta, {"tag": ["report", "audit"]}) is True

    def test_chunk_match_missing_metadata_is_false(self):
        from lfx.components.files_and_knowledge.retrieval import _chunk_matches_filter

        assert _chunk_matches_filter({}, {"tag": ["invoice"]}) is False
        assert _chunk_matches_filter(None, {"tag": ["invoice"]}) is False

    def test_chunk_match_empty_filter_passes_through(self):
        from lfx.components.files_and_knowledge.retrieval import _chunk_matches_filter

        assert _chunk_matches_filter({"source_metadata": "{}"}, {}) is True
